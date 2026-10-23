"""골든 셋 v2 기반 추출 이후 단계(병합·검증·상태 판정) 테스트. LLM/HTTP 호출 없음.

역할:
    - 골든 셋 데이터 자체가 conventions(누락·모호·N05 규칙)를 지키는지 확인한다.
    - LLM 추출 결과를 골든 기대 records로 대체(FakeExtractor)해 파이프라인의
      status / missing_fields / ambiguous_fields / invalid_fields / payload 판정을 검증한다.
    - QueryExtractor의 후처리(모호 필드 null 강제, 숫자 반올림, 비정상 값 처리)를 검증한다.
한계:
    - 실제 LLM이 질의에서 골든 기대값대로 추출하는지는 검증하지 않는다(별도 평가 필요).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from aihub.llm import EXTRACTION_SYSTEM_PROMPT
from aihub.pipeline import (
    DefectRatePipeline,
    ExtractionResult,
    QueryExtractor,
    SlotFillingSession,
)
from aihub.schema import ALL_FIELDS, DefectRateInput, build_payload, extraction_json_schema

GOLDEN_V2 = Path(__file__).resolve().parents[1] / "data" / "golden_set_v2.json"
GOLDEN = json.loads(GOLDEN_V2.read_text(encoding="utf-8"))
CASES: list[dict[str, Any]] = GOLDEN["cases"]
MULTI_TURN: list[dict[str, Any]] = GOLDEN.get("multi_turn_cases", [])
# 실측 회귀 기준값(docs/architecture.md 7.2)
KNOWN_PREDICTION_PCT = 1.6498678908


def _prefix(case_id: str) -> str:
    """C01 또는 C01-설명 형태의 ID에서 접두어를 반환한다."""
    return case_id.split("-")[0]


def _case(prefix: str) -> dict[str, Any]:
    """접두어로 골든 케이스를 찾는다."""
    return next(c for c in CASES if _prefix(c["id"]) == prefix)


def _invalid_fields_of(case: dict[str, Any]) -> list[str]:
    """invalid_field가 문자열이든 목록이든 목록으로 반환한다."""
    v = case.get("invalid_field") or []
    return [v] if isinstance(v, str) else list(v)


# ---------------------------------------------------------------------------
# 테스트 대역
# ---------------------------------------------------------------------------
class FakeExtractor:
    """extract 호출 시 미리 지정한 ExtractionResult를 돌려준다."""

    def __init__(self, result: ExtractionResult) -> None:
        self.result = result
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def extract(self, query: str, known: dict[str, Any] | None = None) -> ExtractionResult:
        self.calls.append((query, known))
        return copy.deepcopy(self.result)


class FakeML:
    """DefectRateMLClient.predict와 같은 형태로 결과를 돌려주고 호출 여부를 기록한다."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def predict(self, records: list[DefectRateInput]) -> dict[str, Any]:
        payload = build_payload(records)
        self.calls.append(payload)
        preds = [KNOWN_PREDICTION_PCT + i for i in range(len(records))]
        return {"payload": payload, "predictions": preds, "unit": "percent", "latency_ms": 0}


class FakeLLMClient:
    """QueryExtractor용 chat_json 대역."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw

    def chat_json(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return copy.deepcopy(self.raw)


def _pipeline(extraction: ExtractionResult) -> tuple[DefectRatePipeline, FakeML]:
    """설정·외부 호출 없이 동작하는 파이프라인을 만든다."""
    ml = FakeML()
    return DefectRatePipeline(extractor=FakeExtractor(extraction), ml_client=ml), ml


def _from_expected(case: dict[str, Any]) -> ExtractionResult:
    """골든 기대값을 LLM 추출 결과로 간주한다."""
    e = case["expected"]
    return ExtractionResult(
        records=copy.deepcopy(e["records"]),
        ambiguous_fields=list(e.get("ambiguous_fields") or []),
    )


# ---------------------------------------------------------------------------
# 1) 골든 데이터 자체의 일관성 (conventions)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_golden_case_follows_conventions(case):
    """누락·모호·invalid·N05 규칙이 골든 기대값에 일관되게 반영됐는지 확인한다."""
    e = case["expected"]
    records, missing = e["records"], e["missing_fields"]
    ambiguous = e.get("ambiguous_fields") or []
    assert len(missing) == len(set(missing)), "missing_fields 중복"
    assert set(missing) <= set(ALL_FIELDS)
    assert set(ambiguous) <= set(missing), "ambiguous_fields ⊄ missing_fields"
    for rec in records:
        assert set(rec) == set(ALL_FIELDS), "레코드는 12개 키를 모두 가져야 함"

    if e["status"] == "invalid_input":
        assert missing == []
        assert _invalid_fields_of(case), "invalid 케이스는 invalid_field가 필요"
    elif not records:
        # N05: 예측 요청이 아니면 records=[]이고 12개 전체가 누락
        assert e["status"] == "need_more_info"
        assert set(missing) == set(ALL_FIELDS)
    else:
        nulls = {f for rec in records for f in ALL_FIELDS if rec[f] is None}
        assert set(missing) == nulls
        assert (e["status"] == "ok") == (not missing)

    if e["status"] == "ok":
        assert case.get("expected_payload") == {"data": records}


def test_golden_n05_is_the_only_empty_records_case():
    """records=[]인 케이스는 범위 밖 질의(N05)뿐이어야 한다(N04는 전 필드 null 레코드)."""
    empty = [_prefix(c["id"]) for c in CASES if not c["expected"]["records"]]
    assert empty == ["N05"]
    n04 = _case("N04")["expected"]["records"]
    assert len(n04) == 1 and all(v is None for v in n04[0].values())


# ---------------------------------------------------------------------------
# 2) 파이프라인 판정 (추출 결과 = 골든 기대값)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_pipeline_status_matches_golden(case):
    """추출이 정확하다는 전제에서 status·누락·모호·위반 필드·payload가 골든과 일치해야 한다."""
    e = case["expected"]
    pipe, ml = _pipeline(_from_expected(case))
    res = pipe.run(case["query"], session=SlotFillingSession(), explain=False)

    assert res.status == e["status"]
    assert set(res.missing_fields) == set(e["missing_fields"])
    assert set(res.ambiguous_fields) == set(e.get("ambiguous_fields") or [])
    assert set(res.ambiguous_fields) <= set(res.missing_fields)

    if e["status"] == "ok":
        assert ml.calls == [case["expected_payload"]]
        assert len(res.predictions) == len(e["records"])
    else:
        # 누락·모호·위반이면 ML API를 호출하지 않는다.
        assert ml.calls == []
    if e["status"] == "invalid_input":
        assert set(_invalid_fields_of(case)) <= set(res.invalid_fields)
    if not e["records"]:
        assert res.model_input == []


def test_n05_does_not_advance_turn_but_known_session_still_merges():
    """N05(빈 세션)는 turn을 늘리지 않고, 확인값이 있는 세션의 records=[]는 병합 경로로 예측한다."""
    pipe, ml = _pipeline(ExtractionResult(records=[]))
    s = SlotFillingSession()
    res = pipe.run("이 모델은 어떤 알고리즘으로 학습됐나요?", session=s, explain=False)
    assert res.status == "need_more_info"
    assert s.turn == 0
    assert "공정 조건을 찾지 못했습니다" in res.answer

    # 이미 12개 값이 모두 있는 세션에서 "그대로 다시 예측"처럼 새 값이 없는 발화
    full = _case("C01")["expected"]["records"][0]
    s2 = SlotFillingSession(slots=dict(full))
    res2 = pipe.run("그대로 다시 예측해줘", session=s2, explain=False)
    assert res2.status == "ok"
    assert ml.calls == [{"data": [full]}]


def test_invalid_code_removed_from_session_for_correction():
    """허용값 밖 코드는 invalid_input이 되고, 정정할 수 있도록 세션에서 제거된다."""
    rec = dict(_case("C01")["expected"]["records"][0], production_line="LINE-BPR-03")
    pipe, ml = _pipeline(ExtractionResult(records=[rec]))
    s = SlotFillingSession()
    res = pipe.run("LINE-BPR-03 ...", session=s, explain=False)
    assert res.status == "invalid_input"
    assert res.invalid_fields == ["production_line"]
    assert "production_line" not in s.slots
    assert "허용값" in res.answer
    assert ml.calls == []


def test_ambiguous_field_already_known_is_not_reported():
    """세션에 이미 값이 있는 필드는 병합 후 null이 아니므로 ambiguous_fields에서 빠진다."""
    full = _case("C01")["expected"]["records"][0]
    known = {k: v for k, v in full.items() if k != "tool_wear_pct"}
    rec = {f: None for f in ALL_FIELDS}
    pipe, _ = _pipeline(
        ExtractionResult(records=[rec], ambiguous_fields=["ambient_humidity_pct", "tool_wear_pct"])
    )
    res = pipe.run("습도는 좀 높고 공구도 꽤 닳았어요", session=SlotFillingSession(slots=known), explain=False)
    assert res.status == "need_more_info"
    assert res.missing_fields == ["tool_wear_pct"]
    assert res.ambiguous_fields == ["tool_wear_pct"]
    assert "모호" in res.answer


# ---------------------------------------------------------------------------
# 3) 멀티턴 기대 payload
# ---------------------------------------------------------------------------
MT_PAYLOAD_TURNS = [
    (m["id"], i, t)
    for m in MULTI_TURN
    for i, t in enumerate(m["turns"], start=1)
    if t.get("expected_payload")
]


@pytest.mark.parametrize("mt_id, turn_no, turn", MT_PAYLOAD_TURNS,
                         ids=[f"{m}-t{i}" for m, i, _ in MT_PAYLOAD_TURNS])
def test_multi_turn_expected_payload_is_valid(mt_id, turn_no, turn):
    """멀티턴의 기대 payload는 입력 검증을 통과하고, 실측값이 붙은 턴은 C01과 같은 payload여야 한다."""
    rows = turn["expected_payload"]["data"]
    assert build_payload([DefectRateInput(**r) for r in rows]) == turn["expected_payload"]
    if "known_prediction_pct" in turn:
        assert turn["known_prediction_pct"] == pytest.approx(KNOWN_PREDICTION_PCT)
        assert turn["expected_payload"] == _case("C01")["expected_payload"]


# ---------------------------------------------------------------------------
# 4) QueryExtractor 후처리 · 스키마 · 프롬프트
# ---------------------------------------------------------------------------
def test_extractor_nulls_ambiguous_and_filters_unknown_names():
    """모호 표시된 필드는 값이 있어도 null이 되고, 알 수 없는 필드명은 버린다."""
    raw = {
        "records": [{"ambient_humidity_pct": 55.0, "shift": "day", "tool_wear_pct": 40}],
        "ambiguous_fields": ["ambient_humidity_pct", "not_a_field", 3],
        "notes": None,
    }
    out = QueryExtractor(client=FakeLLMClient(raw)).extract("q")
    assert out.ambiguous_fields == ["ambient_humidity_pct"]
    assert out.records[0]["ambient_humidity_pct"] is None
    assert out.records[0]["shift"] == "DAY"
    assert out.records[0]["tool_wear_pct"] == 40.0


def test_extractor_handles_missing_ambiguous_key():
    """json_object/prompt 폴백 응답에 ambiguous_fields 키가 없어도 동작한다."""
    out = QueryExtractor(client=FakeLLMClient({"records": []})).extract("q")
    assert out.records == [] and out.ambiguous_fields == []


@pytest.mark.parametrize("raw_value, expected", [
    (0.0984 * 1000, 98.4),          # mm→um 환산 오차 제거
    (79.22, 79.22),
    (True, None),                   # bool은 수치로 보지 않음
    (float("nan"), None),
    (float("inf"), None),
    ("abc", None),
])
def test_coerce_numeric(raw_value, expected):
    """수치 필드 정규화: 6자리 반올림, bool/NaN/inf/변환 불가 값은 None."""
    out = QueryExtractor._coerce({"coating_target_thickness_um": raw_value})
    assert out["coating_target_thickness_um"] == expected


def test_coerce_keeps_out_of_whitelist_code_for_validation():
    """허용값 밖 코드는 대문자화만 하고 그대로 둬서 검증 단계에서 차단되게 한다."""
    out = QueryExtractor._coerce({"production_line": " line-bpr-03 "})
    assert out["production_line"] == "LINE-BPR-03"
    with pytest.raises(ValidationError):
        DefectRateInput(**{**_case("C01")["expected"]["records"][0], **{"production_line": "LINE-BPR-03"}})


def test_extraction_schema_has_ambiguous_fields():
    """strict 스키마는 모든 최상위 속성을 required로 두고 ambiguous_fields를 필드명 enum으로 제한한다."""
    schema = extraction_json_schema()
    assert set(schema["required"]) == set(schema["properties"]) == {"records", "ambiguous_fields", "notes"}
    assert schema["properties"]["ambiguous_fields"]["items"]["enum"] == ALL_FIELDS


@pytest.mark.parametrize("keyword", [
    "ambiguous_fields", "오후조", "LINE-BPR-03", "마이크로미터", "범위", "번복", "모든 필드가 null인 레코드",
])
def test_extraction_prompt_mentions_rules(keyword):
    """추출 프롬프트에 갱신된 규칙의 핵심 키워드가 포함돼 있는지 확인한다(회귀 방지용)."""
    assert keyword in EXTRACTION_SYSTEM_PROMPT
