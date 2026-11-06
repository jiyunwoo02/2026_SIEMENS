# NICE평가정보 신용평가 모델 - AI Studio 프로세스 문서

## 개요

이 프로젝트는 **NICE평가정보 신용평가 LightGBM 모델**을 Altair AI Studio에서 구현한 것으로,  
모델 학습부터 신용 스코어 산출까지의 파이프라인을 담고 있습니다.

- **알고리즘**: LightGBM 이진 분류 (TARGET: 0/1)
- **출력**: 신용 스코어 (0 ~ 1000점)
- **구현 방식**: 2가지 (기본 Python Extension / 신규 Python SDK)

---

## 전체 동작 원리

### 1단계: 모델 학습 (create_model_process)

train_data 전체를 사용해 LightGBM 이진 분류 모델을 학습합니다.

- **입력**: `train_data.txt` — 고객별 신용 피처 + `TARGET`(0: 정상, 1: 불량) 컬럼 포함
- **목표**: 각 고객이 불량(TARGET=1)일 확률을 예측하는 분류 모델 생성
- **출력**: 학습 완료된 모델 파일 (`.rmmodel`) — 이후 스코어링에 재사용

> train/test 분할 없이 전체 train 데이터로 학습합니다.  
> 모델 성능 검증은 별도 프로세스에서 수행하는 것을 전제로 합니다.

### 2단계: 스코어 산출 (scoring_process)

배포 환경에서 **외부로부터 새 데이터가 입력**되면, 저장된 모델을 불러와 스코어를 계산합니다.

```
외부 데이터 입력 (TARGET 없는 피처 데이터)
  │
  ▼
Apply Model — 학습된 LightGBM 모델로 TARGET 예측
  │
  │  출력: prediction (예측 클래스)
  │        confidence(conf(0)) = P(정상) 확률
  │        confidence(conf(1)) = P(불량) 확률
  │
  ▼
스코어 변환 — confidence 값 기반으로 신용점수 산출
  │
  ▼
Score (0 ~ 1000점)
```

**confidence → 신용점수 변환 공식**

LightGBM이 출력하는 불량 확률 `P(1)`과 정상 확률 `P(0)`을 odds로 변환한 뒤,  
로그 오즈 스케일링으로 신용점수를 계산합니다.

```python
anchor = 640          # 기준 점수 (odds=1일 때의 점수)
pdo    = 80           # Points to Double the Odds (오즈가 2배 될 때 점수 변화량)
factor = pdo / ln(2)  # ≈ 115.44

odds  = P(0) / P(1)              # 정상/불량 오즈
Score = anchor + factor × ln(odds)
Score = clip(Score, 0, 1000).round(0)
```

| 상황 | P(1) | odds | Score |
|---|---|---|---|
| 완전 정상 예측 | → 0 | → ∞ | 1000 (상한) |
| 기준점 (odds=1) | 0.5 | 1.0 | 640 |
| 완전 불량 예측 | → 1 | → 0 | 0 (하한) |

> **점수가 높을수록 신용도 우량**, 낮을수록 불량 가능성 높음

---

## 폴더 구조

### AI Hub 배포 프로젝트 (`Projects/jiyoon-nice/`)

```
jiyoon-nice/
├── data/
│   ├── train_data.txt                  # 모델 학습용 원본 데이터
│   └── test_data.txt                   # 모델 테스트용 데이터
├── model/
│   ├── create_lightgbm_process.rmp     # 모델 학습 프로세스
│   ├── test_scoring_process.rmp        # 로컬 테스트용 스코어링 프로세스
│   └── 261106_pyl_lightgbm.rmmodel     # 학습 완료된 LightGBM 모델
└── deploy/
    └── deploy_scoring_process.rmp      # AI Hub 배포용 스코어링 프로세스
```

### 로컬 테스트 폴더 (`Local Repository/processes/ICX/NICE평가정보/Test/`)

```
Test/
├── 기본 Python Extension 프로세스/
│   ├── ckj_original_file/
│   │   ├── train_data.txt              # 모델 학습용 원본 데이터
│   │   ├── test_data.txt               # 모델 평가용 테스트 데이터
│   │   └── lightgbm_ver1.rmmodel       # 저장된 모델 (ver1)
│   ├── test_sample_3.csv               # 스코어링 샘플 데이터
│   ├── 0519_pyl_lightgbm.rmmodel       # 저장된 학습 모델
│   ├── ckj_create_model_process.rmp    # 모델 학습 프로세스
│   └── ckj_scoring_process.rmp         # 스코어 산출 프로세스
│
└── 신규 Python SDK 프로세스/
    ├── Customer_process/
    │   ├── train_data.txt                      # 학습 데이터
    │   ├── model.rmmodel                       # 저장된 모델
    │   ├── 0519_pyl_lightgbm.rmmodel           # 저장된 모델 (참조용)
    │   ├── ckj_create_model_process.rmp        # 모델 학습 프로세스
    │   ├── ckj_scoring_process.rmp             # 스코어 산출 프로세스
    │   └── ckj_scoring_process_operator.rmp    # 오퍼레이터 분리형 스코어링
    ├── Siemens_process/
    │   ├── train_data.txt              # 학습 데이터
    │   ├── test_data.txt               # 테스트 데이터
    │   ├── gbm_model_customer.ioo      # 저장된 모델 (SDK 포맷)
    │   ├── modeling - 2.rmp            # 모델 학습 프로세스 (SDK 방식)
    │   └── deploy - 2.rmp              # 스코어링/배포 프로세스 (SDK 방식)
    └── SDK 파일/
        └── lgbm-2.9.0.zip              # LightGBM 패키지 (오프라인 설치용)
```

---

## 방식 1: 기본 Python Extension 프로세스

AI Studio의 **Python Extension 오퍼레이터**에 Python 코드를 직접 삽입하는 구방식입니다.

### 모델 학습 (`ckj_create_model_process.rmp`)

```
train_data.txt
  → Open File
  → Read CSV
  → Numerical to Polynominal  (TARGET 컬럼: 숫자 0/1 → nominal 변환)
  → Set Role                   (TARGET → label)
  → Python Learner             (LightGBM 학습)
  → Store                      (모델 저장: 0519_pyl_lightgbm)
```

**LightGBM 하이퍼파라미터**

| 파라미터 | 값 |
|---|---|
| n_estimators | 3000 |
| max_depth | 3 |
| num_leaves | 8 |
| min_child_samples | 800 |
| learning_rate | 0.005 |
| subsample | 0.8 |
| colsample_bytree | 0.3 |
| reg_alpha | 15 |
| reg_lambda | 200 |
| min_split_gain | 0.5 |
| scale_pos_weight | 240 |
| random_state | 317 |

### 스코어 산출 (`ckj_scoring_process.rmp`)

```
(외부 데이터 입력)
  → Apply Model                (저장된 LightGBM 모델 적용 → 확률값 산출)
  → 스코어산출_train            (Python 스크립트: 확률 → 신용점수 변환)
  → 결과 출력
```

**스코어 변환 공식**

```python
anchor = 640
pdo    = 80
factor = pdo / np.log(2)   # ≈ 115.44

odds  = P(0) / P(1)
Score = anchor + factor * ln(odds)
Score = clip(Score, 0, 1000).round(0)
```

> P(1): 불량 확률, P(0): 정상 확률  
> 점수가 높을수록 신용도 우량

---

## 방식 2: 신규 Python SDK 프로세스

### 2-1. Customer_process

기본 Python Extension 방식과 **동일한 LightGBM 학습 로직**을 유지하되,  
AI Studio 버전을 12.0.002로 맞추고 모델 저장명을 `model`로 변경한 버전입니다.

- 학습 프로세스: `ckj_create_model_process.rmp` (기본 방식과 동일 구조)
- 스코어링 프로세스: `ckj_scoring_process.rmp` (동일 스코어 공식 적용)
- 추가: `ckj_scoring_process_operator.rmp` — 스코어링 로직을 별도 오퍼레이터로 분리한 형태

### 2-2. Siemens_process (SDK 오퍼레이터 방식)

AI Studio의 **Python SDK 전용 오퍼레이터** (`py_gbm` 클래스)를 사용하는 신방식입니다.  
모델 포맷이 `.rmmodel` 대신 `.ioo`로 저장됩니다.

#### 모델 학습 (`modeling - 2.rmp`)

```
train_data.txt
  → Open File
  → Read CSV
  → Gbm Train (py_gbm:gbm_train, label_column=TARGET)
  → Store      (모델 저장: gbm_model_customer → .ioo 포맷)
```

#### 스코어링/배포 (`deploy - 2.rmp`)

```
(외부 데이터 입력)
  → Gbm Apply From File  (py_gbm:gbm_apply_from_file, 저장된 .ioo 모델 적용)
  → Generate Attributes  (스코어 공식 적용)
  → 결과 출력
```

**스코어 변환 공식 (Generate Attributes 오퍼레이터)**

```
score = max(0, min(1000, round(640 + (115.44 × log(confidence(0.0) / confidence(1.0))), 0)))
```

---

## 두 방식 비교

| 항목 | 기본 Python Extension | 신규 Python SDK |
|---|---|---|
| 학습 오퍼레이터 | `python_scripting:python_learner` | `py_gbm:gbm_train` |
| 스코어링 오퍼레이터 | `apply_model` + `execute_python` | `py_gbm:gbm_apply_from_file` + `generate_columns` |
| 모델 파일 포맷 | `.rmmodel` | `.ioo` |
| 스코어 공식 적용 | Python 스크립트 내 numpy 연산 | Generate Attributes 수식 |
| LightGBM 패키지 | conda 환경 기본 설치 | `lgbm-2.9.0.zip` 오프라인 설치 |
| AI Studio 버전 | 12.0.005 | 12.0.002 |

---

## 로컬 테스트 프로세스 (`test_scoring_process.rmp`)

**위치**: `Projects/jiyoon-nice/test_scoring_process.rmp`

배포 환경(AI Hub) 없이 로컬 AI Studio에서 모델 스코어링을 검증하기 위한 프로세스입니다.  
`train_data.txt`의 일부를 샘플링해 스코어를 산출하고, 실제 TARGET과 예측값을 함께 확인할 수 있습니다.

```
train_data.txt
  → Read CSV
  → Sample (기본 1,000행 / 전체 실행 시 비활성화)
  → Numerical to Polynominal (TARGET)
  → Set Role (TARGET → label)
  → Apply Model ← Retrieve Model (261106_pyl_lightgbm)
  → Generate Attributes (Score 계산)
  → result
```

**결과 컬럼**

| 컬럼 | 설명 |
|---|---|
| `TARGET` | 실제 레이블 (0: 정상, 1: 불량) |
| `prediction(TARGET)` | 모델 예측값 |
| `confidence(conf(0))` | 정상 확률 P(0) |
| `confidence(conf(1))` | 불량 확률 P(1) |
| `Score` | 신용점수 (0~1000) |

> Sample 오퍼레이터를 우클릭 → Deactivate하면 전체 데이터(875,624행)로 실행 가능.

---

## 배포 정보

스코어링 프로세스(`ckj_scoring_process.rmp`)는 Altair AI Hub에 REST API로 배포되어 있습니다.

| 항목 | 값 |
|---|---|
| AI Hub 프로젝트 | `jiyoon-nice` |
| 서비스명 | `nice_score` |
| Endpoint | `https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/nice_score/ckj_scoring_process` |

요청/응답 형식 및 컬럼 목록 상세는 [endpoint.md](./endpoint.md) 참조.

---

## 데이터 구조

- **형식**: CSV (`,` 구분자, 헤더 포함)
- **인코딩**: SYSTEM (한국어 환경)
- **타임존**: Asia/Seoul
- **주요 컬럼**
  - `KEY`: 고객 식별자 (id 역할)
  - `TARGET`: 레이블 (0: 정상, 1: 불량)
  - 나머지: 신용평가 피처 변수들
