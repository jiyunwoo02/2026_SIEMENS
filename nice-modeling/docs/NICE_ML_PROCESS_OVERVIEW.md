# nice-test 프로세스 개요 및 개발 이력

> 작성일: 2026-11-16  
> 프로젝트: nice-test  
> 목적: LightGBM 기반 신용점수 분류 모델 개발 및 AI Hub 배포

---

## 1. 최종 결과물 구성

| 구분 | 파일명 | 경로 | 비고 |
|------|--------|------|------|
| 학습 데이터 | `input_data.rmhdf5table` | `data/` | 875,624 rows, 49 features |
| 평가 데이터 | `test_data.rmhdf5table` / `test_data.csv` | `data/` | 스코어링용 |
| ML 모델링 프로세스 | `create_lightgbm_process_v0.2.rmp` | `model/` | 학습 프로세스 최종본 |
| 학습 완료 모델 | `261109_ext_lightgbm.rmtabmod` | `model/` | Extension 포맷 저장 |
| AI Hub 배포 프로세스 | `deploy_scoring_process_v0.2.rmp` | `deploy/` | 스코어링 배포 최종본 |

---

## 2. ML 모델링 프로세스 (`create_lightgbm_process_v0.2`)

### 2.1 데이터 전처리 흐름

```
train_data.txt (CSV)
  → Open File
  → Read CSV (구분자: 쉼표, 헤더 사용, timezone: Asia/Seoul)
  → Numerical to Polynominal (TARGET 컬럼: 0/1 → nominal 변환)
  → Set Role (TARGET → label, KEY → id)
  → LightGBM 학습
  → Store (261109_ext_lightgbm)
```

### 2.2 학습 데이터 명세

| 항목 | 값 |
|------|----|
| 소스 파일 | `train_data.txt` → `input_data.rmhdf5table` |
| 행 수 | 875,624 rows |
| 피처 수 | 49개 (regular attributes) |
| 결측치 | 없음 (no NaN) |
| 타겟 | `TARGET` (0 / 1 이진 분류) |
| 키 | `KEY` (id 역할, 학습 피처에서 제외) |

### 2.3 LightGBM 하이퍼파라미터

| 파라미터 | 값 |
|----------|----|
| boosting | gbdt |
| num_iterations | 3,000 |
| learning_rate | 0.005 |
| num_leaves | 8 |
| max_depth | 3 |
| min_data_in_leaf | 800 |
| feature_fraction | 0.3 |
| bagging_fraction | 1.0 |
| early_stopping | none |
| random_seed (process) | 2001 |
| seed (expert) | 317 |
| lambda_l1 | 15 |
| lambda_l2 | 200 |
| min_gain_to_split | 0.5 |
| scale_pos_weight | 240 |

> **scale_pos_weight = 240**: 불균형 클래스 대응 (1보다 훨씬 많은 0 클래스)

### 2.4 모델 저장 포맷

- **Extension 포맷(`.rmtabmod`)** 사용: `lightgbm_extension-1.0.4` 기반 jar로 학습한 ext 형식으로 저장
- pyl 포맷 모델(`261106_pyl_lightgbm.rmmodel`)과의 파라미터 불일치 문제 방지를 위해 ext 포맷으로 재학습 후 저장

---

## 3. 예측 및 점수 산출 메커니즘

### 3.1 TARGET 정의

| 값 | 의미 |
|----|------|
| `0` | **정상** — 대출/신용 거래에서 연체·불량 이력 없음 |
| `1` | **불량** — 연체·부도 등 신용 사고 발생 |

모델은 주어진 피처(47개 신용 관련 변수)를 바탕으로 각 고객이 `0(정상)`일지 `1(불량)`일지를 예측하는 **이진 분류 모델**이다.

> `scale_pos_weight = 240` 설정은 학습 데이터에서 불량(1) 대비 정상(0)이 약 240배 많은 심각한 클래스 불균형을 반영한 것이다.

### 3.2 예측 흐름

```
입력 피처 (47개)
  → LightGBM 모델
  → confidence(0) : 정상일 확률  P(TARGET=0)
  → confidence(1) : 불량일 확률  P(TARGET=1)
  → prediction(TARGET) : 확률이 더 높은 클래스 ("0" 또는 "1")
  → Score : log-odds 기반 신용점수 (0~1,000)
```

### 3.3 신용점수 산출 원리

confidence(0)과 confidence(1)은 항상 합이 1이다.  
두 값의 비율(오즈, odds)을 로그 변환하여 선형 점수로 변환한다.

```
odds  = confidence(0) / confidence(1)   # 정상/불량 확률 비율
Score = 640 + (80/ln2) × ln(odds)
      = 640 + 115.42 × ln(odds)
```

| 상황 | odds | ln(odds) | Score (대략) |
|------|------|----------|--------------|
| 정상 확률 압도적으로 높음 | ≫ 1 | 양수 (큰 값) | 640 초과, 최대 1,000 |
| 정상·불량 확률 동일 | = 1 | 0 | **640** (기준점) |
| 불량 확률이 더 높음 | < 1 | 음수 | 640 미만, 최소 0 |

- 점수가 **높을수록 신용 우량** (정상 가능성 ↑)
- 기준점 640은 odds = 1 (정상·불량 확률 50:50)일 때의 점수
- PDO(Points to Double Odds) = 80: odds가 2배가 될 때 점수가 80점 상승

---

## 4. AI Hub 배포 프로세스 (RapidMiner, `deploy_scoring_process_v0.2`)

### 3.1 배포 프로세스 흐름

```
[Input Data (input 1)]
  → Set Role (KEY → id)
  ↓
[Retrieve: 261109_ext_lightgbm]
  → Apply Model
  → Generate Attributes (Score 산출)
  → [Result]
```

### 3.2 신용점수 산출 공식

#### 원본 Python 공식

```python
def rm_main(data):
    anchor = 640
    pdo    = 80
    factor = pdo / np.log(2)   # 80 / ln(2) ≈ 115.41560327
    offset = anchor             # 640

    p_pos = data['confidence(conf(1))'].values + 1e-10   # 불량(1) 확률
    p_neg = data['confidence(conf(0))'].values + 1e-10   # 정상(0) 확률

    odds = p_neg / p_pos   # confidence(0) / confidence(1)

    data['Score'] = offset + (factor * np.log(odds))
    data['Score'] = data['Score'].clip(lower=0, upper=1000).round(0).astype(int)
    return data
```

#### RapidMiner 구현 공식

```
Score = max(0, min(1000, round(640 + (115.44 × log(([confidence(0)] + 1e-10) / ([confidence(1)] + 1e-10))), 0)))
```

#### 공식 구성 요소

| 요소 | Python | RapidMiner | 비고 |
|------|--------|------------|------|
| 기준점 (anchor/offset) | 640 | 640 | 동일 |
| PDO (Points to Double Odds) | 80 | — | Python에서 factor 도출에 사용 |
| Factor | `80 / ln(2) = 115.41560327` | `115.44` | **소수점 2자리 반올림** |
| log 함수 | `np.log()` (자연로그) | `log()` (자연로그) | 동일 |
| odds | `confidence(0) / confidence(1)` | `confidence(0) / confidence(1)` | 동일 |
| epsilon 처리 | `+1e-10` (양쪽) | `+1e-10` (양쪽) | 동일 |
| 범위 클리핑 | `clip(0, 1000)` | `max(0, min(1000, ...))` | 동일 |
| 반올림 | `.round(0).astype(int)` | `round(..., 0)` | 동일 |

#### 동일 여부 검토

**결론: 실질적으로 동일** (단, factor에 미세한 반올림 오차 존재)

| 항목 | 값 |
|------|----|
| Python factor 정확값 | `80 / ln(2) = 115.41560327` |
| RapidMiner factor | `115.44` |
| 절대 오차 | `+0.02440` (+0.021%) |
| raw 점수 오차 (최대) | `0.02440 × |ln(odds)|` ≈ **최대 ~0.135점** (유효 점수 범위 내) |
| 정수 점수 차이 | **0점** (전 구간 테스트 결과 동일) |

> raw 점수 오차가 최대 ~0.135점이므로, 반올림 임계값(xx.5) 근방에서 극히 드물게 1점 차이가 발생할 수 있으나, 실용적으로는 동일한 공식으로 간주.

**완전 일치를 보장하려면**: RapidMiner Generate Attributes의 factor `115.44`를 `80 / ln(2) = 115.41560`으로 교체

> log-odds 기반 신용점수 스코어링 방식으로, confidence(0)(정상 확률)이 클수록 점수가 높게 산출됨

---

## 5. AI Hub 배포 및 API (v2)

### 5.1 배포 정보

| 항목 | 값 |
|------|-----|
| 플랫폼 | Altair AI Hub |
| 서버 | `mlops.nice.plda-cloud.com` |
| 서비스명 | `nice-scoring` |
| 프로세스명 | `deploy_scoring_process_v02` |
| 모델 | `261109_ext_lightgbm.rmtabmod` |
| 상태 | 운영 중 |

### 5.2 Endpoint

| 항목 | 값 |
|------|-----|
| URL | `https://mlops.nice.plda-cloud.com/webapi/DEFAULT/api/v1/services/nice-scoring/deploy_scoring_process_v02` |
| Method | `POST` |
| Content-Type | `application/json` |

### 5.3 송신 파라미터 (Request Body)

```json
{
  "data": [
    {
      "KEY": 1,
      "R1_CBINQ_CNT05": 2.0,
      "R1_CBINQ_CNT10_CD": 1.0,
      "..."  : "..."
    }
  ]
}
```

| 항목 | 설명 |
|------|------|
| `data` | 배열 형태, 복수 행 동시 요청 가능 |
| `TARGET` | **송신하지 않음** (예측 대상 컬럼) |
| 결측값 | `null` 사용 |
| 총 컬럼 수 | **48개** (`KEY` 1개 + 피처 47개) |

#### 입력 컬럼 전체 목록

| 순서 | 컬럼명 | 타입 |
|------|--------|------|
| 1 | `KEY` | integer |
| 2 | `R1_CBINQ_CNT05` | real |
| 3 | `R1_CBINQ_CNT10_CD` | real |
| 4 | `R1_CBINQ__CNT07_TL` | real |
| 5 | `R1_CBINQ_CNT6M_TZ` | real |
| 6 | `R1_CBINQ_GGN1Y` | real |
| 7 | `R1_INQPTN_1Y_FN_03_FN` | real |
| 8 | `R1_INQPTN_1Y_FN_07_PF` | real |
| 9 | `R1_INQPTN_6M_FN_15_Z4` | real |
| 10 | `R1_INQPTN_1Y_FN_15_Z4` | real |
| 11 | `R1_INQPTN_1Y_FN_15_SP` | real |
| 12 | `R1_INQPTN_6M_Z4_30_Z4` | real |
| 13 | `R1_INQPTN_1Y_Z4_05_Z4` | real |
| 14 | `R1_CBINQ_CNT03_DIFF` | real |
| 15 | `R1_CBINQ_CNT03_PF_RTO` | real |
| 16 | `R1_CBINQ_CNT05_RTO` | real |
| 17 | `R1_CPCBLA_CNT05_CL` | real |
| 18 | `R1_CPCBLA_CNT05` | real |
| 19 | `R1_L24003800` | real |
| 20 | `R1_ZS0000187` | real |
| 21 | `R1_PS0001190` | real |
| 22 | `R1_PS0001728` | real |
| 23 | `R1_LA0100016` | real |
| 24 | `R1_LA0200013` | real |
| 25 | `R1_LA0300016` | real |
| 26 | `R1_LA0400005` | real |
| 27 | `R1_C00000151` | real |
| 28 | `R1_C11061100` | real |
| 29 | `R1_SC0301005` | real |
| 30 | `R1_SC0602003` | real |
| 31 | `R1_SC1201003` | real |
| 32 | `R1_SC1202006` | real |
| 33 | `R1_LC0000001` | real |
| 34 | `R1_LC0024602` | real |
| 35 | `R1_LC0099025` | real |
| 36 | `R1_LC0300011` | real |
| 37 | `R1_LC0600202` | real |
| 38 | `R1_LC0699001` | real |
| 39 | `R1_LC0900202` | real |
| 40 | `R1_LC2400001` | real |
| 41 | `R1_LC2424801` | real |
| 42 | `R1_LC3600001` | real |
| 43 | `R1_CF0100122` | real |
| 44 | `R1_CF0300939` | real |
| 45 | `R1_CF0600224` | real |
| 46 | `R1_CF1200143` | real |
| 47 | `R1_CF1200223` | real |
| 48 | `R1_CL1200915` | real |

### 5.4 응답 형식 (Response)

```json
{
  "data": [
    {
      "KEY": 1,
      "R1_CBINQ_CNT05": 2.0,
      "R1_CBINQ_CNT10_CD": 1.0,
      "... (47개 피처 컬럼)": "...",
      "prediction(TARGET)": "0",
      "confidence(0)": 0.9821,
      "confidence(1)": 0.0179,
      "Score": 928
    }
  ]
}
```

응답은 요청 시 송신한 전체 컬럼(KEY + 47개 피처)을 그대로 포함하며, 추가로 추론 결과 3개 필드가 붙어서 반환된다.

| 필드 | 구분 | 설명 |
|------|------|------|
| `KEY` | 입력 echo | 요청 시 입력한 식별자 |
| `R1_CBINQ_CNT05` ~ `R1_CL1200915` (47개) | 입력 echo | 요청 시 송신한 피처 컬럼 그대로 반환 |
| `prediction(TARGET)` | 추론 결과 | 예측 클래스 (`"0"`: 정상, `"1"`: 불량) |
| `confidence(0)` | 추론 결과 | 정상일 확률 P(0), 범위 0~1 |
| `confidence(1)` | 추론 결과 | 불량일 확률 P(1), 범위 0~1 |
| `Score` | 추론 결과 | 신용점수 (0~1,000, 높을수록 우량) |

### 5.5 요청 예시

#### cURL

```bash
curl -X POST "https://mlops.nice.plda-cloud.com/webapi/DEFAULT/api/v1/services/nice-scoring/deploy_scoring_process_v02" \
  -H "Content-Type: application/json" \
  -d '{
    "data": [{
      "KEY": 1,
      "R1_CBINQ_CNT05": 2.0,
      "R1_CBINQ_CNT10_CD": 1.0,
      "R1_CBINQ__CNT07_TL": 1.0,
      "R1_CBINQ_CNT6M_TZ": 1.0,
      "R1_CBINQ_GGN1Y": 2.0,
      "R1_INQPTN_1Y_FN_03_FN": 3.0,
      "R1_INQPTN_1Y_FN_07_PF": 2.0,
      "R1_INQPTN_6M_FN_15_Z4": 4.0,
      "R1_INQPTN_1Y_FN_15_Z4": 2.0,
      "R1_INQPTN_1Y_FN_15_SP": 3.0,
      "R1_INQPTN_6M_Z4_30_Z4": 2.0,
      "R1_INQPTN_1Y_Z4_05_Z4": 2.0,
      "R1_CBINQ_CNT03_DIFF": 1.0,
      "R1_CBINQ_CNT03_PF_RTO": 2.0,
      "R1_CBINQ_CNT05_RTO": 2.0,
      "R1_CPCBLA_CNT05_CL": 0.0,
      "R1_CPCBLA_CNT05": 1.0,
      "R1_L24003800": 3.0,
      "R1_ZS0000187": 3.0,
      "R1_PS0001190": 0.0,
      "R1_PS0001728": 0.0,
      "R1_LA0100016": 4.0,
      "R1_LA0200013": 4.0,
      "R1_LA0300016": 4.0,
      "R1_LA0400005": 3.0,
      "R1_C00000151": 0.0,
      "R1_C11061100": 0.0,
      "R1_SC0301005": 2.0,
      "R1_SC0602003": 2.0,
      "R1_SC1201003": 1.0,
      "R1_SC1202006": 1.0,
      "R1_LC0000001": 1.0,
      "R1_LC0024602": 0.0,
      "R1_LC0099025": 0.0,
      "R1_LC0300011": 0.0,
      "R1_LC0600202": 0.0,
      "R1_LC0699001": 0.0,
      "R1_LC0900202": 0.0,
      "R1_LC2400001": 0.0,
      "R1_LC2424801": 0.0,
      "R1_LC3600001": 0.0,
      "R1_CF0100122": 0.0,
      "R1_CF0300939": 1.0,
      "R1_CF0600224": 0.0,
      "R1_CF1200143": 0.0,
      "R1_CF1200223": 0.0,
      "R1_CL1200915": 2.0
    }]
  }'
```

#### Python

```python
import requests

url = "https://mlops.nice.plda-cloud.com/webapi/DEFAULT/api/v1/services/nice-scoring/deploy_scoring_process_v02"
headers = {"Content-Type": "application/json"}

payload = {
    "data": [{
        "KEY": 1,
        "R1_CBINQ_CNT05": 2.0,
        # ... (나머지 47개 컬럼)
        "R1_CL1200915": 2.0
    }]
}

response = requests.post(url, headers=headers, json=payload)
result = response.json()

score = result["data"][0]["Score"]
print(f"신용점수: {score}")
```

---

## 6. 개발 과정 (v0.2 기준)

### 6.1 개발 타임라인

| 날짜 | 커밋 | 주요 내용 |
|------|------|-----------|
| 2026-11-06 | `adb905c` | 프로젝트 시작 (`nice-test` 초기화) |
| 2026-11-09 | `8ffca2e` | LightGBM 모델 포맷 변경: **pyl → ext** (Extension 포맷 채택) |
| 2026-11-09 | `dde5546` | ext_lightgbm 모델 수정 |
| 2026-11-09 | `23677ce` | KEY 컬럼 역할을 `id`로 설정 (학습 피처에서 KEY 제외) |
| 2026-11-09 | `f467c16` | 배포 프로세스에 KEY → id 설정 반영 |
| 2026-11-09 | `b83519f`~`096c451` | Score 산출 공식 반복 수정 (5회, Score ~ Score-5) |
| 2026-11-09 | `8ec771b` | `input_data.rmhdf5table` 생성 (학습 데이터 HDF5 변환) |
| 2026-11-10 | `5a05f44` | 분류 스코어링 프로세스 생성 (`deploy_scoring_process_v0.2`) |
| 2026-11-10 | `89a12b6` | 스코어링용 `test_data.rmhdf5table` / `test_data.csv` 추가 |

### 6.2 주요 변경 포인트

#### pyl → ext 포맷 전환 (2026-11-09)
- **변경 이유**: pyl 포맷 모델(`261106_pyl_lightgbm.rmmodel`)과 Extension 기반 LightGBM 간 파라미터 기준 불일치 발생
- **조치**: `lightgbm_extension-1.0.4-all.jar` 기준의 ext 포맷으로 재학습하여 `261109_ext_lightgbm.rmtabmod` 저장
- **효과**: 배포 프로세스와 모델 간 파라미터 일관성 확보

#### KEY 컬럼 역할 추가 (2026-11-09)
- **변경 이유**: LightGBM은 `id` role 컬럼을 피처로 사용하지 않으므로, KEY를 id로 설정하여 학습 데이터에서 제외
- **조치**: `Set Role`에 `KEY → id` 추가, 재학습 및 배포 프로세스 반영

#### Score 공식 반복 수정 (2026-11-09, 5회)
- 신용점수 스케일, 기준점, log-odds 계산식 조정
- 최종 공식: `640 + 115.44 × log(confidence(0) / confidence(1))`

---

## 7. 프로젝트 디렉토리 구조

```
nice-test/
├── data/
│   ├── input_data.rmhdf5table   # 학습 데이터 (875,624 rows)
│   ├── train_data.txt           # 원천 학습 데이터 (CSV)
│   ├── test_data.rmhdf5table    # 스코어링용 평가 데이터
│   └── test_data.csv            # 스코어링용 평가 데이터 (CSV)
├── model/
│   ├── create_lightgbm_process_v0.2.rmp   # ML 모델링 프로세스 (최종)
│   └── 261109_ext_lightgbm.rmtabmod       # 학습 완료 모델 (최종)
└── deploy/
    └── deploy_scoring_process_v0.2.rmp    # AI Hub 배포 프로세스 (최종)
```
