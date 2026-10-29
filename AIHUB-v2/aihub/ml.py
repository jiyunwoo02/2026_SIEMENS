from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from .config import get_settings
from .schema import DefectRateInput, DefectRatePrediction, build_payload

logger = logging.getLogger(__name__)


class MLEndpointError(RuntimeError):
    """예측 API 호출 실패 또는 응답 검증 오류를 상위 파이프라인에 전달한다."""

    pass


class _RetryableError(RuntimeError):
    """서버 오류를 내부 재시도 처리로 전달하기 위한 예외."""

    pass


class DefectRateMLClient:
    """GBT 결함률 예측 API. POST {"data": [12컬럼, ...]}."""

    def __init__(self, endpoint_url: str | None = None, api_key: str | None = None) -> None:
        """공통 설정을 읽고 명시적으로 전달된 주소와 인증 키를 적용한다."""
        s = get_settings()
        self._s = s
        self._url = (endpoint_url or s.ai_hub_endpoint_url).strip()
        # None이면 설정 키를 사용하고, 빈 문자열이면 인증 키를 사용하지 않는다.
        self._key = api_key if api_key is not None else s.ai_hub_api_key

    def _headers(self) -> dict[str, str]:
        """JSON 요청 헤더를 만들고 인증 키가 있을 때만 인증 헤더를 추가한다."""
        h = {"Content-type": "application/json", "Accept": "application/json"}
        if self._key:
            h[self._s.ai_hub_auth_header] = f"{self._s.ai_hub_auth_scheme} {self._key}".strip()
        return h

    def _post(self, payload: dict[str, Any]) -> tuple[Any, int]:
        """예측 요청을 전송하고 응답 본문과 마지막 시도의 소요 시간(ms)을 반환한다."""
        last_err: Exception | None = None
        # 최초 호출 1회에 설정된 추가 재시도 횟수를 더해 시도한다.
        for attempt in range(self._s.ai_hub_max_retries + 1):
            try:
                started = time.perf_counter()
                # 각 시도마다 클라이언트를 생성하고 요청 완료 후 연결 자원을 정리한다.
                with httpx.Client(
                    timeout=self._s.ai_hub_timeout_seconds,
                    verify=self._s.ai_hub_verify_ssl,
                ) as client:
                    r = client.post(self._url, json=payload, headers=self._headers())
                # 클라이언트 생성·정리 시간을 포함하며, 이전 시도와 재시도 대기는 제외한다.
                latency_ms = int((time.perf_counter() - started) * 1000)
                # 4xx는 즉시 오류로 반환하고, 5xx는 재시도 대상으로 분류한다.
                if r.status_code >= 400:
                    if r.status_code < 500:
                        raise MLEndpointError(
                            f"HTTP {r.status_code} (입력 확인 필요): {r.text[:500]}"
                        )
                    raise _RetryableError(f"HTTP {r.status_code}: {r.text[:300]}")
                try:
                    return r.json(), latency_ms
                except json.JSONDecodeError:
                    # JSON이 아니면 원문을 넘기고, parse에서 최종 응답 오류를 보고한다.
                    return r.text, latency_ms
            except httpx.SSLError as e:
                raise MLEndpointError(
                    f"SSL 검증 실패: {e}\n사내 엔드포인트라면 .env 에 "
                    "AI_HUB_VERIFY_SSL=false 를 설정하세요."
                ) from e
            except (httpx.TimeoutException, httpx.TransportError, _RetryableError) as e:
                last_err = e
                if attempt < self._s.ai_hub_max_retries:
                    # 지수 백오프: 0.5초, 1초, 2초 순으로 대기 시간을 늘린다.
                    backoff = 0.5 * (2**attempt)
                    logger.warning("엔드포인트 호출 실패(%s). %.1fs 후 재시도", e, backoff)
                    time.sleep(backoff)
        raise MLEndpointError(f"엔드포인트 호출 실패: {last_err}")

    def predict(self, records: list[DefectRateInput]) -> dict[str, Any]:
        """입력 레코드를 예측하고 요청 데이터, 예측값, 원본 응답을 함께 반환한다."""
        payload = build_payload(records)
        if self._s.mock_ml:
            # 외부 API 없이 레코드 순서에 따라 1.65%, 2.65%, ...의 테스트 값을 만든다.
            logger.warning("MOCK_ML=true -> 더미 예측 반환")
            results = [
                DefectRatePrediction(defect_rate_pct=1.65 + i, echoed_input=row)
                for i, row in enumerate(payload["data"])
            ]
            raw: Any = {"mock": True}
            latency_ms = 0
        else:
            raw, latency_ms = self._post(payload)
            results = self.parse(raw, payload["data"])
        # 예측값은 이미 퍼센트 단위이므로 100을 곱하거나 나누지 않는다.
        return {
            "payload": payload,
            "results": results,
            "predictions": [p.defect_rate_pct for p in results],
            "unit": "percent",
            "raw": raw,
            "latency_ms": latency_ms,
        }

    def parse(self, body: Any, sent_rows: list[dict[str, Any]]) -> list[DefectRatePrediction]:
        """응답 구조, 레코드 수, 예측 컬럼 및 입력 컬럼 누락 여부를 검사한다."""
        # 문자열로 전달된 응답은 먼저 JSON으로 변환한다.
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError as e:
                raise MLEndpointError(f"JSON이 아닌 응답: {body[:300]}") from e

        # 설정된 키로 감싼 객체와 최상위 배열 형태의 응답을 모두 지원한다.
        key = self._s.ai_hub_response_key
        if isinstance(body, dict):
            if key not in body:
                raise MLEndpointError(f"응답에 '{key}' 키가 없습니다. 실제 키={list(body)}")
            rows = body[key]
        elif isinstance(body, list):
            rows = body
        else:
            raise MLEndpointError(f"지원하지 않는 응답 타입: {type(body)}")

        if not isinstance(rows, list):
            raise MLEndpointError(f"'{key}' 가 리스트가 아닙니다: {type(rows)}")
        # 요청과 응답을 순서대로 대응시키기 전에 건수가 같은지 확인한다.
        if len(rows) != len(sent_rows):
            raise MLEndpointError(f"요청 {len(sent_rows)}건 / 응답 {len(rows)}건 불일치")

        col = self._s.ai_hub_prediction_column
        out: list[DefectRatePrediction] = []
        # API가 요청 순서를 유지한다고 가정하며 별도 식별자로 재정렬하지 않는다.
        for i, (row, sent) in enumerate(zip(rows, sent_rows)):
            if not isinstance(row, dict):
                raise MLEndpointError(f"data[{i}] 가 dict가 아닙니다: {row!r}")
            if col not in row:
                raise MLEndpointError(
                    f"data[{i}] 에 예측 컬럼 '{col}' 이 없습니다. 키={list(row)}"
                )
            # 숫자 형태의 문자열도 허용하도록 예측값을 실수로 변환한다.
            try:
                value = float(row[col])
            except (TypeError, ValueError) as e:
                raise MLEndpointError(
                    f"data[{i}]['{col}'] 를 float로 변환 실패: {row[col]!r}"
                ) from e
            # 에코 검사는 입력 컬럼의 존재 여부만 확인하며 값의 동일성은 비교하지 않는다.
            dropped = [k for k in sent if k not in row]
            if dropped:
                msg = f"data[{i}]: 전송한 컬럼이 응답 에코에 없습니다 -> {dropped}"
                # 엄격 모드에서는 중단하고, 그렇지 않으면 경고 후 결과를 유지한다.
                if self._s.ai_hub_strict_echo:
                    raise MLEndpointError(msg)
                logger.warning(msg)
            # 예측 컬럼을 제외한 응답 필드와 누락 컬럼 목록을 결과에 보관한다.
            out.append(
                DefectRatePrediction(
                    defect_rate_pct=value,
                    echoed_input={k: v for k, v in row.items() if k != col},
                    dropped_columns=dropped,
                )
            )
        return out
