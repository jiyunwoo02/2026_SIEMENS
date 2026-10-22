# 실행·테스트 가이드

## pytest가 뭔가

pytest는 Python 단위 테스트 실행기입니다. `test_*.py` 안의 `test_` 함수를 찾아 실행하고, `assert`가 실패하면 어디서 깨졌는지 보여줍니다.

이 프로젝트에서는 `test/test_core.py`가 pytest 대상입니다. 스키마 정규화, 멀티턴 슬롯 채우기, ML 응답 파싱, 골든셋 G01/G10만 검증합니다. **LLM과 ML 엔드포인트를 호출하지 않으므로** `.env`나 네트워크 없이도 돌아갑니다.

실제 질의 → 추출 → 예측 → 해설은 pytest가 아니라 아래 CLI/curl/HTTP로 확인합니다.

## 준비

워크스페이스 루트의 가상환경을 켠 뒤 `AIHUB`로 이동합니다.

```bash
source /home/jywoo/siemens/venv.sh
cd /home/jywoo/siemens/AIHUB
```

전체 파이프라인(CLI, HTTP)은 `.env`에 다음이 있어야 합니다.

- `api_key` — Siemens SDC LLM
- `LLM_MODEL`
- `AI_HUB_ENDPOINT_URL`

ML만 가짜 값으로 보려면 `MOCK_ML=true` 로 둡니다. LLM은 항상 실제 게이트웨이를 씁니다.

## 1. 로직 테스트 (pytest)

```bash
pytest
```

통과하면 `.` 다섯 개와 `[100%]`가 나옵니다. 실패하면 함수 이름과 assertion 내용이 출력됩니다.

특정 함수만 돌리려면:

```bash
pytest test/test_core.py::test_parse_real_ml_response
```

## 2. ML 엔드포인트만 (curl)

```bash
bash test/curl_test.sh
```

확인할 것:

- HTTP 200
- `prediction(defect_rate_pct)` ≈ `1.6498` (약 1.65%)

## 3. 전체 파이프라인 (CLI)

### `python -m aihub --json`의 의미

다음 명령은 **aihub 패키지를 실행하여 대화형으로 질의를 입력받고, 각 질의의 처리 결과를 JSON으로 출력**합니다.

```bash AIHUB/docs/run.md
python -m aihub --json
```

| 구성 요소 | 의미 |
| --- | --- |
| `python` | 현재 환경의 Python 인터프리터를 실행합니다. |
| `-m` | 뒤의 이름을 Python 모듈 또는 패키지로 찾아 실행하는 Python 옵션입니다. |
| `aihub` | 실행할 패키지 이름입니다. 파일 경로가 아닙니다. |
| `--json` | Python 자체가 아니라 aihub CLI에 전달하는 출력 형식 옵션입니다. |

터미널 앞의 `(.venv)`는 가상환경이 활성화되어 있다는 표시이며 명령어에 포함하지 않습니다. 일반적으로 이 상태의 `python`은 해당 가상환경의 인터프리터를 사용합니다.

### 폴더인 `aihub`를 실행할 수 있는 이유

`AIHUB`는 프로젝트 디렉터리이고, 그 안의 `aihub`는 Python 패키지입니다. Python은 모듈 검색 경로에서 패키지를 찾으며, 이 가이드처럼 `AIHUB`에서 실행하면 현재 디렉터리의 `aihub`를 찾을 수 있습니다.

패키지를 `-m`으로 실행하면 폴더 안의 모든 파일이 실행되는 것이 아니라 **패키지의 `__main__.py`가 진입점으로 실행**됩니다. 다른 모듈은 import되거나 함수가 호출되는 흐름에 따라 사용됩니다.

이 프로젝트의 실제 실행 흐름은 다음과 같습니다.

1. `python -m aihub --json`으로 패키지 실행을 요청합니다.
2. `aihub/__main__.py`가 실행됩니다.
3. `__main__.py`가 `aihub/cli.py`의 `main()`을 호출합니다.
4. `main()`의 `argparse`가 질의와 `--json`, `--no-explain` 옵션을 해석합니다.
5. 설정 검증과 파이프라인 초기화가 성공하면 질의를 처리합니다. 질의를 인자로 주지 않았다면 대화형 입력을 시작합니다.
6. 종료 시 `main()`의 반환값이 `SystemExit`를 통해 프로세스 종료 코드로 전달됩니다.

### 파일 직접 실행과 `-m` 실행의 차이

- `python 파일.py`: 파일 경로를 지정하여 직접 실행합니다.
- `python -m 패키지명`: Python이 패키지를 찾아 `__main__.py`를 실행합니다.
- `python -m 패키지명.모듈명`: 패키지 안의 특정 모듈을 실행합니다.

이 프로젝트는 `from .config import get_settings`처럼 같은 패키지 내부를 참조하는 **상대 import**를 사용합니다. `cli.py`를 파일로 직접 실행하면 패키지 문맥이 없어 상대 import 오류가 발생할 수 있으므로 `python -m aihub` 방식을 권장합니다.

### 질의 유무와 출력 옵션

| 실행 방식 | 동작 |
| --- | --- |
| `python -m aihub` | 대화형으로 입력받고 일반 텍스트로 결과를 출력합니다. |
| `python -m aihub --json` | 대화형으로 입력받고 각 처리 결과를 JSON으로 출력합니다. |
| `python -m aihub "질의 내용" --json` | 해당 질의를 한 번 처리한 뒤 결과를 JSON으로 출력하고 종료합니다. |
| `python -m aihub --json --no-explain` | 대화형 JSON 출력에서 예측 결과의 LLM 해설 생성을 생략합니다. |

공백이 있는 질의는 따옴표로 묶어 하나의 인자로 전달합니다. 한 번만 처리하는 모드에서는 값이 부족하더라도 추가 질문 결과를 출력한 뒤 종료하므로, 이어서 값을 입력하려면 대화형 모드를 사용합니다.

`--json`은 **출력 형식만 변경**합니다. LLM 호출을 끄거나 입력을 JSON으로 받는 옵션은 아닙니다. `--no-explain`도 결과 해설용 LLM 호출만 생략하며, 자연어 입력 추출에는 LLM을 계속 사용합니다.

또한 `--json`을 사용해도 대화형 입력 안내문, 입력 프롬프트, `reset` 확인 메시지는 일반 텍스트입니다. 로그는 별도로 표준 오류에 출력될 수 있으므로, 터미널에 보이는 전체 내용을 하나의 JSON 문서로 간주하면 안 됩니다.

대화형 모드에서는 같은 세션을 유지합니다. `reset`은 저장된 입력값을 초기화하고, `exit` 또는 `quit`은 프로그램을 종료합니다.

### 실행 예시

골든셋 G01 질의. 기대 결과는 `[ok]`와 예측값 약 `1.65%`입니다.

```bash
python -m aihub "LINE-BPR-01 주간조에서 SIM-SUP-B 자재로 533개 생산 예정입니다. 작업장 습도는 54.49%, 입고 자재 품질점수 83.95, 코팅 목표두께 79.22um, 용접 에너지 설정 92.67%, 지그 정렬 오프셋 0.112mm, 공정 설정편차 13.06%, 공구 마모도 14.41%이고 마지막 정비 후 30일 지났습니다. 결함률 예측해주세요."
```

- `--no-explain` — LLM 해설 없이 수치만
- `--json` — `PipelineResult`를 JSON으로 출력

되묻기·멀티턴은 인자 없이 대화형으로 실행합니다.

```bash
python -m aihub
```

예: `LINE-BPR-01 결함률 예측해줘` → 누락 항목을 물어보면 이어서 값을 넣습니다.

- `reset` — 세션 초기화
- `exit` — 종료

## 4. HTTP API

```bash
uvicorn aihub.api:app --reload
```

| 메서드 | 경로 | 용도 |
| --- | --- | --- |
| GET | `/health` | 설정·세션 수 확인 |
| POST | `/chat/predict` | 자연어 → 예측. body: `{"query": "...", "session_id": "선택", "explain": true}` |
| DELETE | `/chat/session/{session_id}` | 세션 삭제 |

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/chat/predict \
  -H 'Content-Type: application/json' \
  -d '{"query":"LINE-BPR-01 결함률 예측해줘"}'
```

응답의 `session_id`를 다음 요청에 넣으면 슬롯이 이어집니다.
