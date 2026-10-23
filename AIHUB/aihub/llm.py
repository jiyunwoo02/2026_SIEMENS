from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx

from .config import get_settings
from .schema import ALLOWED_SHIFTS, FIELD_SPEC

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """LLM 호출, 모델 탐색, 응답 처리 과정에서 명시적으로 보고하는 오류."""

    pass


def _field_doc() -> str:
    """공통 필드 명세를 추출 프롬프트에 사용할 설명 목록으로 변환한다."""
    return "\n".join(
        f"- {name} ({spec['type']}): {spec['desc']}" for name, spec in FIELD_SPEC.items()
    )


# 입력값 추출용 지침: 추측을 금지하고 단위 정규화와 대화 맥락 처리 규칙을 전달한다.
# [수정] docs/input_schema.md 공통 규칙에 맞춰 모호값 6유형과 ambiguous_fields 출력, 허용값 밖 값 보존,
#        한글 단위, 예측 의도 판단(조건 나열·필요 입력 질문) 규칙을 추가했다. 이전에는 상대 표현만 다뤘다.
# 필드 설명과 허용 교대조 목록은 모듈 로딩 시 공통 스키마에서 가져온다.
EXTRACTION_SYSTEM_PROMPT = f"""당신은 제조 공정 데이터 추출기입니다.
사용자 발화에서 결함률 예측 모델의 입력 피처를 추출해 JSON으로만 응답합니다.

[추출 대상 필드]
{_field_doc()}

[절대 규칙]
1. 발화에 명시되지 않은 값은 절대 추측하지 말고 null로 둔다.
   기본값, 평균값, 업계 통념 수치를 임의로 채우지 않는다. 모르면 null이 정답이다.
   특히 누락된 수치를 0으로 채우지 않는다.
2. 값이 언급됐어도 하나로 확정할 수 없으면 null로 두고, 그 필드명을 ambiguous_fields에 넣는다.
   - 정성·상대 표현: "평소보다 높다", "꽤 닳았다", "꽤 높은 편", "얼마 전에 정비", "약간", "보통 수준"
   - 범위 표현: "습도 50에서 60% 사이", "460~470개" (평균·중간값으로 확정하지 않는다)
   - 단위 없는 코팅 두께: "코팅 0.08" (mm인지 um인지 알 수 없음)
   - 미확정 코드: "BPR 라인 중 한 곳", "저녁 근무", "오후조", "공급사는 A나 B"
   - 발화 안에서의 번복: "44.2%라고 했는데 54.2%였나"
   - 기준 없는 참조: "나머지는 평소랑 비슷" -> 그렇게 가리킨 필드들
   단순히 언급되지 않은 필드는 ambiguous_fields에 넣지 않는다.
3. 허용값에 없는 코드(예: LINE-BPR-03, SIM-SUP-D)와 범위를 벗어난 수치(예: 공구 마모 140%, -5%)도
   발화에 적힌 그대로 추출한다. 비슷한 허용값으로 바꾸거나 null로 바꾸지 않는다. 검증은 시스템이 한다.

[정규화 규칙]
4. 단위가 함께 적힌 경우 숫자만 추출한다. ("습도 54.49%" -> 54.49)
   한글 단위도 인식한다: "퍼센트" = %, "마이크로미터"·"마이크론" = um, "밀리"·"밀리미터" = mm
5. coating_target_thickness_um 만 mm로 주어지면 um로 환산한다. (0.08mm -> 80, 0.0984mm -> 98.4)
   fixture_alignment_offset_mm 는 mm 단위 그대로 둔다. 환산하지 않는다.
6. 교대조는 {ALLOWED_SHIFTS} 중 하나로 정규화한다.
   주간/오전/낮/day/주간조 -> DAY, 야간/밤/night/야간조 -> NIGHT
   "저녁 근무", "오후조"처럼 어느 쪽인지 확정할 수 없으면 규칙 2에 따라 null이다.
7. 라인·공급사 코드는 대문자로 정규화한다. (line-bpr-01 -> LINE-BPR-01)

[레코드 구성 규칙]
8. 조건을 비교하는 질의는 records에 여러 건으로 분리하고,
   공통 조건을 각 레코드에 동일하게 복사한다. 공통으로 빠진 필드는 모든 레코드에서 null이다.
9. 단일 조건이면 records 길이는 1이다.
10. "예측해줘" 같은 문구가 없어도 공정 조건을 나열한 발화는 예측 요청으로 본다.
11. 예측에 필요한 입력이 무엇인지 묻는 발화도 예측 요청으로 보고,
    모든 필드가 null인 레코드 1개를 둔다.
12. 공정·결함률 예측과 무관한 발화(모델 학습 방식 질문, 잡담 등)만 records를 빈 배열로 둔다.

[대화 맥락 규칙]
13. [이미 확인된 값]이 주어진 경우, 이번 발화에서 새로 언급되거나 정정된 값만 채우고
    나머지는 null로 둔다. 기존 값을 복사해 넣지 않는다. 병합은 시스템이 처리한다.
14. 정정 발화("A가 아니라 B입니다")는 해당 필드에 새 값을 넣는다.

ambiguous_fields가 없으면 빈 배열로 둔다. JSON 외의 설명 문장은 출력하지 않는다."""


# 해설 생성용 지침: 예측값의 퍼센트 단위를 유지하고 근거 없는 수치 생성을 금지한다.
ANSWER_SYSTEM_PROMPT = """당신은 제조 품질 분석 어시스턴트입니다.
GBT 모델의 결함률 예측 결과와 입력 조건을 바탕으로 한국어로 간결하게 답변합니다.

[단위 규칙 — 매우 중요]
- predicted_defect_rate_pct 의 단위는 퍼센트(%)입니다.
- 1.65 는 "1.65%" 입니다. "0.0165%" 나 "165%" 로 바꾸지 마세요.
- 소수점 둘째 자리까지 표기합니다.

[작성 규칙]
- 예측값을 첫 문장에 제시합니다.
- 입력 조건 중 해석에 중요한 항목(공구 마모도, 정비 경과일, 자재 품질점수, 설정 편차 등)을 언급합니다.
- 모델이 반환하지 않은 수치(신뢰구간, 피처 기여도, 중요도 순위)를 지어내지 않습니다.
  원인 분석은 "일반적으로 ~ 요인이 영향을 줍니다" 수준의 일반론으로만 서술하고,
  모델이 그렇게 판단했다고 단정하지 않습니다.
- 레코드가 2건 이상이면 비교 표로 정리하고 차이를 한 문장으로 요약합니다.
- 전체 3~6문장 이내."""


def build_extraction_user_content(query: str, known: dict[str, Any] | None = None) -> str:
    """기존 확인값과 이번 발화를 구분하여 추출 요청의 사용자 메시지를 만든다."""
    if not known:
        return query
    # 기존 값은 맥락으로만 제공한다. 새 값과의 실제 병합은 파이프라인에서 수행한다.
    return (
        "[이미 확인된 값]\n"
        + json.dumps(known, ensure_ascii=False, indent=2)
        + "\n\n[이번 발화]\n"
        + query
        + "\n\n이번 발화에서 새로 언급되거나 정정된 값만 채우고, 나머지는 null로 두세요."
    )


@dataclass
class ModelGroup:
    """게이트웨이 카탈로그의 도구 이름, 호출 경로, 모델 목록을 보관한다."""

    tool: str
    base_path: str
    models: list[str]


class SDCLLMClient:
    """Siemens SDC LLM Gateway. 인증은 x-api-key."""

    def __init__(self, settings=None) -> None:
        """설정과 카탈로그 캐시를 준비하고 인증 헤더를 가진 HTTP 클라이언트를 만든다."""
        self._s = settings or get_settings()
        self._catalog: list[ModelGroup] | None = None
        # 구조화 출력이 성공하면 해당 모드를 저장하여 이후 요청에도 사용한다.
        self._json_mode = self._s.llm_json_mode
        self._client = httpx.Client(
            timeout=self._s.llm_timeout_seconds,
            headers={"x-api-key": self._s.api_key, "Content-Type": "application/json"},
        )

    def list_models(self, refresh: bool = False) -> list[ModelGroup]:
        """모델 카탈로그를 조회한다. refresh=True이면 캐시 대신 서버에서 다시 읽는다."""
        if self._catalog is not None and not refresh:
            return self._catalog
        url = f"{self._s.base_url.rstrip('/')}/models"
        r = self._client.get(url)
        if r.status_code >= 400:
            raise LLMError(f"GET {url} -> HTTP {r.status_code}: {r.text[:300]}")
        payload = r.json()
        self._catalog = [
            ModelGroup(
                tool=g.get("tool", "unknown"),
                base_path=g.get("base_path", ""),
                models=list(g.get("models", [])),
            )
            for g in payload.get("catalog", [])
        ]
        return self._catalog

    def resolve_base_path(self, model: str) -> str:
        """직접 지정한 경로를 우선 사용하고, 없으면 카탈로그에서 모델 경로를 찾는다."""
        if self._s.llm_base_path:
            return self._s.llm_base_path.rstrip("/")
        for g in self.list_models():
            if model in g.models:
                return g.base_path.rstrip("/")
        available = sorted({m for g in self.list_models() for m in g.models})
        raise LLMError(f"model '{model}' 을 catalog에서 찾을 수 없습니다. 사용 가능: {available}")

    def _chat_url(self, model: str) -> str:
        """모델 경로 형태에 맞춰 chat/completions 요청 URL을 구성한다."""
        # 절대 URL이면 그대로 사용하고, 경로만 있으면 게이트웨이 원점에 붙인다.
        # 경로가 비어 있으면 설정의 base_url을 사용한다.
        bp = self.resolve_base_path(model)
        if bp.startswith("http"):
            return f"{bp.rstrip('/')}/chat/completions"
        if bp:
            return f"{self._s.api_origin}{bp}/chat/completions"
        return f"{self._s.base_url.rstrip('/')}/chat/completions"

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        """대화 메시지를 전송하고 응답에서 텍스트 콘텐츠를 추출한다."""
        # 모델을 생략하면 기본 모델을 사용하며, 출력 형식은 지정된 경우에만 전송한다.
        model = model or self._s.llm_model
        body: dict[str, Any] = {"model": model, "messages": messages}
        if response_format:
            body["response_format"] = response_format
        url = self._chat_url(model)
        r = self._client.post(url, json=body)
        if r.status_code >= 400:
            raise LLMError(f"POST {url} -> HTTP {r.status_code}: {r.text[:500]}")
        return self._extract_content(r.json())

    @staticmethod
    def _extract_content(body: Any) -> str:
        """문자열 응답과 여러 게이트웨이 응답 구조에서 콘텐츠를 찾는다."""
        if isinstance(body, str):
            return body
        if isinstance(body, dict):
            # OpenAI 호환 구조에서는 첫 번째 선택지만 사용한다.
            choices = body.get("choices")
            if choices:
                msg = choices[0].get("message") or {}
                content = msg.get("content")
                # 콘텐츠가 블록 배열이면 딕셔너리 블록의 text를 순서대로 연결한다.
                if isinstance(content, list):
                    content = "".join(b.get("text", "") for b in content if isinstance(b, dict))
                if content:
                    return content
                if "text" in choices[0]:
                    return choices[0]["text"]
            # choices에서 찾지 못하면 최상위 텍스트 필드를 확인한다.
            for k in ("content", "output_text", "text"):
                if isinstance(body.get(k), str):
                    return body[k]
        raise LLMError(f"응답에서 content를 찾지 못했습니다: {str(body)[:300]}")

    def chat_json(
        self,
        system_prompt: str,
        user_content: str,
        *,
        json_schema: dict[str, Any],
        schema_name: str = "structured_output",
    ) -> dict[str, Any]:
        """JSON 출력을 요청하고, auto 모드에서는 실패 시 다음 방식으로 재시도한다."""
        # 명시적으로 지정했거나 이전에 성공한 모드가 있으면 해당 방식만 사용한다.
        modes = (
            ["json_schema", "json_object", "prompt"]
            if self._json_mode == "auto"
            else [self._json_mode]
        )
        last_err: Exception | None = None
        for mode in modes:
            sys_prompt = system_prompt
            rf: dict[str, Any] | None = None
            if mode == "json_schema":
                # 서버에 strict JSON Schema 기반의 구조화 출력을 요청한다.
                rf = {
                    "type": "json_schema",
                    "json_schema": {"name": schema_name, "strict": True, "schema": json_schema},
                }
            elif mode == "json_object":
                # 서버에는 JSON 객체를 요청하고, 구체적인 스키마는 프롬프트로 전달한다.
                rf = {"type": "json_object"}
                sys_prompt += (
                    "\n\n[출력 스키마] 아래 JSON Schema를 정확히 따르는 JSON만 출력하라.\n"
                    + json.dumps(json_schema, ensure_ascii=False)
                )
            else:
                # response_format 없이 프롬프트 지침만으로 JSON 출력을 유도한다.
                sys_prompt += (
                    "\n\n[출력 형식] 아래 JSON Schema를 따르는 JSON 객체만 출력하라. "
                    "코드펜스와 설명 문장 금지.\n"
                    + json.dumps(json_schema, ensure_ascii=False)
                )
            try:
                raw = self.chat(
                    [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    response_format=rf,
                )
                # JSON 구문을 파싱할 뿐, 여기서 스키마 일치 여부를 별도로 검증하지는 않는다.
                parsed = self._loads_lenient(raw)
                if self._json_mode == "auto" and mode != modes[0]:
                    logger.warning("json 모드 폴백 적용: %s", mode)
                # 성공한 방식을 고정한다. 이후 호출에서는 auto 폴백 목록을 다시 만들지 않는다.
                self._json_mode = mode
                return parsed
            # 호출 또는 파싱 실패를 기록하고, 남은 모드가 있으면 다음 방식을 시도한다.
            except Exception as e:  # noqa: BLE001
                last_err = e
                logger.info("json 모드 '%s' 실패: %s", mode, e)
        raise LLMError(f"구조화 출력 실패(모든 모드): {last_err}")

    @staticmethod
    def _loads_lenient(text: str) -> dict[str, Any]:
        """코드펜스나 주변 설명이 포함된 응답에서 JSON 파싱을 시도한다."""
        # 응답 양 끝의 Markdown 코드펜스를 제거하고 전체 문자열부터 파싱한다.
        t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE).strip()
        try:
            return json.loads(t)
        except json.JSONDecodeError:
            pass
        # 전체 파싱이 실패하면 첫 여는 중괄호부터 마지막 닫는 중괄호까지 다시 시도한다.
        # JSON 객체 타입이나 필드 구조를 검증하는 단계는 아니다.
        start, end = t.find("{"), t.rfind("}")
        if start != -1 and end > start:
            return json.loads(t[start : end + 1])
        raise LLMError(f"JSON 파싱 실패: {t[:300]}")
