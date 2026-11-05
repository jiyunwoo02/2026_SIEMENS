# AI Agent 학습 프로젝트

> Tool Calling · MCP · AI Agent 개념을 Siemens SDC 환경에서 직접 구현해보는 학습 레포

---

## 목차

1. [학습 목표](#학습-목표)
2. [프로젝트 구조](#프로젝트-구조)
3. [환경 설정](#환경-설정)
4. [개념 개요](#개념-개요)
5. [실행 순서](#실행-순서)

---

## 학습 목표

| 단계 | 주제         | 핵심 질문                                              |
| ---- | ------------ | ------------------------------------------------------ |
| 1    | Tool Calling | LLM이 외부 함수를 어떻게 호출하는가?                   |
| 2    | MCP Server   | 도구를 어떻게 표준화해서 연결하는가?                   |
| 3    | AI Agent     | Tool Calling을 반복하는 자율 루프는 어떻게 작동하는가? |

---

## 프로젝트 구조

```
agent-learning/
├── .env                        # API 키, 엔드포인트 URL
├── requirements.txt
├── CLAUDE.md                   # Claude Code 가이드
│
├── core/                       # 인프라 계층 — 외부 API I/O만 담당
│   ├── config.py               # .env 로딩 및 상수 export
│   ├── llm.py                  # SDC LLM Gateway 호출 (call_llm)
│   └── ml.py                   # AI Hub ML API 호출 (call_ml_api), mock 포함
│
├── tools/                      # 도메인 계층 — 비즈니스 로직·스키마·라우팅
│   ├── schemas.py              # OpenAI Tool JSON Schema 정의
│   ├── functions.py            # 실제 함수 구현 (get_shift_stats 등)
│   └── registry.py             # 도구 이름→함수 매핑 및 execute_tool 디스패처
│
├── 01_tool_calling/            # 1단계: Tool Calling
│   ├── README.md
│   ├── basic.py                # 기본 Tool Calling (통계 조회 + 알림)
│   └── with_ml_api.py          # ML API를 Tool로 연결한 완전한 예시
│
├── 02_mcp_server/              # 2단계: MCP Server
│   ├── README.md
│   ├── server.py               # FastMCP 서버 (stdio / SSE 모드)
│   └── test_client.py          # MCP 클라이언트 테스트 (서버 자동 실행)
│
├── 03_agent/                   # 3단계: AI Agent
│   ├── README.md
│   └── react_agent.py          # ReAct 패턴 Multi-Tool Agent (최대 15 스텝)
│
└── docs/
    └── ai_agent_guide.html     # 개념 가이드 문서
```

---

## 환경 설정

```bash
# WSL Ubuntu 기준 (agent-learning/ 루트에서 실행)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`.env` 파일은 이미 Siemens SDC 연결 정보가 담겨 있습니다.

> **주의**: 모든 스크립트는 `agent-learning/` 루트에서 실행해야 합니다.
> 스크립트 내부에서 `sys.path.insert(0, ...)` 로 루트를 추가하므로
> 서브디렉토리에서 실행하면 import 오류가 납니다.

---

## 개념 개요

### Tool Calling이란?

LLM이 직접 외부 API를 호출하는 것이 아니라, **호출 의사를 JSON으로 표현**하면 앱 코드가 실제로 실행합니다.

```
사용자 질의
   ↓
LLM (도구 선택 판단)
   ↓ tool_calls JSON 반환
앱 코드 (실제 함수 실행)
   ↓ 실행 결과
LLM (최종 답변 생성)
   ↓
사용자에게 답변
```

### MCP란?

**Model Context Protocol** - 도구 연결을 USB처럼 표준화한 규격.

- 한 번 MCP 서버를 만들면 Claude Desktop, Cursor 등 모든 MCP 클라이언트에서 사용 가능
- LLM 벤더와 무관한 표준 인터페이스
- `@mcp.tool()` 데코레이터만으로 함수 시그니처가 자동으로 Tool Schema로 변환됨

### AI Agent란?

Tool Calling을 **반복**하며 복잡한 목표를 자율 수행하는 시스템.
핵심 패턴: **ReAct (Reasoning + Acting)**

```python
while not goal_achieved():
    thought = llm.reason(현재_상황)   # 다음 행동 계획
    action  = llm.decide(thought)     # 도구 선택
    result  = execute_tool(action)    # 실행
    # → 결과를 보고 다시 reason()
```

---

## 실행 순서

```bash
# 1단계: Tool Calling 기본 개념 (통계 조회 + 알림)
python 01_tool_calling/basic.py

# 2단계: 실제 ML API를 Tool로 연결
python 01_tool_calling/with_ml_api.py

# ML API 없이 테스트 (mock 모드)
MOCK_ML=true python 01_tool_calling/with_ml_api.py

# 3단계: MCP 클라이언트 테스트 (서버를 subprocess로 자동 실행, 터미널 1개로 충분)
python 02_mcp_server/test_client.py

# MCP 서버를 SSE HTTP 모드로 직접 실행할 경우 (별도 터미널)
python 02_mcp_server/server.py --port 8000

# 4단계: ReAct Agent
python 03_agent/react_agent.py
```

```
1단계: 가상환경 설정 (최초 1회)

cd ~/siemens/agent-learning
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

2단계: 실행 순서

# 1. Tool Calling 기본 (mock 도구만 사용, 가장 단순)
python 01_tool_calling/basic.py

# 2. ML API 연동 (MOCK_ML=true 로 먼저 테스트)
MOCK_ML=true python 01_tool_calling/with_ml_api.py

# 3. MCP 클라이언트 테스트 (서버 자동 실행됨, 터미널 1개로 충분)
python 02_mcp_server/test_client.py

# 4. ReAct Agent (가장 복잡, 도구를 여러 번 자율 실행)
python 03_agent/react_agent.py
```

---

## 사용 API

| API                     | 용도                              | 비고                                     |
| ----------------------- | --------------------------------- | ---------------------------------------- |
| Siemens SDC LLM Gateway | 자연어 이해, 도구 선택, 답변 생성 | OpenAI 호환, `x-api-key` 인증          |
| AI Hub GBT 예측         | 12개 피처 → 결함률(%) 예측       | POST `{"data": [{...}]}`, 자체서명 SSL |
