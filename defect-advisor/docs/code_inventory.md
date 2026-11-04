# 코드 목록 (Code Inventory)

패키지는 프로젝트 루트의 `aihub/` 입니다. import는 `from aihub.pipeline import DefectRatePipeline` 형태입니다.

이 프로젝트는 [`defect-predictor`](../../defect-predictor/) 패키지와 거의 동일한 기반 구조(스키마 12개 필드, LLM 추출, 예측 파이프라인)에 **공정 최적화 API 연동**을 추가한 버전으로 보입니다(코드 비교 결과이며, 두 저장소 사이의 명시적 연결 선언이나 공통 이력은 확인하지 못했습니다).

실행·설치 방법은 [`../README.md`](../README.md)를 참고합니다.

## 패키지 `aihub/`

| 파일 | 역할 |
| --- | --- |
| `__init__.py` | 패키지 공개 API 재노출(`DefectRatePipeline`, `PipelineResult`, `SlotFillingSession`, `DefectRateInput`, `build_payload`), `__version__ = "1.0.0"`. `OptimizationClient` 등 최적화 관련 클래스는 재노출하지 않는다 |
| `__main__.py` | `python -m aihub` 진입점. `cli.main()`을 호출하고 반환값을 `SystemExit`으로 전달한다 |
| `config.py` | `.env`에서 설정을 로드하는 `Settings` 클래스(pydantic-settings). LLM·예측 API·최적화 API 3그룹의 설정을 관리한다. `validate_runtime()`은 최적화 API 주소를 필수로 검사하지 않으며, 실제 호출 시점에만 오류를 낸다 |
| `schema.py` | 12개 공정 입력 필드(`ALL_FIELDS`, `FIELD_SPEC`)와 `INTENTS`(6종: `predict`/`optimize_reduce_defect`/`optimize_find_defect_risk`/`predict_and_optimize`/`predict_and_find_risk`/`clarify`) 정의. `FIELD_LABELS`(한글 라벨), `UNCONTROLLABLE_FIELDS`(현재 빈 집합), `DefectRateInput`(Pydantic 검증 모델), `validate_provided_fields()`(슬롯 부분 검증), `extraction_json_schema()`(LLM 추출용 JSON Schema) 포함 |
| `llm.py` | SDC LLM 게이트웨이 클라이언트(`SDCLLMClient`). `EXTRACTION_SYSTEM_PROMPT`가 12개 필드와 intent를 동시에 추출하며, LLM이 `target` 숫자를 직접 고르지 않도록 명시한다. `ANSWER_SYSTEM_PROMPT`는 예측 결과 한국어 해설에 사용한다. JSON 출력은 `json_schema → json_object → prompt` 폴백 순서로 시도한다 |
| `ml.py` | 결함률 예측 POST API 클라이언트(`DefectRateMLClient`). 재시도(5xx·타임아웃만), 에코 검증, 모의(`mock_ml`) 모드를 지원한다 |
| `optimization.py` | 최적화 GET API 클라이언트(`OptimizationClient`). `INTENT_TO_TARGET` 고정 사전과 `build_target()`으로 intent를 `target`(`"0"`/`"1"`)으로 변환해 LLM이 직접 고르지 않게 한다. `parse_optimization_response()`로 응답에서 최적 조건과 불량/정상 확률을 추출한다. 재시도 정책은 `ml.py`와 동일(5xx·타임아웃만 재시도, 4xx는 즉시 실패) |
| `pipeline.py` | 질의 추출 → intent 분기 → 예측/최적화 → 포맷을 조율하는 오케스트레이터. `run()`이 intent로 `_run_predict`·`_run_optimize_only`·`_run_predict_and_optimize`·`_run_clarify` 네 메서드로 분기하며, `_gather_and_predict()`가 예측 계열 세 경로(`predict`·`predict_and_optimize`·`predict_and_find_risk`)의 공통 단계(슬롯 병합 → 검증 → ML 호출)를 담당한다. 최적화 결과는 LLM 없이 코드가 결정적으로 Markdown을 생성한다(`_format_conditions_table`, `_format_optimize_only`, `_format_predict_and_optimize`). `PipelineResult`에 `intent`·`optimization`·`errors` 필드가 포함된다 |
| `api.py` | FastAPI 앱. 웹 UI 정적 파일 제공(`GET /`, `/ui-assets/*`), `/health`(설정 요약·활성 세션 수), `POST /chat/predict`(세션 관리·파이프라인 위임), `DELETE /chat/session/{id}`. 응답 HTTP 상태는 항상 200이며 `status` 필드로 처리 결과를 구분한다 |
| `cli.py` | argparse 기반 CLI. 단일 질의(`python -m aihub "질의" --json`)와 대화형 멀티턴(`python -m aihub`) 모드를 지원한다. `optimization.latency_ms`가 있으면 최적화 응답 시간을 별도 줄로 출력한다 |

### 하위 폴더

| 경로 | 역할 |
| --- | --- |
| `prompt/prompt-v1.py` | 추출·해설 프롬프트 변경 이력 스냅샷. `llm.py`보다 `주의:` 절과 `ANSWER_SYSTEM_PROMPT`가 더 상세한 과거 버전이며, `llm.py`가 import하지 않는다 |
| `prompt/prompt-v2.py` | 추출 프롬프트(`EXTRACTION_SYSTEM_PROMPT`)만 포함한 스냅샷. `llm.py` 현재 버전과 거의 동일하며, `llm.py`가 import하지 않는다 |
| `web/index.html`, `web/app.js`, `web/style.css`, `web/favicon.ico` | 로컬 웹 UI 정적 파일. `api.py`가 `/`와 `/ui-assets/*`로 제공한다. `app.js`가 `status`·`intent`별 상태 문구와 `optimization.latency_ms` 표시를 처리한다. 최적화 조건 전용 렌더링 영역은 없고, 결과는 `answer` 텍스트와 `raw` JSON에서만 확인할 수 있다 |
| `web/ui.sh` | `defect-advisor/` 디렉터리로 이동한 뒤 `uvicorn`을 실행하는 스크립트. 포트는 첫 번째 인자(기본 8000), 호스트는 `HOST` 환경변수(기본 `127.0.0.1`)로 지정하며, `.env`가 없으면 경고만 출력하고 계속한다 |

## 테스트 (`test/`)

pytest를 사용하지 않으며 자동화된 단위/회귀 테스트가 없다. 아래의 수동 스모크 테스트로 동작을 확인한다.

| 파일/폴더 | 역할 |
| --- | --- |
| `curl_test_classification.sh` | 최적화 API를 curl로 직접 호출하는 스크립트. `target=0`/`target=1` 두 방향 결과 비교(`diff`)와 응답 시간 측정 용도로 사용한다 |
| `web_smoke_test.sh` | 실행 중인 서버에 curl로 `/health`, `/chat/predict`(8케이스), `/chat/session/{id}`를 호출하는 수동 스모크 테스트 |
| `cli_smoke_test.sh` | `python -m aihub`를 단일 실행 7케이스 + 대화형 멀티턴 1케이스로 반복 실행하는 수동 스모크 테스트 |
| `results/api/out_0.json`, `results/api/out_1.json` | `curl_test_classification.sh`로 받은 실제 최적화 API 응답 샘플(`target=0`/`target=1` 각각). `parse_optimization_response()`가 기대하는 응답 구조와 일치한다 |

## 문서 (`docs/`)

| 경로 | 역할 |
| --- | --- |
| `docs/architecture.md` | 전체 아키텍처 문서(intent 분기, 상태 정의, 컴포넌트별 동작) |
| `docs/logic.md` | 처리 흐름·intent 분기·슬롯 필링 등 동작 로직 요약 |
| `docs/code_inventory.md` | 이 문서 |
| `docs/agent-v2/optimization_chatbot_spec.md` | 최적화 전용 독립 챗봇 초기 명세서. `intent` 4종(`optimize_reduce_defect`/`optimize_find_defect_risk`/`clarify`/`out_of_scope`)이며 `out_of_scope`는 `schema.INTENTS`에 없다. **실제 코드에 채택되지 않았다** |
| `docs/agent-v2/bak/chatbot_optimization_feature_spec.md` | 채택된 설계 명세서(통합형). 기존 예측 파이프라인에 최적화 의도 3종(`optimize_reduce_defect`/`optimize_find_defect_risk`/`predict_and_optimize`)과 `clarify`를 통합하며, 실제 코드와 대체로 일치한다. `predict_and_find_risk`는 이 명세서에 없는 추가 의도이다 |
| `docs/agent-v2/aistudio_optimization_troubleshooting.md` | Altair AI Studio 최적화(Prescriptive Analytics) 구성 트러블슈팅 기록. Python 코드와 직접 관련 없는 서버(모델) 측 참고 자료 |

## 변경 이력

- (작성일 미상) 이 문서 최초 작성: `defect-predictor`의 `docs/code_inventory.md` 형식을 기준으로 `defect-advisor`용으로 작성했다. 소스(`aihub/` 전체, `docs/agent-v2/` 3개 문서)를 열람해 대조했으며, 실행 검증은 하지 않았다.
- (작성일 미상) `docs/architecture.md` 신규 작성 후 문서 표에 항목을 추가했다. 이전에는 README가 defect-predictor 쪽 문서를 대신 가리키고 있었다.
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
- **2026-11-02**: 소스 대조 후 2건 수정. (1) 하위 폴더(web/) 파일 목록에 `favicon.ico` 추가. (2) 문서(docs/) 섹션에 `logic.md` 항목 추가.
- **2026-11-02**: 패키지 테이블 전체 항목을 간략하게 재작성. 변경 이력 성격의 `[수정]`/`[신규]`/`[확인 필요]` 주석을 제거하고, 현재 상태 기준으로 각 파일 역할을 1~2문장으로 정리했다. 테스트 섹션 서두와 문서 섹션 항목도 같은 방식으로 간소화했다.
