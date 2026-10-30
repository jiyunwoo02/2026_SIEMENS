# 코드 목록 (Code Inventory)

패키지는 프로젝트 루트의 `aihub/` 입니다. import는 `from aihub.pipeline import DefectRatePipeline` 형태입니다.

이 프로젝트는 [`AIHUB`](../../AIHUB/) 패키지와 거의 동일한 기반 구조(스키마 12개 필드, LLM 추출, 예측 파이프라인)에 **공정 최적화 API 연동**을 추가한 버전으로 보입니다(코드 비교 결과이며, 두 저장소 사이의 명시적 연결 선언이나 공통 이력은 확인하지 못했습니다).

실행·설치 방법은 [`../README.md`](../README.md)를 참고합니다.

## 패키지 `aihub/`

| 파일 | 역할 |
| --- | --- |
| `__init__.py` | 패키지 공개 API 재노출(`DefectRatePipeline`, `PipelineResult`, `SlotFillingSession`, `DefectRateInput`, `build_payload`), `__version__ = "1.0.0"`. 최적화 관련 클래스(`OptimizationClient` 등)는 재노출하지 않는다 |
| `__main__.py` | `python -m aihub` 진입점. `cli.main()`을 호출하고 반환값을 `SystemExit`으로 전달 |
| `config.py` | `.env` 설정. 기존 LLM/예측 API 설정에 더해 **[신규]** 최적화 API 설정 3종(`optimization_api_url`, `optimization_api_token`, `optimization_timeout_seconds` 기본 180초, `optimization_max_retries` 기본 1회)을 추가. `validate_runtime()`은 최적화 설정을 시작 시점 필수값으로 검사하지 않는다(선택 기능으로 취급, 호출 시점에만 오류) |
| `schema.py` | 12개 필드 정의, 라인·공급사 화이트리스트, `DefectRateInput` 검증, `validate_provided_fields()`. `INTENTS`(`predict`/`optimize_reduce_defect`/`optimize_find_defect_risk`/`predict_and_optimize`/`predict_and_find_risk`/`clarify` **6종** — **[수정] 2026-10-29**: 명세서(`docs/agent-v2/bak/chatbot_optimization_feature_spec.md`)에는 없는 `predict_and_find_risk`가 추가됨, 아래 `README.md` "배경" 절 참고), `FIELD_LABELS`(12개 필드 → 한글 라벨, `web/app.js`의 `welcomeMessage`와 수동 동기화 필요), `UNCONTROLLABLE_FIELDS`(현장에서 바꾸기 어려운 5개 필드로 제안됐던 상수). **[수정] 2026-10-29 (담당자 확인)**: 담당자가 이 상수를 **비활성화했다고 직접 확인**했다. `pipeline.py`의 `_format_conditions_table()`에서 이미 "참고값" 표시 기능이 제거된 것(2026-10-27)과 일관되며, 더 이상 사용되지 않는 것으로 정리됐다. 추출 JSON Schema(`extraction_json_schema()`)의 최상위 `required`에 `intent`가 추가됨 |
| `llm.py` | SDC LLM 클라이언트 + 추출 프롬프트(`EXTRACTION_SYSTEM_PROMPT`) + 해설 프롬프트(`ANSWER_SYSTEM_PROMPT`, 변경 없음). 추출 프롬프트에 `[의도 분류 — intent]` 절이 있어 LLM이 `INTENTS`(6종) 중 하나를 고르게 한다. **[수정] 2026-10-29**: 해당 절에 `predict_and_find_risk`("이 조건 결함률 예측하고, 불량이 더 심해지는 위험 조건도 알려줘") 정의·예시가 추가됨(소스 확인, `predict_and_optimize`와 나란히 서술). 단, **target 숫자(0/1)는 LLM이 직접 고르지 않고** `optimization.build_target()`이 코드로 고정 변환한다(프롬프트에도 "절대 직접 고르지 않는다"로 명시) |
| `ml.py` | 결함률 예측(POST) API 클라이언트 (재시도, 에코 검증). 이번 변경에서 수정되지 않음 |
| `optimization.py` | 최적화(GET, `target` 쿼리 파라미터) API 클라이언트. `INTENT_TO_TARGET` 고정 사전(`optimize_reduce_defect`·`predict_and_optimize`→`"1"`, `optimize_find_defect_risk`·`predict_and_find_risk`→`"0"`; **[수정] 2026-10-29**: `predict_and_find_risk` 추가), `build_target()`, `parse_optimization_response()`(`confidence(1)`/`confidence(0)`/`prediction(high_defect_flag)` 파싱, 나머지 키는 조건으로 간주), `OptimizationClient`(ml.py와 동일한 재시도 정책: 5xx·타임아웃만 재시도, 4xx는 즉시 실패). 모듈 docstring이 작성되지 않은 `test/test_optimization.py`를 아직 언급하고 있으며, `INTENT_TO_TARGET` 매핑을 고정하는 자동 테스트는 없다 |
| `pipeline.py` | 기존 추출·세션 병합·검증·예측·해설 흐름(`_run_predict`, `_gather_and_predict`, `_explain`)은 로직 변경 없이 유지. `run()`이 `intent`로 분기한다: `_run_optimize_only`(최적화 API만 호출), `_run_predict_and_optimize`(예측 후 최적화 추가 호출), `_run_clarify`(API 미호출, 방향을 되묻는 고정 문구). **[수정] 2026-10-29**: `_run_predict_and_optimize(extraction, session, intent)`가 `predict_and_find_risk`도 처리하도록 일반화되어 `build_target(intent)`로 target을 동적으로 정한다(기존에는 `target="1"` 하드코딩). 최적화가 실패해도(`OptimizationEndpointError`/`ValueError`) `status="ok"`, `optimization=None`, `errors=[...]`로 부분 성공을 반환한다. `_run_optimize_only(intent)`의 상태 매핑은 `ValueError`→`llm_error`, `OptimizationEndpointError`→`endpoint_error`, 성공→`ok`. 포맷 함수: `_format_conditions_table()`은 2026-10-27에 "참고값" 열이 제거되어 `항목 | 값` 2열 표만 만들고 `UNCONTROLLABLE_FIELDS`는 사용하지 않는다(담당자 확인으로 비활성화). `_format_optimize_only()`는 불량/정상 확률과 "모델 기반 추정" 고지를 표시한다. ⚠️ **알려진 불일치**: "참고값으로 표시된 항목은..." 문구가 남아 있지만 표에는 참고값 표시가 없다. `_format_predict_and_optimize()`는 `intent=="predict_and_find_risk"`에 따라 제목·라벨·실패 문구를 달리 렌더링하며, `defect_probability`만 표시한다. `shift`는 `_SHIFT_DISPLAY`(`DAY`→"주간 (DAY)", `NIGHT`→"야간 (NIGHT)", 그 외는 원문)로 표시한다. `PipelineResult`에 `intent`(기본 `"predict"`), `optimization`, `errors` 필드가 추가됐다. 위 내용은 모두 소스로 확인했다(`docs/architecture.md` 4.5절 참고) |
| `api.py` | FastAPI: 웹 UI 정적 제공(`GET /`, `GET /ui-assets/*`) + `/health`, `/chat/predict`, 세션 삭제. **이번 변경에서 수정되지 않음** — `/health`에 최적화 API 설정 여부는 없고, `/chat/predict`는 `PipelineResult.to_dict()`를 그대로 반환하므로 `intent`/`optimization` 필드가 함께 전달된다 |
| `cli.py` | 한 줄/대화형 CLI (`python -m aihub`). **[수정] 2026-10-28**: `--help`(`description`/`epilog`)와 대화형 배너에 최적화 의도 질의 예시를 추가하고, `res.optimization`이 있으면 최적화 API 응답 시간(`latency_ms`)을 별도 줄로 출력한다. **[수정] 2026-10-29**: `predict_and_find_risk` 예시를 추가해 최적화 의도가 "네 가지"로 바뀌었다(안내 문구만 변경, 로직 변경 없음). `res.answer`를 그대로 출력하므로 최적 조건 표·고지 문구도 텍스트로 보인다 |

### 하위 폴더

| 경로 | 역할 |
| --- | --- |
| `prompt/prompt-v1.py` | **[수정] 파일명 정정**(`llm_prompt_v1.py` → `prompt-v1.py`). 추출 프롬프트 변경 이력 스냅샷이며 `llm.py`는 import하지 않는다(`__init__.py` 없음). `[의도 분류 — intent]` 절과 한글 별칭 정규화 규칙을 포함한다(이전 문서의 "intent 절 없음"은 사실이 아니었다). `llm.py`의 현재 프롬프트보다 `주의:` 절이 더 상세하고, `ANSWER_SYSTEM_PROMPT`도 "GBT 기반 회귀 모델" 설명 등으로 더 상세한 별도 버전이다 |
| `prompt/prompt-v2.py` | **[수정] 파일명 정정**(`llm_prompt_v2.py` → `prompt-v2.py`). `EXTRACTION_SYSTEM_PROMPT`만 포함하며 intent 절과 별칭 정규화 규칙이 있다. `llm.py` 현재 버전과 거의 동일하고, 첫 문장만 "JSON으로 응답합니다"(현재는 "JSON으로만")로 다르다. `v1`/`v2` 이름이 실제 버전 순서를 반영하는지는 확인되지 않았다 |
| `web/index.html`, `web/app.js`, `web/style.css` | 로컬 웹 UI 정적 파일. `api.py`가 `/`와 `/ui-assets/*`로 제공한다. **[수정] 2026-10-28**: `app.js`에 `clarify` 상태 추가, `describeStatus()`의 intent별 상태 문구, `clarify`를 정상 응답으로 처리하는 `renderResult()`, `optimization.latency_ms` 표시를 반영했고, `index.html`에는 최적화 예제 버튼(`example-optimize`)과 안내 문구를 추가했다. **[수정] 2026-10-29 (소스 확인)**: `describeStatus()`에 `predict_and_find_risk` 분기("⚠️ 예측 및 위험 조건 탐색 완료")와 `welcomeMessage` 예시 문구를 추가했다. `noMissingIsExpected`에 이 의도가 빠진 것은 조건 입력이 여전히 필요하기 때문이며 버그가 아니다. 최적화 조건 표 전용 렌더링 영역은 없고, 결과는 `answer` 텍스트(Markdown 표)와 `raw` JSON에서만 볼 수 있다 |
| `web/ui.sh` | **[수정] 2026-10-28**: "메모"라는 이전 서술은 오류였고, 실제로 실행 가능한 스크립트다. 프로젝트 루트로 이동한 뒤(`.env` 로드용) `python -m uvicorn aihub.api:app --reload`를 실행한다. 포트는 첫 번째 인자(기본 8000), 호스트는 `HOST` 환경변수(기본 127.0.0.1)로 지정하며, `.env`가 없으면 경고만 출력하고 계속한다. `web/bak/style.css`는 존재하지 않아 해당 행을 제거했다 |

## 테스트 (`test/`)

**[수정] pytest 미사용 결정**: 이전 버전에는 `test/__pycache__/`에 `test_core`, `test_golden_v2`, `test_api`, `golden_llm_extract`의 `.pyc` 캐시만 남아 있고 대응하는 `.py` 원본이 없는 상태였다(pytest로 수집해도 테스트 0개). 이번에 `pytest`가 **미사용으로 확인되어** `requirements.txt`의 `pytest` 의존성과 `pyproject.toml`의 `[tool.pytest.ini_options]` 설정을 제거했고, 위 `.pyc` 캐시 파일(및 `.pytest_cache/`)은 더 이상 쓰이지 않는 로컬 산출물이다(둘 다 `.gitignore` 대상이라 Git에는 추적되지 않음 - 로컬에서 직접 지워도 무방함: `rm -rf test/__pycache__ .pytest_cache`). `aihub/optimization.py` docstring이 언급하던 `test/test_optimization.py`도 애초에 작성되지 않았다.

현재 이 저장소에는 **자동화된(단위/회귀) 테스트가 없으며**, 대신 아래의 수동 스모크 테스트로 동작을 확인한다.

| 파일/폴더 | 역할 |
| --- | --- |
| `curl_test_classification.sh` | 최적화 API를 curl로 직접 호출하는 스크립트. 기본 호출, `target=0`/`target=1` 매크로 반영 비교(`diff`), 응답 시간 측정 3가지 용도. 엔드포인트 주소가 파일에 직접 적혀 있다(`.env`의 `OPTIMIZATION_API_URL`과 같은 값으로 추정되나 교차 확인은 하지 않았다) |
| `web_smoke_test.sh` | **[신규]** 실행 중인 서버에 curl로 `/health`, `/chat/predict`(8케이스), `/chat/session/{id}`를 호출하는 수동 스모크 테스트. 작성 시점에 실제 서버/LLM/API로 실행 검증하지 않았다 |
| `cli_smoke_test.sh` | **[신규]** `python -m aihub`를 단일 실행 7케이스 + 대화형 멀티턴 1케이스로 반복 실행하는 수동 스모크 테스트. 마찬가지로 실행 검증하지 않았다 |
| `results/api/out_0.json`, `results/api/out_1.json` | `curl_test_classification.sh`로 받은 실제 응답 샘플. `optimization.parse_optimization_response()`가 기대하는 응답 구조(12개 조건 필드 + `confidence(1)`/`confidence(0)`/`prediction(high_defect_flag)`)와 일치함을 확인했다 |

`INTENT_TO_TARGET` 매핑(4.4절 참고)처럼 틀리면 기능 의미가 반대로 뒤집히는 로직을 고정하는 자동 테스트가 전혀 없다는 점은 여전히 남은 위험이다.

## 문서 (`docs/`)

| 경로 | 역할 |
| --- | --- |
| `docs/architecture.md` | 전체 아키텍처 문서(intent 분기, 상태 정의, 컴포넌트별 동작) |
| `docs/code_inventory.md` | 이 문서 |
| `docs/agent-v2/optimization_chatbot_spec.md` | 최적화 전용 독립 챗봇 초기 명세서. `intent` 4종(`optimize_reduce_defect`/`optimize_find_defect_risk`/`clarify`/`out_of_scope`)이며 `out_of_scope`는 `schema.INTENTS`에 없다. **실제 코드에 채택되지 않았다** |
| `docs/agent-v2/bak/chatbot_optimization_feature_spec.md` | **[수정] 경로 정정**: 이전의 `pre-version/` 경로는 존재하지 않고 실제 경로는 `bak/`이다(파일시스템 확인). 기존 예측 파이프라인에 최적화 의도 3종(`optimize_reduce_defect`/`optimize_find_defect_risk`/`predict_and_optimize`)과 `clarify`를 통합하는 명세서이며, `schema.py`·`pipeline.py`·`optimization.py`가 4~6장 구조를 따른다. **`predict_and_find_risk`는 이 명세서에 없고 2026-10-29에 추가됐다**(`README.md` "배경" 절 참고) |
| `docs/agent-v2/aistudio_optimization_troubleshooting.md` | Altair AI Studio 최적화(Prescriptive Analytics) 구성 트러블슈팅 기록. Python 코드와 직접 관련 없는 서버(모델) 측 참고 자료 |

## 변경 이력

- (작성일 미상) 이 문서 최초 작성: `AIHUB`의 `docs/code_inventory.md` 형식을 기준으로 `AIHUB-v2`용으로 작성했다. 소스(`aihub/` 전체, `docs/agent-v2/` 3개 문서)를 열람해 대조했으며, 실행 검증은 하지 않았다.
- (작성일 미상) `docs/architecture.md` 신규 작성 후 문서 표에 항목을 추가했다. 이전에는 README가 AIHUB 쪽 문서를 대신 가리키고 있었다.
- (작성일 미상) pytest 미사용 결정에 따라 `requirements.txt`의 `pytest`와 `pyproject.toml`의 `[tool.pytest.ini_options]`를 제거하고, "테스트 (`test/`)" 절을 실제 파일(`curl_test_classification.sh`, `web_smoke_test.sh`, `cli_smoke_test.sh`, `results/`) 기준으로 다시 썼다.
- (소스 재대조) `optimization.py`, `cli.py`, `web/*`, `prompt/*`를 다시 읽고 이전 서술의 오류 6건을 정정했다.
  1. `optimization.py` docstring의 `test/test_optimization.py` 언급은 제거되지 않고 남아 있다.
  2. `cli.py`는 "수정되지 않음"이 아니라 2026-10-28에 최적화 안내 문구·응답시간 출력이 추가됐다.
  3. `web/index.html`·`app.js`는 `clarify` 처리, intent별 상태 문구, 지연시간 표시, 예제 버튼이 반영됐다(최적화 조건 전용 렌더링 영역은 없음).
  4. `web/ui.sh`는 메모가 아니라 실행 가능한 스크립트다.
  5. `aihub/prompt/`의 실제 파일명은 `prompt-v1.py`/`prompt-v2.py`이며 둘 다 intent 분류 절을 포함한다.
  6. 존재하지 않는 `web/bak/style.css` 행을 제거했다.
- **[수정] 2026-10-29, `predict_and_find_risk` 추가 반영**: `schema.py`(`INTENTS` 5종→6종), `optimization.py`(`INTENT_TO_TARGET`에 `"0"` 매핑 추가), `llm.py`(프롬프트 예시 추가), `cli.py`·`web/app.js`(안내·상태 문구 추가)를 소스 열람으로 확인해 반영했다. 이 시점의 `pipeline.py` 내용은 README 서술에만 의존했다.
- **[수정] 2026-10-29 (`pipeline.py` 소스 확인 1차)**: `_run_predict_and_optimize`/`_run_optimize_only`/`_run_clarify`/`_explain` 소스를 받아 추정 서술을 확인된 내용으로 교체했다(`intent` 인자, `build_target(intent)` 호출 등).
- **[수정] 2026-10-29 (`pipeline.py` 소스 확인 2차)**: 포맷 함수 소스를 받아 `pipeline.py` 행을 정정했다.
  1. `_format_conditions_table`의 "참고값" 열은 2026-10-27에 제거되어 2열 표만 남았다.
  2. 그 결과 `_format_optimize_only`의 "참고값" 안내 문구와 표가 맞지 않는 **알려진 불일치**를 기록했다.
  3. `_format_predict_and_optimize`가 `intent`별로 제목·라벨·문구를 달리 렌더링함을 확인했다.
- **[수정] 2026-10-29 (담당자 확인)**: 담당자가 `UNCONTROLLABLE_FIELDS` 비활성화를 확인해 `schema.py`·`pipeline.py` 행의 "추가 확인 필요" 문구를 비활성화 사실로 교체했다.
- **[수정] 2026-10-29 (소스 확인, 마무리)**: `_SHIFT_DISPLAY` 정의를 받아 `pipeline.py` 행의 마지막 미확인 항목을 해소했다. 이로써 `pipeline.py` 포맷 로직은 모두 소스로 확인됐으며, CLI·HTTP·실제 LLM 호출로는 재확인하지 않았다.
- **[수정] 문서 요약**: 변경 이력의 각 항목을 의미 변경 없이 축약했다(포맷/분량 정리이며 내용 변경 아님).
