#!/usr/bin/env bash
# AIHUB-v2 HTTP API(/health, /chat/predict, /chat/session/{id})를 curl로 호출해보는
# 수동 스모크 테스트 스크립트. pytest가 아니라 실행 중인 서버에 실제 요청을 보낸다.
#
# 전제 조건:
#   1) 다른 터미널에서 먼저 서버를 띄워야 한다.
#        bash aihub/web/ui.sh                (또는) python -m uvicorn aihub.api:app --reload
#   2) AIHUB-v2/.env 에 LLM 설정(api_key, LLM_MODEL)이 있어야 한다(없으면 /chat/predict가 503).
#   3) 예측 API는 MOCK_ML=true 로 더미 응답으로 대체할 수 있지만, LLM과 최적화 API는
#      이 스크립트에서 항상 실제로 호출된다(.env의 OPTIMIZATION_API_URL 등 필요).
#   4) curl, python3 필요. jq는 선택(있으면 더 보기 좋게 출력, 없으면 python -m json.tool 사용).
#
# [중요] 이 스크립트는 작성 시점에 실제 서버/LLM/최적화 API에 대고 실행해 검증하지 않았다.
# 각 케이스 옆의 "기대 status"는 docs/architecture.md 5~6절(코드 기준)을 따른 것이며,
# 실제 LLM의 intent 분류 결과에 따라 달라질 수 있다(특히 predict_and_optimize, clarify 케이스).
# "[확인 필요]"로 표시되는 결과는 실패가 아니라 "코드를 읽고 예상한 값과 다르다"는 뜻이다.
#
# 사용법:
#   bash test/web_smoke_test.sh
#   BASE_URL=http://127.0.0.1:9000 bash test/web_smoke_test.sh

set -uo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
PASS=0
TOTAL=0
LAST_STATUS=""
LAST_SESSION_ID=""

# 보기 좋은 JSON 출력. jq가 있으면 jq, 없으면 python -m json.tool을 쓴다.
pp() {
  if command -v jq >/dev/null 2>&1; then
    jq . 2>/dev/null || cat
  else
    python3 -m json.tool 2>/dev/null || cat
  fi
}

# 응답 JSON 문자열과 키를 받아 값을 출력한다. 파싱 실패/키 없음이면 빈 문자열을 출력한다.
json_get() {
  python3 -c '
import json, sys
try:
    d = json.loads(sys.argv[1])
    v = d.get(sys.argv[2])
    print(v if v is not None else "")
except Exception:
    print("")
' "$1" "$2"
}

# query(그리고 선택적으로 session_id)를 받아 /chat/predict 요청 본문 JSON을 만든다.
# python으로 생성해 따옴표·퍼센트 기호 등 이스케이프 문제를 피한다.
build_body() {
  python3 - "$@" <<'PY'
import json, sys
query = sys.argv[1]
session_id = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
body = {"query": query}
if session_id:
    body["session_id"] = session_id
print(json.dumps(body, ensure_ascii=False))
PY
}

# 제목·기대 status·요청 본문을 받아 /chat/predict를 호출하고 결과를 출력한다.
# 성공 시 LAST_STATUS / LAST_SESSION_ID 전역 변수를 갱신한다.
call_predict() {
  local title="$1" expected="$2" body="$3"
  TOTAL=$((TOTAL + 1))
  echo
  echo "=== [$TOTAL] $title ==="
  echo "요청 본문: $body"
  local resp
  resp="$(curl -sS --max-time 60 -X POST "$BASE_URL/chat/predict" \
    -H "Content-Type: application/json" -d "$body")"
  local curl_rc=$?
  if [[ $curl_rc -ne 0 || -z "$resp" ]]; then
    echo "[FAIL] 요청 실패 (curl 종료 코드: $curl_rc). 서버가 $BASE_URL 에서 실행 중인지 확인하세요."
    LAST_STATUS=""
    LAST_SESSION_ID=""
    return
  fi
  echo "$resp" | pp
  LAST_STATUS="$(json_get "$resp" status)"
  LAST_SESSION_ID="$(json_get "$resp" session_id)"
  if [[ "$LAST_STATUS" == "$expected" ]]; then
    echo "[PASS] status=$LAST_STATUS"
    PASS=$((PASS + 1))
  else
    echo "[확인 필요] status=$LAST_STATUS (기대: $expected) - 실제 LLM intent 분류 결과에 따라 달라질 수 있음"
  fi
}

echo "### 0. 서버 설정 확인: GET /health ###"
HEALTH_RESP="$(curl -sS --max-time 10 "$BASE_URL/health")"
if [[ -z "$HEALTH_RESP" ]]; then
  echo "[FAIL] /health 응답 없음. 서버가 $BASE_URL 에서 실행 중인지 먼저 확인하세요 (bash aihub/web/ui.sh)."
  echo "### 중단: 서버에 연결할 수 없어 이후 테스트를 진행하지 않습니다. ###"
  exit 1
fi
echo "$HEALTH_RESP" | pp

# --- 조건 12개를 모두 채운 질의(두 테스트에서 공용으로 사용) ---
FULL_QUERY='LINE-BPR-01 주간조에서 SIM-SUP-B 자재로 533개 생산 예정입니다. 작업장 습도는 54.49%, 입고 자재 품질점수 83.95, 코팅 목표두께 79.22um, 용접 에너지 설정 92.67%, 지그 정렬 오프셋 0.112mm, 공정 설정편차 13.06%, 공구 마모도 14.41%이고 마지막 정비 후 30일 지났습니다.'

echo
echo "### 1. predict 계열 ###"

# 1-1. predict: 조건을 한 번에 모두 입력 -> ok
call_predict "predict (조건 전체 입력)" "ok" \
  "$(build_body "${FULL_QUERY} 결함률 예측해주세요.")"

# 1-2. predict: 조건 일부만 입력 -> need_more_info (세션 ID를 이어서 2-turn 테스트에 사용)
call_predict "predict (조건 일부만 입력 -> 되묻기)" "need_more_info" \
  "$(build_body "LINE-BPR-01 결함률 예측해줘")"
PARTIAL_SESSION="$LAST_SESSION_ID"

# 1-3. 같은 세션으로 나머지 11개 값을 이어서 입력 -> ok (멀티턴 슬롯 필링)
if [[ -n "$PARTIAL_SESSION" ]]; then
  REMAIN_QUERY='야간조 SIM-SUP-A 자재로 200개 생산, 작업장 습도 50%, 입고 자재 품질점수 80, 코팅 목표두께 75um, 용접 에너지 설정 90%, 지그 정렬 오프셋 0.1mm, 공정 설정편차 10%, 공구 마모도 20%, 마지막 정비 후 15일 지났습니다.'
  call_predict "predict (멀티턴 - 같은 세션에 나머지 값 입력)" "ok" \
    "$(build_body "$REMAIN_QUERY" "$PARTIAL_SESSION")"
else
  echo "[건너뜀] 이전 단계에서 session_id를 얻지 못해 멀티턴 테스트를 생략합니다."
fi

# 1-4. invalid_input: 허용되지 않는 라인 코드
INVALID_LINE_QUERY='LINE-BPR-99 주간조에서 SIM-SUP-B 자재로 533개 생산 예정입니다. 작업장 습도는 54.49%, 입고 자재 품질점수 83.95, 코팅 목표두께 79.22um, 용접 에너지 설정 92.67%, 지그 정렬 오프셋 0.112mm, 공정 설정편차 13.06%, 공구 마모도 14.41%이고 마지막 정비 후 30일 지났습니다. 결함률 예측해주세요.'
call_predict "predict (허용되지 않는 라인 값 -> invalid_input)" "invalid_input" \
  "$(build_body "$INVALID_LINE_QUERY")"

echo
echo "### 2. 최적화 계열 (신규) ###"

# 2-1. optimize_reduce_defect: 조건 입력 없이도 동작해야 한다
call_predict "optimize_reduce_defect (조건 입력 없이 불량 최소화 조건 요청)" "ok" \
  "$(build_body "불량률을 줄이려면 어떤 공정 조건이 좋을지 알려줘")"

# 2-2. optimize_find_defect_risk
call_predict "optimize_find_defect_risk (위험 조건 탐색)" "ok" \
  "$(build_body "불량이 발생하기 쉬운 위험한 공정 조건을 찾아줘")"

# 2-3. predict_and_optimize: 조건 + 최적화를 함께 요청
call_predict "predict_and_optimize (예측 + 최적화 동시 요청)" "ok" \
  "$(build_body "${FULL_QUERY} 결함률도 예측해주고, 불량을 줄이려면 어떻게 바꿔야 할지도 알려줘.")"

# 2-4. clarify: 방향이 불분명한 최적화 요청
call_predict "clarify (방향 불분명 -> 되묻기)" "clarify" \
  "$(build_body "최적화 좀 해줘")"

echo
echo "### 3. 세션 삭제: DELETE /chat/session/{id} ###"
if [[ -n "${PARTIAL_SESSION:-}" ]]; then
  TOTAL=$((TOTAL + 1))
  echo "대상 세션: $PARTIAL_SESSION"
  DEL_RESP="$(curl -sS --max-time 10 -o /dev/null -w "%{http_code}" -X DELETE \
    "$BASE_URL/chat/session/$PARTIAL_SESSION")"
  if [[ "$DEL_RESP" == "200" ]]; then
    echo "[PASS] HTTP $DEL_RESP"
    PASS=$((PASS + 1))
  else
    echo "[확인 필요] HTTP $DEL_RESP (기대: 200)"
  fi
  # 이미 지운 세션을 다시 삭제하면 404여야 한다.
  TOTAL=$((TOTAL + 1))
  DEL_AGAIN="$(curl -sS --max-time 10 -o /dev/null -w "%{http_code}" -X DELETE \
    "$BASE_URL/chat/session/$PARTIAL_SESSION")"
  if [[ "$DEL_AGAIN" == "404" ]]; then
    echo "[PASS] 이미 삭제된 세션 재삭제 -> HTTP $DEL_AGAIN"
    PASS=$((PASS + 1))
  else
    echo "[확인 필요] 이미 삭제된 세션 재삭제 -> HTTP $DEL_AGAIN (기대: 404)"
  fi
else
  echo "[건너뜀] 삭제할 session_id가 없습니다."
fi

echo
echo "### 결과: $PASS / $TOTAL 건이 기대 status와 일치 ###"
echo "(predict_and_optimize·clarify 등은 실제 LLM 분류 결과에 따라 기대와 다를 수 있습니다."
echo " '[확인 필요]'는 실패가 아니라 직접 응답 내용을 확인하라는 의미입니다.)"
