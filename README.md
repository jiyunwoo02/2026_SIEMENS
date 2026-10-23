# Siemens AI Demo

Siemens AI Platform 관련 서비스 연동 및 로컬 머신러닝 데모 프로젝트입니다.

## 한눈에 보기

| 폴더 | 한 줄 설명 | 주요 기술 |
|---|---|---|
| `AIHUB/` | 자연어 질의에서 공정 조건 12개를 추출해 외부 결함률 예측 API로 보내고, 결과를 해설하는 대화형 서비스 (CLI, HTTP API, 로컬 웹 UI) | Python, FastAPI, Pydantic, httpx, Siemens SDC LLM Gateway |
| `ICX_DEMO/` | 같은 12개 공정 조건으로 결함률(%)을 예측하는 모델을 로컬에서 탐색·학습·예측해 보는 스크립트 모음 | Python, pandas, scikit-learn, joblib |

두 폴더는 서로 독립된 프로젝트이며 코드로 연결되어 있지 않습니다. 다만 입력 컬럼 12개의 이름이 같습니다(아래 [두 프로젝트의 관계](#두-프로젝트의-관계) 참고).

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

## ICX_DEMO

### 목적

공정 조건 12개(범주형 3개 + 수치형 9개)로 결함률(`defect_rate_pct`, %)을 회귀 예측하는 모델을 로컬에서 학습하고 사용해 보는 스크립트 모음입니다. EDA → 학습·선정 → 예측 순서로 실행합니다. 데이터는 합성(`SYNTHETIC`) 데이터를 전제로 합니다(`eda.py`가 `data_origin` 분포를 확인).

폴더 구조, 설치, 실행 방법, 알려진 불일치는 [`ICX_DEMO/README.md`](ICX_DEMO/README.md)를 보세요. <!-- [추가] 2026-10-22: ICX_DEMO 상세 문서 링크 (문서 변경, 로직 변경 없음) -->


---

## 두 프로젝트의 관계

- **코드 연동 없음**: `AIHUB`는 `ICX_DEMO`를 import하지 않고, `ICX_DEMO`도 `AIHUB`를 호출하지 않습니다.
- **입력 스키마가 같음**: 두 프로젝트의 입력 피처 12개(`production_line`, `shift`, `supplier_code` + 수치형 9개)는 이름이 동일합니다(`ICX_DEMO/src/config.py`와 `AIHUB/aihub/schema.py`를 비교해 확인).
- **외부 예측 API와의 관계는 미확인**: AIHUB가 호출하는 외부 예측 API가 `ICX_DEMO`로 학습한 모델을 서빙하는지는 이 저장소의 코드만으로는 알 수 없습니다. (AIHUB 해설 프롬프트가 “GBT 모델”이라고 언급하고 ICX_DEMO 학습 후보에 GBT가 있지만, 이것만으로 같은 모델이라고 단정할 수 없습니다.)
- 모델 출력 형태가 다릅니다. `ICX_DEMO/predict.py`는 소수 3자리로 반올림한 값과 위험 등급을, AIHUB는 외부 API가 돌려준 예측값(%)을 그대로 사용합니다.


## 이 문서의 검증 범위

- 소스·설정·기존 문서를 읽고 작성했습니다. pytest, CLI, 웹 UI, ICX_DEMO 스크립트를 **실행해 확인한 결과는 없습니다**.
- `ICX_DEMO/data/ML_data.csv`와 `AIHUB/data/defect_pred_input.csv`의 내용·크기는 확인하지 못했습니다.

<!-- [수정] 2026-10-22: 루트 README를 폴더별 목적·구성·설치·실행 중심으로 재작성 (문서 변경, 로직 변경 없음) -->
