# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 실행 명령어

```bash
# 가상환경 설정 (최초 1회)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 각 단계별 실행 (agent-learning/ 루트에서)
python 01_tool_calling/basic.py
python 01_tool_calling/with_ml_api.py
python 03_agent/react_agent.py

# MCP 서버 테스트 (터미널 2개 필요)
python 02_mcp_server/server.py          # 터미널 1: stdio 모드
python 02_mcp_server/test_client.py     # 터미널 2: 클라이언트

# ML API 없이 테스트 (mock 모드)
MOCK_ML=true python 01_tool_calling/with_ml_api.py
```

모든 스크립트는 `agent-learning/` 루트에서 실행해야 합니다. 스크립트 내부에서 `sys.path.insert(0, ...)` 로 루트를 추가하므로 서브디렉토리에서 실행하면 import 오류가 납니다.

## 아키텍처

책임 계층을 3단계로 분리합니다.

```
core/        ← 인프라: 환경변수·HTTP 호출만 처리
tools/       ← 도메인: 비즈니스 로직·스키마·라우팅
01~03/       ← 애플리케이션: 대화 루프·ReAct 루프
```

**`core/`** — 외부 API I/O만 담당. 비즈니스 로직 없음.
- `config.py`: `.env` 로딩 및 상수 export (`API_KEY`, `BASE_URL`, `LLM_MODEL`, `ML_URL`, `MOCK_ML`)
- `llm.py`: `call_llm(messages, tools, model)` → OpenAI 호환 JSON 반환. `x-api-key` 헤더 사용 (SDC Gateway 전용, `Authorization: Bearer` 아님)
- `ml.py`: `call_ml_api(row: dict) → float`. `MOCK_ML=true`이거나 `ML_URL`이 비어 있으면 자동으로 mock 사용

**`tools/`** — 도구 정의와 구현.
- `schemas.py`: OpenAI Tool JSON Schema 정의. `TOOLS_BASIC`, `TOOLS_ML`, `TOOLS_AGENT` 세 가지 그룹으로 묶여 있음
- `functions.py`: 실제 함수 구현 (`get_shift_stats`, `create_alert`, `predict_defect_rate`). ML 호출은 `core/ml.call_ml_api`에 위임
- `registry.py`: `REGISTRY_BASIC / REGISTRY_ML / REGISTRY_AGENT` 딕셔너리와 `execute_tool(name, args, registry) → str` 디스패처

**스크립트 계층** — 루프 로직만 포함, `core/`와 `tools/`를 조합.
- `01_tool_calling/basic.py`: `TOOLS_BASIC` + `REGISTRY_BASIC` 사용, 도구 1~2회 호출
- `01_tool_calling/with_ml_api.py`: `TOOLS_ML` + `REGISTRY_ML`, LLM이 자연어에서 12개 파라미터 추출
- `02_mcp_server/server.py`: FastMCP `@mcp.tool()` 래퍼. 실제 구현은 `tools/functions.py`에 위임
- `03_agent/react_agent.py`: `TOOLS_AGENT` + `REGISTRY_AGENT`, ReAct 루프 최대 `MAX_STEPS=15`

## 주요 API 동작 방식

**LLM Gateway (SDC)**
- 인증: `x-api-key` 헤더 (표준 `Authorization: Bearer` 아님)
- 모델: `gpt-5`, OpenAI 호환 `/chat/completions` 엔드포인트

**AI Hub ML API**
- 요청: `POST {"data": [{12개 피처 딕셔너리}]}`
- 응답: `{"data": [{echo된 입력 + "prediction(defect_rate_pct)": float}]}`
- SSL 인증서 자체서명 → `httpx.Client(verify=False)` 사용

## 새 도구 추가 방법

1. `tools/schemas.py`에 `SCHEMA_*` 상수 추가
2. `tools/functions.py`에 함수 구현
3. `tools/registry.py`의 적절한 `REGISTRY_*`에 등록
4. 사용할 스크립트의 `TOOLS_*` 그룹에 스키마 추가
