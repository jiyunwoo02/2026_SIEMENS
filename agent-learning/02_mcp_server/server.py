"""
02_mcp_server/server.py
=======================
FastMCP를 사용한 MCP 서버 구현.

[제공하는 도구 (Tools)]
1. predict_defect_rate  : GBT ML 모델로 결함률(%) 예측
2. get_shift_stats      : 교대조·라인별 과거 통계 조회
3. create_quality_alert : 품질 알림 발송

[실행 방법]
  python server.py          → stdio 모드 (Claude Desktop 연결)
  python server.py --port 8000  → SSE HTTP 모드 (웹 클라이언트 연결)

[Claude Desktop 설정 (~/.config/claude/claude_desktop_config.json)]
  {
    "mcpServers": {
      "defect-predictor": {
        "command": "python",
        "args": ["/home/jywoo/side-project/agent-learning/02_mcp_server/server.py"],
        "env": {"API_KEY": "...", "ML_ENDPOINT_URL": "..."}
      }
    }
  }

[MCP vs 직접 Tool Calling의 차이]
  Tool Calling : 개발자가 각 LLM 앱마다 tools 배열을 직접 구성해야 함
  MCP          : 서버를 한 번 만들면 → Claude, Cursor 등 모든 MCP 클라이언트가 연결 가능
                 LLM 벤더 종속 없음, 도구 목록을 서버가 자동으로 광고(advertise)

[모듈 역할 분리]
  core/ml.py         → ML API HTTP 호출
  tools/functions.py → 실제 비즈니스 로직
  이 파일           → @mcp.tool() 래퍼로 MCP 프로토콜에 등록
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP

# 실제 구현은 tools/functions.py에서 가져옴
# MCP 서버는 얇은 래퍼(thin wrapper) 역할만 합니다.
from tools.functions import (
    create_alert,
    get_shift_stats as _get_shift_stats,
    predict_defect_rate as _predict_defect_rate,
)

mcp = FastMCP("defect-predictor-mcp")


# ══════════════════════════════════════════════════════════════════
# MCP Tool 1: ML 결함률 예측
#
# @mcp.tool() 데코레이터만 붙이면 함수 시그니처와 docstring이
# 자동으로 MCP Tool Schema로 변환됩니다.
# ══════════════════════════════════════════════════════════════════

@mcp.tool()
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
) -> dict[str, Any]:
    """
    GBT(Gradient Boosted Trees) 모델로 공정 결함률(%)을 예측합니다.

    Args:
        production_line: 생산 라인 코드 (LINE-BPR-01 또는 LINE-BPR-02)
        shift: 교대조 (DAY=주간, NIGHT=야간)
        supplier_code: 공급업체 코드 (SIM-SUP-A, SIM-SUP-B, SIM-SUP-C)
        planned_quantity: 계획 생산 수량 (개)
        ambient_humidity_pct: 작업장 습도 (%, 0~100)
        incoming_material_quality_score: 입고 자재 품질 점수 (0~100)
        coating_target_thickness_um: 코팅 목표 두께 (마이크로미터)
        weld_energy_setting_pct: 용접 에너지 설정값 (%, 0~150)
        fixture_alignment_offset_mm: 지그 정렬 오프셋 (mm, 0 이상)
        process_setting_deviation_pct: 공정 설정 편차 (%, 음수 허용)
        tool_wear_pct: 공구 마모도 (%, 0~100)
        days_since_maintenance: 마지막 정비 이후 경과 일수

    Returns:
        prediction_defect_rate_pct (float): 예측 결함률 (%)
        mode: "real" | "mock"
    """
    return _predict_defect_rate(
        production_line=production_line,
        shift=shift,
        supplier_code=supplier_code,
        planned_quantity=planned_quantity,
        ambient_humidity_pct=ambient_humidity_pct,
        incoming_material_quality_score=incoming_material_quality_score,
        coating_target_thickness_um=coating_target_thickness_um,
        weld_energy_setting_pct=weld_energy_setting_pct,
        fixture_alignment_offset_mm=fixture_alignment_offset_mm,
        process_setting_deviation_pct=process_setting_deviation_pct,
        tool_wear_pct=tool_wear_pct,
        days_since_maintenance=days_since_maintenance,
    )


# ══════════════════════════════════════════════════════════════════
# MCP Tool 2: 과거 통계 조회
# ══════════════════════════════════════════════════════════════════

@mcp.tool()
def get_shift_stats(shift: str, production_line: str) -> dict[str, Any]:
    """
    특정 교대조와 생산 라인의 과거 6개월 평균 결함률과 생산량을 조회합니다.

    Args:
        shift: 교대조 (DAY 또는 NIGHT)
        production_line: 생산 라인 코드 (LINE-BPR-01 또는 LINE-BPR-02)

    Returns:
        avg_defect_pct: 평균 결함률 (%)
        avg_quantity: 평균 생산량 (개)
        sample_count: 데이터 샘플 수
    """
    return _get_shift_stats(shift=shift, production_line=production_line)


# ══════════════════════════════════════════════════════════════════
# MCP Tool 3: 품질 알림 발송
# ══════════════════════════════════════════════════════════════════

@mcp.tool()
def create_quality_alert(message: str, severity: str, production_line: str) -> dict[str, Any]:
    """
    품질 이상을 담당자에게 알립니다.

    Args:
        message: 알림 본문 (결함률 수치, 원인 등을 포함)
        severity: 심각도 (LOW | MEDIUM | HIGH | CRITICAL)
        production_line: 대상 생산 라인

    Returns:
        status: "sent"
        alert_id: 알림 ID
    """
    return create_alert(message=message, severity=severity, production_line=production_line)


# ══════════════════════════════════════════════════════════════════
# 서버 실행
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if "--port" in sys.argv:
        idx  = sys.argv.index("--port")
        port = int(sys.argv[idx + 1])
        print(f"[MCP] SSE 모드로 시작: http://localhost:{port}/sse")
        mcp.run(transport="sse", host="0.0.0.0", port=port)
    else:
        print("[MCP] stdio 모드로 시작", file=sys.stderr)
        mcp.run(transport="stdio")
