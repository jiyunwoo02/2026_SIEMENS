"""
02_mcp_server/test_client.py
============================
MCP 클라이언트를 사용해 server.py가 제공하는 도구를 테스트합니다.

[테스트 항목]
1. 서버가 광고하는 도구 목록 조회
2. get_shift_stats 도구 직접 호출
3. predict_defect_rate 도구 직접 호출

[실행]
  python 02_mcp_server/test_client.py

  서버를 별도로 실행할 필요 없습니다.
  MCP 클라이언트 SDK가 server.py를 subprocess로 자동 실행합니다.
"""

from __future__ import annotations

import asyncio
import os
import sys

# MCP Python SDK - 클라이언트 라이브러리
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# server.py의 절대 경로
SERVER_PATH = os.path.join(os.path.dirname(__file__), "server.py")
PYTHON_EXE  = sys.executable  # 현재 가상환경의 Python


async def run_client_tests() -> None:
    """MCP 서버에 연결해 도구 목록과 호출을 테스트합니다."""

    # StdioServerParameters: 서버를 subprocess로 실행하고 stdin/stdout으로 통신
    server_params = StdioServerParameters(
        command=PYTHON_EXE,
        args=[SERVER_PATH],
        env={
            **os.environ,
            "MOCK_ML": "true",  # 테스트용: 실제 ML API 없이 더미 예측 사용
        },
    )

    print("=" * 60)
    print("MCP 클라이언트 테스트")
    print("=" * 60)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:

            # ── 1. 세션 초기화 ──────────────────────────────────
            # 클라이언트 ↔ 서버 간 프로토콜 버전과 기능을 협상
            await session.initialize()
            print("\n✅ MCP 세션 초기화 완료")

            # ── 2. 도구 목록 조회 ──────────────────────────────
            # 서버가 제공하는 모든 Tool의 이름, 설명, 파라미터를 가져옴
            tools_result = await session.list_tools()
            tools = tools_result.tools

            print(f"\n📋 서버가 제공하는 도구 목록 ({len(tools)}개):")
            for tool in tools:
                print(f"\n  🔧 {tool.name}")
                print(f"     설명: {tool.description[:80]}...")
                params = tool.inputSchema.get("properties", {})
                print(f"     파라미터: {list(params.keys())}")

            # ── 3. get_shift_stats 호출 ────────────────────────
            print("\n" + "-" * 60)
            print("테스트: get_shift_stats (주간 1라인)")

            stats_result = await session.call_tool(
                "get_shift_stats",
                arguments={"shift": "DAY", "production_line": "LINE-BPR-01"},
            )
            # MCP 도구 결과는 content 리스트로 반환됨
            stats_content = stats_result.content[0].text if stats_result.content else "{}"
            print(f"결과: {stats_content}")

            # ── 4. predict_defect_rate 호출 ────────────────────
            print("\n" + "-" * 60)
            print("테스트: predict_defect_rate (실제 공정 조건)")

            pred_result = await session.call_tool(
                "predict_defect_rate",
                arguments={
                    "production_line":                 "LINE-BPR-01",
                    "shift":                           "DAY",
                    "supplier_code":                   "SIM-SUP-A",
                    "planned_quantity":                480,
                    "ambient_humidity_pct":            58.0,
                    "incoming_material_quality_score": 82.0,
                    "coating_target_thickness_um":     75.0,
                    "weld_energy_setting_pct":         92.0,
                    "fixture_alignment_offset_mm":     0.15,
                    "process_setting_deviation_pct":   1.8,
                    "tool_wear_pct":                   35.0,
                    "days_since_maintenance":          21,
                },
            )
            pred_content = pred_result.content[0].text if pred_result.content else "{}"
            print(f"결과: {pred_content}")

            # ── 5. create_quality_alert 호출 ───────────────────
            print("\n" + "-" * 60)
            print("테스트: create_quality_alert")

            alert_result = await session.call_tool(
                "create_quality_alert",
                arguments={
                    "message":         "예측 결함률 2.5% 초과 감지. 공구 마모 35%, 정비 경과 21일.",
                    "severity":        "HIGH",
                    "production_line": "LINE-BPR-01",
                },
            )
            alert_content = alert_result.content[0].text if alert_result.content else "{}"
            print(f"결과: {alert_content}")

    print("\n" + "=" * 60)
    print("✅ MCP 클라이언트 테스트 완료")


if __name__ == "__main__":
    asyncio.run(run_client_tests())
