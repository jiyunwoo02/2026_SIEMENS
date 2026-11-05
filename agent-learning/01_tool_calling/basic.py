"""
01_tool_calling/basic.py
========================
Tool Calling의 전체 흐름을 가장 단순한 형태로 구현합니다.

[사용 도구 (mock)]
- get_shift_stats : 교대조·라인별 과거 평균 결함률 조회
- create_alert    : 임계치 초과 시 담당자 알림 발송

[흐름]
  사용자 메시지
    → LLM (tool_calls JSON 반환)
      → 앱 코드가 실제 함수 실행
        → 결과를 대화에 추가
          → LLM (최종 텍스트 답변)

[모듈 역할 분리]
  core/config.py    → 환경변수 로딩
  core/llm.py       → LLM API 호출
  tools/schemas.py  → Tool JSON Schema (TOOLS_BASIC)
  tools/registry.py → 도구 이름→함수 매핑 및 디스패처
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (core/, tools/ import를 위해)
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.llm import call_llm, get_finish_reason, get_message
from tools.registry import REGISTRY_BASIC, execute_tool
from tools.schemas import TOOLS_BASIC


# ══════════════════════════════════════════════════════════════════
# Tool Calling 메인 루프
#
# [상세 흐름]
# 1. 사용자 메시지 + tools 목록을 LLM에 전송
# 2. LLM 응답 확인:
#    - finish_reason == "tool_calls" → 도구 실행 필요
#    - finish_reason == "stop"       → 최종 텍스트 답변
# 3. tool_calls가 있으면:
#    a. 각 tool_call의 name, arguments 추출
#    b. 실제 함수 실행
#    c. 결과를 role="tool" 메시지로 대화에 추가
#    d. 다시 LLM 호출 (2번으로 돌아감)
# ══════════════════════════════════════════════════════════════════

def chat_with_tools(user_message: str) -> str:
    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "당신은 제조 공정 분석 어시스턴트입니다. "
                "도구를 적절히 활용해 데이터를 조회하고 분석합니다. "
                "도구 결과가 있으면 수치를 정확히 인용해서 답변하세요."
            ),
        },
        {"role": "user", "content": user_message},
    ]

    print(f"\n{'='*60}")
    print(f"👤 사용자: {user_message}")
    print(f"{'='*60}")

    # LLM 호출 루프: 도구 호출이 끝날 때까지 반복
    while True:
        response      = call_llm(messages, tools=TOOLS_BASIC)
        message       = get_message(response)
        finish_reason = get_finish_reason(response)

        if finish_reason != "tool_calls":
            # 도구 호출 없음 → 최종 텍스트 답변
            break

        # ── 도구 호출 처리 ──────────────────────────────────────
        tool_calls = message.get("tool_calls", [])

        # [중요] 어시스턴트 메시지(tool_calls 포함)를 히스토리에 추가
        # 이 단계를 빠뜨리면 LLM이 맥락을 잃음
        messages.append({
            "role":       "assistant",
            "content":    message.get("content"),
            "tool_calls": tool_calls,
        })

        for tc in tool_calls:
            tool_name = tc["function"]["name"]
            tool_args = json.loads(tc["function"]["arguments"])
            tool_id   = tc["id"]  # 결과 매핑에 사용

            print(f"\n🔧 도구 호출: {tool_name}")
            print(f"   인자: {json.dumps(tool_args, ensure_ascii=False)}")

            result = execute_tool(tool_name, tool_args, REGISTRY_BASIC)
            print(f"   결과: {result}")

            # [중요] 도구 결과를 role="tool"로 히스토리에 추가
            # tool_call_id로 LLM이 어느 호출의 결과인지 매핑함
            messages.append({
                "role":         "tool",
                "tool_call_id": tool_id,
                "content":      result,
            })
        # ── 도구 결과 추가 완료, 다시 LLM 호출 ──────────────────

    final_answer = message.get("content", "")
    print(f"\n🤖 AI 답변:\n{final_answer}")
    return final_answer


# ══════════════════════════════════════════════════════════════════
# 테스트
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # 테스트 1: 단순 조회 (도구 1번 호출)
    chat_with_tools("LINE-BPR-01 주간 교대조의 평균 결함률이 얼마야?")

    # 테스트 2: 비교 질의 (도구 2번 호출)
    chat_with_tools("1라인과 2라인의 주간 결함률을 비교해줘")

    # 테스트 3: 조건부 알림 (도구를 연속 호출)
    chat_with_tools(
        "야간 2라인의 결함률을 조회하고, 2.5%를 초과하면 HIGH 심각도로 알림 보내줘"
    )
