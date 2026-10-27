# 코드 목록 (Code Inventory)

패키지는 프로젝트 루트의 `aihub/` 입니다. import는 `from aihub.pipeline import DefectRatePipeline` 형태입니다.

실행·테스트 방법과 pytest 설명은 [`run.md`](./run.md)를 참고합니다.

## 패키지 `aihub/`

| 파일 | 역할 |
| --- | --- |
| `__init__.py` | [신규 기재] 패키지 공개 API 재노출(`DefectRatePipeline`, `PipelineResult`, `SlotFillingSession`, `DefectRateInput`, `build_payload`), `__version__ = "1.0.0"` |
| `__main__.py` | [신규 기재] `python -m aihub` 진입점. `cli.main()`을 호출하고 반환값을 `SystemExit`으로 전달 |
| `config.py` | `.env` 설정 (SDC LLM, ML 엔드포인트, `MOCK_ML`) |
| `schema.py` | 12개 필드 정의, 라인·공급사 화이트리스트(`ALLOWED_PRODUCTION_LINES` 2종, `ALLOWED_SUPPLIER_CODES` 3종), `DefectRateInput` 검증, 필드 단위 검증 `validate_provided_fields()` (2026-10-23 추가), 추출 JSON Schema, payload |
| `llm.py` | SDC LLM 클라이언트 + 추출 프롬프트(`EXTRACTION_SYSTEM_PROMPT`, 불확실한 값을 A/B 두 유형으로 분류·단위 환산·항목 표시 없는 값 매칭·`[아직 필요한 값]` 목록 생성 포함) + 해설 프롬프트(`ANSWER_SYSTEM_PROMPT`) |
| `ml.py` | 결함률 예측 API 클라이언트 (재시도, 에코 검증) |
| `pipeline.py` | 추출·모호 정정 처리(확인된 필드를 모호하게 정정하면 세션 슬롯을 비우고 재질문, 2026-10-26 추가)·필드 단위 검증·세션 병합·검증·예측·해설 |
| `api.py` | FastAPI: 로컬 웹 UI 정적 제공(`GET /` → `web/index.html`, `GET /ui-assets/*` → `web/` 디렉터리 마운트) + `/health`, `/chat/predict`, 세션 삭제 |
| `cli.py` | 한 줄/대화형 CLI (`python -m aihub`) |

### 하위 폴더

| 경로 | 역할 |
| --- | --- |
| `prompt/llm_prompt_v1.py`, `prompt/llm_prompt_v2.py` | [신규 기재] `EXTRACTION_SYSTEM_PROMPT` 변경 이력을 남긴 스냅샷 파일. `llm.py`는 프롬프트 문자열을 자체적으로 정의하며 이 두 파일을 import하지 않는다(소스 전체를 읽어 확인; `__init__.py`가 없어 공식 서브패키지도 아니다). `llm_prompt_v2.py`의 `EXTRACTION_SYSTEM_PROMPT`는 현재 `llm.py`의 내용과 텍스트가 동일해 과거 버전과의 차이를 비교하는 이력 자료로 보인다. 실행에는 영향이 없다 |
| `web/index.html`, `web/app.js`, `web/style.css`, `web/ui.sh` | 로컬 웹 UI 정적 파일. `api.py`가 `/`(index.html)와 `/ui-assets/*`로 제공한다. 상세 사양·DOM·API 계약은 `docs/web_ui.md` 참고 |

## 테스트 (`test/`)

| 파일 | 역할 |
| --- | --- |
| `test_core.py` | 스키마, 슬롯 필링, ML 응답 파싱, 골든 v2(`data/v2/`) C01/I01. LLM·HTTP 없음 |
| `test_golden_v2.py` | 골든 v2(`data/v2/golden_set_v2.json`) 전체 케이스: 데이터 규칙 일관성, 추출 이후 판정(status·missing·ambiguous·invalid·payload), 멀티턴 기대 payload, 추출 후처리·스키마·프롬프트, 필드 단위 검증·남은 필드 매칭·항목 표시 없는 숫자 회귀 테스트(2026-10-23 추가), 확인된 필드의 모호한 정정 → 슬롯 비움·재질문 회귀 테스트(2026-10-26 추가). LLM 추출은 대역(실제 LLM의 단위 환산·매칭 정확도는 미검증) |
| `test_api.py` | 정적 UI 라우트와 대화 API 계약. 파이프라인은 대역 |
| `golden_llm_extract.py` | pytest가 아닌 실행형 스크립트. 골든 v3 JSON(`data/golden_set_v3.json`)의 단일 턴 질의를 **실제 LLM**에 보내 추출 결과를 기대값과 비교해 CSV로 저장한다(`test/results/`). 추출 단계만 실행하며 멀티턴·ML 호출·해설은 하지 않는다. `.env`의 LLM 설정과 네트워크가 필요하다 |
| `results/` | `golden_llm_extract.py`가 만든 비교 결과 CSV(`golden_v2_llm_*`, `golden_v3_llm_*`). 이번 문서 정리에서는 내용을 읽지 않았다 |
| `curl_test.sh` | ML 엔드포인트 스모크 curl |

<!-- [수정] 2026-10-26 (문서 변경, 로직 변경 없음): golden_llm_extract.py·results/ 항목 추가. pytest 두 파일은 아직 v2 JSON을 읽고 v3는 읽지 않는다 -->
> 현재 pytest(`test_core.py`, `test_golden_v2.py`)는 v2 골든 셋만 검증하며, v3(`data/golden_set_v3.*`)를 읽는 테스트는 없습니다. v3는 `golden_llm_extract.py`(실제 LLM, 단일 턴)만 사용합니다.

## 데이터·문서

| 경로 | 역할 |
| --- | --- |
| `data/golden_set_v3.json` (= `golden_set_v3.csv`) | 현행 골든 셋 v3 단일 턴 60건 (C01–C19, P01–P12, N01–N05, A01–A12, I01–I12). `test/golden_llm_extract.py`(실제 LLM, 추출 단계만)가 JSON을 읽고, pytest는 읽지 않는다. 건수는 CSV의 ID를 세어 확인했다. JSON은 용량이 커서 열어 보지 못했으므로 CSV와 내용·건수가 일치하는지는 확인이 필요하다 |
| `data/golden_set_v3_multi_turn.csv` | v3 멀티턴 14건 (MT01–MT14, 턴별 기대값). 이를 읽는 코드·테스트는 확인되지 않음 |
| `data/v2/golden_set_v2.json` (+ `.csv`) | 이전 버전 v2.0 (C01–C10, P01–P08, N01–N05, A01–A07, I01–I05, MT01–MT06). 현재 pytest가 읽는다 |
| `data/v1/golden_set.json` (+ `.csv`) | 이전 버전 v1.1 (G01–G14, M01–M03) |
| `data/base/defect_pred_input.csv` | 예측용 입력 CSV (내용은 이번에 확인하지 않음) |
| `docs/architecture.md` | 파이프라인 설계 |
| `docs/input_schema.md` | 12개 입력 필드 |
| `docs/run.md` | pytest 설명, CLI/HTTP/curl 실행 가이드 |
| `docs/web_ui.md` | 로컬 웹 UI 구현, API 계약, 제약 |
| `architecture.svg`, `example.svg` | 예제 기반 파이프라인 도식화 |

## 변경 이력

<!-- [추가] 2026-10-27 (문서 변경, 로직 변경 없음): 실제 날짜를 확인할 방법이 없어 기존 변경 이력의 날짜 표기 관례를 이어서 썼다 -->
- 2026-10-27 (문서 변경, 로직 변경 없음): `aihub/__init__.py`, `aihub/__main__.py`, `aihub/prompt/`(미사용 프롬프트 스냅샷), `aihub/web/`(로컬 UI 정적 파일)을 목록에서 누락해 추가했다. `api.py`가 `/`, `/ui-assets/*`로 정적 UI를 제공한다는 점과 `schema.py`의 라인·공급사 화이트리스트, `llm.py`의 해설 프롬프트(`ANSWER_SYSTEM_PROMPT`)를 표에 반영했다. 소스를 다시 읽어 대조했으며 `prompt/`가 어디서도 import되지 않는 것을 `llm.py`·`pipeline.py`·`cli.py`·`api.py`·`__init__.py` 전체를 읽어 확인했다(원격 터미널의 `grep` 출력은 이 환경에서 캡처되지 않아 사용하지 못했다).
- 2026-10-26 (문서 변경, 로직 변경 없음): 골든 v3 데이터 파일·`golden_llm_extract.py`·`test/results/`·`docs/web_ui.md`를 목록에 추가하고, `data/golden_set_v2.json` 경로를 `data/v2/`로 정정. pytest가 v2만 읽는다는 점을 명시.
