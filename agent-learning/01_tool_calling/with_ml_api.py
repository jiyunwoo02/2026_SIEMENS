"""
01_tool_calling/with_ml_api.py
==============================
실제 ML API(AI Hub GBT 결함률 예측 모델)를 Tool로 연결한 완전한 예시.

[흐름]
  사용자 자연어 질의
    → LLM: 질의에서 12개 파라미터 추출 → predict_defect_rate Tool 호출
      → AI Hub ML API 실제 호출 (POST {data: [{12개 피처}]})
        → 예측값(결함률 %) 반환
          → LLM: 예측값 기반 한국어 답변 생성

[연결된 ML API]
  POST https://.../defect_rate_pred/deploy
  Request : {"data": [{production_line, shift, supplier_code, 9개 수치 피처}]}
  Response: {"data": [{echoed_input + "prediction(defect_rate_pct)": float}]}

[포인트]
  - LLM이 한국어 자연어에서 필드명/단위 변환까지 처리
  - 실제 ML API는 Tool 내부에서만 호출 (LLM이 직접 호출하지 않음)
  - MOCK_ML=true 환경변수로 실제 API 없이 테스트 가능

[모듈 역할 분리]
  core/config.py    → 환경변수 로딩
  core/llm.py       → LLM API 호출
  core/ml.py        → ML API HTTP 호출 및 응답 파싱
  tools/schemas.py  → Tool JSON Schema (TOOLS_ML)
  tools/functions.py → predict_defect_rate 구현
  tools/registry.py  → 도구 디스패처
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.llm import call_llm, get_finish_reason, get_message
from tools.registry import REGISTRY_ML, execute_tool
from tools.schemas import TOOLS_ML


# ══════════════════════════════════════════════════════════════════
# Tool Calling 루프
#
# LLM의 역할:
#   1차 호출: 자연어 → 12개 파라미터 추출 (Tool Calling JSON 반환)
#   2차 호출: ML 예측 결과 → 한국어 해설 답변 생성
# ══════════════════════════════════════════════════════════════════

def predict_from_query(user_query: str) -> str:
    messages: list[dict] = [
        {
            "role": "system",
            "content": (
                "당신은 제조 공정 결함률 예측 어시스턴트입니다.\n"
                "사용자 발화에서 공정 파라미터를 추출해 predict_defect_rate 도구를 호출하세요.\n"
                "단위 변환 규칙:\n"
                "  - '1라인' → LINE-BPR-01, '주간' → DAY\n"
                "  - 'A공급사' → SIM-SUP-A\n"
                "  - '2주' → days_since_maintenance=14\n"
                "예측 결과를 받으면 수치를 정확히 인용하고 주요 위험 요인을 간략히 설명하세요."
            ),
        },
        {"role": "user", "content": user_query},
    ]

    print(f"\n{'='*65}")
    print(f"👤 사용자: {user_query}")
    print(f"{'='*65}")

    while True:
        response      = call_llm(messages, tools=TOOLS_ML)
        message       = get_message(response)
        finish_reason = get_finish_reason(response)

        if finish_reason != "tool_calls":
            break

        tool_calls = message.get("tool_calls", [])
        messages.append({
            "role":       "assistant",
            "content":    message.get("content"),
            "tool_calls": tool_calls,
        })

        for tc in tool_calls:
            name  = tc["function"]["name"]
            args  = json.loads(tc["function"]["arguments"])
            tc_id = tc["id"]

            print(f"\n🔧 LLM이 추출한 파라미터 ({name}):")
            for k, v in args.items():
                print(f"   {k:45s} = {v}")

            result = execute_tool(name, args, REGISTRY_ML)
            print(f"\n📊 ML 예측 결과: {result}")

            messages.append({"role": "tool", "tool_call_id": tc_id, "content": result})

    final = message.get("content", "")
    print(f"\n🤖 AI 답변:\n{final}")
    return final


# ══════════════════════════════════════════════════════════════════
# 테스트
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    predict_from_query(
        "1라인 주간 교대조, A공급사 소재 사용, 오늘 계획 생산량은 480개야. "
        "현재 습도 58%, 자재 품질 점수 82점, 코팅 두께 목표 75um, "
        "용접 에너지 92%, 지그 오프셋 0.15mm, 공정 편차 +1.8%, "
        "공구 마모 35%, 마지막 정비는 3주 전이야. 결함률 예측해줘."
    )

    print("\n")

    predict_from_query(
        "2라인 야간조, B공급사, 500개 계획. 습도 65%, 품질 점수 78점, "
        "코팅 80um, 용접 에너지 88%, 지그 오프셋 0.2mm, 편차 -0.5%, "
        "공구 마모 60%, 정비 후 45일 경과. 결함률 얼마나 될까?"
    )
