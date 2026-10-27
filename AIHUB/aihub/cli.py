from __future__ import annotations

import argparse
import json
import logging
import sys

from .config import get_settings
from .pipeline import DefectRatePipeline, SlotFillingSession


def main() -> int:
    """단일 질의 또는 대화형 CLI를 실행하고 프로세스 종료 코드를 반환한다."""
    # 질의는 선택 인자이며, 출력 형식과 LLM 해설 생성 여부를 옵션으로 받는다.
    parser = argparse.ArgumentParser(description="AIHUB 결함률 예측 어시스턴트")
    parser.add_argument("query", nargs="?", help="자연어 질의 (생략 시 대화형 모드)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-explain", action="store_true")
    args = parser.parse_args()

    # 공통 설정의 로그 수준을 CLI에도 적용한다.
    logging.basicConfig(
        level=get_settings().log_level, format="%(levelname)s %(name)s | %(message)s"
    )
    try:
        pipe = DefectRatePipeline()
    except RuntimeError as e:
        # 초기화 실패는 표준 오류로 출력하고 비정상 종료 코드로 알린다.
        print(e, file=sys.stderr)
        return 1

    # 실행 중에는 같은 세션을 사용하여 이전 입력의 슬롯 값을 유지한다.
    session = SlotFillingSession()

    def handle(q: str) -> None:
        """한 번의 질의를 처리하고 선택된 형식으로 결과를 출력한다."""
        res = pipe.run(q, session=session, explain=not args.no_explain)
        if args.json:
            # 한글을 그대로 출력하고 기본 JSON 타입이 아닌 값은 문자열로 변환한다.
            print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2, default=str))
            return
        print(f"\n[{res.status}]")
        print(res.answer)
        if res.predictions:
            # 예측값은 이미 퍼센트 단위이므로 배율 변환 없이 표시한다.
            preds = ", ".join(f"{p:.2f}%" for p in res.predictions)
            print(f"\npredictions = [{preds}]  ({res.latency_ms}ms)")

    # 위치 인자로 질의를 받으면 한 번만 처리한 뒤 종료한다.
    if args.query:
        handle(args.query)
        return 0

    # 질의가 없으면 입력을 반복해서 받으며 reset, exit, quit 명령을 처리한다.
    print("🤖 질의를 입력하세요. (reset: 세션 초기화, exit: 종료)")
    while True:
        try:
            q = input("\n> ").strip()
        # 입력 종료나 사용자 인터럽트는 정상 종료로 처리한다.
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not q:
            continue
        if q.lower() in {"exit", "quit"}:
            return 0
        if q.lower() == "reset":
            session.reset()
            print("세션을 초기화했습니다.")
            continue
        handle(q)


# 모듈을 직접 실행할 때 main의 반환값을 프로세스 종료 코드로 사용한다.
if __name__ == "__main__":
    sys.exit(main())
