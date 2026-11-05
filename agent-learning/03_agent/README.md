# 03. AI Agent & ReAct Pattern

## 개념

**AI Agent = "Tool Calling을 반복하며 복잡한 목표를 자율 수행하는 시스템"**

단순 Tool Calling이 "질문 → 도구 1번 → 답변"이라면,
Agent는 "목표 → 계획 → 도구 N번 → 중간 결과 평가 → 도구 → ... → 최종 답변"입니다.

## ReAct 패턴 (Reasoning + Acting)

LLM이 Thought(추론) → Action(행동) → Observation(관찰)을 반복합니다.

```
목표: "결함률 조회 후 임계치 초과 시 알림, 최고 위험 라인 보고"

Thought 1: "먼저 모든 라인·교대조 조합의 통계를 조회해야 한다"
Action 1 : get_shift_stats(DAY, LINE-BPR-01)
Obs 1    : avg_defect_pct=1.82%

Thought 2: "1라인 주간 조회 완료. 나머지 조합도 조회한다"
Action 2 : get_shift_stats(DAY, LINE-BPR-02)
Obs 2    : avg_defect_pct=2.14%

...

Thought N: "2라인 야간이 2.91%로 가장 높고 임계치(2.5%) 초과"
Action N : create_alert("2라인 야간 결함률 2.91%", severity="HIGH")
Obs N    : status=sent

최종 답변: "조사 결과 가장 위험한 라인은 ..."
```

## 단순 Tool Calling vs Agent

| 항목 | 단순 Tool Calling | AI Agent |
|------|-------------------|----------|
| 도구 호출 횟수 | 1회 (고정) | N회 (동적) |
| 계획 수립 | 없음 | LLM이 스스로 단계 분해 |
| 중간 결과 반영 | 없음 | 각 결과를 보고 다음 행동 결정 |
| 오류 처리 | 앱 코드 담당 | LLM이 오류 보고 재시도 |

## 주의사항

- **Max Steps 제한 필수**: 무한 루프 방지를 위해 최대 반복 횟수를 설정
- **비용 증가**: 각 도구 호출마다 LLM API 호출이 발생 (토큰 비용)
- **레이턴시**: 반복 호출로 응답 시간 증가

## 실행

```bash
python 03_agent/react_agent.py
```
