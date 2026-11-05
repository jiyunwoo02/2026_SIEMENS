"""
core/llm.py
Siemens SDC LLM Gateway 호출을 담당합니다.

다른 모듈은 call_llm() 하나만 import해서 사용합니다.
인증·URL 조합·에러 처리는 모두 여기서 처리합니다.
"""
from __future__ import annotations

import httpx

from core.config import API_KEY, BASE_URL, LLM_MODEL


def call_llm(
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str | None = None,
) -> dict:
    """
    SDC LLM Gateway에 채팅 요청을 보냅니다.

    Args:
        messages : OpenAI 형식 대화 메시지 목록
        tools    : Tool Calling용 도구 스키마 목록. None이면 일반 채팅.
        model    : 사용할 모델명. None이면 .env의 LLM_MODEL 사용.

    Returns:
        OpenAI 호환 응답 JSON dict

    Raises:
        RuntimeError: HTTP 4xx/5xx 응답 시
    """
    url = f"{BASE_URL.rstrip('/')}/chat/completions"
    payload: dict = {
        "model":    model or LLM_MODEL,
        "messages": messages,
    }
    if tools:
        payload["tools"]       = tools
        payload["tool_choice"] = "auto"

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            url,
            json=payload,
            headers={"x-api-key": API_KEY, "Content-Type": "application/json"},
        )

    if resp.status_code >= 400:
        raise RuntimeError(f"LLM API {resp.status_code}: {resp.text[:300]}")

    return resp.json()


def extract_text(response: dict) -> str:
    """LLM 응답 JSON에서 텍스트 콘텐츠를 추출합니다."""
    return response["choices"][0]["message"].get("content", "")


def get_finish_reason(response: dict) -> str:
    """LLM 응답의 finish_reason을 반환합니다. ('stop' | 'tool_calls' | ...)"""
    return response["choices"][0].get("finish_reason", "stop")


def get_message(response: dict) -> dict:
    """LLM 응답의 message 객체를 반환합니다."""
    return response["choices"][0]["message"]
