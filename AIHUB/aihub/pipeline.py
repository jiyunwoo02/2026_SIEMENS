from __future__ import annotations

import json
import logging
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
from .schema import ALL_FIELDS, FIELD_SPEC, NUMERIC_FIELDS, DefectRateInput, extraction_json_schema

logger = logging.getLogger(__name__)

# API와 CLI에 전달할 처리 결과: 성공, 추가 입력 필요, 입력 오류, 외부 서비스 오류.
Status = Literal["ok", "need_more_info", "invalid_input", "endpoint_error", "llm_error"]


@dataclass
class ExtractionResult:
    """LLM에서 추출한 조건별 레코드와 부가 설명을 보관한다."""

    records: list[dict[str, Any]] = field(default_factory=list)
    notes: str | None = None


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
        return ExtractionResult(
            records=[self._coerce(r) for r in (raw.get("records") or [])],
            notes=raw.get("notes"),
        )

    @staticmethod
    def _coerce(item: dict[str, Any]) -> dict[str, Any]:
        """필드 타입을 맞추고 누락값이나 변환할 수 없는 값을 None으로 처리한다."""
        # 허용 범위 검증은 이후 DefectRateInput 생성 단계에서 수행한다.
        out: dict[str, Any] = {}
        for f in ALL_FIELDS:
            v = item.get(f)
            if v is None or (isinstance(v, str) and not v.strip()):
                out[f] = None
                continue
            expected = FIELD_SPEC[f]["type"]
            try:
                # 정수 필드는 실수 변환 후 반올림하고, 문자열은 공백 제거·대문자화한다.
                if expected == "integer":
                    out[f] = int(round(float(v)))
                elif expected == "number":
                    out[f] = float(v)
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
    missing: list[str], *, repeated: int = 0, known: dict[str, Any] | None = None
) -> str:
    """누락 필드의 설명과 확인된 값을 이용해 추가 입력 안내문을 만든다."""
    known = known or {}
    lines = [f"- **{f}** — {FIELD_SPEC[f]['desc']}" for f in missing]
    head = (
        f"예측에 필요한 값 {len(missing)}개가 아직 없습니다. 아래 항목을 알려주세요.\n"
        if len(missing) < len(ALL_FIELDS)
        else "결함률 예측을 위해 아래 12개 값이 모두 필요합니다.\n"
    )
    body = head + "\n".join(lines)
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


@dataclass
class PipelineResult:
    """성공과 오류 모두에 사용하는 공통 응답 구조."""

    status: Status
    answer: str
    predictions: list[float] = field(default_factory=list)
    unit: str = "percent"
    model_input: list[dict[str, Any]] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    known_slots: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    # ML 클라이언트가 보고한 호출 시간으로, LLM 처리 등 전체 실행 시간은 아니다.
    latency_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        """API 및 CLI에서 출력할 수 있도록 데이터클래스를 딕셔너리로 변환한다."""
        return asdict(self)


class DefectRatePipeline:
    """질의 추출 → 슬롯 병합 → 입력 검증 → ML 예측 → 결과 설명을 조율한다."""

    def __init__(self) -> None:
        # 필수 설정을 확인하고 추출과 해설 생성에 사용할 LLM 클라이언트를 공유한다.
        s = get_settings()
        s.validate_runtime()
        self._llm = SDCLLMClient(s)
        self._extractor = QueryExtractor(client=self._llm)
        self._ml = DefectRateMLClient()

    def run(
        self,
        query: str,
        *,
        session: SlotFillingSession | None = None,
        explain: bool = True,
    ) -> PipelineResult:
        """한 번의 발화를 처리하고 현재 단계에 맞는 결과를 반환한다."""
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

        # 모든 비교 조건 중 하나라도 값이 없으면 해당 필드를 추가 질문 대상으로 삼는다.
        merged = session.merge(extraction.records)
        missing = sorted(
            {f for row in merged for f in ALL_FIELDS if row.get(f) is None},
            key=ALL_FIELDS.index,
        )
        # 필수값이 모이기 전에는 ML API를 호출하지 않는다.
        if missing:
            session.track_missing(missing)
            return PipelineResult(
                status="need_more_info",
                answer=build_question(
                    missing, repeated=session.repeated_asks, known=session.known()
                ),
                missing_fields=missing,
                known_slots=session.known(),
                model_input=merged,
            )
        session.track_missing([])

        # 타입 정규화 이후 실제 모델의 수치 범위와 코드 제약을 검증한다.
        try:
            records = [DefectRateInput(**{f: row[f] for f in ALL_FIELDS}) for row in merged]
        except ValidationError as e:
            reasons = [
                f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()
            ]
            # 검증 오류에 나온 필드를 세션에서 제거하여 다음 발화에서 정정할 수 있게 한다.
            for err in e.errors():
                if err["loc"]:
                    session.slots.pop(str(err["loc"][0]), None)
            return PipelineResult(
                status="invalid_input",
                answer="입력값이 모델 허용 범위를 벗어났습니다. 다시 알려주세요.\n- "
                + "\n- ".join(reasons),
                errors=reasons,
                known_slots=session.known(),
            )

        # 검증을 통과한 레코드만 예측 클라이언트에 전달한다.
        try:
            out = self._ml.predict(records)
        except MLEndpointError as e:
            return PipelineResult(
                status="endpoint_error",
                answer=f"예측 API 호출에 실패했습니다. 엔드포인트 상태를 확인해주세요.\n{e}",
                model_input=[r.to_row() for r in records],
                errors=[str(e)],
                known_slots=session.known(),
            )

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
        )

    def _explain(self, query: str, out: dict[str, Any]) -> str:
        """입력 조건과 실제 예측값을 LLM에 제공하여 한국어 해설을 생성한다."""
        # 해설용 수치만 소수점 네 자리로 반올림하며 원본 예측값은 수정하지 않는다.
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
