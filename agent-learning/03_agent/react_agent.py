"""
03_agent/react_agent.py
=======================
ReAct (Reasoning + Acting) 패턴으로 구현한 AI Agent.

[단순 Tool Calling과의 차이]
  Tool Calling : 질문 → 도구 1번 → 답변 (단방향, 계획 없음)
  Agent        : 목표 → LLM이 계획 → 도구 N번 반복 → 각 결과로 다음 행동 결정 → 최종 답변

[ReAct 루프]
  while not done:
    Thought    = LLM이 현재 상황 분석 & 다음 행동 결정
    Action     = 선택한 도구 호출 (또는 최종 답변)
    Observation= 도구 결과를 대화 맥락에 추가

[이 Agent가 가진 도구]
  - get_shift_stats      : 교대조·라인별 과거 결함률 조회
  - predict_defect_rate  : 실제 ML API로 결함률 예측
  - create_alert         : 임계치 초과 시 담당자 알림

[시나리오 예시]
  "모든 라인·교대조 조합의 결함률을 조회하고,
   가장 위험한 조합을 ML로 재예측한 후 2.5% 초과시 알림 보내줘"
  → Agent가 스스로 4번의 통계 조회, 1번의 ML 예측, 1번의 알림을 순서대로 실행

[모듈 역할 분리]
  core/llm.py       → LLM API 호출
  tools/schemas.py  → Tool JSON Schema (TOOLS_AGENT)
  tools/registry.py → 도구 디스패처
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.llm import call_llm, get_finish_reason, get_message
from tools.registry import REGISTRY_AGENT, execute_tool
from tools.schemas import TOOLS_AGENT

MAX_STEPS = 15  # 무한 루프 방지용 최대 반복 횟수

_SYSTEM_PROMPT = """당신은 제조 공정 품질 분석 Agent입니다.
주어진 목표를 달성하기 위해 단계적으로 도구를 사용합니다.

[행동 원칙]
- 목표를 작은 단계로 분해하고 순서대로 실행하세요.
- 각 도구 결과를 보고 다음 행동을 결정하세요.
- 모든 조회·예측이 완료되면 결과를 종합해 최종 답변을 작성하세요.
- 임계치 판단이 필요할 때는 명시된 기준을 사용하고, 없으면 2.5%를 기본 임계치로 사용하세요.

[사용 가능한 도구]
- get_shift_stats: 과거 평균 결함률 조회
- predict_defect_rate: ML 모델로 현재 조건 예측
- create_alert: 이상 상황 담당자 알림

최종 답변에는 반드시:
1. 조회/예측한 모든 수치를 표 형식으로 정리
2. 가장 위험한 조합과 그 이유
3. 발송한 알림 목록 (해당하는 경우)
을 포함하세요."""


# ══════════════════════════════════════════════════════════════════
# ReAct Agent 메인 루프
# ══════════════════════════════════════════════════════════════════

def run_agent(goal: str) -> str:
    """
    ReAct 패턴 Agent 실행 함수.

    루프마다 LLM에게 현재 대화 맥락(이전 도구 결과 포함)을 전달하고,
    LLM이 다음 행동(도구 호출 또는 최종 답변)을 결정합니다.
    개발자는 각 단계를 하드코딩하지 않아도 됩니다.
    """
    messages: list[dict] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user",   "content": goal},
    ]

    print(f"\n{'='*65}")
    print(f"🎯 목표: {goal}")
    print(f"{'='*65}")

    step = 0

    # ── ReAct 루프 시작 ─────────────────────────────────────────
    while step < MAX_STEPS:
        step += 1
        print(f"\n── STEP {step} {'─'*50}")

        response      = call_llm(messages, tools=TOOLS_AGENT)
        message       = get_message(response)
        finish_reason = get_finish_reason(response)

        if finish_reason != "tool_calls":
            # 도구 호출 없음 → Agent가 최종 답변을 결정했음
            print(f"[Agent] 최종 답변 도출 (총 {step}단계)")
            break

        # ── Thought: LLM의 판단 내용 (content가 있으면 출력) ───
        if message.get("content"):
            print(f"💭 Thought: {message['content']}")

        # ── Action: 선택된 도구 실행 ────────────────────────────
        tool_calls = message.get("tool_calls", [])
        messages.append({
            "role":       "assistant",
            "content":    message.get("content"),
            "tool_calls": tool_calls,
        })

        for tc in tool_calls:
            tool_name = tc["function"]["name"]
            tool_args = json.loads(tc["function"]["arguments"])
            tool_id   = tc["id"]

            print(f"⚙️  Action: {tool_name}({json.dumps(tool_args, ensure_ascii=False)})")

            # ── Observation: 도구 실행 결과 ─────────────────────
            result = execute_tool(tool_name, tool_args, REGISTRY_AGENT)
            print(f"📋 Obs:    {result}")

            messages.append({
                "role":         "tool",
                "tool_call_id": tool_id,
                "content":      result,
            })

    else:
        # MAX_STEPS 초과 → 강제 종료
        messages.append({"role": "user", "content": "지금까지의 결과를 종합해서 최종 답변을 작성해줘."})
        response = call_llm(messages)
        message  = get_message(response)
        print(f"\n⚠️  MAX_STEPS({MAX_STEPS}) 도달, 강제 종료")

    # ── 최종 답변 출력 ──────────────────────────────────────────
    final = message.get("content", "")
    print(f"\n{'='*65}")
    print("🤖 Agent 최종 보고서:")
    print(f"{'='*65}")
    print(final)
    return final


# ══════════════════════════════════════════════════════════════════
# 테스트 시나리오
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    # 시나리오 1: 전체 라인 현황 조회 + 위험 알림
    # Agent가 스스로 4개 조합(2라인 × 2교대)을 모두 조회하고
    # 임계치 초과 조합에 알림을 발송하도록 목표를 설정합니다.
    run_agent(
        "1라인과 2라인의 주간·야간 교대조 결함률을 모두 조회하고, "
        "결과를 비교해줘. 그리고 2.5%를 초과하는 조합은 "
        "HIGH 심각도로 알림을 발송해줘."
    )

    print("\n\n")

    # 시나리오 2: 특정 조건의 ML 예측 + 과거 비교 + 조건부 알림
    run_agent(
        "2라인 야간 교대조의 과거 평균 결함률을 조회하고, "
        "다음 조건으로 ML 예측도 해줘: "
        "B공급사, 계획 500개, 습도 65%, 자재 품질 76점, "
        "코팅 두께 80um, 용접 에너지 88%, 지그 오프셋 0.2mm, "
        "공정 편차 -0.5%, 공구 마모 60%, 정비 경과 45일. "
        "과거 평균과 비교하고, 예측값이 과거 평균보다 높으면 CRITICAL 알림을 발송해줘."
    )
