"""최적화(불량 최소화/위험 조건 탐색) API 클라이언트.

[추가] 2026-10-27: docs/agent-v2/pre-version/chatbot_optimization_feature_spec.md 4장·6장 구현.

기존 ml.py(DefectRateMLClient)와 역할이 다르다:
- ml.py: POST, 여러 공정 조건(data 배열)을 보내 각 조건의 결함률(%)을 예측한다.
- 이 모듈: GET, target("0" 또는 "1") 하나만 보내 "그 라벨이 나올 확률을 최소화하는" 최적 조건
  1세트를 돌려받는다. 즉 입력이 아니라 "찾아줘" 요청이다.

target 값은 LLM이 직접 고르지 않는다(환각 방지). 챗봇 의도(intent)를 code가 build_target()으로
변환한다 - 이 매핑이 틀리면 전체 기능의 의미가 반대로 뒤집힌다.
[확인 필요] 이 매핑을 고정하는 자동(단위) 테스트가 현재 없다(프로젝트가 pytest를 사용하지
않기로 해 test/test_optimization.py도 작성되지 않았음). 대신 test/cli_smoke_test.sh,
test/web_smoke_test.sh 수동 스모크 테스트로 일부 케이스만 확인한다.

확인 필요: 실제 API 응답 시간, 인증 필요 여부, 동시 요청 허용 여부는 운영 중인 엔드포인트로
직접 검증되지 않았다(추정 기반 구현). docs 9장 '확인 필요' 항목 참고.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from .config import get_settings

logger = logging.getLogger(__name__)

# 불량(high_defect_flag=1) 확률이 가장 낮아지는 조건을 찾을 때 target="1",
# 정상(=0) 확률이 가장 낮아지는(=불량 유발) 조건을 찾을 때 target="0".
# [확인 필요] 이 매핑은 스펙 4.4의 서술("특정 클래스가 나올 확률을 최소화")을 근거로 한 것으로,
# 실제 API 동작으로 검증되지 않았다. 운영 API로 한 번은 교차 검증을 권장한다.
INTENT_TO_TARGET: dict[str, str] = {
    "optimize_reduce_defect": "1",
    "predict_and_optimize": "1",
    "optimize_find_defect_risk": "0",
}


def build_target(intent: str) -> str:
    """챗봇 의도를 최적화 API의 target 쿼리 파라미터로 변환한다.

    입력: intent - schema.INTENTS 중 최적화 관련 의도 문자열.
    출력: "0" 또는 "1".
    예외: ValueError - 최적화와 무관한 의도(predict, clarify) 또는 알 수 없는 값.
    """
    target = INTENT_TO_TARGET.get(intent)
    if target is None:
        raise ValueError(f"최적화 대상이 아닌 의도입니다: {intent!r}")
    return target


class OptimizationEndpointError(RuntimeError):
    """최적화 API 호출 실패 또는 응답 형식이 예상과 달라 파싱하지 못한 경우."""


class _RetryableError(RuntimeError):
    """5xx·네트워크 오류 등 재시도 가치가 있는 내부 신호. 외부에 노출하지 않는다."""


def parse_optimization_response(payload: Any) -> dict[str, Any]:
    """최적화 API 응답에서 최적 조건·확률·예측 라벨을 추출한다.

    test/results/api/out_0.json, out_1.json 형식을 기준으로 한다:
    {"data": [{<12개 조건 필드>, "confidence(1)": float, "confidence(0)": float,
               "prediction(high_defect_flag)": "0"|"1"}]}

    입력: payload - httpx Response.json() 결과.
    출력: {"conditions": dict, "defect_probability": float, "normal_probability": float,
          "predicted_label": str}
    예외: OptimizationEndpointError - 구조가 다르거나 필수 키가 없는 경우.
    """
    if not isinstance(payload, dict):
        raise OptimizationEndpointError(f"지원하지 않는 응답 형식입니다(dict 아님): {type(payload).__name__}")
    rows = payload.get("data")
    if not isinstance(rows, list) or not rows:
        raise OptimizationEndpointError(f"응답에 data 배열이 없거나 비어 있습니다: {payload!r}")
    row = rows[0]
    if not isinstance(row, dict):
        raise OptimizationEndpointError(f"data[0]이 객체가 아닙니다: {row!r}")
    try:
        defect_probability = float(row["confidence(1)"])
        normal_probability = float(row["confidence(0)"])
        predicted_label = str(row["prediction(high_defect_flag)"])
    except KeyError as e:
        raise OptimizationEndpointError(f"응답에 필수 키가 없습니다: {e}") from e
    except (TypeError, ValueError) as e:
        raise OptimizationEndpointError(f"확률 값을 숫자로 변환하지 못했습니다: {e}") from e
    # confidence(*)/prediction(*)을 제외한 나머지가 최적 조건 12개다.
    conditions = {
        k: v for k, v in row.items() if not (k.startswith("confidence(") or k.startswith("prediction("))
    }
    return {
        "conditions": conditions,
        "defect_probability": defect_probability,
        "normal_probability": normal_probability,
        "predicted_label": predicted_label,
    }


class OptimizationClient:
    """최적화 API(GET, target 쿼리 파라미터)를 호출하고 응답을 파싱해 반환한다.

    ml.py의 DefectRateMLClient와 동일한 재시도(타임아웃·5xx만 재시도, 4xx는 즉시 실패) 정책을
    따른다. url/token을 생략하면 config.get_settings()의 optimization_api_url/token을 쓴다.
    """

    def __init__(self, url: str | None = None, token: str | None = None) -> None:
        settings = get_settings()
        self._settings = settings
        self._url = (url if url is not None else settings.optimization_api_url).strip()
        self._token = token if token is not None else settings.optimization_api_token

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _request(self, target: str) -> tuple[Any, int]:
        """HTTP GET을 보내고 (JSON 본문, 지연시간ms)를 반환한다. 재시도는 settings 설정을 따른다."""
        if not self._url:
            raise OptimizationEndpointError(
                "최적화 API 주소(OPTIMIZATION_API_URL)가 설정되지 않았습니다. .env를 확인해주세요."
            )
        attempts = max(0, self._settings.optimization_max_retries) + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            started = time.perf_counter()
            try:
                with httpx.Client(timeout=self._settings.optimization_timeout_seconds) as client:
                    response = client.get(self._url, params={"target": target}, headers=self._headers())
                latency_ms = int((time.perf_counter() - started) * 1000)
                if response.status_code >= 500:
                    raise _RetryableError(f"HTTP {response.status_code}")
                if response.status_code >= 400:
                    # 4xx는 요청 자체의 문제(잘못된 target, 인증 등)이므로 재시도하지 않는다.
                    raise OptimizationEndpointError(
                        f"최적화 API가 오류를 반환했습니다: HTTP {response.status_code}"
                    )
                try:
                    return response.json(), latency_ms
                except ValueError as e:
                    raise OptimizationEndpointError("최적화 API 응답이 JSON 형식이 아닙니다.") from e
            except httpx.TimeoutException as e:
                last_error = e
                if attempt < attempts - 1:
                    logger.warning(
                        "optimization request timeout target=%s attempt=%s/%s", target, attempt + 1, attempts
                    )
                    continue
                raise OptimizationEndpointError(
                    "최적화 계산이 오래 걸려 시간이 초과되었습니다. 잠시 후 다시 시도해주세요."
                ) from e
            except (httpx.TransportError, _RetryableError) as e:
                last_error = e
                if attempt < attempts - 1:
                    logger.warning(
                        "optimization request failed target=%s attempt=%s/%s error=%s",
                        target, attempt + 1, attempts, e,
                    )
                    continue
                raise OptimizationEndpointError(f"최적화 API 호출에 실패했습니다: {e}") from e
        # 이론상 도달하지 않지만, 정적 분석과 방어적 코드 품질을 위해 남겨둔다.
        raise OptimizationEndpointError(f"최적화 API 호출에 실패했습니다: {last_error}")

    def optimize(self, target: str) -> dict[str, Any]:
        """target("0"/"1")에 대한 최적 조건을 조회한다.

        입력: target - "0"(정상 확률 최소화=불량 위험 조건 탐색) 또는 "1"(불량 확률 최소화).
        출력: parse_optimization_response() 결과에 "latency_ms"(int), "target"(str)을 더한 dict.
        예외: ValueError - target이 "0"/"1"이 아님. OptimizationEndpointError - 호출/파싱 실패.
        """
        if target not in ("0", "1"):
            raise ValueError(f"target은 '0' 또는 '1'이어야 합니다: {target!r}")
        payload, latency_ms = self._request(target)
        result = parse_optimization_response(payload)
        result["latency_ms"] = latency_ms
        result["target"] = target
        return result
