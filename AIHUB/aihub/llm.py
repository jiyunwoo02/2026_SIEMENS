from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx

from .config import get_settings
from .schema import ALL_FIELDS, ALLOWED_SHIFTS, FIELD_SPEC

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """LLM 호출, 모델 탐색, 응답 처리 과정에서 명시적으로 보고하는 오류."""

    pass


def _field_doc() -> str:
    """공통 필드 명세를 추출 프롬프트에 사용할 설명 목록으로 변환한다."""
    return "\n".join(
        f"- {name} ({spec['type']}): {spec['desc']}" for name, spec in FIELD_SPEC.items()
    )

# 필드 설명과 허용 교대조 목록은 모듈 로딩 시 공통 스키마에서 가져온다.
EXTRACTION_SYSTEM_PROMPT = f"""당신은 제조 공정 데이터 추출기입니다.
사용자 발화에서 결함률 예측 모델의 입력 피처를 추출해 JSON으로만 응답합니다.

[필드 정의]
{_field_doc()}

[기본 원칙]
- 발화에 적힌 것만 추출한다. 기본값·평균값·업계 통념으로 채우지 않고, 누락을 0으로 채우지 않는다. 모르면 null이 정답이다.
- 허용값 밖 코드(LINE-BPR-03, SIM-SUP-D)와 범위 밖 수치(공구 마모 140%, -5%)도 적힌 그대로 추출한다. 검증은 시스템이 한다.
- 언급되지 않은 필드는 그냥 null이며 ambiguous_fields에 넣지 않는다.

[불확실한 값: A / B 두 가지로만 처리한다]
A. 필드는 특정되나 값을 하나로 확정할 수 없다 -> 값은 null, 필드명을 ambiguous_fields에 추가
   - 정성·상대 표현: "평소보다 높다", "꽤 닳았다", "약간", "얼마 전에 정비"
   - 범위 표현: "50~60%", "460~470개" (평균·중간값으로 확정하지 않는다)
   - 발화 내 번복: "44.2%라고 했는데 54.2%였나"
   - 미확정 코드: "BPR 라인 중 한 곳", "오후조", "공급사는 A나 B"
   - 필드와 맞지 않는 단위("습도 5mm"), 환산표에 없는 단위(시간·개월), 단위 없는 코팅 두께("코팅 0.08")
   - 특정 필드를 지목한 기준 참조: "습도는 평소와 같아요"
B. 값은 있으나 어느 필드인지 특정할 수 없다 -> 값을 버리고 notes에만 기록 (ambiguous_fields에는 넣지 않는다)
   - notes 형식: "'80'이(가) 어떤 항목의 값인지 알 수 없어 반영하지 않았습니다."
   - 필드를 지목하지 않은 기준 참조("평소랑 비슷한 조건")도 B로 본다.
     이때 전 필드 null, notes: "기준 조건을 알 수 없어 반영하지 않았습니다."

[항목명 없는 값의 필드 결정]
- 항목명(수량, 습도, 마모, 정비 경과일 등)이 붙어 있으면 그 필드의 값이다.
- 문자 값은 형태로 결정한다.
  LINE- -> production_line / SIM-SUP- -> supplier_code / DAY·NIGHT·주간·야간 -> shift
- 수치 값은 후보를 좁혀서 판단한다.
  후보 = [아직 필요한 값]의 수치 필드 중, 아래 환산표에서 그 단위를 받을 수 있는 필드.
  목록이 주어지지 않은 첫 발화에서는 12개 필드 전체를 목록으로 본다.
  - 후보가 정확히 1개 -> 그 필드에 넣는다.
    예) "533개" -> planned_quantity, "83.95점" -> incoming_material_quality_score, "2주" -> days_since_maintenance
    예) 필요한 값이 supplier_code, planned_quantity뿐일 때 "SIM-SUP-B, 480" -> 각각에 배정
  - 후보가 0개 또는 2개 이상 -> B로 처리한다. 순서나 크기로 추측하지 않는다.
    예) 단위 없는 "80", "35%", "0.3mm"
- 같은 발화의 다른 값(라인, 교대조 등)은 정상적으로 추출한다.

[정규화]
- 숫자만 추출하고 천 단위 쉼표는 제거한다("1,200" -> 1200).
- 코드는 대문자로 정규화한다(line-bpr-01 -> LINE-BPR-01).
- 교대조는 {ALLOWED_SHIFTS} 중 하나로: 주간·오전·낮·day·주간조 -> DAY / 야간·밤·night·야간조 -> NIGHT
- 한글 단위: 퍼센트=% / 마이크로미터·마이크론=um / 밀리·밀리미터=mm / 센티·센티미터=cm / 미터=m
- 반드시 기준 단위로 환산해서 넣는다. 계산은 정확히 하고, 환산 후 범위 검증은 시스템이 한다.
  | 필드 | 기준 단위 | 환산 |
  |---|---|---|
  | fixture_alignment_offset_mm | mm | um /1000, cm x10, m x1000 |
  | coating_target_thickness_um | um | mm x1000, cm x10000, m x1000000 |
  | days_since_maintenance | 일 | 주 x7 (시간·개월은 A) |
  | planned_quantity | 개 | 천 x1000, 만 x10000 (units·pcs 그대로) |
  | ambient_humidity_pct / weld_energy_setting_pct / process_setting_deviation_pct / tool_wear_pct | % | %·퍼센트만 인식 |
  | incoming_material_quality_score | 점 | 숫자 그대로 |
- 환산했으면 notes에 "지그 정렬 오차 0.2cm -> 2mm"처럼 원 표현과 환산값을 적는다.
  notes에 적을 내용이 여러 건이면 한 문자열로 이어 쓴다.

[records 구성]
- 조건을 비교하는 질의는 레코드를 분리하고, 공통 조건을 각 레코드에 동일하게 복사한다.
  공통으로 빠진 필드는 모든 레코드에서 null이다.
- 단일 조건이면 1건이다. "예측해줘"가 없어도 공정 조건을 나열한 발화는 예측 요청으로 본다.
- 예측에 필요한 입력이 무엇인지 묻는 발화도 예측 요청으로 보고, 전 필드가 null인 레코드 1건을 둔다.
- 공정·결함률 예측과 무관한 발화(모델 학습 방식 질문, 잡담)만 records를 빈 배열로 둔다.

[대화 맥락]
- [이미 확인된 값]이 주어지면, 이번 발화에서 새로 언급되거나 정정된 값만 채우고 나머지는 null로 둔다.
  기존 값을 복사하지 않는다. 병합은 시스템이 처리한다.
- 정정 발화("A가 아니라 B입니다")는 해당 필드에 새 값을 넣는다.
- [아직 필요한 값]은 위 후보 축소에만 쓴다. 목록에 있다는 이유로 발화에 없는 값을 채우지 않는다.
- [이미 확인된 값]에 있는 필드를 이번 발화가 모호하게 바꾸려 하면
  ("습도가 꽤 높아졌다면", "마모가 더 심해지면") 값은 null로 두고 그 필드명을 ambiguous_fields에 넣는다.
- 확인된 값에서 증감량을 추정해 새 값을 만들지 않는다. (54.49에서 "꽤 높아졌다"로 70을 만들지 않는다.)

ambiguous_fields가 없으면 빈 배열로 둔다. JSON 외의 설명 문장은 출력하지 않는다."""


# 해설 생성용 지침: 예측값의 퍼센트 단위를 유지하고 근거 없는 수치 생성을 금지한다.
ANSWER_SYSTEM_PROMPT = """당신은 제조 품질 분석 어시스턴트입니다.
GBT(Gradient Boosted Trees) 기반 회귀(Regression) 모델의 결함률 예측 결과와 입력 조건을 바탕으로 한국어로 간결하게 답변합니다.

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
    """기존 확인값, 아직 필요한 값, 이번 발화를 구분하여 추출 요청의 사용자 메시지를 만든다.

    [수정] 2026-10-23: 항목 표시 없는 값을 남은 필드와 매칭할 수 있도록 [아직 필요한 값] 목록을 추가했다.
    목록은 known에 없는 필드를 ALL_FIELDS 순서로 계산한다(SlotFillingSession.missing()과 같은 기준이므로
    extract() 시그니처는 바뀌지 않는다). known이 비어 있으면 질의 원문만 전달한다(기존과 동일, 이 경우 프롬프트가 12개 전체를 목록으로 간주한다).
    """
    if not known:
        return query
    needed = [f for f in ALL_FIELDS if f not in known]
    needed_doc = (
        "\n".join(f"- {f} ({FIELD_SPEC[f]['type']}): {FIELD_SPEC[f]['desc']}" for f in needed)
        if needed
        else "(없음 - 모든 값이 확인됨)"
    )
    # 기존 값은 맥락으로만 제공한다. 새 값과의 실제 병합은 파이프라인에서 수행한다.
    return (
        "[이미 확인된 값]\n"
        + json.dumps(known, ensure_ascii=False, indent=2)
        + "\n\n[아직 필요한 값]\n"
        + needed_doc
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
