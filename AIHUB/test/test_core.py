"""스키마·세션·ML 응답 파싱. LLM/HTTP 호출 없음."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aihub.ml import DefectRateMLClient, MLEndpointError
from aihub.pipeline import SlotFillingSession, build_question
from aihub.schema import ALL_FIELDS, DefectRateInput, build_payload

# 정상 범위의 12개 입력값. 문자열은 대문자 정규화를 확인하기 위해 소문자로 둔다.
SAMPLE = {
    "production_line": "line-bpr-01",
    "shift": "day",
    "supplier_code": "sim-sup-b",
    "planned_quantity": 533,
    "ambient_humidity_pct": 54.49,
    "incoming_material_quality_score": 83.95,
    "coating_target_thickness_um": 79.22,
    "weld_energy_setting_pct": 92.67,
    "fixture_alignment_offset_mm": 0.112,
    "process_setting_deviation_pct": 13.06,
    "tool_wear_pct": 14.41,
    "days_since_maintenance": 30,
}

# 예측 API 응답 형식의 고정 샘플로, 입력 에코와 퍼센트 단위 예측값을 포함한다.
# 실제 HTTP 요청 없이 parse 메서드에 직접 전달한다.
REAL_RESPONSE = {
    "data": [{
        "production_line": "LINE-BPR-01", "shift": "DAY", "supplier_code": "SIM-SUP-B",
        "planned_quantity": 533.0, "ambient_humidity_pct": 54.49,
        "incoming_material_quality_score": 83.95, "coating_target_thickness_um": 79.22,
        "weld_energy_setting_pct": 92.67, "fixture_alignment_offset_mm": 0.112,
        "process_setting_deviation_pct": 13.06, "tool_wear_pct": 14.41,
        "days_since_maintenance": 30.0,
        "prediction(defect_rate_pct)": 1.649867890802181,
    }]
}


def _partial(**overrides):
    """일부 필드만 언급된 추출 결과를 만들고 나머지는 None으로 채운다."""
    row = {f: None for f in ALL_FIELDS}
    row.update(overrides)
    return row


def test_normalize_payload_and_reject_out_of_range():
    """문자열 정규화, 요청 본문 구조, 허용 범위 초과값 거부를 검증한다."""
    rec = DefectRateInput(**SAMPLE)
    assert rec.production_line == "LINE-BPR-01"
    assert rec.shift == "DAY"
    # 최상위 키가 data 하나이고 단일 레코드에 12개 입력 컬럼이 있는지 확인한다.
    payload = build_payload([rec])
    assert list(payload) == ["data"]
    assert len(payload["data"][0]) == 12

    # 공구 마모도의 상한인 100을 초과하면 Pydantic 검증 오류가 발생해야 한다.
    with pytest.raises(ValidationError):
        DefectRateInput(**{**SAMPLE, "tool_wear_pct": 140})


def test_slot_filling_what_if_and_correction():
    """단계별 슬롯 수집, 조건 변경, 정정 및 비교 레코드의 공통값 보존을 검증한다."""
    s = SlotFillingSession()
    # 세션 자체는 대문자화를 하지 않으므로 정규화된 추출 결과를 가정한다.
    full = {k: v.upper() if isinstance(v, str) else v for k, v in SAMPLE.items()}
    # 첫 입력에서 세 필드를 제외하고 이후 두 번의 입력으로 완성한다.
    t1 = {k: v for k, v in full.items()
          if k not in ("shift", "supplier_code", "days_since_maintenance")}
    s.merge([_partial(**t1)])
    s.merge([_partial(shift="DAY", supplier_code="SIM-SUP-B")])
    merged = s.merge([_partial(days_since_maintenance=30)])
    assert merged[0] == full

    # 가정 조건을 바꾸면 해당 값은 갱신되고 기존 생산 라인은 유지되어야 한다.
    what_if = s.merge([_partial(tool_wear_pct=90.0)])
    assert what_if[0]["tool_wear_pct"] == 90.0
    assert what_if[0]["production_line"] == "LINE-BPR-01"

    # 이미 저장된 교대조도 새로 전달된 정정값으로 덮어쓸 수 있어야 한다.
    s.merge([_partial(shift="NIGHT")])
    assert s.slots["shift"] == "NIGHT"

    # 두 비교 조건에서 다른 생산 라인은 공통 슬롯에서 제외하고 같은 교대조는 저장한다.
    # [수정] 운영 라인이 LINE-BPR-01/02 2종으로 확정되어 비교 대상도 실제 존재하는 두 번째 라인으로 맞춘다.
    a = _partial(**full)
    b = _partial(**{**full, "production_line": "LINE-BPR-02"})
    cmp_session = SlotFillingSession()
    cmp_session.merge([a, b])
    assert "production_line" not in cmp_session.slots
    assert cmp_session.slots["shift"] == "DAY"


def test_question_template_and_repeated_ask():
    """누락 항목이 많을 때 입력 템플릿이 생성되고 반복 질문 횟수가 기록되는지 확인한다."""
    # 8개 필드가 누락된 경우 첫 질문에도 일괄 입력 템플릿이 포함되어야 한다.
    q = build_question(ALL_FIELDS[:8], repeated=0)
    assert "production_line=" in q
    s = SlotFillingSession()
    # 최초 누락 기록은 반복 0회, 같은 목록의 두 번째 기록은 반복 1회이다.
    s.track_missing(["shift"])
    s.track_missing(["shift"])
    assert s.repeated_asks == 1


def test_parse_real_ml_response():
    """고정 응답의 예측값 파싱·표시 형식과 입력 에코 누락 오류를 검증한다."""
    # 클라이언트의 parse만 호출하므로 실제 예측 엔드포인트에는 접속하지 않는다.
    sent = build_payload([DefectRateInput(**SAMPLE)])["data"]
    results = DefectRateMLClient().parse(REAL_RESPONSE, sent)
    # 부동소수점 값은 상대 허용오차로 비교하고, 표시는 소수점 두 자리인지 확인한다.
    assert results[0].defect_rate_pct == pytest.approx(1.6498678908, rel=1e-9)
    assert results[0].format() == "1.65%"

    # 입력 에코에서 공구 마모도만 제거한다. 엄격 에코 검사가 활성화된 설정을 전제로 한다.
    broken = {"data": [{k: v for k, v in REAL_RESPONSE["data"][0].items()
                        if k != "tool_wear_pct"}]}
    # 예외 타입뿐 아니라 오류 메시지에 누락된 컬럼명이 포함되는지도 확인한다.
    with pytest.raises(MLEndpointError, match="tool_wear_pct"):
        DefectRateMLClient().parse(broken, sent)


# [수정] 2026-10-22: v1 골든 셋(data/golden_set.json)이 data/v1/로 이동되어 경로가 깨져 있었다.
# v2(data/golden_set_v2.json)의 C01/I01로 교체하고, 실행 위치와 무관하게 이 파일 기준 절대 경로를 쓴다.
# ID 꼴이 "C01" 또는 "C01-..." 어느 쪽이어도 동작하도록 접두어(첫 "-" 앞)로 찾는다.
# [수정] 2026-10-26: 골든 v2가 data/v2/로 이동되어 경로가 다시 깨져 있었다. 경로만 변경, 로직 변경 없음.
GOLDEN_V2 = Path(__file__).resolve().parents[1] / "data" / "v2" / "golden_set_v2.json"


def test_golden_c01_and_i01():
    """골든 v2의 정상 요청 본문(C01)과 제약 위반 입력 거부(I01)를 검증한다."""
    golden = json.loads(GOLDEN_V2.read_text(encoding="utf-8"))
    cases = {c["id"].split("-")[0]: c for c in golden["cases"]}
    # C01의 기대 레코드로 요청을 만들며, 자연어를 LLM으로 추출하는 과정은 실행하지 않는다.
    c01 = cases["C01"]
    records = [DefectRateInput(**rec) for rec in c01["expected"]["records"]]
    assert build_payload(records) == c01["expected_payload"]
    # I01의 레코드는 입력 모델 생성 단계에서 거부되어야 한다.
    i01 = cases["I01"]
    with pytest.raises(ValidationError):
        [DefectRateInput(**rec) for rec in i01["expected"]["records"]]
