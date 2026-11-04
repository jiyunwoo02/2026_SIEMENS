#!/usr/bin/env bash
# AIHUB-v2 CLI(`python -m aihub`)를 여러 질의로 실행해보는 수동 스모크 테스트 스크립트.
# pytest가 아니라 실제 LLM(+ 예측/최적화 API)을 호출하는 CLI 프로세스를 반복 실행한다.
#
# 전제 조건:
#   1) 프로젝트 루트(AIHUB-v2/)에서 실행해야 .env를 읽는다. 이 스크립트는 자동으로
#      프로젝트 루트로 이동한다.
#   2) 가상환경 활성화 및 `pip install -r requirements.txt` 완료, .env에 LLM 설정 필요.
#   3) 예측 API는 .env의 MOCK_ML=true 로 더미 응답으로 대체할 수 있지만, LLM과
#      최적화 API(OPTIMIZATION_API_URL)는 이 스크립트에서 항상 실제로 호출된다.
#   4) python3, jq(선택, 있으면 status 필드만 보기 좋게 추출) 필요.
#
# [중요] 이 스크립트는 작성 시점에 실제 LLM/최적화 API에 대고 실행해 검증하지 않았다.
# 각 케이스 옆의 "기대 status"는 docs/architecture.md 5~6절(코드 기준)을 따른 것이며,
# 실제 LLM의 intent 분류 결과에 따라 달라질 수 있다(특히 predict_and_optimize, clarify 케이스).
# "[확인 필요]"로 표시되는 결과는 실패가 아니라 "코드를 읽고 예상한 값과 다르다"는 뜻이다.
#
# 사용법:
#   bash test/cli_smoke_test.sh

set -uo pipefail

# 이 스크립트(test/cli_smoke_test.sh) 위치 기준으로 프로젝트 루트(AIHUB-v2/)로 이동한다.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -f .env ]]; then
  echo "[경고] $PROJECT_ROOT/.env 가 없습니다. LLM 설정이 없으면 모든 호출이 실패합니다 (README의 \"설정\" 절 참고)." >&2
fi

PASS=0
TOTAL=0

# JSON 문자열과 키를 받아 값을 출력한다. 파싱 실패/키 없음이면 빈 문자열을 출력한다.
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

# 표준입력으로 받은 텍스트(일반 로그 줄과 여러 줄짜리 JSON 블록이 섞여 있음)에서
# 마지막으로 등장하는 완전한 JSON 객체의 status 값만 뽑는다.
# CLI --json은 json.dumps(..., indent=2)로 여러 줄에 걸쳐 출력하므로 grep으로는 못 뽑고,
# '{' 위치마다 json.JSONDecoder.raw_decode를 시도해 성공하는 객체만 모은다.
last_json_status() {
  python3 -c '
import json, sys
text = sys.stdin.read()
decoder = json.JSONDecoder()
results = []
i, n = 0, len(text)
while i < n:
    start = text.find("{", i)
    if start == -1:
        break
    try:
        obj, end = decoder.raw_decode(text, start)
        results.append(obj)
        i = end
    except json.JSONDecodeError:
        i = start + 1
print(results[-1].get("status", "") if results else "")
'
}

# 제목·기대 status·질의를 받아 `python -m aihub "질의" --json`을 한 번 실행한다(매번 새 세션).
run_single() {
  local title="$1" expected="$2" query="$3"
  TOTAL=$((TOTAL + 1))
  echo
  echo "=== [$TOTAL] $title ==="
  echo "질의: $query"
  local resp
  resp="$(python -m aihub "$query" --json 2>&1)"
  local rc=$?
  if [[ $rc -ne 0 ]]; then
    echo "[FAIL] CLI 종료 코드 $rc (설정 오류 등). 출력:"
    echo "$resp"
    return
  fi
  echo "$resp"
  local status
  status="$(json_get "$resp" status)"
  if [[ "$status" == "$expected" ]]; then
    echo "[PASS] status=$status"
    PASS=$((PASS + 1))
  else
    echo "[확인 필요] status=$status (기대: $expected) - 실제 LLM intent 분류 결과에 따라 달라질 수 있음"
  fi
}

echo "### 1. predict 계열 (단일 실행, 매번 새 세션) ###"

FULL_QUERY='LINE-BPR-01 주간조에서 SIM-SUP-B 자재로 533개 생산 예정입니다. 작업장 습도는 54.49%, 입고 자재 품질점수 83.95, 코팅 목표두께 79.22um, 용접 에너지 설정 92.67%, 지그 정렬 오프셋 0.112mm, 공정 설정편차 13.06%, 공구 마모도 14.41%이고 마지막 정비 후 30일 지났습니다. 결함률 예측해주세요.'

run_single "predict (조건 전체 입력)" "ok" "$FULL_QUERY"

run_single "predict (조건 일부만 입력 -> 되묻기)" "need_more_info" \
  "LINE-BPR-01 결함률 예측해줘"

run_single "predict (허용되지 않는 라인 값 -> invalid_input)" "invalid_input" \
  "LINE-BPR-99 주간조에서 결함률 예측해줘"

echo
echo "### 2. 최적화 계열 (단일 실행) ###"

run_single "optimize_reduce_defect (조건 입력 없이 불량 최소화 조건 요청)" "ok" \
  "불량률을 줄이려면 어떤 공정 조건이 좋을지 알려줘"

run_single "optimize_find_defect_risk (위험 조건 탐색)" "ok" \
  "불량이 발생하기 쉬운 위험한 공정 조건을 찾아줘"

run_single "predict_and_optimize (예측 + 최적화 동시 요청)" "ok" \
  "${FULL_QUERY} 그리고 불량을 줄이려면 어떻게 바꿔야 할지도 알려줘."

run_single "clarify (방향 불분명 -> 되묻기)" "clarify" \
  "최적화 좀 해줘"

echo
echo "### 3. 멀티턴 (대화형 모드 - 같은 프로세스/세션에서 두 번 입력) ###"
echo "같은 세션으로 '조건 일부' -> '나머지 조건'을 순서대로 입력해 need_more_info -> ok 로"
echo "이어지는지 확인한다. 대화형 모드에 reset/exit 명령도 함께 넣어본다."
echo

REMAIN_QUERY='야간조 SIM-SUP-A 자재로 200개 생산, 작업장 습도 50%, 입고 자재 품질점수 80, 코팅 목표두께 75um, 용접 에너지 설정 90%, 지그 정렬 오프셋 0.1mm, 공정 설정편차 10%, 공구 마모도 20%, 마지막 정비 후 15일 지났습니다.'

TOTAL=$((TOTAL + 1))
echo "입력 순서: [1] LINE-BPR-01 결함률 예측해줘  ->  [2] (나머지 값)  ->  reset  ->  exit"
MULTI_OUT="$(printf '%s\n%s\nreset\nexit\n' "LINE-BPR-01 결함률 예측해줘" "$REMAIN_QUERY" | python -m aihub --json 2>&1)"
echo "$MULTI_OUT"
# --json 모드는 턴마다 여러 줄짜리(indent=2) JSON을 출력하므로, 마지막으로 완성된 JSON 객체(두 번째 턴 결과)의 status만 추출한다.
MULTI_STATUS="$(echo "$MULTI_OUT" | last_json_status)"
if [[ "$MULTI_STATUS" == "ok" ]]; then
  echo "[PASS] 멀티턴 두 번째 턴 status=ok"
  PASS=$((PASS + 1))
else
  echo "[확인 필요] 멀티턴 두 번째 턴 status=$MULTI_STATUS (기대: ok)"
fi

echo
echo "### 결과: $PASS / $TOTAL 건이 기대 status와 일치 ###"
echo "(predict_and_optimize·clarify 등은 실제 LLM 분류 결과에 따라 기대와 다를 수 있습니다."
echo " '[확인 필요]'는 실패가 아니라 직접 출력 내용을 확인하라는 의미입니다.)"
