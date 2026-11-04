# sdc llm model test
# 지원되는 모델 목록 출력
# GET /v1/models 는 OpenAI 형식이 아니라 SDC catalog JSON을 반환함

import json
import os
import urllib.request
from pathlib import Path


def load_env(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()

api_key = os.getenv("api_key")
base_url = os.getenv("base_url", "https://llm.sdc.siemens.cloud/v1").rstrip("/")

if not api_key:
    raise SystemExit(".env 에 api_key 가 없습니다.")

req = urllib.request.Request(
    f"{base_url}/models",
    headers={"x-api-key": api_key},
)

try:
    with urllib.request.urlopen(req) as resp:
        payload = json.load(resp)

    print("=== 지원되는 모델 목록 ===")
    catalog = payload.get("catalog", [])
    if not catalog:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for group in catalog:
            tool = group.get("tool", "unknown")
            base_path = group.get("base_path", "")
            print(f"\n[{tool}] {base_path}")
            for model in group.get("models", []):
                print(f"  - {model}")
except Exception as e:
    print(f"에러 발생: {e}")
