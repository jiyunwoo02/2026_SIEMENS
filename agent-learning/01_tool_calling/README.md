# 01. Tool Calling

## 개념

**Tool Calling = "LLM이 외부 함수를 사용하겠다는 의사를 JSON으로 선언하는 메커니즘"**

LLM은 직접 API를 호출하지 않습니다. 대신 "어떤 함수를, 어떤 인자로 호출하라"는 JSON을 반환하고,
애플리케이션 코드가 실제로 호출한 뒤 결과를 LLM에 돌려줍니다.

```
┌──────────────────────────────────────────────────────────┐
│  사용자: "1라인 주간 평균 결함률 알려줘"                      │
└────────────────────┬─────────────────────────────────────┘
                     │  질의 + tools 목록
                     ▼
              ┌─────────────┐
              │  LLM        │  ← 도구를 선택하고 인자를 추출
              └──────┬──────┘
                     │  tool_calls JSON 반환
                     │  {"name": "get_shift_stats",
                     │   "arguments": {"shift": "DAY",
                     │                 "production_line": "LINE-BPR-01"}}
                     ▼
              ┌─────────────┐
              │  앱 코드    │  ← 실제 함수/API 호출
              └──────┬──────┘
                     │  결과: {"avg_defect_pct": 1.82, ...}
                     ▼
              ┌─────────────┐
              │  LLM        │  ← 결과를 보고 최종 답변 생성
              └──────┬──────┘
                     │
                     ▼
              "1라인 주간 평균 결함률은 1.82%입니다."
```

## 핵심 구조 (OpenAI 호환 형식)

### 1. Tool 선언 (개발자 → LLM)

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_shift_stats",
            "description": "교대조와 라인의 과거 결함률을 조회합니다.",  # LLM이 이 설명으로 판단
            "parameters": {
                "type": "object",
                "properties": {
                    "shift": {"type": "string", "enum": ["DAY", "NIGHT"]},
                    "production_line": {"type": "string"}
                },
                "required": ["shift", "production_line"]
            }
        }
    }
]
```

### 2. LLM 응답 (tool_calls)

```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "tool_calls": [{
        "id": "call_abc123",
        "type": "function",
        "function": {
          "name": "get_shift_stats",
          "arguments": "{\"shift\": \"DAY\", \"production_line\": \"LINE-BPR-01\"}"
        }
      }]
    },
    "finish_reason": "tool_calls"
  }]
}
```

### 3. 도구 결과 반환 (앱 → LLM)

```python
messages.append({
    "role": "tool",
    "tool_call_id": "call_abc123",   # LLM 응답의 id와 매칭
    "content": '{"avg_defect_pct": 1.82}'
})
```

## 파일 설명

| 파일 | 내용 |
|------|------|
| `basic.py` | mock 도구 2개로 Tool Calling 전체 흐름 구현 |
| `with_ml_api.py` | 실제 ML API를 Tool로 연결 (12개 파라미터 추출 → 예측 → 답변) |

## 실행

```bash
python 01_tool_calling/basic.py
python 01_tool_calling/with_ml_api.py
```
