#!/usr/bin/env bash
# AIHUB-v2 로컬 웹 UI(FastAPI + 정적 파일)를 실행하는 스크립트.
#
# [수정] 2026-10-28: 기존 파일은 실행 가능한 스크립트가 아니라 명령어 한 줄을 적어 둔
# 메모였다(주석 처리된 프롬프트 포함, 실행하면 주석만 남아 아무 동작도 하지 않았음).
# config.py가 현재 작업 디렉터리의 .env를 읽으므로, 이 스크립트가 어디서 호출되든
# 프로젝트 루트(AIHUB-v2/)로 먼저 이동한 뒤 uvicorn을 실행하도록 바꿨다.
# 로직(uvicorn 실행 커맨드 자체)은 바뀌지 않았고, 실행 가능하게 만들고 몇 가지
# 안내만 추가했다.
#
# 사용법:
#   bash aihub/web/ui.sh            # 기본 host=127.0.0.1, port=8000
#   bash aihub/web/ui.sh 9000       # 포트만 바꾸기
#   HOST=0.0.0.0 bash aihub/web/ui.sh 9000   # 호스트도 바꾸기 (같은 네트워크의 다른 기기에서 접속 시)
#
# 실행 후 브라우저에서 http://<HOST>:<PORT>/ 로 접속합니다. 종료는 Ctrl+C.
set -euo pipefail

PORT="${1:-8000}"
HOST="${HOST:-127.0.0.1}"

# 이 스크립트(aihub/web/ui.sh) 위치 기준으로 프로젝트 루트(AIHUB-v2/)를 계산한다.
# 어느 디렉터리에서 호출해도 동일하게 동작하도록 하기 위함이다.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." >/dev/null 2>&1 && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -f .env ]]; then
  echo "[경고] $PROJECT_ROOT/.env 가 없습니다. LLM/예측/최적화 API 설정 없이 기동을 시도합니다 (README의 \"설정\" 절 참고)." >&2
fi

echo "AIHUB-v2 웹 UI: http://${HOST}:${PORT}/  (종료: Ctrl+C)"
exec python -m uvicorn aihub.api:app --reload --host "$HOST" --port "$PORT"