"""
tools/schemas.py
OpenAI Tool Calling JSON Schema 정의.

각 스크립트는 여기서 미리 묶인 그룹을 import해 사용합니다:
  TOOLS_BASIC  → 01_tool_calling/basic.py
  TOOLS_ML     → 01_tool_calling/with_ml_api.py
  TOOLS_AGENT  → 03_agent/react_agent.py
  (MCP 서버는 @mcp.tool() 데코레이터가 스키마를 자동 생성해 여기 사용하지 않음)
"""
from __future__ import annotations

# ── 개별 스키마 ────────────────────────────────────────────────────

SCHEMA_GET_SHIFT_STATS: dict = {
    "type": "function",
    "function": {
        "name": "get_shift_stats",
        "description": (
            "특정 교대조와 생산 라인의 과거 평균 결함률, 평균 생산량, "
            "데이터 샘플 수를 조회합니다. 현재 상태 비교나 기준선 파악에 사용합니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "shift": {
                    "type": "string",
                    "enum": ["DAY", "NIGHT"],
                    "description": "교대조. DAY=주간조, NIGHT=야간조",
                },
                "production_line": {
                    "type": "string",
                    "enum": ["LINE-BPR-01", "LINE-BPR-02"],
                    "description": "생산 라인 코드",
                },
            },
            "required": ["shift", "production_line"],
        },
    },
}

SCHEMA_CREATE_ALERT: dict = {
    "type": "function",
    "function": {
        "name": "create_alert",
        "description": (
            "결함률이 임계치를 초과하거나 이상 상태를 감지했을 때 "
            "담당자에게 알림을 발송합니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "알림 본문 메시지",
                },
                "severity": {
                    "type": "string",
                    "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                    "description": "심각도. LOW < MEDIUM < HIGH < CRITICAL",
                },
            },
            "required": ["message", "severity"],
        },
    },
}

SCHEMA_CREATE_QUALITY_ALERT: dict = {
    "type": "function",
    "function": {
        "name": "create_alert",
        "description": "결함률 이상을 담당자에게 알립니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "message":         {"type": "string"},
                "severity":        {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
                "production_line": {"type": "string", "description": "대상 생산 라인 코드"},
            },
            "required": ["message", "severity", "production_line"],
        },
    },
}

SCHEMA_PREDICT_DEFECT_RATE: dict = {
    "type": "function",
    "function": {
        "name": "predict_defect_rate",
        "description": (
            "GBT(Gradient Boosted Trees) 모델로 공정 결함률(%)을 예측합니다. "
            "사용자 발화에서 12개 공정 파라미터를 추출하여 호출합니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "production_line": {
                    "type": "string",
                    "enum": ["LINE-BPR-01", "LINE-BPR-02"],
                    "description": "생산 라인 코드. '1라인'→LINE-BPR-01, '2라인'→LINE-BPR-02",
                },
                "shift": {
                    "type": "string",
                    "enum": ["DAY", "NIGHT"],
                    "description": "교대조. 주간·오전·낮→DAY / 야간·밤·야간조→NIGHT",
                },
                "supplier_code": {
                    "type": "string",
                    "enum": ["SIM-SUP-A", "SIM-SUP-B", "SIM-SUP-C"],
                    "description": "공급업체 코드. A공급사→SIM-SUP-A, B→SIM-SUP-B, C→SIM-SUP-C",
                },
                "planned_quantity": {
                    "type": "integer",
                    "description": "계획 생산 수량 (개). 0 이상.",
                },
                "ambient_humidity_pct": {
                    "type": "number",
                    "description": "작업장 습도 (%). 0~100 범위.",
                },
                "incoming_material_quality_score": {
                    "type": "number",
                    "description": "입고 자재 품질 점수. 0~100 범위.",
                },
                "coating_target_thickness_um": {
                    "type": "number",
                    "description": "코팅 목표 두께 (마이크로미터, um). 0 이상.",
                },
                "weld_energy_setting_pct": {
                    "type": "number",
                    "description": "용접 에너지 설정값 (%). 0~150 범위.",
                },
                "fixture_alignment_offset_mm": {
                    "type": "number",
                    "description": "지그 정렬 오프셋 (mm). 0 이상.",
                },
                "process_setting_deviation_pct": {
                    "type": "number",
                    "description": "공정 설정 편차 (%). 음수 허용.",
                },
                "tool_wear_pct": {
                    "type": "number",
                    "description": "공구 마모도 (%). 0~100 범위.",
                },
                "days_since_maintenance": {
                    "type": "integer",
                    "description": "마지막 정비 이후 경과 일수. 0 이상.",
                },
            },
            "required": [
                "production_line", "shift", "supplier_code",
                "planned_quantity", "ambient_humidity_pct",
                "incoming_material_quality_score", "coating_target_thickness_um",
                "weld_energy_setting_pct", "fixture_alignment_offset_mm",
                "process_setting_deviation_pct", "tool_wear_pct",
                "days_since_maintenance",
            ],
        },
    },
}


# ── 용도별 그룹 ────────────────────────────────────────────────────

# 01_tool_calling/basic.py : 통계 조회 + 알림 (ML 없음)
TOOLS_BASIC: list[dict] = [SCHEMA_GET_SHIFT_STATS, SCHEMA_CREATE_ALERT]

# 01_tool_calling/with_ml_api.py : ML 예측만
TOOLS_ML: list[dict] = [SCHEMA_PREDICT_DEFECT_RATE]

# 03_agent/react_agent.py : 통계 + ML 예측 + 알림 (라인 포함)
TOOLS_AGENT: list[dict] = [SCHEMA_GET_SHIFT_STATS, SCHEMA_PREDICT_DEFECT_RATE, SCHEMA_CREATE_QUALITY_ALERT]
