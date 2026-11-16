# AI Studio 신용평가 스코어링 모델 가이드

NICE평가정보 신용평가 데이터 기반 스코어링 모델 구축 가이드 (Altair AI Studio / RapidMiner)

---

## 1단계 — 데이터 로드 & EDA

| 오퍼레이터 | 주요 파라미터 |
|-----------|-------------|
| **Read CSV / Read Excel** | encoding, decimal character, date format |
| **Set Role** | `target` → label 지정 (예: `default_flag`, `bad_flag`) |
| **Statistics** | 분포 확인, 결측률 파악 |
| **Data to Similarity** | 상관관계 행렬 |

---

## 2단계 — 전처리

### 결측치
| 오퍼레이터 | 파라미터 | 권장값 |
|-----------|---------|-------|
| **Filter Examples** | condition → `attribute(변수명) != missing` | 결측률 50% 이상 행 제거 |
| **Replace Missing Values** | replenishment → `average` (수치형) / `mode` (범주형) | 결측률 낮을 때 |

### 클래스 불균형 (신용 데이터는 불량률 보통 3~15%)
| 오퍼레이터 | 파라미터 |
|-----------|---------|
| **Sample (Stratified)** | sample size, balance classes → `true` |
| **SMOTE** (Synthetic Minority Oversampling) | sample size ratio → 불량 클래스 증폭 비율 |

> 신용평가에선 **SMOTE보다 cost-sensitive learning** 또는 **stratified sampling**이 더 안전한 경우 많음

### 변수 변환
| 오퍼레이터 | 용도 |
|-----------|-----|
| **Nominal to Numerical** | 범주형 → 더미 인코딩 |
| **Normalize** | z-score / min-max (로지스틱 회귀 필수) |
| **Remove Correlated Attributes** | correlation threshold → `0.85` 이상 제거 |
| **Weight by Information Gain** | IV(Information Value) 기반 변수 선택 사전 확인용 |

---

## 3단계 — WoE 변환 (스코어카드 방식 시)

AI Studio 기본 오퍼레이터엔 WoE 빈이 없어서 **Python Script 오퍼레이터**로 처리:

```python
# Python Script 오퍼레이터 내부
import pandas as pd
import numpy as np

df = rm_main  # RapidMiner에서 넘겨준 DataFrame

def calc_woe_iv(df, feature, target):
    lst = []
    for val in df[feature].unique():
        sub = df[df[feature] == val]
        good = (sub[target] == 0).sum()
        bad  = (sub[target] == 1).sum()
        lst.append({'Value': val, 'Good': good, 'Bad': bad})
    d = pd.DataFrame(lst)
    d['Dist_Good'] = d['Good'] / d['Good'].sum()
    d['Dist_Bad']  = d['Bad']  / d['Bad'].sum()
    d['WoE'] = np.log(d['Dist_Good'] / d['Dist_Bad'])
    d['IV']  = (d['Dist_Good'] - d['Dist_Bad']) * d['WoE']
    return d

rm_main = df  # 변환 결과 반환
```

**IV 기준 변수 선택 기준**

| IV 범위 | 해석 |
|---------|-----|
| < 0.02 | 예측력 없음 (제거) |
| 0.02–0.1 | 약한 예측력 |
| 0.1–0.3 | 중간 예측력 |
| > 0.3 | 강한 예측력 |

---

## 4단계 — 모델 선택

신용평가는 **해석 가능성**이 핵심이라 모델 선택이 중요합니다.

| 모델 | AI Studio 오퍼레이터 | 적합 상황 |
|-----|-------------------|---------|
| **Logistic Regression** | `Logistic Regression` | 스코어카드 필요 시 (규제 대응) |
| **Decision Tree** | `Decision Tree` | 의사결정 규칙 추출 필요 시 |
| **GBT** | `Gradient Boosted Trees` | 성능 우선, 내부 심사 목적 |
| **Random Forest** | `Random Forest` | 앙상블, 변수 중요도 파악 |

### Logistic Regression 주요 파라미터
```
solver              → Auto
regularization type → Ridge (L2)  ← 과적합 방지
C (regularization)  → 1.0 (기본값, Grid Search로 튜닝)
max iterations      → 100~500
```

### GBT 주요 파라미터
```
number_of_trees   → 50~300
maximal_depth     → 3~6  ← 신용평가는 얕게
learning_rate     → 0.01~0.05
early stopping    → true
```

---

## 5단계 — 교차 검증 & 평가

```
Cross Validation (k=5, stratified=true)
└── [모델 오퍼레이터]
└── Performance (Binominal Classification)
    ├── AUC             ← 필수
    ├── accuracy
    ├── precision/recall
    └── lift chart
```

### 신용평가 핵심 지표 — Python Script로 추가 계산

```python
from sklearn.metrics import roc_auc_score
import numpy as np

# Gini = 2 * AUC - 1
gini = 2 * auc - 1

# KS Statistic
from scipy import stats
ks = stats.ks_2samp(scores[y==0], scores[y==1]).statistic
```

| 지표 | 양호 기준 |
|-----|---------|
| **Gini** | > 0.4 |
| **KS** | > 0.3 |
| **AUC** | > 0.7 |

---

## 6단계 — 하이퍼파라미터 최적화

```
Optimize Parameters (Grid)
├── 오퍼레이터: GBT 또는 Logistic Regression
├── Cross Validation (k=5)
└── 최적화 기준: AUC (accuracy보다 불균형 데이터에 적합)
```

---

## 전체 프로세스 흐름

```
Read Data
→ Set Role (target=bad_flag)
→ Filter Examples (결측 제거)
→ Replace Missing Values
→ [Python Script: WoE 변환 & IV 계산]
→ Select Attributes (IV 기준 필터링)
→ Remove Correlated Attributes
→ Normalize
→ Optimize Parameters (Grid)
    └── Cross Validation
        └── Logistic Regression / GBT
        └── Performance (AUC)
→ Apply Model
→ [Python Script: Gini, KS 계산]
→ Store Model
```

---

## NICE 데이터 특성상 추가로 고려할 점

- **개인정보 변수 제거**: 주민번호, 이름 등은 Set Role로 `id` 처리
- **시점 기준(빈티지 분석)**: 대출 실행일 기준 N개월 후 연체 여부를 target으로 정의
- **Population Stability Index(PSI)**: 개발 샘플 vs 검증 샘플 분포 차이 모니터링 — Python Script로 계산
