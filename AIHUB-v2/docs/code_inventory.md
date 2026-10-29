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
| `schema.py` | 12개 필드 정의, 라인·공급사 화이트리스트, `DefectRateInput` 검증, `validate_provided_fields()`. **[신규]** `INTENTS`(`predict`/`optimize_reduce_defect`/`optimize_find_defect_risk`/`predict_and_optimize`/`clarify` 5종), `FIELD_LABELS`(12개 필드 → 한글 라벨, `web/app.js`의 `welcomeMessage`와 수동 동기화 필요), `UNCONTROLLABLE_FIELDS`(현장에서 바꾸기 어려운 5개 필드, 명세의 예시를 그대로 사용해 담당자 확인 필요). 추출 JSON Schema(`extraction_json_schema()`)의 최상위 `required`에 `intent`가 추가됨 |
| `llm.py` | SDC LLM 클라이언트 + 추출 프롬프트(`EXTRACTION_SYSTEM_PROMPT`) + 해설 프롬프트(`ANSWER_SYSTEM_PROMPT`, 변경 없음). 추출 프롬프트에 **[신규]** `[의도 분류 — intent]` 절이 추가되어 LLM이 `INTENTS` 중 하나를 고르게 한다. 단, **target 숫자(0/1)는 LLM이 직접 고르지 않고** `optimization.build_target()`이 코드로 고정 변환한다(프롬프트에도 "절대 직접 고르지 않는다"로 명시) |
| `ml.py` | 결함률 예측(POST) API 클라이언트 (재시도, 에코 검증). 이번 변경에서 수정되지 않음 |
| `optimization.py` | **[신규]** 최적화(GET, `target` 쿼리 파라미터) API 클라이언트. `INTENT_TO_TARGET` 고정 사전(`optimize_reduce_defect`→`"1"`, `predict_and_optimize`→`"1"`, `optimize_find_defect_risk`→`"0"`), `build_target()`, `parse_optimization_response()`(`confidence(1)`/`confidence(0)`/`prediction(high_defect_flag)` 파싱, 나머지 키를 조건으로 간주), `OptimizationClient`(ml.py와 동일한 재시도 정책: 5xx·타임아웃만 재시도, 4xx는 즉시 실패). **[수정]** 모듈 docstring에서 `test/test_optimization.py` 언급을 제거했다(pytest 미사용 결정으로 애초에 작성되지 않았음). `INTENT_TO_TARGET` 매핑을 고정하는 자동 테스트는 여전히 없다 |
| `pipeline.py` | **[확장]** 기존 추출·세션 병합·검증·예측·해설 흐름(`_run_predict`, `_gather_and_predict`)은 로직 변경 없이 유지. `DefectRatePipeline.run()`이 `intent`로 분기하여 `_run_optimize_only`(조건 입력 없이 최적화 API만 호출), `_run_predict_and_optimize`(예측 후 최적화 추가 호출, 최적화 실패해도 예측 결과는 반환), `_run_clarify`(API 미호출, 방향을 되묻는 고정 문구)로 라우팅한다. `_format_optimize_only`/`_format_predict_and_optimize`/`_format_conditions_table`이 최적화 결과를 Markdown으로 포맷하며, 두 포맷 함수 모두 "모델 기반 추정이며 실제 공정 결과를 보장하지 않는다"는 고지 문구를 포함한다. `PipelineResult`에 `intent`(기본값 `"predict"`, 하위 호환용), `optimization`(최적화 원본 파싱 결과 또는 `None`) 필드가 추가됨 |
| `api.py` | FastAPI: 로컬 웹 UI 정적 제공(`GET /` → `web/index.html`, `GET /ui-assets/*`) + `/health`, `/chat/predict`, 세션 삭제. **이번 변경에서 수정되지 않음** — `/health` 응답에 최적화 API 설정 여부가 포함되지 않고, `/chat/predict`는 `PipelineResult.to_dict()`를 그대로 반환하므로 `intent`/`optimization` 필드는 결과적으로 함께 전달된다 |
| `cli.py` | 한 줄/대화형 CLI (`python -m aihub`). 수정되지 않음. `res.answer`를 그대로 출력하므로 최적화 응답(최적 조건 표, 고지 문구)도 텍스트로는 보인다 |

### 하위 폴더

| 경로 | 역할 |
| --- | --- |
| `prompt/llm_prompt_v1.py` | 추출 프롬프트 변경 이력 스냅샷. `llm.py`는 이 파일을 import하지 않는다(`__init__.py` 없음, 공식 서브패키지 아님). 단위 환산·항목 표시 없는 값 처리 규칙까지는 포함하지만 **intent 분류 절은 없다** (intent 도입 이전 스냅샷) |
| `prompt/llm_prompt_v2.py` | 위와 동일한 성격의 스냅샷. 본문을 `llm.py`의 현재 `EXTRACTION_SYSTEM_PROMPT`와 대조한 결과, **`[의도 분류 — intent]` 절과 `shift` 외 `production_line`/`supplier_code`의 한글 별칭 정규화 규칙이 빠져 있어 llm.py보다 이전 버전**으로 보인다. 실행에는 영향이 없다 |
| `web/index.html`, `web/app.js`, `web/style.css` | 로컬 웹 UI 정적 파일. `api.py`가 `/`(index.html)와 `/ui-assets/*`로 제공한다. **최적화 기능 미반영**(아래 "알려진 문제" 참고): `app.js`의 `statuses` 사전에 `clarify` 상태가 없어 해당 응답이 오면 `renderResult()`가 정상 응답 형식 오류로 처리하며, `optimization` 필드와 최적 조건 표를 별도로 렌더링하는 코드도 없다(응답 텍스트 `answer`와 `raw` JSON 영역에서만 확인 가능) |
| `web/ui.sh` | 실행 가능한 스크립트가 아니라 `uvicorn` 실행 명령 한 줄을 적어 둔 메모(주석 처리된 프롬프트 포함) |
| `web/bak/style.css` | 이전 스타일시트 백업으로 보이며 코드에서 참조되지 않는다 |

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
| `docs/architecture.md` | 전체 아키텍처 문서(intent 분기, 상태 정의, 컴포넌트별 상세 동작) |
| `docs/code_inventory.md` | 이 문서 |
| `docs/agent-v2/optimization_chatbot_spec.md` | 최적화 전용 **독립 챗봇**으로 구상한 초기 명세서. `intent` enum이 4종(`optimize_reduce_defect`/`optimize_find_defect_risk`/`clarify`/`out_of_scope`)이며 `out_of_scope`는 `schema.INTENTS`에 없다. **실제 코드에 채택되지 않았다** |
| `docs/agent-v2/pre-version/chatbot_optimization_feature_spec.md` | 기존 예측 파이프라인에 최적화 의도 3종(`optimize_reduce_defect`/`optimize_find_defect_risk`/`predict_and_optimize`)과 `clarify`를 **통합**하는 명세서. `schema.py`·`pipeline.py`·`optimization.py`가 이 문서의 4~6장 구조를 따른다 |
| `docs/agent-v2/aistudio_optimization_troubleshooting.md` | Altair AI Studio에서 최적화(Prescriptive Analytics) 프로세스를 구성하며 겪은 트러블슈팅 기록. 이 저장소의 Python 코드와는 직접 관련이 없고, 서버(모델) 측 구성 참고 자료다 |

## 변경 이력

- (작성일 미상, 추가 수정): `docs/architecture.md`를 새로 작성하면서 문서 표에 항목을 추가했다. 기존에는 이 저장소에 architecture 문서가 없어 README가 AIHUB 쪽 문서를 대신 가리키는 문제가 있었다.
- (작성일 미상, 이 문서 최초 작성): `AIHUB`의 `docs/code_inventory.md` 형식을 기준으로 `AIHUB-v2`용으로 새로 작성했다. 소스(`aihub/` 전체, `docs/agent-v2/` 3개 문서)를 직접 읽고 대조했으며, `test/`의 `.py` 원본 부재와 `test_optimization.py` 미존재, 웹 UI의 `clarify`/`optimization` 미반영은 모두 소스 열람으로 확인한 사실이다. CLI·HTTP·실제 외부 API 호출로 실행해 재확인하지는 않았다.
- (추가 수정): pytest 미사용 결정에 따라 `requirements.txt`의 `pytest` 의존성, `pyproject.toml`의 `[tool.pytest.ini_options]`를 제거하고 "테스트 (`test/`)" 절을 실제 존재하는 파일(`curl_test_classification.sh`, `web_smoke_test.sh`, `cli_smoke_test.sh`, `results/`) 기준으로 다시 썼다. `aihub/optimization.py` docstring의 `test/test_optimization.py` 언급도 제거했다.
