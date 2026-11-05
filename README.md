# Siemens AI Demo

Siemens AI Platform 관련 서비스 연동 및 로컬 머신러닝 데모 프로젝트입니다.

## 한눈에 보기

| 폴더 | 한 줄 설명 | 주요 기술 |
|---|---|---|
| `defect-predictor/` | 자연어 질의에서 공정 조건 12개를 추출해 외부 결함률 예측 API로 보내고, 결과를 해설하는 대화형 서비스 (CLI, HTTP API, 로컬 웹 UI) | Python, FastAPI, Pydantic, httpx, Siemens SDC LLM Gateway |
| `defect-advisor/` | `defect-predictor`와 동일한 예측 기능에 **공정 최적화(불량 최소화 / 위험 조건 탐색) API 연동**을 추가한 버전 (CLI, HTTP API, 로컬 웹 UI — 웹 UI는 최적화 조건 전용 렌더링 영역 없음, 결과는 답변 텍스트와 raw JSON으로 확인) | Python, FastAPI, Pydantic, httpx, Siemens SDC LLM Gateway |
| `local-ml/` | 같은 12개 공정 조건으로 결함률(%)을 예측하는 모델을 로컬에서 탐색·학습·예측해 보는 스크립트 모음 | Python, pandas, scikit-learn, joblib |
| `defect-dashboard/` | 결함률 예측 및 최적 공정조건 추천 Panopticon 대시보드 제작물 (AI Studio GBT 모델 → AI Hub 배포 → Panopticon 시각화) | Altair AI Studio, AI Hub, Panopticon |
| `agent-learning/` | Tool Calling → MCP Server → ReAct Agent 개념을 Siemens SDC 환경에서 단계별로 직접 구현해보는 학습 레포 | Python, httpx, FastMCP, Siemens SDC LLM Gateway, AI Hub GBT 예측 API |
| `test/` | 루트 공통 유틸리티. `llm_model_test.py`: SDC LLM 게이트웨이에 연결해 지원 모델 목록을 출력 (루트 `.env` 필요) | Python 표준 라이브러리 |

네 폴더는 서로 독립된 프로젝트이며 코드로 연결되어 있지 않습니다. `defect-predictor`와 `defect-advisor`는 입력 스키마(12개 필드)와 패키지 구조가 거의 동일해 같은 계통의 코드베이스로 보이지만, 저장소 안에 둘 사이의 명시적인 연결(같은 import, 변경 이력 문서 등)은 확인되지 않았습니다. `local-ml`는 둘 다와 코드로 연결되어 있지 않으며 입력 컬럼 12개의 이름만 같습니다(아래 [두 프로젝트의 관계](#두-프로젝트의-관계) 참고).

## defect-predictor

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
- 자세한 설계와 정책 결정 사항은 [`defect-predictor/docs/architecture.md`](defect-predictor/docs/architecture.md)를 보세요.

폴더 구조, 설치, 설정, 실행 방법은 [`defect-predictor/README.md`](defect-predictor/README.md)를 보세요.


---

## defect-advisor

### 목적

`defect-predictor`의 결함률 예측 기능(추출·슬롯 필링·검증·예측·해설)을 그대로 유지하면서, 자연어로 "불량을 줄이는 조건", "불량이 잘 나는 조건"을 물으면 별도의 **공정 최적화(Prescriptive Analytics) API**를 호출해 최적 조건과 예상 확률을 알려주는 기능을 추가한 버전입니다. 질의 의도(`intent`)는 LLM이 분류하고, 의도를 최적화 API의 `target`(`"0"`/`"1"`) 값으로 바꾸는 작업은 LLM이 아니라 코드가 고정된 사전으로 수행합니다(환각 방지).

### defect-predictor와의 주요 차이

- `aihub/optimization.py`(신규 모듈)가 최적화 API(GET, `target` 쿼리 파라미터)를 호출합니다. 기존 `aihub/ml.py`(POST, 결함률 예측)와는 별개입니다.
- `aihub/schema.py`의 `INTENTS`에 `predict` 외에 `optimize_reduce_defect`, `optimize_find_defect_risk`, `predict_and_optimize`, `predict_and_find_risk`, `clarify` 5종이 추가되었습니다.
- 로컬 웹 UI(`aihub/web/`)는 `clarify` 상태 처리와 intent별 상태 문구를 지원하며, 최적화 결과는 `answer` 텍스트(Markdown 표)와 `raw` JSON으로 확인할 수 있습니다. 최적화 조건 전용 렌더링 영역은 없습니다.
- `defect-advisor/docs/agent-v2/`에 이 기능을 기획한 명세서가 2종 있으며, 서로 다른 설계(독립 챗봇 vs 기존 파이프라인 통합)를 제안합니다. 실제 코드는 통합형 설계를 따릅니다.

### 의도(intent) 구분

| `intent` | 의미 | 호출 대상 | `target` |
|---|---|---|---|
| `predict` | 주어진 조건의 결함률 예측 (`defect-predictor`와 동일) | 예측 API (`ml.py`) | — |
| `optimize_reduce_defect` | 불량을 줄이는 최적 조건 탐색 | 최적화 API (`optimization.py`) | `"1"` |
| `optimize_find_defect_risk` | 불량이 잘 나는 위험 조건 탐색 | 최적화 API (`optimization.py`) | `"0"` |
| `predict_and_optimize` | 결함률 예측 + 불량 최소화 조건 탐색 | 두 API 모두 | `"1"` |
| `predict_and_find_risk` | 결함률 예측 + 불량 유발 위험 조건 탐색 | 두 API 모두 | `"0"` |
| `clarify` | 의도가 불분명해 되묻는 경우 | 호출 없음 (고정 문구 반환) | — |

- `target` 변환은 `aihub/optimization.py`의 `INTENT_TO_TARGET` 고정 사전과 `build_target()`이 담당합니다. LLM이 직접 고르지 않습니다(환각 방지).
- `predict_and_optimize`·`predict_and_find_risk`는 최적화가 실패해도 예측 결과를 포함해 `status="ok"`로 반환합니다(부분 성공). `optimization=null`과 `errors` 필드로 실패 여부를 확인하세요.

폴더 구조, 설치, 설정, 실행 방법, 알려진 문제는 [`defect-advisor/README.md`](defect-advisor/README.md)를 보세요.


---

## defect-dashboard

### 목적

Altair AI Studio에서 학습한 GBT 모델을 AI Hub에 배포하고, Panopticon 대시보드에서 REST API로 호출해 결과를 시각화하는 제작물입니다. 대시보드는 두 종류로 구성됩니다.

| 대시보드 | 동작 |
|---|---|
| **공정 데이터 결함률 예측 플랫폼** | 12개 공정 변수(슬라이더·드롭다운)를 입력 → 결함률(%) 및 등급(양호/주의/불량) 출력 |
| **최적 공정조건 추천 시스템** | 탐색 방향(`target`: 개선/위험) 선택 → 최적 공정 조건 1세트 테이블 출력 |

### 스택

```
[AI Studio (RapidMiner)]         [AI Hub]                    [Panopticon]
GBT 회귀 모델 학습           →   REST API 엔드포인트 배포  →  Python Transform으로 API 호출
GBT 분류 + Prescriptive 학습                                   슬라이더·드롭다운 입력 UI
                                                               결과 시각화 (TextBox, 테이블)
```

### AI Hub 엔드포인트

| 용도 | 메서드 | URL |
|---|---|---|
| 결함률 예측 | `POST` | `https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_rate_pred/deploy` |
| 최적 공정조건 | `GET` | `https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_flag_classification/deploy-optimization?target=0\|1` |

Panopticon의 Python Transform이 이 두 엔드포인트를 직접 호출합니다. 실행 전 **uvicorn Python Transform 서버(포트 9090)** 가 기동되어 있어야 합니다.

자세한 구성·실행 방법·오류 해결 이력은 [`defect-dashboard/README.md`](defect-dashboard/README.md)를 보세요.

---

## local-ml

### 목적

공정 조건 12개(범주형 3개 + 수치형 9개)로 결함률(`defect_rate_pct`, %)을 회귀 예측하는 모델을 로컬에서 학습하고 사용해 보는 스크립트 모음입니다. EDA → 학습·선정 → 예측 순서로 실행합니다. 데이터는 합성(`SYNTHETIC`) 데이터를 전제로 합니다(`eda.py`가 `data_origin` 분포를 확인).

폴더 구조, 설치, 실행 방법, 알려진 불일치는 [`local-ml/README.md`](local-ml/README.md)를 보세요.


---

## 두 프로젝트의 관계

- **코드 연동 없음**: `defect-predictor`/`defect-advisor`는 `local-ml`를 import하지 않고, `local-ml`도 이들을 호출하지 않습니다.
- **입력 스키마가 같음**: 세 프로젝트의 입력 피처 12개(`production_line`, `shift`, `supplier_code` + 수치형 9개)는 이름이 동일합니다(`local-ml/src/config.py`, `defect-predictor/aihub/schema.py`, `defect-advisor/aihub/schema.py`를 비교해 확인).
- **외부 예측 API와의 관계는 미확인**: defect-predictor / defect-advisor가 호출하는 외부 예측 API가 `local-ml`로 학습한 모델을 서빙하는지는 이 저장소의 코드만으로는 알 수 없습니다. (해설 프롬프트가 “GBT 모델”이라고 언급하고 local-ml 학습 후보에 GBT가 있지만, 이것만으로 같은 모델이라고 단정할 수 없습니다.)
- 모델 출력 형태가 다릅니다. `local-ml/predict.py`는 소수 3자리로 반올림한 값과 위험 등급을, defect-predictor / defect-advisor는 외부 API가 돌려준 예측값(%)을 그대로 사용합니다.
- **`defect-predictor`와 `defect-advisor`의 관계**: 두 패키지는 `config.py`/`schema.py`/`ml.py`/`cli.py`/`api.py` 등 상당 부분의 코드가 동일해 보입니다(문서화 과정에서 비교해 확인). `defect-advisor`가 `defect-predictor`를 복사한 뒤 최적화 기능을 추가해 만든 것으로 추정되나, 두 폴더 사이의 git 이력이나 명시적 선언은 확인하지 못해 **추정**입니다. 두 패키지는 코드로 서로 import하지 않습니다.


---

## agent-learning

### 목적

Tool Calling · MCP · AI Agent 개념을 Siemens SDC 환경에서 단계적으로 직접 구현해보는 학습 레포입니다. 각 단계가 독립된 스크립트로 구성되어 있으며, 같은 도메인(공정 결함률 예측)을 소재로 개념을 쌓아 올립니다.

### 학습 단계

| 단계 | 디렉토리 | 핵심 개념 |
|------|----------|-----------|
| 1 | `01_tool_calling/` | LLM이 외부 함수를 어떻게 호출하는가 (Tool Calling 기본 + ML API 연동) |
| 2 | `02_mcp_server/` | 도구를 USB처럼 표준화해 연결하는 MCP 서버 구현 (FastMCP) |
| 3 | `03_agent/` | Tool Calling을 반복하는 자율 루프 — ReAct 패턴 Agent (최대 15 스텝) |

### 아키텍처

```
core/    ← 인프라: 환경변수·HTTP 호출만 처리
tools/   ← 도메인: 비즈니스 로직·스키마·라우팅
01~03/   ← 애플리케이션: 대화 루프·ReAct 루프
```

### defect-predictor / defect-advisor와의 관계

- 같은 AI Hub GBT 결함률 예측 API(12개 피처 → `prediction(defect_rate_pct)`)를 사용합니다.
- `agent-learning`은 개념 학습용이므로 운영 코드(`defect-predictor` 등)의 슬롯 필링·Pydantic 검증 등의 안전장치가 없습니다.
- 코드 의존 없음 — 세 폴더는 import로 연결되어 있지 않습니다.

폴더 구조, 설치, 실행 방법은 [`agent-learning/README.md`](agent-learning/README.md)를 보세요.

---

## 이 문서의 검증 범위

- 소스·설정·기존 문서를 읽고 작성했습니다. CLI, 웹 UI, local-ml 스크립트, 최적화 API를 **실행해 확인한 결과는 없습니다**.
- `local-ml/data/ML_data.csv`와 `defect-predictor/data/defect_pred_input.csv`의 내용·크기는 확인하지 못했습니다.

## 변경 이력

- (작성일 미상) 루트 README 최초 작성: 폴더별 목적·구성·설치·실행 중심으로 작성.
- **2026-11-05**: `agent-learning/` 폴더 추가 — 한눈에 보기 표 및 섹션 반영.
- **2026-11-04**: `defect-dashboard/` README 작성 및 루트 README 섹션 상세화. `defect-dashboard/` 폴더 추가 — 한눈에 보기 표 및 섹션 반영. `llm_model_test.py`를 루트에서 `test/`로 이동. 한눈에 보기 표에 `test/` 항목 추가.
- **2026-11-02**: defect-advisor 섹션을 소스 대조 후 3건 수정. (1) intent 표에 `predict_and_find_risk` 추가, `target` 열 추가, "추정" 주석 제거. (2) 웹 UI 설명을 현재 상태(clarify 처리 완료, 최적화 결과 answer/raw JSON 표시)로 수정. (3) 검증 범위의 pytest/`.pyc` 관련 구 상태 기술 제거.
