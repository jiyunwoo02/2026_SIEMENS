"""
tools/registry.py
도구 이름 → 함수 매핑 및 디스패처.

각 스크립트는 용도에 맞는 레지스트리를 import하거나,
execute_tool()에 registry 인자를 넘겨 실행합니다.
"""
from __future__ import annotations

import json

from tools.functions import create_alert, get_shift_stats, predict_defect_rate

# ── 용도별 레지스트리 ───────────────────────────────────────────────

# 01_tool_calling/basic.py : ML 없이 통계+알림만
REGISTRY_BASIC: dict[str, callable] = {
    "get_shift_stats": get_shift_stats,
    "create_alert":    create_alert,
}

# 01_tool_calling/with_ml_api.py : ML 예측만
REGISTRY_ML: dict[str, callable] = {
    "predict_defect_rate": predict_defect_rate,
}

# 03_agent/react_agent.py : 통계 + ML 예측 + 알림
REGISTRY_AGENT: dict[str, callable] = {
    "get_shift_stats":    get_shift_stats,
    "predict_defect_rate": predict_defect_rate,
    "create_alert":        create_alert,
}


def execute_tool(name: str, args: dict, registry: dict) -> str:
    """
    도구 이름과 인자를 받아 실제 함수를 실행하고 JSON 문자열을 반환합니다.

    Args:
        name    : 도구 이름 (LLM tool_call.function.name)
        args    : 도구 인자 (LLM tool_call.function.arguments 파싱 결과)
        registry: 사용할 레지스트리 (REGISTRY_BASIC / REGISTRY_ML / REGISTRY_AGENT)

    Returns:
        JSON 직렬화된 실행 결과 문자열
    """
    if name not in registry:
        return json.dumps({"error": f"알 수 없는 도구: {name}"}, ensure_ascii=False)
    result = registry[name](**args)
    return json.dumps(result, ensure_ascii=False)
