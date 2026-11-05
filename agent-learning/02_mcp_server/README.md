# 02. MCP Server

## 개념

**MCP (Model Context Protocol) = "Tool 연결을 USB처럼 표준화한 프로토콜"**

Tool Calling은 LLM이 함수를 호출하는 메커니즘이고,
MCP는 그 함수(도구)를 어떻게 LLM에 연결하는지를 표준화한 규격입니다.

```
Before MCP:                    After MCP:
─────────────────────          ─────────────────────────────────
Claude용 코드 따로              MCP Server
GPT용 코드 따로       →→→      (Tools 정의 한 번)
Cursor용 코드 따로                    ↓
각 도구별 연결 별도              MCP Clients (Claude, Cursor, etc.)
                                 → 모두 연결 가능
```

## MCP 구조

```
MCP Server (server.py)                 MCP Client (Claude Desktop 등)
┌──────────────────────┐               ┌──────────────────────┐
│ @mcp.tool()          │               │                      │
│ def predict_defect() │ ←─ JSON-RPC ─→│ Tool Calling 처리    │
│                      │  (stdio/HTTP) │                      │
│ @mcp.tool()          │               │                      │
│ def get_stats()      │               │                      │
└──────────────────────┘               └──────────────────────┘
```

## FastMCP 사용법

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("서버이름")

@mcp.tool()
def my_tool(param: str) -> dict:
    """LLM이 이 docstring을 보고 도구 사용 여부를 판단"""
    return {"result": param}

mcp.run()  # stdio 모드로 실행 (Claude Desktop 연결용)
```

## Claude Desktop 연결 방법

`~/.config/claude/claude_desktop_config.json` 에 추가:

```json
{
  "mcpServers": {
    "defect-predictor": {
      "command": "python",
      "args": ["/path/to/02_mcp_server/server.py"],
      "env": {
        "API_KEY": "...",
        "ML_ENDPOINT_URL": "..."
      }
    }
  }
}
```

## 파일 설명

| 파일 | 내용 |
|------|------|
| `server.py` | FastMCP 서버 (3개 도구 제공) |
| `test_client.py` | MCP 클라이언트로 서버 도구 목록 조회 및 실행 테스트 |

## 실행

```bash
# 서버 단독 실행 (Claude Desktop 연결용)
python 02_mcp_server/server.py

# 클라이언트 테스트 (별도 터미널 불필요, subprocess로 서버 자동 실행)
python 02_mcp_server/test_client.py
```
