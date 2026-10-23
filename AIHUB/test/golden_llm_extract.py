"""골든 셋 v2의 query를 실제 LLM에 보내 추출한 record를 CSV로 기록하고 expected와 비교한다.

목적:
    data/golden_set_v2.json 의 단일 턴 케이스(C/P/N/A/I)의 query를 실제 SDC LLM 추출기
    (aihub.pipeline.QueryExtractor)에 전달하고, 골든 셋의 expected.records 와 LLM이 실제로
    추출한 records 가 같은지 확인한다. pytest(test_golden_v2.py)는 LLM을 대역으로 쓰므로
    이 스크립트가 "실제 LLM 추출 정확도"를 보는 용도다.

범위와 한계:
    - 추출 단계만 실행한다. ML 예측 API 호출, 세션 병합, Pydantic 검증, 해설 생성은 하지 않는다.
    - 멀티턴 케이스(MT01~MT06)는 포함하지 않는다(세션 병합이 필요하여 별도 스크립트로 분리 권장).
    - LLM 응답은 호출마다 달라질 수 있다. 한 번의 결과로 정확도를 단정하지 말고 반복 실행해 비교한다.
    - 이 스크립트 자체는 아직 테스트되지 않았다(작성 시점에 실행 확인 없음).

전제 조건:
    - 패키지 설치: pip install -r requirements.txt
    - AIHUB/.env 에 api_key(또는 llm_api_key), LLM_MODEL 설정. ML 관련 설정은 필요 없다.
    - 실제 LLM 게이트웨이로 네트워크 호출이 발생한다(케이스 수만큼). 비용·쿼터에 유의한다.

실행 (어느 디렉터리에서든 가능. 스크립트가 AIHUB/ 로 이동해 .env 를 읽는다):
    python test/golden_llm_extract.py                  # 전체 단일 턴 케이스
    python test/golden_llm_extract.py --only C01,P03   # 케이스 ID 접두어로 선택
    python test/golden_llm_extract.py --out-dir /tmp/r # 결과 폴더 지정

출력(기본 test/results/):
    golden_v2_llm_records_<시각>.csv : LLM이 추출한 실제 record (레코드당 1행) + expected와의 일치 여부
    golden_v2_llm_diff_<시각>.csv    : 불일치 항목만 필드 단위로 정리 (expected vs actual)
    (컬럼별 의미는 아래 RECORD_COLUMNS, DIFF_COLUMNS 주석 참고)
    CSV는 Excel에서 한글이 깨지지 않도록 UTF-8 BOM(utf-8-sig)으로 저장한다. 빈 칸은 null(None)이다.

보안: 질의·LLM 응답이 파일로 저장된다. 골든 셋은 합성 데이터이지만, 실제 데이터를 query에 넣었다면
    결과 파일을 공유·커밋하기 전에 확인한다. api_key 는 출력 파일에 기록하지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# AIHUB 루트. 스크립트를 어느 위치에서 실행해도 aihub 패키지를 import 하고 .env 를 찾도록 한다.
# (Settings 는 "현재 작업 디렉터리의 .env" 를 읽는다.)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from aihub.config import get_settings  # noqa: E402
from aihub.llm import SDCLLMClient  # noqa: E402
from aihub.pipeline import QueryExtractor  # noqa: E402
from aihub.schema import ALL_FIELDS  # noqa: E402

GOLDEN_PATH = ROOT / "data" / "golden_set_v2.json"
DEFAULT_OUT_DIR = ROOT / "test" / "results"

# 레코드 CSV(golden_v2_llm_records_*.csv)의 컬럼. LLM이 추출한 레코드 1개당 1행이다.
# 12개 필드는 schema.ALL_FIELDS 순서를 따른다. 빈 칸은 null(None)이다.
#
# [컬럼 설명] (주석만 추가, 로직 변경 없음)
#   case_id                   골든 셋 케이스 ID (예: C01-complete-natural)
#   category                  골든 셋 분류: complete / partial / none / ambiguous / invalid
#   record_index              LLM이 추출한 레코드의 순번(0부터). 아래 두 경우는 빈 칸
#                             - LLM이 records=[] 를 반환(예: N05), - LLM 호출 오류(행 1개만 기록)
#   12개 필드(ALL_FIELDS)     LLM이 실제로 추출한 값. QueryExtractor 후처리가 끝난 결과다
#                             (타입 변환, 실수 소수점 6자리 반올림, 코드 대문자화,
#                              ambiguous_fields에 든 필드는 null). expected 값이 아니다.
#   expected_record_count     골든 셋 expected.records 의 레코드 개수
#   actual_record_count       LLM이 추출한 레코드 개수 (오류면 빈 칸)
#   record_match              이 행(레코드)의 12개 필드가 expected 의 같은 인덱스 레코드와
#                             모두 같으면 Y, 하나라도 다르면 N. 이 행만 보는 값이라 레코드 개수
#                             차이는 반영되지 않는다(예: expected 2개, actual 1개여도 0번이
#                             맞으면 Y). 개수 차이는 case_match 와 diff CSV에서 확인한다.
#                             records=[] 인 빈 행은 케이스 전체에 불일치가 없으면 Y.
#   mismatch_fields           expected 와 다른 필드명(세미콜론 ';' 구분). "(record)" 는
#                             expected 에 없는 레코드를 LLM이 추가로 추출했다는 뜻
#   expected_ambiguous_fields 골든 셋의 모호 필드 목록 (';' 구분, 없으면 빈 칸)
#   actual_ambiguous_fields   LLM이 모호하다고 표시한 필드 목록 (';' 구분, 오류면 빈 칸)
#   ambiguous_match           두 모호 필드 목록이 같으면 Y (순서 무관), 다르면 N (오류면 빈 칸)
#   case_match                케이스 최종 판정. 레코드 개수, 모든 레코드의 모든 필드, ambiguous 목록이
#                             모두 같으면 Y, 하나라도 다르면 N, LLM 호출이 실패하면 ERROR.
#                             같은 케이스의 모든 행에 동일한 값이 들어 있다.
#   llm_notes                 LLM이 응답 JSON의 notes 에 적은 텍스트(있을 때만). 참고용이며 채점에 쓰지 않는다.
#   error                     LLM 호출 실패 시 예외 종류와 메시지 (정상이면 빈 칸)
#   elapsed_sec               케이스 1개의 extract() 호출 소요 시간(초). json_schema → json_object →
#                             prompt 폴백 재시도 시간을 포함한다. 같은 케이스의 행마다 동일한 값.
#   llm_model                 실행에 사용한 모델 이름(.env 의 LLM_MODEL)
#   query                     골든 셋의 질의 원문(LLM에 그대로 전달한 문장)
RECORD_COLUMNS = [
    "case_id",
    "category",
    "record_index",
    *ALL_FIELDS,
    "expected_record_count",
    "actual_record_count",
    "record_match",
    "mismatch_fields",
    "expected_ambiguous_fields",
    "actual_ambiguous_fields",
    "ambiguous_match",
    "case_match",
    "llm_notes",
    "error",
    "elapsed_sec",
    "llm_model",
    "query",
]
# 불일치 CSV(golden_v2_llm_diff_*.csv)의 컬럼. 불일치 항목 1개당 1행이다. 불일치가 없으면 헤더만 있다.
#   case_id, category  위 레코드 CSV와 동일
#   record_index       불일치가 발생한 레코드 순번(0부터). 빈 칸이면 레코드가 아니라
#                      케이스 수준의 항목(ambiguous_fields 비교, 오류)이다.
#   field              다른 항목의 이름. 아래 중 하나
#                      - 12개 필드명: 해당 필드의 값이 다름
#                      - "(record)": 레코드 자체가 한쪽에만 있음(개수 차이). expected/actual 에 "있음"/"없음"
#                      - "(ambiguous_fields)": 모호 필드 목록이 다름. expected/actual 은 ';' 구분 목록
#                      - "(error)": LLM 호출 실패. actual 에 오류 메시지
#   expected           골든 셋의 기대값 (null 은 빈 칸)
#   actual             LLM이 실제로 추출한 값 (null 은 빈 칸)
DIFF_COLUMNS = ["case_id", "category", "record_index", "field", "expected", "actual"]


def values_equal(expected: Any, actual: Any) -> bool:
    """두 필드 값이 같은지 비교한다. None은 None끼리만 같고, 숫자는 부동소수점 오차를 허용한다."""
    if expected is None or actual is None:
        return expected is None and actual is None
    both_numbers = (
        isinstance(expected, (int, float))
        and isinstance(actual, (int, float))
        and not isinstance(expected, bool)
        and not isinstance(actual, bool)
    )
    if both_numbers:
        # QueryExtractor._coerce 가 소수점 6자리로 반올림하므로 1e-6 절대 오차까지 같은 값으로 본다.
        return math.isclose(expected, actual, rel_tol=1e-9, abs_tol=1e-6)
    return expected == actual


def compare_records(
    expected: list[dict[str, Any]], actual: list[dict[str, Any]]
) -> tuple[dict[int, list[str]], list[tuple[int, str, Any, Any]]]:
    """expected.records 와 실제 records 를 인덱스 순서로 비교한다.

    입력: 골든 셋 기대 레코드 목록, LLM 추출 레코드 목록
    출력:
        - {actual 레코드 인덱스: 불일치 필드 목록}  (actual 에 존재하는 레코드만)
        - 필드 단위 불일치 목록 [(레코드 인덱스, 필드, expected, actual)]
          레코드 개수가 다르면 필드 "(record)" 로 "있음/없음" 을 기록한다.
    비교는 순서 기준이다. LLM이 비교 질의의 레코드 순서를 바꾸면 불일치로 나온다.
    """
    per_record: dict[int, list[str]] = {i: [] for i in range(len(actual))}
    diffs: list[tuple[int, str, Any, Any]] = []
    for i in range(max(len(expected), len(actual))):
        exp = expected[i] if i < len(expected) else None
        act = actual[i] if i < len(actual) else None
        if exp is None or act is None:
            diffs.append((i, "(record)", "있음" if exp is not None else "없음", "있음" if act is not None else "없음"))
            if act is not None:
                per_record[i].append("(record)")
            continue
        for f in ALL_FIELDS:
            if not values_equal(exp.get(f), act.get(f)):
                per_record[i].append(f)
                diffs.append((i, f, exp.get(f), act.get(f)))
    return per_record, diffs


def cell(value: Any) -> Any:
    """CSV 셀 값을 만든다. None 은 빈 칸으로 쓴다."""
    return "" if value is None else value


def run_case(
    extractor: QueryExtractor, case: dict[str, Any], llm_model: str
) -> tuple[list[dict[str, Any]], list[tuple[int, str, Any, Any]]]:
    """케이스 하나를 LLM에 보내고 (메인 CSV 행 목록, 필드 단위 불일치 목록)을 반환한다."""
    case_id = case["id"]
    expected = case["expected"]
    exp_records = expected.get("records", [])
    exp_amb = [f for f in ALL_FIELDS if f in set(expected.get("ambiguous_fields", []))]

    base = {
        "case_id": case_id,
        "category": case.get("category", ""),
        "expected_record_count": len(exp_records),
        "expected_ambiguous_fields": ";".join(exp_amb),
        "llm_model": llm_model,
        "query": case["query"],
    }

    started = time.perf_counter()
    try:
        result = extractor.extract(case["query"])
    except Exception as e:  # noqa: BLE001 - 배치 실행이므로 한 케이스의 실패가 전체를 멈추지 않게 한다.
        elapsed = round(time.perf_counter() - started, 2)
        row = {
            **base,
            "actual_record_count": "",
            "case_match": "ERROR",
            "error": f"{type(e).__name__}: {e}",
            "elapsed_sec": elapsed,
        }
        return [row], [(-1, "(error)", "", row["error"])]
    elapsed = round(time.perf_counter() - started, 2)

    actual = result.records
    act_amb = list(result.ambiguous_fields)  # extract() 가 ALL_FIELDS 순서로 정렬해 반환
    per_record, diffs = compare_records(exp_records, actual)
    amb_match = set(exp_amb) == set(act_amb)
    if not amb_match:
        diffs.append((-1, "(ambiguous_fields)", ";".join(exp_amb), ";".join(act_amb)))
    case_match = "Y" if not diffs else "N"

    common = {
        **base,
        "actual_record_count": len(actual),
        "actual_ambiguous_fields": ";".join(act_amb),
        "ambiguous_match": "Y" if amb_match else "N",
        "case_match": case_match,
        "llm_notes": result.notes or "",
        "error": "",
        "elapsed_sec": elapsed,
    }

    rows: list[dict[str, Any]] = []
    if not actual:
        # records=[] 인 경우(예: N05)에도 케이스가 CSV에서 사라지지 않도록 빈 행 1개를 쓴다.
        rows.append({**common, "record_index": "", "record_match": "Y" if not diffs else "N", "mismatch_fields": ""})
    for i, rec in enumerate(actual):
        mism = per_record.get(i, [])
        rows.append(
            {
                **common,
                "record_index": i,
                **{f: cell(rec.get(f)) for f in ALL_FIELDS},
                "record_match": "Y" if not mism else "N",
                "mismatch_fields": ";".join(mism),
            }
        )
    return rows, diffs


def select_cases(cases: list[dict[str, Any]], only: str | None) -> list[dict[str, Any]]:
    """--only 값(쉼표 구분 ID 접두어, 예: C01,P03)으로 케이스를 고른다. 없으면 전체."""
    if not only:
        return cases
    prefixes = [p.strip() for p in only.split(",") if p.strip()]
    return [c for c in cases if any(c["id"].startswith(p) for p in prefixes)]


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="골든 셋 v2 query를 실제 LLM에 보내 추출 record를 CSV로 기록한다.")
    p.add_argument("--only", help="실행할 케이스 ID 접두어(쉼표 구분). 예: C01,P03,A")
    p.add_argument("--golden", type=Path, default=GOLDEN_PATH, help="골든 셋 JSON 경로")
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="CSV 저장 폴더")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    settings = get_settings()
    # 추출만 하므로 ML 엔드포인트 설정은 검사하지 않는다(validate_runtime 은 사용하지 않음).
    missing_cfg = [
        name for name, ok in (("api_key", settings.api_key), ("LLM_MODEL", settings.llm_model)) if not ok
    ]
    if missing_cfg:
        print(f"설정 누락: {', '.join(missing_cfg)} (AIHUB/.env 확인)", file=sys.stderr)
        return 2

    golden = json.loads(args.golden.read_text(encoding="utf-8"))
    # query 필드가 있는 단일 턴 케이스만 대상이다. 멀티턴은 golden["multi_turn_cases"] 로 별도 관리된다.
    cases = select_cases(golden["cases"], args.only)
    if not cases:
        print(f"선택된 케이스가 없습니다: --only {args.only}", file=sys.stderr)
        return 2

    extractor = QueryExtractor(client=SDCLLMClient(settings))
    print(f"모델={settings.llm_model}, 케이스 {len(cases)}개 실행 (실제 LLM 호출)")

    all_rows: list[dict[str, Any]] = []
    diff_rows: list[dict[str, Any]] = []
    summary: list[tuple[str, str]] = []
    for n, case in enumerate(cases, 1):
        rows, diffs = run_case(extractor, case, settings.llm_model)
        all_rows.extend(rows)
        for idx, field, exp, act in diffs:
            diff_rows.append(
                {
                    "case_id": case["id"],
                    "category": case.get("category", ""),
                    "record_index": "" if idx < 0 else idx,
                    "field": field,
                    "expected": cell(exp),
                    "actual": cell(act),
                }
            )
        status = rows[0]["case_match"]
        summary.append((case["id"], status))
        print(f"[{n}/{len(cases)}] {case['id']}: {status}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    records_path = args.out_dir / f"golden_v2_llm_records_{stamp}.csv"
    diff_path = args.out_dir / f"golden_v2_llm_diff_{stamp}.csv"
    # utf-8-sig: Excel에서 한글 query가 깨지지 않도록 BOM을 붙인다.
    with records_path.open("w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=RECORD_COLUMNS, extrasaction="ignore", restval="")
        w.writeheader()
        w.writerows(all_rows)
    with diff_path.open("w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=DIFF_COLUMNS)
        w.writeheader()
        w.writerows(diff_rows)

    matched = sum(1 for _, s in summary if s == "Y")
    errors = [cid for cid, s in summary if s == "ERROR"]
    mismatched = [cid for cid, s in summary if s == "N"]
    print(f"\n일치 {matched}/{len(summary)}, 불일치 {len(mismatched)}, 오류 {len(errors)}")
    if mismatched:
        print("불일치 케이스:", ", ".join(mismatched))
    if errors:
        print("오류 케이스:", ", ".join(errors))
    print(f"레코드 CSV: {records_path}")
    print(f"불일치 CSV: {diff_path}")
    # 불일치가 있어도 종료 코드는 0이다. 이 스크립트는 pass/fail 테스트가 아니라 비교 리포트용이다.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
