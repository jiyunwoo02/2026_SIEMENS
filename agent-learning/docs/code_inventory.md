# Code Inventory

각 파일의 역할, 공개 API, 의존 관계를 정리한 문서입니다.

---

## 계층 구조 요약

```
core/        ← 인프라: 환경변수·HTTP 호출만 처리 (비즈니스 로직 없음)
tools/       ← 도메인: 비즈니스 로직·스키마·라우팅
01~03/       ← 애플리케이션: 대화 루프·ReAct 루프
docs/        ← 개념 가이드 문서
```

의존 방향: `01~03` → `tools` → `core` (역방향 의존 없음)

---

## core/

### `core/config.py`

**역할**: `.env` 파일을 읽어 상수로 export하는 단일 진입점. 다른 모든 모듈이 여기서 상수를 import하며, `load_dotenv`는 이 파일에서만 호출됩니다.

| 상수 | 설명 | 기본값 |
|------|------|--------|
| `API_KEY` | SDC LLM Gateway 인증 키 | `""` |
| `BASE_URL` | SDC LLM Gateway 엔드포인트 | `https://llm.sdc.siemens.cloud/v1` |
| `LLM_MODEL` | 사용할 모델명 | `gpt-5` |
| `ML_URL` | AI Hub ML API 엔드포인트 | `""` |
| `MOCK_ML` | mock 모드 활성화 여부 | `false` |

**의존**: `python-dotenv`

---

### `core/llm.py`

**역할**: Siemens SDC LLM Gateway HTTP 호출 전담. 인증 헤더 조립, 에러 처리, 응답 파싱 헬퍼를 제공합니다.

> 인증 방식이 표준 `Authorization: Bearer`가 아닌 `x-api-key` 헤더임에 주의.

| 함수 | 시그니처 | 설명 |
|------|----------|------|
| `call_llm` | `(messages, tools=None, model=None) → dict` | LLM에 채팅 요청. `tools` 전달 시 tool_choice=auto |
| `extract_text` | `(response) → str` | 응답 JSON에서 텍스트 콘텐츠 추출 |
| `get_finish_reason` | `(response) → str` | `"stop"` 또는 `"tool_calls"` 반환 |
| `get_message` | `(response) → dict` | `choices[0].message` 객체 반환 |

**의존**: `core/config.py`, `httpx`

---

### `core/ml.py`

**역할**: AI Hub GBT 결함률 예측 ML API의 HTTP 호출 전담. 비즈니스 로직 없이 "HTTP 요청 → 응답 파싱"만 처리합니다.

- `MOCK_ML=true` 이거나 `ML_URL`이 비어 있으면 자동으로 `_mock_predict`를 사용합니다.
- 자체서명 SSL 인증서 사용 → `httpx.Client(verify=False)`

| 함수 | 시그니처 | 설명 |
|------|----------|------|
| `call_ml_api` | `(row: dict) → float` | 12개 피처 딕셔너리 → 결함률(%) 예측값 반환 |

**mock 로직** (`_mock_predict`): `base=1.5` + 공구 마모·정비 경과일 가산 - 자재 품질 감산

**의존**: `core/config.py`, `httpx`

---

## tools/

### `tools/schemas.py`

**역할**: OpenAI Tool Calling JSON Schema 정의. 개별 스키마 상수와 용도별 그룹을 함께 제공합니다.

| 개별 스키마 | 대응 함수 |
|-------------|-----------|
| `SCHEMA_GET_SHIFT_STATS` | `get_shift_stats(shift, production_line)` |
| `SCHEMA_CREATE_ALERT` | `create_alert(message, severity)` |
| `SCHEMA_CREATE_QUALITY_ALERT` | `create_alert(message, severity, production_line)` |
| `SCHEMA_PREDICT_DEFECT_RATE` | `predict_defect_rate(12개 파라미터)` |

| 그룹 | 포함 스키마 | 사용처 |
|------|------------|--------|
| `TOOLS_BASIC` | `GET_SHIFT_STATS`, `CREATE_ALERT` | `01_tool_calling/basic.py` |
| `TOOLS_ML` | `PREDICT_DEFECT_RATE` | `01_tool_calling/with_ml_api.py` |
| `TOOLS_AGENT` | `GET_SHIFT_STATS`, `PREDICT_DEFECT_RATE`, `CREATE_QUALITY_ALERT` | `03_agent/react_agent.py` |

> MCP 서버(`02_mcp_server/server.py`)는 `@mcp.tool()` 데코레이터가 스키마를 자동 생성하므로 이 파일을 사용하지 않습니다.

**의존**: 없음

---

### `tools/functions.py`

**역할**: 실제 도구 함수 구현. HTTP 호출은 `core/ml.py`에 위임하고, 비즈니스 로직(데이터 조회, 알림 발송, 파라미터 조립)만 처리합니다.

| 함수 | 시그니처 | 설명 |
|------|----------|------|
| `get_shift_stats` | `(shift, production_line) → dict` | mock DB에서 과거 6개월 평균 통계 반환 (`avg_defect_pct`, `avg_quantity`, `sample_count`) |
| `create_alert` | `(message, severity, production_line="") → dict` | 콘솔 출력 형태의 mock 알림 발송. `alert_id`는 타임스탬프 기반 |
| `predict_defect_rate` | `(12개 파라미터) → dict` | 파라미터를 조립해 `core/ml.call_ml_api`에 위임. `mode: "mock"/"real"` 포함 반환 |

**mock DB** (`_MOCK_STATS`): 2라인 × 2교대 조합의 고정 통계값

**의존**: `core/config.py`, `core/ml.py`

---

### `tools/registry.py`

**역할**: 도구 이름 → 함수 매핑 딕셔너리와 `execute_tool` 디스패처 제공. LLM이 반환한 `tool_call.function.name`을 실제 함수 호출로 연결합니다.

| 레지스트리 | 포함 함수 | 사용처 |
|-----------|----------|--------|
| `REGISTRY_BASIC` | `get_shift_stats`, `create_alert` | `01_tool_calling/basic.py` |
| `REGISTRY_ML` | `predict_defect_rate` | `01_tool_calling/with_ml_api.py` |
| `REGISTRY_AGENT` | `get_shift_stats`, `predict_defect_rate`, `create_alert` | `03_agent/react_agent.py` |

| 함수 | 시그니처 | 설명 |
|------|----------|------|
| `execute_tool` | `(name, args, registry) → str` | 함수 실행 후 JSON 직렬화된 결과 문자열 반환 |

**의존**: `tools/functions.py`

---

## 01_tool_calling/

### `01_tool_calling/basic.py`

**역할**: Tool Calling의 전체 흐름을 가장 단순한 형태로 구현한 학습 예제.

**핵심 함수**: `chat_with_tools(user_message: str) → str`

**사용 도구**: `TOOLS_BASIC` (통계 조회 + 알림), `REGISTRY_BASIC`

**흐름**:
```
사용자 메시지 → LLM(tool_calls JSON) → 앱이 함수 실행 → role="tool" 추가 → LLM(최종 답변)
```

**테스트 시나리오** (3개):
1. 단순 조회 (도구 1번 호출)
2. 라인 비교 (도구 2번 호출)
3. 조건부 알림 (통계 조회 → 임계치 판단 → 알림 발송)

**의존**: `core/llm.py`, `tools/schemas.py` (`TOOLS_BASIC`), `tools/registry.py` (`REGISTRY_BASIC`)

---

### `01_tool_calling/with_ml_api.py`

**역할**: 실제 ML API를 Tool로 연결한 완전한 예제. LLM이 한국어 자연어에서 12개 파라미터를 추출해 ML API를 호출합니다.

**핵심 함수**: `predict_from_query(user_query: str) → str`

**사용 도구**: `TOOLS_ML` (ML 예측만), `REGISTRY_ML`

**LLM 역할 분담**:
- 1차 호출: 자연어 → 12개 파라미터 추출 → Tool Calling JSON 반환
- 2차 호출: ML 예측 결과 → 한국어 해설 답변 생성

**mock 실행**: `MOCK_ML=true python 01_tool_calling/with_ml_api.py`

**의존**: `core/llm.py`, `tools/schemas.py` (`TOOLS_ML`), `tools/registry.py` (`REGISTRY_ML`), `core/ml.py` (간접)

---

## 02_mcp_server/

### `02_mcp_server/server.py`

**역할**: FastMCP를 사용한 MCP 서버. `tools/functions.py`의 함수를 `@mcp.tool()` 데코레이터로 MCP 프로토콜에 등록하는 얇은 래퍼(thin wrapper)입니다.

**제공 도구** (3개):

| MCP Tool 이름 | 내부 위임 함수 |
|--------------|--------------|
| `predict_defect_rate` | `tools/functions.predict_defect_rate` |
| `get_shift_stats` | `tools/functions.get_shift_stats` |
| `create_quality_alert` | `tools/functions.create_alert` |

**실행 모드**:
- `python server.py` → stdio 모드 (Claude Desktop 연결)
- `python server.py --port 8000` → SSE HTTP 모드 (웹 클라이언트 연결)

**Tool Calling vs MCP 차이점**:
- Tool Calling: 개발자가 각 LLM 앱마다 `tools` 배열을 직접 구성
- MCP: 서버를 한 번 만들면 Claude, Cursor 등 모든 MCP 클라이언트가 연결 가능

**의존**: `tools/functions.py`, `mcp[cli]`

---

### `02_mcp_server/test_client.py`

**역할**: MCP Python SDK를 사용해 `server.py`의 도구를 직접 호출하는 테스트 클라이언트.

> `StdioServerParameters`를 통해 `server.py`를 subprocess로 자동 실행하므로 **별도 터미널 불필요**.

**테스트 항목** (4개):
1. 서버가 광고하는 도구 목록 조회 (`session.list_tools()`)
2. `get_shift_stats` 직접 호출
3. `predict_defect_rate` 직접 호출 (MOCK_ML=true)
4. `create_quality_alert` 직접 호출

**의존**: `mcp` (ClientSession, StdioServerParameters)

---

## 03_agent/

### `03_agent/react_agent.py`

**역할**: ReAct (Reasoning + Acting) 패턴으로 구현한 AI Agent. LLM이 목표를 스스로 분해하고, 도구를 순서대로 선택·실행하며 최종 답변을 도출합니다.

**핵심 함수**: `run_agent(goal: str) → str`

**사용 도구**: `TOOLS_AGENT` (통계 + ML 예측 + 알림 전부), `REGISTRY_AGENT`

**루프 구조**:
```
Thought  → LLM이 현재 상황 분석 & 다음 행동 결정 (content 출력)
Action   → 선택한 도구 호출 (tool_calls)
Observation → 결과를 messages에 추가
→ 반복 (MAX_STEPS=15)
```

**단순 Tool Calling과의 차이**:

| | Tool Calling | Agent |
|--|--|--|
| 도구 호출 횟수 | 1~2회 | N회 (자율 결정) |
| 계획 주체 | 개발자가 질문으로 유도 | LLM이 스스로 분해·순서 결정 |
| 복잡도 | 단일 질의-응답 | 다단계 목표 수행 |

**테스트 시나리오** (2개):
1. 전체 라인 현황 조회 → 임계치 초과 조합에 HIGH 알림
2. 특정 조건 ML 예측 → 과거 평균과 비교 → 조건부 CRITICAL 알림

**의존**: `core/llm.py`, `tools/schemas.py` (`TOOLS_AGENT`), `tools/registry.py` (`REGISTRY_AGENT`)

---

## docs/

### `docs/ai_agent_guide.html`

**역할**: AI Agent 개념(Tool Calling → MCP → ReAct Agent)을 시각적으로 설명하는 HTML 가이드 문서.

---

## 설정 파일

### `.env`

SDC LLM Gateway 및 AI Hub ML API 연결 정보. `core/config.py`에서만 로딩합니다.

```
API_KEY=...
BASE_URL=https://llm.sdc.siemens.cloud/v1
LLM_MODEL=gpt-5
ML_ENDPOINT_URL=https://...
MOCK_ML=false
```

### `requirements.txt`

| 패키지 | 버전 | 용도 |
|--------|------|------|
| `httpx` | ≥0.27 | LLM/ML API HTTP 호출 |
| `python-dotenv` | ≥1.0 | `.env` 로딩 |
| `pydantic` | ≥2.0 | 데이터 검증 |
| `mcp[cli]` | ≥1.3 | MCP SDK (FastMCP 포함) |

---

## 의존 관계 다이어그램

```
01_tool_calling/basic.py
  └─ tools/schemas.py (TOOLS_BASIC)
  └─ tools/registry.py (REGISTRY_BASIC)
       └─ tools/functions.py
            └─ core/ml.py
                 └─ core/config.py
  └─ core/llm.py
       └─ core/config.py

01_tool_calling/with_ml_api.py
  └─ tools/schemas.py (TOOLS_ML)
  └─ tools/registry.py (REGISTRY_ML) → tools/functions.py → core/ml.py
  └─ core/llm.py

02_mcp_server/server.py
  └─ tools/functions.py (직접 import)
  └─ mcp[cli]

02_mcp_server/test_client.py
  └─ server.py (subprocess)
  └─ mcp (ClientSession)

03_agent/react_agent.py
  └─ tools/schemas.py (TOOLS_AGENT)
  └─ tools/registry.py (REGISTRY_AGENT) → tools/functions.py → core/ml.py
  └─ core/llm.py
```
