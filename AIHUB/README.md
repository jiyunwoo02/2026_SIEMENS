# AIHUB

한국어 자연어 질의에서 공정 조건 12개를 추출해 외부 결함률 예측 API로 전달하고, 반환된 예측값(%)을 LLM이 해설하는 대화형 서비스입니다. CLI, HTTP API, 로컬 웹 UI로 사용할 수 있습니다.

- 핵심 원칙: **추측 금지**. 질의에 없거나 모호한 값은 `null`로 두고, 외부 예측 API를 호출하지 않은 채 추가 입력을 되묻습니다.
- 저장소 전체 개요: [`../README.md`](../README.md)
- 같은 입력 컬럼을 쓰는 로컬 학습 데모: [`../ICX_DEMO/README.md`](../ICX_DEMO/README.md) (코드 연동은 없음)

## 폴더 구조

```text
AIHUB/
├── .env                 로컬 전용 설정 (Git 제외, 직접 작성)
├── pyproject.toml       pytest 설정
├── requirements.txt     의존성
├── aihub/               애플리케이션 패키지
│   ├── cli.py           한 줄 / 대화형 CLI (python -m aihub)
│   ├── api.py           FastAPI: UI, /health, /chat/predict, 세션 삭제
│   ├── config.py        설정 로드·검증
│   ├── schema.py        12개 입력 필드, 검증 모델, 추출 JSON Schema
│   ├── llm.py           SDC LLM 클라이언트, 추출·해설 프롬프트
│   ├── ml.py            예측 API 클라이언트 (재시도, 응답·에코 검증)
│   ├── pipeline.py      추출 → 세션 병합 → 검증 → 예측 → 해설
│   └── web/             로컬 웹 UI (index.html, app.js, style.css, ui.sh)
├── data/                골든 셋(v2, v1), 예측용 입력 CSV
├── docs/                상세 문서 (아래 참고)
└── test/                pytest 3종 + curl 스모크 스크립트
```

## 설치

전제: Python 가상환경. `pyproject.toml`에 지원 Python 버전이 선언되어 있지 않으므로 사용 환경에서 직접 확인해야 합니다. 의존성은 최소 버전 제약이며 고정 버전이 아닙니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

주요 의존성: `pydantic`, `pydantic-settings`, `python-dotenv`, `httpx`, `fastapi`, `uvicorn[standard]`, `pytest`

## 설정

현재 작업 디렉터리의 `.env`를 읽으므로 **`AIHUB/`에서 실행**해야 합니다. 환경 변수가 `.env`보다 우선하고, 설정은 프로세스에 캐시되므로 변경 후 재시작해야 합니다.

```dotenv
# AIHUB/.env (예시: 값은 직접 채우고 절대 커밋하지 마세요)
api_key=<SDC LLM 인증 키>
LLM_MODEL=<사용할 모델 이름>
AI_HUB_ENDPOINT_URL=<예측 API 주소>
# MOCK_ML=true   # ML만 더미 예측(1.65, 2.65, ...)으로 대체. LLM은 실제 호출
```

전체 설정 항목은 `aihub/config.py`를 참고하세요.

## 실행

```bash
python -m aihub                          # 대화형 CLI (reset: 세션 초기화, exit: 종료)
python -m aihub "질의 내용" --json       # 한 번 처리 후 JSON 출력
python -m uvicorn aihub.api:app --reload --host 127.0.0.1 --port 8000   # HTTP API + 웹 UI
```

웹 UI는 서버 실행 후 `http://127.0.0.1:8000/`로 접속합니다. 파일로 직접 열면 안 됩니다.

| 메서드 | 경로 | 용도 |
|---|---|---|
| GET | `/health` | 설정 요약, 활성 세션 수 |
| POST | `/chat/predict` | 자연어 → 예측 (`query`, `session_id`, `explain`) |
| DELETE | `/chat/session/{session_id}` | 세션 삭제 |

응답 `status`는 `ok`, `need_more_info`, `invalid_input`, `llm_error`, `endpoint_error` 5종이며 모두 HTTP 200으로 전달될 수 있습니다. HTTP 성공을 예측 성공으로 판단하면 안 됩니다.

## 테스트

```bash
python -m pytest              # LLM·ML 미호출, .env·네트워크 불필요
bash test/curl_test.sh        # ML 엔드포인트만 직접 호출 (네트워크 필요)
```

pytest는 LLM 추출을 대역으로 대체하므로, 실제 LLM의 추출 정확도는 별도 평가가 필요합니다.

## 문서

| 문서 | 내용 |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | 파이프라인 설계, 상태 정의, 멀티턴, 미결 사항 |
| [`docs/input_schema.md`](docs/input_schema.md) | 12개 입력 필드와 규칙 |
| [`docs/run.md`](docs/run.md) | pytest, CLI, HTTP, curl 실행 가이드 |
| [`docs/web_ui.md`](docs/web_ui.md) | 로컬 웹 UI 구현, API 계약, 제약 |
| [`docs/code_inventory.md`](docs/code_inventory.md) | 파일별 역할 목록 |

## 주의

- 로컬 테스트용입니다. 사용자 인증과 세션 소유권 검증이 없어 공개 서비스로 노출하면 안 됩니다.
- 입력 조건은 설정된 외부 LLM/ML 서비스로 전송됩니다. 비밀번호, API 키, 개인정보를 입력하지 마세요.
- 세션은 서버 프로세스 메모리에만 저장되며 재시작하면 사라집니다.
- `docs/run.md`의 준비 단계에는 작성자 환경의 절대 경로(`/home/jywoo/siemens/...`)가 들어 있습니다. 다른 환경에서는 경로를 바꿔 사용하세요.

> 이 문서는 소스와 `docs/`를 읽고 작성했으며, 실행해 확인하지는 않았습니다.
