"""
tools/functions.py
실제 도구(Tool) 함수 구현.

ML HTTP 호출은 core/ml.py에 위임합니다.
여기서는 비즈니스 로직(데이터 조회, 알림 발송, 파라미터 조립)만 처리합니다.
"""
from __future__ import annotations

import time

from core.config import MOCK_ML, ML_URL
from core.ml import call_ml_api


# ── 과거 통계 (mock DB) ────────────────────────────────────────────

_MOCK_STATS: dict[tuple[str, str], dict] = {
    ("DAY",   "LINE-BPR-01"): {"avg_defect_pct": 1.82, "avg_quantity": 523, "sample_count": 180},
    ("DAY",   "LINE-BPR-02"): {"avg_defect_pct": 2.14, "avg_quantity": 497, "sample_count": 162},
    ("NIGHT", "LINE-BPR-01"): {"avg_defect_pct": 2.45, "avg_quantity": 488, "sample_count": 174},
    ("NIGHT", "LINE-BPR-02"): {"avg_defect_pct": 2.91, "avg_quantity": 471, "sample_count": 158},
}

_SEVERITY_ICON = {"LOW": "ℹ️", "MEDIUM": "⚠️", "HIGH": "🔶", "CRITICAL": "🚨"}


def get_shift_stats(shift: str, production_line: str) -> dict:
    """교대조·라인별 과거 6개월 평균 통계를 반환합니다."""
    key = (shift.upper(), production_line.upper())
    if key not in _MOCK_STATS:
        return {"error": f"데이터 없음: shift={shift}, line={production_line}"}
    return {
        "shift": shift,
        "production_line": production_line,
        **_MOCK_STATS[key],
        "unit": "percent",
    }


def create_alert(message: str, severity: str, production_line: str = "") -> dict:
    """
    이상 알림을 담당자에게 발송합니다 (mock: 콘솔 출력).

    Args:
        message: 알림 본문
        severity: LOW | MEDIUM | HIGH | CRITICAL
        production_line: 대상 생산 라인 (선택)

    Returns:
        status, alert_id, severity, recipients
    """
    icon = _SEVERITY_ICON.get(severity, "📢")
    line_info = f" [{production_line}]" if production_line else ""
    print(f"\n{icon}  [{severity}]{line_info} 알림 발송됨: {message}")

    return {
        "status":      "sent",
        "alert_id":    f"ALERT-{int(time.time())}",
        "severity":    severity,
        "recipients":  ["quality@factory.com"],
        **({"production_line": production_line} if production_line else {}),
    }


def predict_defect_rate(
    production_line: str,
    shift: str,
    supplier_code: str,
    planned_quantity: int,
    ambient_humidity_pct: float,
    incoming_material_quality_score: float,
    coating_target_thickness_um: float,
    weld_energy_setting_pct: float,
    fixture_alignment_offset_mm: float,
    process_setting_deviation_pct: float,
    tool_wear_pct: float,
    days_since_maintenance: int,
) -> dict:
    """
    12개 공정 파라미터를 AI Hub GBT 모델에 전송해 결함률(%)을 예측합니다.

    HTTP 호출 / mock 처리는 core.ml.call_ml_api에 위임합니다.
    """
    row = {
        "production_line":                production_line,
        "shift":                          shift,
        "supplier_code":                  supplier_code,
        "planned_quantity":               planned_quantity,
        "ambient_humidity_pct":           ambient_humidity_pct,
        "incoming_material_quality_score": incoming_material_quality_score,
        "coating_target_thickness_um":    coating_target_thickness_um,
        "weld_energy_setting_pct":        weld_energy_setting_pct,
        "fixture_alignment_offset_mm":    fixture_alignment_offset_mm,
        "process_setting_deviation_pct":  process_setting_deviation_pct,
        "tool_wear_pct":                  tool_wear_pct,
        "days_since_maintenance":         days_since_maintenance,
    }

    print(f"\n📡 ML API 호출 중... (MOCK={MOCK_ML or not ML_URL})")
    defect_pct = call_ml_api(row)

    return {
        "mode":                     "mock" if (MOCK_ML or not ML_URL) else "real",
        "prediction_defect_rate_pct": defect_pct,
    }
