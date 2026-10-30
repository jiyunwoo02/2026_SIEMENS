# AIHUB-v2

한국어 자연어 질의에서 공정 조건 12개를 추출해 외부 결함률 예측 API로 전달하고 결과를 해설하는 기존 [`AIHUB`](../AIHUB/README.md) 챗봇에, **공정 최적화(불량 최소화 / 위험 조건 탐색) 기능**을 추가한 버전입니다. CLI, HTTP API, 로컬 웹 UI로 사용할 수 있습니다.

> 이 문서는 `aihub/` 소스와 `docs/agent-v2/`를 읽고 작성했습니다. **CLI·HTTP·실제 LLM/최적화 API 호출로 검증한 결과는 아님**을 먼저 밝힙니다(이 프로젝트는 pytest를 사용하지 않습니다 — 아래 "테스트" 절 참고). 실행 확인 방법은 [테스트](#테스트) 절을 참고하세요.

## 핵심 원칙 (기존 AIHUB와 동일하게 유지)

- **추측 금지**: 질의에 없거나 모호한 값은 `null`로 두고, 예측 API를 호출하지 않은 채 추가 입력을 되묻습니다.
- **의도(intent) 숫자 변환은 LLM이 하지 않습니다**: LLM은 `predict` / `optimize_reduce_defect` / `optimize_find_defect_risk` / `predict_and_optimize` / `predict_and_find_risk` / `clarify` 중 하나만 고르고, 최적화 API의 `target`(`"0"`/`"1"`) 값으로의 변환은 코드(`optimization.build_target`)가 고정 사전으로 수행합니다(환각 방지).
  <!-- [수정] 2026-10-29: predict_and_find_risk 추가. 아래 "배경" 절 설명 참고. -->

## 이 프로젝트의 배경 (중요 — 명세서 2종과 실제 구현의 차이)

`docs/agent-v2/`에는 최적화 기능에 대한 명세서가 **2개** 있으며 서로 다른 설계를 제안합니다.

| 문서 | 제안한 설계 | 실제 구현과의 관계 |
|---|---|---|
| [`docs/agent-v2/optimization_chatbot_spec.md`](docs/agent-v2/optimization_chatbot_spec.md) | 기존 챗봇과 **무관한 독립 프로젝트**로 최적화 전용 챗봇을 새로 만든다 (`intent`는 `optimize_reduce_defect` / `optimize_find_defect_risk` / `clarify` / `out_of_scope` 4종) | **채택되지 않음.** 실제 코드는 기존 예측 파이프라인과 분리되어 있지 않다 |
| [`docs/agent-v2/bak/chatbot_optimization_feature_spec.md`](docs/agent-v2/bak/chatbot_optimization_feature_spec.md) | 기존 예측 파이프라인(`pipeline.py`)에 최적화 의도 3종(`optimize_reduce_defect` / `optimize_find_defect_risk` / `predict_and_optimize`)과 `clarify`를 **통합**한다 | **대부분 일치.** `schema.INTENTS`, `pipeline.py`의 분기, `optimization.py`가 이 문서의 5~6장을 따른다. 단 `predict_and_find_risk`는 이 문서에 **없는** 추가 의도다(아래 설명 참고) |

즉 **실제로 구현된 것은 "통합형"이며, "독립 프로젝트" 명세서(`optimization_chatbot_spec.md`)는 초기 구상안으로만 남아 있고 코드에 반영되지 않았습니다.** `out_of_scope` 의도도 `schema.INTENTS`에는 없습니다(해당 경우는 `predict`로 분류되어 조건 없는 `need_more_info`로 처리되는 것으로 보이며, 실행으로 재확인하지 않았습니다).

<!-- [수정] 2026-10-29: 문서 경로를 `pre-version/`에서 실제 경로 `bak/`로 수정했다(파일시스템 확인 결과 `pre-version/` 디렉터리는 존재하지 않음 - 기존 문서의 오기로 추정). -->

> **[추가] 2026-10-29: `predict_and_find_risk` 의도(명세서에 없는 추가 구현)**
> 위 명세서 5.1은 "예측 + 최적화" 조합을 `predict_and_optimize`(불량 **감소** 방향, `target="1"`) 하나만 정의합니다.
> 그런데 "이 조건 예측하고, 불량이 더 **심해지는** 위험 조건도 알려줘"처럼 **예측 + 위험(악화) 방향** 탐색을 함께 요청하는 발화는
> 표현할 enum 값이 없었습니다. 이런 발화가 `predict_and_optimize`로 분류되면 `target`이 `"1"`로 고정 호출돼 사용자가 원한
> 방향과 **반대 결과**가 나가는 문제가 있어, 명세서에 없는 `predict_and_find_risk`(`target="0"`)를 추가했습니다.
> 관련 코드: `schema.INTENTS`, `optimization.INTENT_TO_TARGET`, `pipeline.DefectRatePipeline._run_predict_and_optimize`,
> `llm.py`의 `EXTRACTION_SYSTEM_PROMPT` [의도 분류] 절. **실제 LLM 호출로 분류 정확도를 검증하지는 않았습니다(추정).**

## 처리 흐름

```text
사용자 질의
  -> [llm.QueryExtractor]   LLM이 intent + 12개 필드를 JSON으로 추출
  -> intent 분기 (pipeline.DefectRatePipeline.run)
       predict                 -> 기존 예측 흐름 (슬롯 병합 -> 검증 -> ml.DefectRateMLClient -> 해설)
       predict_and_optimize    -> 예측 흐름 완료 후 optimization.OptimizationClient(target="1") 추가 호출
                                   (최적화 실패해도 예측 결과는 반환 - 부분 성공)
       predict_and_find_risk   -> 예측 흐름 완료 후 optimization.OptimizationClient(target="0") 추가 호출
                                   ([추가] 2026-10-29, 명세서에 없음 - 위 "배경" 절 참고. 그 외 동작은
                                   predict_and_optimize와 동일, 부분 성공도 동일)
       optimize_reduce_defect  -> optimization.OptimizationClient(target="1")만 호출 (ML/LLM 해설 없음)
       optimize_find_defect_risk -> optimization.OptimizationClient(target="0")만 호출 (ML/LLM 해설 없음)
       clarify                 -> 어떤 API도 호출하지 않고 방향을 되묻는 고정 문구 반환
```

- `predict` 경로의 세부 동작(슬롯 필링, 모호값 재질문, 레코드 비교 등)은 기존 AIHUB와 동일합니다. intent 분기·최적화 연동을 포함한 전체 아키텍처는 [`docs/architecture.md`](docs/architecture.md)에 정리했습니다. `predict` 경로 자체의 더 상세한 배경은 [`AIHUB/docs/architecture.md`](../AIHUB/docs/architecture.md)(원본 구현체 문서)를 참고하세요.
- 최적화 두 의도(`optimize_reduce_defect`, `optimize_find_defect_risk`)는 **사용자가 공정 조건을 입력하지 않아도** 동작합니다. 최적화 API가 조건 자체를 찾아 돌려주기 때문입니다.
- 세션은 서버 프로세스 메모리에만 저장되며 재시작하면 사라집니다(기존과 동일).

## 폴더 구조

```text
AIHUB-v2/
├── .env                 로컬 전용 설정 (Git 제외, 직접 작성 - 아래 "설정" 참고)
├── pyproject.toml       [수정] pytest 미사용 결정으로 설정을 비움(과거 [tool.pytest.ini_options]만 있었음) - 필요 없으면 직접 삭제 가능
├── requirements.txt     의존성
├── aihub/               애플리케이션 패키지
│   ├── __init__.py      공개 API 재노출(DefectRatePipeline 등), __version__
│   ├── __main__.py      python -m aihub 진입점 (cli.main 호출)
│   ├── cli.py           한 줄 / 대화형 CLI
│   ├── api.py           FastAPI: 로컬 웹 UI 정적 제공, /health, /chat/predict, 세션 삭제
│   ├── config.py        .env 설정 로드 (LLM, 예측 API, 최적화 API 3그룹)
│   ├── schema.py        12개 입력 필드, intent enum(INTENTS), 한글 라벨(FIELD_LABELS),
│   │                    조절 불가 필드 목록(UNCONTROLLABLE_FIELDS), 검증, 추출 JSON Schema
│   ├── llm.py           SDC LLM 클라이언트 + 추출 프롬프트(intent 분류 포함) + 해설 프롬프트
│   ├── ml.py            결함률 예측(POST) API 클라이언트 (재시도, 에코 검증) - 변경 없음
│   ├── optimization.py  [신규] 최적화(GET, target 파라미터) API 클라이언트 + intent->target 매핑
│   ├── pipeline.py      intent 분기 오케스트레이션: 추출 -> 세션 병합 -> 검증 -> 예측/최적화 -> 포맷
│   ├── prompt/          추출 프롬프트 변경 이력 스냅샷, 파일명 prompt-v1.py / prompt-v2.py
│   │                    (llm.py가 import하지 않는 미사용 파일. [수정] 소스 재확인 결과 두 파일
│   │                    모두 intent 분류 절을 포함하며, intent 도입 이전 버전이 아니다 -
│   │                    자세한 비교는 docs/code_inventory.md 참고)
│   └── web/             로컬 웹 UI (index.html, app.js, style.css, ui.sh) -
│                        안내 문구에 최적화 사용법을 반영했으나, 최적화 결과 전용 렌더링은
│                        여전히 없음 (아래 "알려진 문제" 참고)
├── docs/
│   └── agent-v2/        최적화 기능 기획 명세서 2종 + AI Studio 트러블슈팅 기록
├── docs/code_inventory.md  파일별 역할 목록
└── test/                [수정] pytest 미사용 결정으로 자동화된 단위 테스트는 없음(아래 "테스트" 절 참고).
    ├── curl_test_classification.sh  최적화 API를 curl로 직접 호출
    ├── web_smoke_test.sh            [신규] 실행 중인 서버에 curl로 /health, /chat/predict,
    │                                 /chat/session/{id}를 호출하는 수동 스모크 테스트
    └── cli_smoke_test.sh            [신규] `python -m aihub`를 여러 질의로 반복 실행하는
                                      수동 스모크 테스트(단일 실행 + 대화형 멀티턴)
```

## 설치

전제: Python 가상환경. `pyproject.toml`에 지원 Python 버전이 명시되어 있지 않아 사용 환경에서 직접 확인해야 합니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

주요 의존성: `pydantic`, `pydantic-settings`, `python-dotenv`, `httpx`, `fastapi`, `uvicorn[standard]` (pytest는 미사용으로 확인되어 [수정] `requirements.txt`에서 제거함)

## 설정

현재 작업 디렉터리의 `.env`를 읽으므로 **`AIHUB-v2/`에서 실행**해야 합니다. 환경 변수가 `.env`보다 우선하고, 설정은 프로세스에 캐시되므로(`config.get_settings` lru_cache) 변경 후 재시작해야 합니다.

```dotenv
# AIHUB-v2/.env (예시: 값은 직접 채우고 절대 커밋하지 마세요)
api_key=<SDC LLM 인증 키>
LLM_MODEL=<사용할 모델 이름>
AI_HUB_ENDPOINT_URL=<결함률 예측 API 주소 (POST)>
# MOCK_ML=true                    # ML만 더미 예측으로 대체. LLM은 실제 호출

# [신규] 최적화 API (없어도 서버는 기동되며, 최적화 의도 호출 시점에만 오류로 안내됨)
OPTIMIZATION_API_URL=<최적화 API 주소 (GET, target 쿼리 파라미터)>
# OPTIMIZATION_API_TOKEN=<선택: Authorization: Bearer 헤더로 전송>
```

전체 설정 항목(타임아웃, 재시도 횟수 등)은 `aihub/config.py`를 참고하세요. 최적화 API 주소의 실제 변수명과 인증 필요 여부는 `.env` 파일과 `test/curl_test_classification.sh`로 직접 확인하세요(이 문서는 보안상 `.env` 값을 직접 읽지 않았습니다).

> ⚠️ **확인 필요**: `aihub/config.py`의 `validate_runtime()`은 시작 시점에 `optimization_api_url`을 필수로 검사하지 않습니다. 최적화 API 주소가 비어 있으면 서버/CLI는 정상 기동되지만, 최적화 의도를 실제로 요청한 시점에야 `OptimizationEndpointError`로 실패합니다.

## 실행

```bash
python -m aihub                          # 대화형 CLI (reset: 세션 초기화, exit: 종료)
python -m aihub "질의 내용" --json       # 한 번 처리 후 JSON 출력
python -m uvicorn aihub.api:app --reload --host 127.0.0.1 --port 8000   # HTTP API + 웹 UI
bash aihub/web/ui.sh                                                     # 위와 동일 + 자동으로 AIHUB-v2/로 이동, 포트/호스트 인자 지원
```

`ui.sh`는 호출된 위치와 무관하게 먼저 `AIHUB-v2/`로 이동한 뒤 `uvicorn`을 실행하도록 만든 실행 스크립트입니다(`bash aihub/web/ui.sh [포트]`, `HOST=0.0.0.0 bash aihub/web/ui.sh 9000`처럼 사용). `.env`가 없으면 경고만 출력하고 계속 진행합니다.

웹 UI는 서버 실행 후 `http://127.0.0.1:8000/`로 접속합니다. 파일로 직접 열면 안 됩니다.

| 메서드 | 경로 | 용도 |
|---|---|---|
| GET | `/health` | 설정 요약(LLM/ML 설정 여부), 활성 세션 수. **최적화 API 설정 여부는 노출하지 않습니다**(아래 "알려진 문제" 참고) |
| POST | `/chat/predict` | 자연어 -> 예측/최적화 (`query`, `session_id`, `explain`) |
| DELETE | `/chat/session/{session_id}` | 세션 삭제 |

`/chat/predict` 응답은 기존 필드(`status`, `answer`, `predictions`, `missing_fields` 등)에 더해 `intent`(`schema.INTENTS` 중 하나)와 `optimization`(최적화 호출 결과 또는 `null`) 필드를 포함합니다(`pipeline.PipelineResult`).

응답 `status`는 `ok`, `need_more_info`, `invalid_input`, `llm_error`, `endpoint_error`, **`clarify`**(신규) 6종이며 모두 HTTP 200으로 전달될 수 있습니다. HTTP 성공을 처리 성공으로 판단하면 안 됩니다.

## 테스트

**[수정] pytest 미사용 결정**: 이전에는 `test/__pycache__/`에 `test_api`, `test_core`, `test_golden_v2`, `golden_llm_extract`의 `.pyc` 캐시만 있고 `.py` 원본이 없는 상태였습니다(`pytest` 실행 시 수집 0개). 이번에 `pytest`가 미사용으로 확인되어 `requirements.txt`의 의존성과 `pyproject.toml`의 pytest 설정을 제거했습니다. 현재 자동화된 단위/회귀 테스트는 없고, 아래 수동 스모크 테스트로만 동작을 확인합니다.

> **[수정] 소스 재확인**: 이 절의 이전 버전은 "`aihub/optimization.py` docstring이 언급하던 `test/test_optimization.py`도 함께 제거했습니다"라고 적었으나, 이는 사실이 아니었습니다 — `aihub/optimization.py`의 모듈 docstring은 지금도 "`test/test_optimization.py`가 pytest 미사용 결정으로 애초에 작성되지 않았다"는 내용을 그대로 언급하고 있습니다(코드에서 해당 문구를 삭제한 적이 없습니다). 아래 "알려진 문제" 절의 `INTENT_TO_TARGET` 항목도 이 사실과 일치합니다.

```bash
bash test/curl_test_classification.sh   # 최적화 API를 curl로 직접 호출 (네트워크 필요, 결과를 out_0.json/out_1.json으로 저장)

# [추가] 실제 LLM/예측/최적화 API를 호출하는 수동 스모크 테스트(pytest 아님).
# 둘 다 작성 시점에 실제 서버/API에 대고 실행해 검증하지 않았다(각 스크립트 상단 주석 참고).
bash aihub/web/ui.sh                  # (다른 터미널에서 먼저 서버 기동)
bash test/web_smoke_test.sh           # HTTP API: /health, /chat/predict(8가지 케이스), 세션 삭제
bash test/cli_smoke_test.sh           # CLI: python -m aihub 단일 실행 7가지 케이스 + 대화형 멀티턴 1가지
```

두 스모크 테스트 스크립트는 각 케이스의 실제 응답 `status`가 `docs/architecture.md` 기준 기대값과
일치하는지 보여주지만, 불일치(`[확인 필요]`로 표시)는 실패가 아니라 실제 LLM의 intent 분류 결과에
따라 달라질 수 있다는 뜻이다(특히 `predict_and_optimize`, `clarify` 케이스는 질의 문구 해석에 민감함).

`test/results/api/out_0.json`, `out_1.json`은 `curl_test_classification.sh`가 생성한 실제 응답 샘플로 보이며, `optimization.parse_optimization_response()`가 가정하는 응답 형식과 구조가 일치함을 확인했습니다(필드명, `confidence(1)`/`confidence(0)`/`prediction(high_defect_flag)` 키 포함).

## 문서

| 문서 | 내용 |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | 전체 아키텍처: intent 분기, 상태 정의, 컴포넌트별 상세 동작 |
| [`docs/code_inventory.md`](docs/code_inventory.md) | 파일별 역할 목록 |
| [`docs/agent-v2/optimization_chatbot_spec.md`](docs/agent-v2/optimization_chatbot_spec.md) | (채택되지 않은 초기 구상안) 독립 최적화 챗봇 설계 |
| [`docs/agent-v2/pre-version/chatbot_optimization_feature_spec.md`](docs/agent-v2/pre-version/chatbot_optimization_feature_spec.md) | (채택된 설계, 실제 코드와 일치) 기존 파이프라인 통합형 최적화 기능 명세 |
| [`docs/agent-v2/aistudio_optimization_troubleshooting.md`](docs/agent-v2/aistudio_optimization_troubleshooting.md) | Altair AI Studio 측 최적화 프로세스 구축 트러블슈팅 기록 (이 저장소 코드와는 무관, 서버 측 참고 자료) |

## 알려진 문제 / 확인 필요 사항

<!-- [수정] 2026-10-29: 내용 변경 없이 각 항목을 요약해 분량만 줄임(문서 정리). -->

소스를 읽다 발견한 문제이며, 대부분 미수정 상태로 사실만 기록합니다(pytest 제거만 실제 반영).

- **[수정] 웹 UI/CLI 안내 문구 반영 (2026-10-28)**: `app.js`의 `statuses`에 `clarify`를 추가해 미처리 버그를 고쳤습니다. 안내 문구(환영 메시지, 예제 버튼, `--help`, 대화형 배너)에 최적화 3개 의도 예시를 넣고, `endpoint_error`/지연시간 표시는 ML API와 최적화 API를 구분하도록 했습니다(`describeStatus()`). 최적화 조건 표 전용 렌더링은 없고 `answer`와 `raw` JSON에서만 확인할 수 있습니다. 실제 호출로 검증하지 않았습니다.
- **[추가] `predict_and_find_risk` 의도 추가 (2026-10-29)**: 명세서에 없던 "예측 + 위험 조건" 의도입니다(배경은 위 "배경" 절 참고). 영향 파일은 `schema.py`, `optimization.py`, `pipeline.py`, `llm.py`, `app.js`, `cli.py`입니다. 기존 `predict_and_optimize` 동작은 바뀌지 않았고, 분류 정확도는 검증하지 않았습니다.
- **`/health` 미반영**: `optimization_api_url` 설정 여부가 `/health`에 없어 웹 UI 배너에서 최적화 설정 상태를 알 수 없습니다(미수정).
- **`INTENT_TO_TARGET` 부분 검증**: `aistudio_optimization_troubleshooting.md` 4절의 `curl` 테스트가 "target=1 → confidence(1) 최소화" 해석을 뒷받침하지만, 자동 테스트로 고정되어 있지 않습니다(`test/test_optimization.py` 부재). 매핑이 틀리면 기능 의미가 반대로 뒤집힙니다([`docs/architecture.md`](docs/architecture.md) 4.4절 참고).
- **`UNCONTROLLABLE_FIELDS` 임의 지정**: `shift`, `supplier_code`, `planned_quantity`, `ambient_humidity_pct`, `production_line` 5개는 명세서 예시를 그대로 가져온 것입니다. 실제 조정 가능 변수는 담당자 확인이 필요합니다.
- **자동화된 테스트 부재**: pytest를 제거해 단위/회귀 테스트가 없습니다. 수동 스모크 테스트 2개(`test/web_smoke_test.sh`, `test/cli_smoke_test.sh`)만 있습니다.

## 주의

- 로컬 테스트용입니다. 사용자 인증과 세션 소유권 검증이 없어 공개 서비스로 노출하면 안 됩니다.
- 입력 조건은 설정된 외부 LLM/예측 API/최적화 API로 전송됩니다. 비밀번호, API 키, 개인정보를 입력하지 마세요.
- 세션은 서버 프로세스 메모리에만 저장되며 재시작하면 사라집니다.
- 최적화 결과는 모델 기반 추정이며 호출마다 달라질 수 있고 실제 공정 결과를 보장하지 않습니다(응답 문구에도 포함됨, `pipeline._format_optimize_only`/`_format_predict_and_optimize` 참고).

> 이 문서는 소스(`aihub/`, `docs/agent-v2/`)를 읽고 작성했으며, CLI·HTTP·실제 외부 API 호출로 실행 검증하지 않았습니다.

