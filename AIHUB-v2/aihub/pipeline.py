from __future__ import annotations

import json
import logging
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from pydantic import ValidationError

from .config import get_settings
from .llm import (
    ANSWER_SYSTEM_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
    LLMError,
    SDCLLMClient,
    build_extraction_user_content,
)
from .ml import DefectRateMLClient, MLEndpointError
from .optimization import OptimizationClient, OptimizationEndpointError, build_target
from .schema import (
    ALL_FIELDS,
    FIELD_LABELS,
    FIELD_SPEC,
    INTENTS,
    NUMERIC_FIELDS,
    UNCONTROLLABLE_FIELDS,
    DefectRateInput,
    extraction_json_schema,
    validate_provided_fields,
)

logger = logging.getLogger(__name__)

# API와 CLI에 전달할 처리 결과: 성공, 추가 입력 필요, 입력 오류, 외부 서비스 오류.
# [수정] 2026-10-27: 최적화 의도가 불분명할 때 쓰는 "clarify" 상태를 추가했다(예측 경로는 영향 없음).
Status = Literal["ok", "need_more_info", "invalid_input", "endpoint_error", "llm_error", "clarify"]


@dataclass
class ExtractionResult:
    """LLM에서 추출한 조건별 레코드와 부가 설명을 보관한다."""

    records: list[dict[str, Any]] = field(default_factory=list)
    # [추가] 모호한 표현 때문에 null로 둔 필드명(ALL_FIELDS 순서, 중복 없음).
    ambiguous_fields: list[str] = field(default_factory=list)
    notes: str | None = None
    # [추가] 2026-10-27: 챗봇 의도(schema.INTENTS). enum 밖 값이나 누락 시 "clarify"로 처리한다(extract() 참고).
    intent: str = "clarify"


class QueryExtractor:
    """자연어 질의를 모델 입력 필드로 추출하고 기본 타입을 정규화한다."""

    def __init__(self, client: SDCLLMClient | None = None) -> None:
        self._client = client or SDCLLMClient()

    def extract(self, query: str, known: dict[str, Any] | None = None) -> ExtractionResult:
        """기존 확인값을 맥락으로 제공하여 이번 발화의 조건을 JSON으로 추출한다."""
        raw = self._client.chat_json(
            EXTRACTION_SYSTEM_PROMPT,
            build_extraction_user_content(query, known),
            json_schema=extraction_json_schema(),
            schema_name="defect_rate_extraction",
        )
        # [수정] ambiguous_fields를 읽는다. json_object/prompt 폴백에서는 키가 없거나 잘못된
        # 이름이 올 수 있으므로 알려진 필드만 남긴다.
        raw_amb = raw.get("ambiguous_fields") or []
        amb_set = {f for f in raw_amb if isinstance(f, str)} if isinstance(raw_amb, list) else set()
        ambiguous = [f for f in ALL_FIELDS if f in amb_set]
        records = [self._coerce(r) for r in (raw.get("records") or []) if isinstance(r, dict)]
        # "모호한 값은 null" 원칙을 코드에서도 보장한다. LLM이 값과 모호 표시를 함께 내면 값을 버린다.
        for rec in records:
            for f in ambiguous:
                rec[f] = None
        # [추가] 2026-10-27: json_object/prompt 폴백에서는 intent 키가 없거나 enum 밖 값이 올 수 있어
        # 알 수 없는 의도는 "clarify"로 처리한다(최적화 API를 잘못된 의도로 호출하지 않기 위한 안전장치).
        raw_intent = raw.get("intent")
        intent = raw_intent if raw_intent in INTENTS else "clarify"
        return ExtractionResult(records=records, ambiguous_fields=ambiguous, notes=raw.get("notes"), intent=intent)

    @staticmethod
    def _coerce(item: dict[str, Any]) -> dict[str, Any]:
        """필드 타입을 맞추고 누락값이나 변환할 수 없는 값을 None으로 처리한다."""
        # 허용 범위 검증은 이후 DefectRateInput 생성 단계에서 수행한다.
        out: dict[str, Any] = {}
        for f in ALL_FIELDS:
            v = item.get(f)
            # [수정] bool은 int의 하위 타입이라 True가 1로 변환되므로 미확정(None)으로 처리한다.
            if v is None or isinstance(v, bool) or (isinstance(v, str) and not v.strip()):
                out[f] = None
                continue
            expected = FIELD_SPEC[f]["type"]
            try:
                # 정수 필드는 실수 변환 후 반올림하고, 문자열은 공백 제거·대문자화한다.
                if expected in ("integer", "number"):
                    num = float(v)
                    # [수정] NaN/inf는 범위 제약이 없는 필드에서 검증을 통과할 수 있어 미확정으로 처리한다.
                    if not math.isfinite(num):
                        raise ValueError("non-finite number")
                    # [수정] mm→um 환산(0.0984*1000=98.39999...) 같은 부동소수점 오차를 없애기 위해
                    # 소수점 6자리로 반올림한다. 골든 셋의 최대 자릿수(예: 0.112)보다 충분히 길다.
                    out[f] = int(round(num)) if expected == "integer" else round(num, 6)
                else:
                    out[f] = str(v).strip().upper()
            except (TypeError, ValueError):
                logger.warning("필드 '%s' 타입 변환 실패(값=%r) -> None", f, v)
                out[f] = None
        return out


@dataclass
class SlotFillingSession:
    """여러 대화에 걸쳐 입력 슬롯과 누락 항목 재질문 상태를 유지한다."""

    session_id: str = "default"
    slots: dict[str, Any] = field(default_factory=dict)
    # merge가 호출된 횟수이며, 추출 단계에서 실패한 요청은 포함하지 않는다.
    turn: int = 0
    last_missing: list[str] = field(default_factory=list)
    repeated_asks: int = 0

    def known(self) -> dict[str, Any]:
        """세션에 저장된 값 중 None이 아닌 값만 반환한다."""
        return {k: v for k, v in self.slots.items() if v is not None}

    def missing(self) -> list[str]:
        """세션 기준으로 아직 값이 없는 필드를 공통 필드 순서대로 반환한다."""
        return [f for f in ALL_FIELDS if self.slots.get(f) is None]

    def merge(self, extracted_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """각 추출 레코드에 기존 슬롯을 채우고 새로 언급된 값으로 덮어쓴다."""
        self.turn += 1
        # 추출 레코드가 없어도 기존 슬롯을 바탕으로 한 레코드를 생성한다.
        if not extracted_records:
            extracted_records = [{}]
        merged: list[dict[str, Any]] = []
        for rec in extracted_records:
            row = {f: self.slots.get(f) for f in ALL_FIELDS}
            for f in ALL_FIELDS:
                v = rec.get(f)
                # None은 이번 발화에서 언급하지 않았다는 뜻이므로 기존 값을 유지한다.
                if v is not None:
                    row[f] = v
            merged.append(row)
        self._absorb_common(merged)
        return merged

    def _absorb_common(self, merged: list[dict[str, Any]]) -> None:
        """레코드들에 공통인 값을 저장하고 서로 다른 값은 공통 슬롯에서 제거한다."""
        for f in ALL_FIELDS:
            values = [row[f] for row in merged]
            # 하나라도 미확정이면 해당 슬롯은 변경하지 않는다.
            if any(v is None for v in values):
                continue
            # 실수는 소수점 여섯 자리로 반올림하여 비교하되 저장할 때는 원래 값을 쓴다.
            if len({round(v, 6) if isinstance(v, float) else v for v in values}) == 1:
                self.slots[f] = values[0]
            else:
                self.slots.pop(f, None)

    def track_missing(self, missing: list[str]) -> None:
        """동일한 누락 목록이 연속으로 나타난 횟수를 기록한다(최초 요청은 0)."""
        if missing and missing == self.last_missing:
            self.repeated_asks += 1
        else:
            self.repeated_asks = 0
        self.last_missing = list(missing)

    def reset(self) -> None:
        """세션 ID는 유지하고 저장된 값, 턴 수, 재질문 이력을 초기화한다."""
        self.slots.clear()
        self.turn = 0
        self.last_missing.clear()
        self.repeated_asks = 0


def build_question(
    missing: list[str],
    *,
    repeated: int = 0,
    known: dict[str, Any] | None = None,
    ambiguous: list[str] | None = None,
    no_conditions: bool = False,
    notes: str | None = None,
) -> str:
    """누락·모호 필드의 설명과 확인된 값을 이용해 추가 입력 안내문을 만든다.

    입력:
        missing: 값이 없는 필드 목록(모호 필드 포함).
        repeated: 같은 누락 목록을 연속으로 물은 횟수.
        known: 세션에 확인된 값.
        ambiguous: [추가] 모호한 표현 때문에 null이 된 필드. missing에 없는 이름은 무시한다.
        no_conditions: [추가] 질의에서 공정 조건을 전혀 찾지 못한 경우(N05) 안내 문구를 붙인다.
        notes: [추가] 2026-10-23: 추출기가 남긴 부가 설명. 항목명 없는 숫자('80')를 어떤 필드에도
            배정하지 않은 사유를 사용자에게 알리기 위해 안내문 앞에 덧붙인다.
    출력: Markdown 형식의 안내문.
    """
    known = known or {}
    amb_set = set(ambiguous or [])
    amb = [f for f in missing if f in amb_set]
    plain = [f for f in missing if f not in amb_set]
    parts: list[str] = []
    # [추가] 2026-10-23: 값을 버린 이유(예: "80"이 어떤 항목인지 알 수 없음)를 먼저 보여준다.
    if notes and notes.strip():
        parts.append(f"※ {notes.strip()}")
    if no_conditions:
        parts.append("질의에서 예측에 쓸 공정 조건을 찾지 못했습니다. 이 서비스는 공정 조건으로 결함률(%)을 예측합니다.")
    # [수정] 모호한 항목은 "값이 없다"가 아니라 정확한 값을 요청하는 별도 문구로 안내한다.
    if amb:
        parts.append(
            "다음 항목은 표현이 모호해 값을 확정하지 못했습니다. 정확한 수치(단위 포함)나 코드로 알려주세요.\n"
            + "\n".join(f"- **{f}** — {FIELD_SPEC[f]['desc']}" for f in amb)
        )
    if plain:
        head = (
            "결함률 예측을 위해 아래 12개 값이 모두 필요합니다.\n"
            if len(plain) == len(ALL_FIELDS)
            else f"예측에 필요한 값 {len(plain)}개가 아직 없습니다. 아래 항목을 알려주세요.\n"
        )
        parts.append(head + "\n".join(f"- **{f}** — {FIELD_SPEC[f]['desc']}" for f in plain))
    body = "\n\n".join(parts)
    # 확인된 값은 최대 6개만 보여주고 나머지는 개수로 요약한다.
    if known:
        confirmed = ", ".join(f"{k}={v}" for k, v in list(known.items())[:6])
        more = f" 외 {len(known) - 6}개" if len(known) > 6 else ""
        body += f"\n\n(확인된 값: {confirmed}{more})"
    # 재질문이거나 누락 항목이 많으면 일괄 입력 형식을 덧붙인다.
    # 템플릿의 0은 형식 예시이며, 실제 입력값을 자동으로 채우는 기본값이 아니다.
    if repeated >= 1 or len(missing) >= 6:
        template = ", ".join(
            f"{f}=" + ("0" if f in NUMERIC_FIELDS else "값") for f in missing
        )
        body += f"\n\n아래 형식으로 한 번에 입력하셔도 됩니다.\n```\n{template}\n```"
    return body


def _invalid_result(reasons_by_field: dict[str, str], session: SlotFillingSession) -> "PipelineResult":
    """위반 필드 -> 오류 메시지로 invalid_input 응답을 만든다.

    [수정] 2026-10-23(로직 변경 없는 추출): 기존 ValidationError 처리 블록을 그대로 함수로 분리했다.
    필드 단위 사전 검증과 최종 검증이 같은 응답 형식을 쓰기 위함이다.
    위반 필드는 세션에서 제거하여 다음 발화에서 정정할 수 있게 한다.
    """
    invalid_fields = [f for f in ALL_FIELDS if f in reasons_by_field]
    reasons = [f"{f}: {reasons_by_field[f]}" for f in invalid_fields]
    for f in invalid_fields:
        session.slots.pop(f, None)
    hints = [f"- **{f}** — {FIELD_SPEC[f]['desc']}" for f in invalid_fields]
    return PipelineResult(
        status="invalid_input",
        answer="입력값이 모델 허용 범위를 벗어났습니다. 다시 알려주세요.\n- "
        + "\n- ".join(reasons)
        + ("\n\n허용 범위:\n" + "\n".join(hints) if hints else ""),
        errors=reasons,
        invalid_fields=invalid_fields,
        known_slots=session.known(),
    )


# [추가] 2026-10-27: 최적화 API 응답의 교대조 코드를 사람이 읽기 좋은 표현으로 바꾼다.
# 없는 값(예상치 못한 코드)은 원본 문자열을 그대로 보여준다.
_SHIFT_DISPLAY: dict[str, str] = {"DAY": "주간 (DAY)", "NIGHT": "야간 (NIGHT)"}


def _format_condition_value(field_name: str, value: Any) -> str:
    """최적화 결과의 조건 값 하나를 표시용 문자열로 바꾼다."""
    if field_name == "shift" and isinstance(value, str):
        return _SHIFT_DISPLAY.get(value, value)
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _format_conditions_table(conditions: dict[str, Any]) -> str:
    """최적화 API가 돌려준 조건 dict를 Markdown 목록 문자열로 만든다.

    [추가] 2026-10-27: FIELD_LABELS에 없는 키(사전에 없는 응답 필드)는 키 이름을 그대로 보여준다.
    UNCONTROLLABLE_FIELDS에 속한 항목에는 "참고값" 안내를 덧붙인다(스펙 4.5/6.4).
    """
    ordered_keys = [f for f in ALL_FIELDS if f in conditions] + [
        k for k in conditions if k not in ALL_FIELDS
    ]
    lines = []
    for key in ordered_keys:
        label = FIELD_LABELS.get(key, key)
        value_str = _format_condition_value(key, conditions[key])
        suffix = " _(참고값: 현장에서 바로 조정하기 어려운 값)_" if key in UNCONTROLLABLE_FIELDS else ""
        lines.append(f"- **{label}**: {value_str}{suffix}")
    return "\n".join(lines)


def _format_optimize_only(intent: str, result: dict[str, Any]) -> str:
    """[추가] 2026-10-27: 조건 입력 없이 최적화만 요청한 경우의 답변. LLM 호출 없이 결정적으로 생성한다
    (스펙 6.3: "최적 조건 표와 예상 결함률만 보여준다" - 수치를 모델/LLM이 지어내지 않도록 서식만 적용).
    """
    headline = (
        "불량 확률을 최소화하는 최적 조건입니다."
        if intent == "optimize_reduce_defect"
        else "불량이 발생하기 쉬운(위험) 조건입니다."
    )
    defect_pct = result["defect_probability"] * 100
    normal_pct = result["normal_probability"] * 100
    table = _format_conditions_table(result["conditions"])
    return (
        f"{headline}\n\n{table}\n\n"
        f"이 조건에서의 예상 확률 — 불량: {defect_pct:.2f}%, 정상: {normal_pct:.2f}%\n\n"
        "※ 참고값으로 표시된 항목은 현장에서 바로 바꾸기 어려운 값입니다.\n"
        # [추가] 2026-10-27: 스펙 6.3 필수 고지 문구("모델 기반 추정이며 보장하지 않음")가 누락되어 있어 추가했다.
        "※ 이 결과는 모델 기반 추정이며 실제 공정 결과를 보장하지 않습니다."
    )


def _format_predict_and_optimize(
    predictions: list[float],
    optimization: dict[str, Any] | None,
    optimization_error: str | None,
) -> str:
    """[추가] 2026-10-27: 예측과 최적화를 함께 요청한 경우의 답변(스펙 5.3/6.3).

    최적화 호출이 실패해도(optimization=None) 예측 결과는 보여준다(부분 성공 허용, 스펙 6.2).
    """
    parts = ["현재 조건의 예측 결함률: " + ", ".join(f"{p:.2f}%" for p in predictions)]
    if optimization is not None:
        defect_pct = optimization["defect_probability"] * 100
        table = _format_conditions_table(optimization["conditions"])
        parts.append(
            "불량 확률을 최소화하는 개선 조건입니다.\n\n"
            + table
            + f"\n\n개선 조건 적용 시 예상 불량 확률: {defect_pct:.2f}%\n\n"
            # [추가] 2026-10-27: 스펙 6.3 필수 고지 문구를 추가했다(_format_optimize_only와 동일).
            "※ 이 결과는 모델 기반 추정이며 실제 공정 결과를 보장하지 않습니다."
        )
    elif optimization_error:
        parts.append(f"※ 개선 조건 계산에는 실패했습니다: {optimization_error}")
    return "\n\n".join(parts)


@dataclass
class PipelineResult:
    """성공과 오류 모두에 사용하는 공통 응답 구조."""

    status: Status
    answer: str
    predictions: list[float] = field(default_factory=list)
    unit: str = "percent"
    model_input: list[dict[str, Any]] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    # [추가] missing_fields 중 모호한 표현 때문에 null이 된 필드(항상 부분집합).
    ambiguous_fields: list[str] = field(default_factory=list)
    # [추가] invalid_input일 때 범위·허용값 검증에 실패한 필드(ALL_FIELDS 순서, 중복 없음).
    invalid_fields: list[str] = field(default_factory=list)
    known_slots: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    # ML 클라이언트가 보고한 호출 시간으로, LLM 처리 등 전체 실행 시간은 아니다.
    latency_ms: int = 0
    # [추가] 2026-10-27: 이번 응답을 만든 챗봇 의도(schema.INTENTS). 기본값 "predict"는 기존 호출부
    # (테스트 등)가 intent 없이 PipelineResult를 직접 만들던 코드와의 하위 호환을 위한 것이다.
    intent: str = "predict"
    # [추가] 2026-10-27: 최적화 API 원본 응답(파싱 결과). optimization.parse_optimization_response()
    # 형식 - {"conditions": dict, "defect_probability": float, "normal_probability": float,
    # "predicted_label": str, "latency_ms": int, "target": str}. 최적화를 호출하지 않았거나 실패하면 None.
    optimization: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """API 및 CLI에서 출력할 수 있도록 데이터클래스를 딕셔너리로 변환한다."""
        return asdict(self)


class DefectRatePipeline:
    """질의 추출 → 슬롯 병합 → 입력 검증 → ML 예측 → 결과 설명을 조율한다."""

    def __init__(
        self,
        *,
        extractor: QueryExtractor | None = None,
        ml_client: DefectRateMLClient | None = None,
        llm: SDCLLMClient | None = None,
    ) -> None:
        """구성 요소를 준비한다.

        [수정] 테스트에서 LLM/ML 대역을 주입할 수 있도록 선택 인자를 추가했다.
        인자를 생략하면 기존과 같이 설정을 검증하고 실제 클라이언트를 만든다.
        extractor만 주고 llm을 생략하면 해설 단계는 수치 답변으로 대체된다.
        """
        if extractor is None or ml_client is None:
            # 필수 설정을 확인한다. 설정 누락 시 RuntimeError(api.py에서 503으로 변환).
            get_settings().validate_runtime()
        if llm is None and extractor is None:
            llm = SDCLLMClient(get_settings())
        # 추출과 해설 생성에 같은 LLM 클라이언트를 공유한다.
        self._llm = llm
        self._extractor = extractor or QueryExtractor(client=llm)
        self._ml = ml_client or DefectRateMLClient()

    def run(
        self,
        query: str,
        *,
        session: SlotFillingSession | None = None,
        explain: bool = True,
    ) -> PipelineResult:
        """한 번의 발화를 처리하고 현재 의도에 맞는 결과를 반환한다.

        [수정] 2026-10-27: intent(의도)에 따라 기존 예측 흐름(_run_predict)과 신규 최적화 흐름
        (_run_optimize_only / _run_predict_and_optimize / _run_clarify)으로 분기한다. intent=="predict"일 때의
        동작은 리팩터링 이전과 동일하다(로직 이동만 했다, chatbot_optimization_feature_spec.md 3.2).
        """
        # 외부에서 세션을 전달해야 다음 요청에서도 입력값이 유지된다.
        session = session or SlotFillingSession()
        try:
            extraction = self._extractor.extract(query, known=session.known())
        except LLMError as e:
            return PipelineResult(
                status="llm_error",
                answer=f"질의 해석에 실패했습니다. 잠시 후 다시 시도해주세요. ({e})",
                errors=[str(e)],
                known_slots=session.known(),
            )

        intent = extraction.intent
        if intent == "clarify":
            return self._run_clarify()
        if intent in ("optimize_reduce_defect", "optimize_find_defect_risk"):
            return self._run_optimize_only(intent)
        if intent == "predict_and_optimize":
            return self._run_predict_and_optimize(extraction, session)
        # intent == "predict" (기존에 유일한 경로였다)
        return self._run_predict(query, extraction, session, explain)

    def _gather_and_predict(
        self, extraction: "ExtractionResult", session: SlotFillingSession
    ) -> tuple[PipelineResult | None, dict[str, Any] | None]:
        """조건 병합 -> 검증 -> ML 예측까지의 공통 단계를 수행한다.

        [수정] 2026-10-27(로직 변경 없는 추출): 이전 run() 본문을 그대로 옵긴 것이다. predict와
        predict_and_optimize 두 의도가 동일한 조건 수집/검증 로직을 공유하기 위함이다.

        반환: (early_result, data)
          - 조건이 부족하거나 검증 실패, ML 호출 실패 시: (PipelineResult, None) - 그대로 반환하면 된다.
          - 성공 시: (None, {"records": [...], "out": {...}}) - out은 DefectRateMLClient.predict() 결과.
        """
        # [추가] 예측 요청이 아니거나 공정 조건이 전혀 없고(records=[]) 세션에도 확인값이 없으면
        # 골든 N05 규칙대로 records=[], missing_fields=12개 전체를 반환한다. 빈 레코드를 병합하지 않으므로 turn도
        # 증가하지 않는다. 세션에 값이 있으면(예: "그대로 다시 예측") 기존처럼 병합 경로를 탄다.
        if not extraction.records and not session.known():
            missing = list(ALL_FIELDS)
            session.track_missing(missing)
            return (
                PipelineResult(
                    status="need_more_info",
                    answer=build_question(
                        missing, repeated=session.repeated_asks, no_conditions=True
                    ),
                    missing_fields=missing,
                ),
                None,
            )

        # [수정] 2026-10-26 (로직 변경): 이미 확인된 필드를 모호하게 정정한 경우(예: 습도 54.49 확인 후
        # "습도가 꽤 높아졌다면?") 추출값은 null이라 병합에서 기존 값이 조용히 유지되고,
        # 그 결과 missing/ambiguous_fields에서 빠져 예측이 그대로 진행되던 문제를 막는다.
        # 모호하다고 표시된 필드는 세션 슬롯에서 비워 병합 후 null이 되게 하고, 재질문 대상(missing)과
        # 모호 필드(ambiguous_fields)로 남긴다. 기존 값으로 예측하면 사용자의 what-if 의도와 어긋나기 때문이다.
        # 값이 없는 필드에 대한 pop은 영향이 없다(세션에 없던 필드는 기존대로 누락 처리).
        for f in extraction.ambiguous_fields:
            session.slots.pop(f, None)

        # [추가] 2026-10-23: 슬롯이 다 차기 전에도 값이 있는 필드는 즉시 검증한다.
        # 이전에는 12개가 모두 찬 뒤에만 검증해서 허용값 밖 코드(SIM-SUP-D)가 세션에 저장됐다.
        # 위반 필드는 null로 바꿔 병합 대상에서 빼고(세션에 저장하지 않음), 같은 발화의 유효한 값은 유지한다.
        bad_reasons: dict[str, str] = {}
        for rec in extraction.records:
            for f, msg in validate_provided_fields(rec).items():
                bad_reasons.setdefault(f, msg)
        if bad_reasons:
            for rec in extraction.records:
                for f in bad_reasons:
                    rec[f] = None
            session.merge(extraction.records)
            return _invalid_result(bad_reasons, session), None

        # 모든 비교 조건 중 하나라도 값이 없으면 해당 필드를 추가 질문 대상으로 삼는다.
        merged = session.merge(extraction.records)
        missing = sorted(
            {f for row in merged for f in ALL_FIELDS if row.get(f) is None},
            key=ALL_FIELDS.index,
        )
        # 필수값이 모이기 전에는 ML API를 호출하지 않는다.
        if missing:
            session.track_missing(missing)
            # [추가] 모호 필드는 실제로 누락된 필드만 남겨 ambiguous_fields ⊆ missing_fields를 보장한다.
            # [수정] 2026-10-26: 모호 필드는 위에서 세션 슬롯을 비웠고 extract()가 모든 레코드에서 해당 값을
            # null로 만들기 때문에, 이미 확인됐던 필드도 병합 후 missing에 남아 이 목록에 포함된다.
            ambiguous = [f for f in missing if f in set(extraction.ambiguous_fields)]
            return (
                PipelineResult(
                    status="need_more_info",
                    answer=build_question(
                        missing,
                        repeated=session.repeated_asks,
                        known=session.known(),
                        ambiguous=ambiguous,
                        # [추가] 2026-10-23: 항목 불명 수치를 버린 사유를 사용자에게 전달한다.
                        notes=extraction.notes,
                    ),
                    missing_fields=missing,
                    ambiguous_fields=ambiguous,
                    known_slots=session.known(),
                    model_input=merged,
                ),
                None,
            )
        session.track_missing([])

        # 타입 정규화 이후 실제 모델의 수치 범위와 코드 제약을 검증한다.
        try:
            records = [DefectRateInput(**{f: row[f] for f in ALL_FIELDS}) for row in merged]
        except ValidationError as e:
            # [수정] 2026-10-23: 사전 검증을 통과했더라도 남을 수 있는 위반에 대한 안전망으로 유지하며,
            # 응답 생성은 _invalid_result로 통일했다(동작·메시지 형식 동일).
            final_reasons: dict[str, str] = {}
            for err in e.errors():
                if err["loc"]:
                    final_reasons.setdefault(str(err["loc"][0]), err["msg"])
            return _invalid_result(final_reasons, session), None

        # 검증을 통과한 레코드만 예측 클라이언트에 전달한다.
        try:
            out = self._ml.predict(records)
        except MLEndpointError as e:
            return (
                PipelineResult(
                    status="endpoint_error",
                    answer=f"예측 API 호출에 실패했습니다. 엔드포인트 상태를 확인해주세요.\n{e}",
                    model_input=[r.to_row() for r in records],
                    errors=[str(e)],
                    known_slots=session.known(),
                ),
                None,
            )
        return None, {"records": records, "out": out}

    def _run_predict(
        self, query: str, extraction: "ExtractionResult", session: SlotFillingSession, explain: bool
    ) -> PipelineResult:
        """기존 결함률 예측 흐름(동작 변경 없음)."""
        early, data = self._gather_and_predict(extraction, session)
        if early is not None:
            return early
        out = data["out"]
        # 해설을 요청하지 않으면 추가 LLM 호출 없이 예측 수치만 표시한다.
        answer = (
            self._explain(query, out)
            if explain
            else "예측 결함률: " + ", ".join(f"{p:.2f}%" for p in out["predictions"])
        )
        return PipelineResult(
            status="ok",
            answer=answer,
            predictions=out["predictions"],
            unit=out["unit"],
            model_input=out["payload"]["data"],
            known_slots=session.known(),
            latency_ms=out["latency_ms"],
            intent="predict",
        )

    def _run_predict_and_optimize(
        self, extraction: "ExtractionResult", session: SlotFillingSession
    ) -> PipelineResult:
        """[추가] 2026-10-27: 현재 조건의 결함률 예측과 개선 조건 탐색을 함께 수행한다(스펙 5.3/6.3).

        예측에 필요한 조건이 부족하면(기존 _run_predict와 동일 기준) 최적화를 호출하지 않고
        그대로 되묻는다. 조건이 충족된 이후에만 최적화 API를 호출하며, 최적화 호출이
        실패해도 예측 결과는 그대로 보여준다(부분 성공, 스펙 6.2).
        """
        early, data = self._gather_and_predict(extraction, session)
        if early is not None:
            return early
        out = data["out"]

        optimization_result: dict[str, Any] | None = None
        optimization_error: str | None = None
        try:
            target = build_target("predict_and_optimize")
            optimization_result = OptimizationClient().optimize(target)
            logger.info(
                "optimization intent=predict_and_optimize target=%s latency_ms=%s status=ok",
                target, optimization_result.get("latency_ms"),
            )
        except (OptimizationEndpointError, ValueError) as e:
            optimization_error = str(e)
            logger.info("optimization intent=predict_and_optimize status=error error=%s", e)

        answer = _format_predict_and_optimize(out["predictions"], optimization_result, optimization_error)
        return PipelineResult(
            status="ok",
            answer=answer,
            predictions=out["predictions"],
            unit=out["unit"],
            model_input=out["payload"]["data"],
            known_slots=session.known(),
            latency_ms=out["latency_ms"],
            intent="predict_and_optimize",
            optimization=optimization_result,
            errors=[optimization_error] if optimization_error else [],
        )

    def _run_optimize_only(self, intent: str) -> PipelineResult:
        """[추가] 2026-10-27: 조건 입력 없이 최적화 API만 호출하는 두 의도
        (불량 최소화/위험 조건 탐색). 이 경로는 ML 예측 API나 LLM 해설을 호출하지 않는다.
        """
        try:
            target = build_target(intent)
        except ValueError as e:
            # INTENT_TO_TARGET에 없는 의도가 여기로 오면 내부 분기 오류이므로 clarify보다 명확히 알린다.
            return PipelineResult(
                status="llm_error",
                answer="요청을 처리할 수 없습니다. 다시 시도해주세요.",
                errors=[str(e)],
                intent=intent,
            )
        try:
            result = OptimizationClient().optimize(target)
            logger.info(
                "optimization intent=%s target=%s latency_ms=%s status=ok",
                intent, target, result.get("latency_ms"),
            )
        except OptimizationEndpointError as e:
            logger.info("optimization intent=%s target=%s status=error error=%s", intent, target, e)
            return PipelineResult(
                status="endpoint_error",
                answer=f"최적화 계산 중 오류가 발생했습니다.\n{e}",
                errors=[str(e)],
                intent=intent,
            )
        return PipelineResult(
            status="ok",
            answer=_format_optimize_only(intent, result),
            intent=intent,
            optimization=result,
        )

    def _run_clarify(self) -> PipelineResult:
        """[추가] 2026-10-27: 최적화 의도는 있으나 방향이 분명하지 않은 경우. 어떤 API도 호출하지 않는다."""
        return PipelineResult(
            status="clarify",
            answer=(
                "요청하신 의도를 정확히 파악하지 못했습니다. "
                "불량을 줄이는 조건을 찾고 싶으신가요, 아니면 불량이 발생하기 쉬운 위험 조건을 찾고 싶으신가요?\n"
                '예: "불량을 줄이는 조건 알려줘" 또는 "불량이 잘 나는 조건 알려줘"'
            ),
            intent="clarify",
        )

    def _explain(self, query: str, out: dict[str, Any]) -> str:
        """입력 조건과 실제 예측값을 LLM에 제공하여 한국어 해설을 생성한다."""
        # 해설용 수치만 소수점 네 자리로 반올림하며 원본 예측값은 수정하지 않는다.
        # [추가] LLM 클라이언트 없이 생성된 경우(테스트 주입) 수치 답변으로 대체한다.
        if self._llm is None:
            return "예측 결함률: " + ", ".join(f"{p:.2f}%" for p in out["predictions"])
        context = {
            "user_query": query,
            "model_input": out["payload"]["data"],
            "predicted_defect_rate_pct": [round(p, 4) for p in out["predictions"]],
            "unit": "percent",
        }
        try:
            return self._llm.chat(
                [
                    {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
                ]
            ).strip()
        except LLMError as e:
            # 예측 자체는 성공했으므로 해설 오류가 발생해도 수치 결과는 반환한다.
            logger.warning("해설 생성 실패(%s) -> 수치만 반환", e)
            return "예측 결함률: " + ", ".join(f"{p:.2f}%" for p in out["predictions"])
