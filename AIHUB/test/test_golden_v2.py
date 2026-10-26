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

from aihub.llm import EXTRACTION_SYSTEM_PROMPT, build_extraction_user_content
from aihub.pipeline import (
    DefectRatePipeline,
    ExtractionResult,
    QueryExtractor,
    SlotFillingSession,
)
from aihub.schema import ALL_FIELDS, DefectRateInput, build_payload, extraction_json_schema

# [수정] 2026-10-26: 골든 v2가 data/v2/로 이동되어 경로가 깨져 있었다(수집 단계 FileNotFoundError). 경로만 변경, 로직 변경 없음.
GOLDEN_V2 = Path(__file__).resolve().parents[1] / "data" / "v2" / "golden_set_v2.json"
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


def test_out_of_whitelist_code_is_not_stored_while_slots_incomplete():
    """[추가] 2026-10-23: 슬롯이 덜 찬 상태에서도 SIM-SUP-D는 invalid_input이어야 하고 세션에 저장되면 안 된다.

    같은 발화의 유효한 값(라인, 교대조)은 유지된다.
    """
    rec = {f: None for f in ALL_FIELDS}
    rec.update(production_line="LINE-BPR-01", shift="DAY", supplier_code="SIM-SUP-D")
    pipe, ml = _pipeline(ExtractionResult(records=[rec]))
    s = SlotFillingSession()
    res = pipe.run("LINE-BPR-01, 주간, SIM-SUP-D", session=s, explain=False)
    assert res.status == "invalid_input"
    assert res.invalid_fields == ["supplier_code"]
    assert res.missing_fields == []
    assert "supplier_code" not in s.slots
    assert s.slots == {"production_line": "LINE-BPR-01", "shift": "DAY"}
    assert ml.calls == []


def test_partial_valid_values_still_need_more_info():
    """[추가] 사전 검증이 유효한 부분 입력을 막지 않는다(회귀 방지)."""
    rec = {f: None for f in ALL_FIELDS}
    rec.update(production_line="LINE-BPR-01", shift="DAY", supplier_code="SIM-SUP-A")
    pipe, _ = _pipeline(ExtractionResult(records=[rec]))
    res = pipe.run("LINE-BPR-01, 주간, SIM-SUP-A", session=SlotFillingSession(), explain=False)
    assert res.status == "need_more_info"
    assert "planned_quantity" in res.missing_fields


def test_bare_number_is_reported_via_notes_not_assigned():
    """[추가] 항목 불명 숫자('80')를 대화 응답에서 안내하고 planned_quantity는 비워둔다.

    추출 결과가 정해진 뒤의 파이프라인 동작만 검증한다. 실제 LLM이 규칙 2-1을 따르는지는 별도 평가가 필요하다.
    """
    rec = {f: None for f in ALL_FIELDS}
    rec.update(production_line="LINE-BPR-01", shift="DAY", supplier_code="SIM-SUP-A")
    note = "'80'이(가) 어떤 항목의 값인지 알 수 없어 반영하지 않았습니다."
    pipe, _ = _pipeline(ExtractionResult(records=[rec], notes=note))
    s = SlotFillingSession()
    res = pipe.run("LINE-BPR-01, 주간, SIM-SUP-A, 80", session=s, explain=False)
    assert res.status == "need_more_info"
    assert "planned_quantity" in res.missing_fields
    assert "planned_quantity" not in s.slots
    assert note in res.answer


def test_two_remaining_fields_text_and_number_are_both_accepted():
    """[추가] 2026-10-23: 남은 필드가 문자 1개(supplier_code)·숫자 1개(planned_quantity)뿐일 때,
    항목명 없이 입력한 "SIM-SUP-B, 480"이 각각 필드에 매칭되어 예측까지 진행되는지 확인한다.

    이 테스트는 추출 결과가 정해진 뒤의 파이프라인 동작만 검증한다. LLM이 규칙 2-1대로 매칭하는지는
    실제 LLM 평가(test/golden_llm_extract.py 또는 멀티턴 시나리오)가 필요하다.
    """
    full = _case("C01")["expected"]["records"][0]
    known = {k: v for k, v in full.items() if k not in ("supplier_code", "planned_quantity")}
    rec = {f: None for f in ALL_FIELDS}
    rec.update(supplier_code=full["supplier_code"], planned_quantity=full["planned_quantity"])
    pipe, ml = _pipeline(ExtractionResult(records=[rec]))
    res = pipe.run("SIM-SUP-B, 533", session=SlotFillingSession(slots=dict(known)), explain=False)
    assert res.status == "ok"
    assert ml.calls == [_case("C01")["expected_payload"]]


def test_extraction_user_content_lists_still_needed_fields():
    """[추가] 확인된 값이 있을 때 아직 필요한 값 목록이 요청에 포함되고, 비어 있으면 질의 원문만 전달한다."""
    full = _case("C01")["expected"]["records"][0]
    known = {k: v for k, v in full.items() if k not in ("supplier_code", "planned_quantity")}
    content = build_extraction_user_content("SIM-SUP-B, 533", known)
    needed_part = content.split("[아직 필요한 값]")[1].split("[이번 발화]")[0]
    assert "supplier_code" in needed_part and "planned_quantity" in needed_part
    assert "tool_wear_pct" not in needed_part  # 이미 확인된 필드는 목록에 없어야 한다.
    # 모든 값이 확인된 경우
    assert "없음" in build_extraction_user_content("그대로", dict(full)).split("[아직 필요한 값]")[1]
    # 확인된 값이 없으면 질의 원문 그대로(기존 동작 유지)
    assert build_extraction_user_content("안녕", {}) == "안녕"


def test_validate_provided_fields_reports_only_given_fields():
    """[추가] 필드 단위 검증은 전달된 필드의 위반만 보고하고 None은 건너뛴다."""
    from aihub.schema import validate_provided_fields

    assert validate_provided_fields({}) == {}
    assert validate_provided_fields({"supplier_code": None}) == {}
    assert validate_provided_fields({"supplier_code": "sim-sup-a"}) == {}
    assert set(validate_provided_fields({"supplier_code": "SIM-SUP-D", "tool_wear_pct": 140})) == {
        "supplier_code",
        "tool_wear_pct",
    }
    assert validate_provided_fields({"fixture_alignment_offset_mm": -0.1}).keys() == {
        "fixture_alignment_offset_mm"
    }


def test_ambiguous_field_already_known_is_cleared_and_reported():
    """[수정] 2026-10-26 (동작 변경): 세션에 이미 값이 있는 필드를 모호하게 정정하면
    슬롯이 비워지고 missing_fields·ambiguous_fields에 나타나야 한다(이전: 기존 값이 조용히 유지되어 목록에서 빠짐).

    습도(확인됨)와 공구 마모(미확인)를 모두 모호하게 말한 발화로, 두 필드가 모두 되묻기 대상이 되고
    나머지 확인값은 유지되며 ML은 호출되지 않는다.
    """
    full = _case("C01")["expected"]["records"][0]
    known = {k: v for k, v in full.items() if k != "tool_wear_pct"}
    rec = {f: None for f in ALL_FIELDS}
    pipe, ml = _pipeline(
        ExtractionResult(records=[rec], ambiguous_fields=["ambient_humidity_pct", "tool_wear_pct"])
    )
    s = SlotFillingSession(slots=known)
    res = pipe.run("습도는 좀 높고 공구도 꽤 닳았어요", session=s, explain=False)
    assert res.status == "need_more_info"
    # ALL_FIELDS 순서: ambient_humidity_pct가 tool_wear_pct보다 앞이다.
    assert res.missing_fields == ["ambient_humidity_pct", "tool_wear_pct"]
    assert res.ambiguous_fields == ["ambient_humidity_pct", "tool_wear_pct"]
    assert "ambient_humidity_pct" not in s.slots
    assert s.slots["production_line"] == full["production_line"]  # 다른 확인값은 유지
    assert "모호" in res.answer
    assert ml.calls == []


def test_vague_correction_of_confirmed_field_asks_again_instead_of_predicting():
    """[추가] 2026-10-26: 12개가 모두 확인된 뒤 "습도가 꽤 높아졌다면?"이 오면
    기존 습도(54.49)로 예측하지 않고 습도를 되묻는다. 이후 수치를 입력하면 예측이 진행된다.

    추출 결과는 대역이므로 실제 LLM이 프롬프트대로 ambiguous_fields를 내는지는 검증하지 않는다.
    """
    full = _case("C01")["expected"]["records"][0]
    s = SlotFillingSession(slots=dict(full))
    blank = {f: None for f in ALL_FIELDS}

    # 1턴: 모호한 정정 -> 재질문, 예측 미호출, 습도 슬롯 제거
    ml = FakeML()
    vague = DefectRatePipeline(
        extractor=FakeExtractor(ExtractionResult(records=[blank], ambiguous_fields=["ambient_humidity_pct"])),
        ml_client=ml,
    )
    res = vague.run("습도가 꽤 높아졌다면?", session=s, explain=False)
    assert res.status == "need_more_info"
    assert res.missing_fields == ["ambient_humidity_pct"]
    assert res.ambiguous_fields == ["ambient_humidity_pct"]
    assert "ambient_humidity_pct" not in s.known()
    assert ml.calls == []

    # 2턴: 수치 확정 -> 나머지는 이전 값 유지, 습도만 새 값으로 예측
    answer = dict(blank, ambient_humidity_pct=61.5)
    confirm = DefectRatePipeline(extractor=FakeExtractor(ExtractionResult(records=[answer])), ml_client=ml)
    res2 = confirm.run("61.5%입니다", session=s, explain=False)
    assert res2.status == "ok"
    assert ml.calls == [{"data": [dict(full, ambient_humidity_pct=61.5)]}]


def test_ambiguous_field_not_in_session_behaves_as_before():
    """[추가] 2026-10-26: 세션에 없던 필드의 모호 표시는 기존대로 누락+모호 처리되고 다른 슬롯은 유지된다(회귀 방지)."""
    full = _case("C01")["expected"]["records"][0]
    known = {k: v for k, v in full.items() if k != "tool_wear_pct"}
    pipe, _ = _pipeline(
        ExtractionResult(records=[{f: None for f in ALL_FIELDS}], ambiguous_fields=["tool_wear_pct"])
    )
    s = SlotFillingSession(slots=dict(known))
    res = pipe.run("공구가 꽤 닳았어요", session=s, explain=False)
    assert res.missing_fields == ["tool_wear_pct"]
    assert res.ambiguous_fields == ["tool_wear_pct"]
    assert s.known() == known


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
    # [추가] 2026-10-26: 확인된 필드를 모호하게 정정하는 경우의 지침 키워드
    "모호하게 바꾸려 하면", "증감량을 추정해",
    # [추가] 2026-10-23: 항목 표시 없는 숫자 규칙(2-1)의 핵심 키워드
    "항목 표시가 없는 숫자",
    # [추가] 2026-10-23: 단위 환산·남은 필드 매칭 규칙의 핵심 키워드
    "센티", "cm는 x10", "[아직 필요한 값]", "필드별 기준 단위",
])
def test_extraction_prompt_mentions_rules(keyword):
    """추출 프롬프트에 갱신된 규칙의 핵심 키워드가 포함돼 있는지 확인한다(회귀 방지용)."""
    assert keyword in EXTRACTION_SYSTEM_PROMPT
