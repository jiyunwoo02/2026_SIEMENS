"""
core/config.py
환경변수 로딩을 한 곳에서만 처리합니다.
다른 모듈은 여기서 상수를 import해 사용합니다.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# agent-learning/.env 경로를 절대경로로 고정
# 어떤 디렉터리에서 실행해도 올바른 .env를 로딩합니다.
_ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

# LLM Gateway
API_KEY   = os.getenv("API_KEY", "")
BASE_URL  = os.getenv("BASE_URL", "https://llm.sdc.siemens.cloud/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-5")

# ML API
ML_URL  = os.getenv("ML_ENDPOINT_URL", "")
MOCK_ML = os.getenv("MOCK_ML", "false").lower() == "true"
