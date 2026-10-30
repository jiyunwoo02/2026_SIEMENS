# Siemens AI Demo

Siemens AI Platform 관련 서비스 연동 및 로컬 머신러닝 데모 프로젝트입니다.

## 한눈에 보기

| 폴더 | 한 줄 설명 | 주요 기술 |
|---|---|---|
| `AIHUB/` | 자연어 질의에서 공정 조건 12개를 추출해 외부 결함률 예측 API로 보내고, 결과를 해설하는 대화형 서비스 (CLI, HTTP API, 로컬 웹 UI) | Python, FastAPI, Pydantic, httpx, Siemens SDC LLM Gateway |
| `AIHUB-v2/` | `AIHUB`와 동일한 예측 기능에 **공정 최적화(불량 최소화 / 위험 조건 탐색) API 연동**을 추가한 버전 (CLI, HTTP API, 로컬 웹 UI — 웹 UI는 최적화 결과 표시 미반영) | Python, FastAPI, Pydantic, httpx, Siemens SDC LLM Gateway |
| `ICX_DEMO/` | 같은 12개 공정 조건으로 결함률(%)을 예측하는 모델을 로컬에서 탐색·학습·예측해 보는 스크립트 모음 | Python, pandas, scikit-learn, joblib |

세 폴더는 서로 독립된 프로젝트이며 코드로 연결되어 있지 않습니다. `AIHUB`와 `AIHUB-v2`는 입력 스키마(12개 필드)와 패키지 구조가 거의 동일해 같은 계통의 코드베이스로 보이지만, 저장소 안에 둘 사이의 명시적인 연결(같은 import, 변경 이력 문서 등)은 확인되지 않았습니다. `ICX_DEMO`는 둘 다와 코드로 연결되어 있지 않으며 입력 컬럼 12개의 이름만 같습니다(아래 [두 프로젝트의 관계](#두-프로젝트의-관계) 참고).

## AIHUB

### 목적

사용자가 한국어 자연어로 적은 생산 조건(예: `LINE-BPR-01 주간조, SIM-SUP-B 자재, 533개 ...`)에서 LLM이 입력 값 12개를 추출하고, 값이 모두 확정되면 외부 결함률 예측 API를 호출합니다. 예측값(단위 %)은 LLM이 해설해 응답합니다. 핵심 원칙은 **추측 금지**입니다. 질의에 없거나 모호한 값은 `null`로 두고, API를 호출하지 않은 채 추가 입력을 되묻습니다.

### 처리 흐름

```text
사용자 질의
  → [llm.py / pipeline.QueryExtractor]  LLM이 12개 필드를 JSON으로 추출 (명시되지 않은 값은 null)
  → [pipeline.SlotFillingSession]       이전 턴에서 확인된 값과 병합
  → 누락·모호 필드가 있으면 need_more_info (ML 미호출)
  → [schema.DefectRateInput]             Pydantic으로 타입·범위·허용값 검증, 위반 시 invalid_input (ML 미호출)
  → [ml.DefectRateMLClient]             {"data": [...]} 한 번의 POST (재시도, 응답 검증)
  → [llm.py]                            예측값 해설 (실패해도 수치 답변으로 대체)
  → status = ok
```

- 조건을 비교하는 질의(예: 라인 01과 02 비교)는 LLM이 레코드 여러 건으로 분리하고, ML API는 **레코드 전체를 한 번의 요청**으로 받습니다. 레코드별 병렬 호출이 아닙니다. 레코드 분리 자체는 코드가 아니라 추출 프롬프트의 규칙에 의존합니다.
- 세션은 서버 프로세스 메모리에만 저장되며 재시작하면 사라집니다. 만료·영속 저장·워커 간 공유는 없습니다.
- 자세한 설계와 정책 결정 사항은 [`AIHUB/docs/architecture.md`](AIHUB/docs/architecture.md)를 보세요.

폴더 구조, 설치, 설정, 실행 방법은 [`AIHUB/README.md`](AIHUB/README.md)를 보세요. <!-- [추가] 2026-10-22: AIHUB 상세 문서 링크 (문서 변경, 로직 변경 없음) -->


---

## AIHUB-v2

<!-- [수정] 2026-10-22: 날짜 누락된 변경 주석을 정리하고, 의도(intent) 분기 표와 확인되지 않은 항목 명시를 추가 (문서 변경, 로직 변경 없음) -->
### 목적

`AIHUB`의 결함률 예측 기능(추출·슬롯 필링·검증·예측·해설)을 그대로 유지하면서, 자연어로 "불량을 줄이는 조건", "불량이 잘 나는 조건"을 물으면 별도의 **공정 최적화(Prescriptive Analytics) API**를 호출해 최적 조건과 예상 확률을 알려주는 기능을 추가한 버전입니다. 질의 의도(`intent`)는 LLM이 분류하고, 의도를 최적화 API의 `target`(`"0"`/`"1"`) 값으로 바꾸는 작업은 LLM이 아니라 코드가 고정된 사전으로 수행합니다(환각 방지).

### AIHUB와의 주요 차이

- `aihub/optimization.py`(신규 모듈)가 최적화 API(GET, `target` 쿼리 파라미터)를 호출합니다. 기존 `aihub/ml.py`(POST, 결함률 예측)와는 별개입니다.
- `aihub/schema.py`의 `INTENTS`에 `predict` 외에 `optimize_reduce_defect`, `optimize_find_defect_risk`, `predict_and_optimize`, `predict_and_find_risk`, `clarify` 5종이 추가되었습니다.
- 로컬 웹 UI(`aihub/web/`)는 **아직 최적화 기능을 반영하지 못했습니다**(`clarify` 상태 처리 누락 등). CLI와 HTTP API는 최적화 결과를 다루지만, 웹 UI 화면에는 표시되지 않습니다. 자세한 내용은 [`AIHUB-v2/README.md`의 "알려진 문제"](AIHUB-v2/README.md#알려진-문제--확인-필요-사항)를 보세요.
- `AIHUB-v2/docs/agent-v2/`에 이 기능을 기획한 명세서가 2종 있으며, 서로 다른 설계(독립 챗봇 vs 기존 파이프라인 통합)를 제안합니다. 실제 코드는 통합형 설계를 따릅니다.

### 의도(intent) 구분

| `intent` | 의미 | 호출 대상 |
|---|---|---|
| `predict` | 주어진 조건의 결함률 예측 (`AIHUB`와 동일) | 예측 API (`ml.py`) |
| `optimize_reduce_defect` | 불량을 줄이는 조건 탐색 | 최적화 API (`optimization.py`) |
| `optimize_find_defect_risk` | 불량이 잘 나는 위험 조건 탐색 | 최적화 API (`optimization.py`) |
| `predict_and_optimize` | 예측과 최적화를 함께 요청 | 두 API 모두 (추정, 코드 확인 필요) |
| `clarify` | 의도가 불분명해 되묻는 경우 | 호출 없음 (추정, 코드 확인 필요) |

- 각 `intent`가 `target` `"0"`/`"1"` 중 어느 값에 대응하는지는 `aihub/optimization.py`의 매핑 사전을 직접 확인해야 합니다. 이 문서에서는 값을 단정하지 않습니다.
- 표에서 "추정"으로 표시한 항목은 이 저장소의 기존 문서와 명칭을 근거로 한 것이며, 코드를 실행해 검증하지 않았습니다.

폴더 구조, 설치, 설정, 실행 방법, 알려진 문제는 [`AIHUB-v2/README.md`](AIHUB-v2/README.md)를 보세요.


---

## ICX_DEMO

### 목적

공정 조건 12개(범주형 3개 + 수치형 9개)로 결함률(`defect_rate_pct`, %)을 회귀 예측하는 모델을 로컬에서 학습하고 사용해 보는 스크립트 모음입니다. EDA → 학습·선정 → 예측 순서로 실행합니다. 데이터는 합성(`SYNTHETIC`) 데이터를 전제로 합니다(`eda.py`가 `data_origin` 분포를 확인).

폴더 구조, 설치, 실행 방법, 알려진 불일치는 [`ICX_DEMO/README.md`](ICX_DEMO/README.md)를 보세요. <!-- [추가] 2026-10-22: ICX_DEMO 상세 문서 링크 (문서 변경, 로직 변경 없음) -->


---

## 두 프로젝트의 관계

- **코드 연동 없음**: `AIHUB`/`AIHUB-v2`는 `ICX_DEMO`를 import하지 않고, `ICX_DEMO`도 이들을 호출하지 않습니다.
- **입력 스키마가 같음**: 세 프로젝트의 입력 피처 12개(`production_line`, `shift`, `supplier_code` + 수치형 9개)는 이름이 동일합니다(`ICX_DEMO/src/config.py`, `AIHUB/aihub/schema.py`, `AIHUB-v2/aihub/schema.py`를 비교해 확인).
- **외부 예측 API와의 관계는 미확인**: AIHUB(-v2)가 호출하는 외부 예측 API가 `ICX_DEMO`로 학습한 모델을 서빙하는지는 이 저장소의 코드만으로는 알 수 없습니다. (해설 프롬프트가 “GBT 모델”이라고 언급하고 ICX_DEMO 학습 후보에 GBT가 있지만, 이것만으로 같은 모델이라고 단정할 수 없습니다.)
- 모델 출력 형태가 다릅니다. `ICX_DEMO/predict.py`는 소수 3자리로 반올림한 값과 위험 등급을, AIHUB(-v2)는 외부 API가 돌려준 예측값(%)을 그대로 사용합니다.
- **`AIHUB`와 `AIHUB-v2`의 관계**: 두 패키지는 `config.py`/`schema.py`/`ml.py`/`cli.py`/`api.py` 등 상당 부분의 코드가 동일해 보입니다(문서화 과정에서 비교해 확인). `AIHUB-v2`가 `AIHUB`를 복사한 뒤 최적화 기능을 추가해 만든 것으로 추정되나, 두 폴더 사이의 git 이력이나 명시적 선언은 확인하지 못해 **추정**입니다. 두 패키지는 코드로 서로 import하지 않습니다.


## 이 문서의 검증 범위

- 소스·설정·기존 문서를 읽고 작성했습니다. pytest, CLI, 웹 UI, ICX_DEMO 스크립트, 최적화 API를 **실행해 확인한 결과는 없습니다**.
- `ICX_DEMO/data/ML_data.csv`와 `AIHUB/data/defect_pred_input.csv`의 내용·크기는 확인하지 못했습니다.
- `AIHUB-v2/test/`에는 `.py` 테스트 원본이 없고 커맴파일(`.pyc`)만 남아 있어, 현재 상태에서 `pytest`가 테스트를 수집하는지는 확인하지 못했습니다(자세히는 `AIHUB-v2/README.md`의 "테스트" 절 참고).

<!-- [수정] 2026-10-22: 루트 README를 폴더별 목적·구성·설치·실행 중심으로 재작성 (문서 변경, 로직 변경 없음) -->
