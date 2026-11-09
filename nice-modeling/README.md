# nice-modeling

NICE평가정보 신용평가 데이터 기반 LightGBM 이진 분류 모델.  
AI Studio(RapidMiner)로 학습하고 AI Hub를 통해 REST API로 서빙한다.  
예측 결과로부터 신용점수(0–1000)를 산출한다.

---

## 프로젝트 구조

```
nice-modeling/
├── data/
│   ├── train_data.txt           — 학습 데이터 (CSV, 875,624행)
│   └── test_data.txt            — 테스트 데이터 (JSON Lines, 245,614건)
├── model/
│   ├── 261106_pyl_lightgbm.rmmodel       ← 현행 학습 완료 모델 (3.79 MB)
│   ├── create_lightgbm_process.rmp       — 모델 학습 프로세스
│   └── test_scoring_process.rmp          — 로컬 테스트용 스코어링 프로세스
├── deploy/
│   └── deploy_scoring_process.rmp        — AI Hub 배포용 스코어링 프로세스
├── docs/
│   ├── guide-nice-scoring.html  — 전체 가이드 (HTML, 한눈에 보기용)
│   ├── lightgbm.md              — LightGBM 파라미터 · 마이그레이션 가이드 (상세)
│   └── test/
│       ├── endpoint.md          — API 엔드포인트 명세
│       ├── initial_guide.md     — AI Studio 모델 구축 가이드
│       ├── logic.md             — 프로젝트 동작 원리 & 프로세스 문서
│       └── troubleshooting.md   — 트러블슈팅 기록
```

---

## 데이터

| 파일 | 형식 | 행 수 | 설명 |
|------|------|-------|------|
| `train_data.txt` | CSV | 875,624 | 학습 데이터. `TARGET`(레이블), `KEY`(ID), 피처 47개 |
| `test_data.txt` | JSON Lines | 245,614 | 스코어링 입력 전용. `TARGET` 미포함 |

### 입력 피처 (47개)

모두 real형. 접두사 패턴 기준:

| 접두사 | 설명 |
|--------|------|
| `R1_CBINQ_*` | 신용조회 관련 |
| `R1_INQPTN_*` | 조회 패턴 |
| `R1_CPCBLA_*` | 카드/CB 잔액 |
| `R1_L*` | 대출 관련 |
| `R1_Z*`, `R1_P*` | 기타 신용 지표 |
| `R1_CF*`, `R1_CL*`, `R1_LC*` | 현금흐름·한도 관련 |

### 레이블

| 값 | 의미 |
|----|------|
| `0` | 정상 (우량) |
| `1` | 불량 |

> **주의**: `train_data.txt` 헤더의 `KEY` 컬럼명 앞에 공백이 있음 (` KEY`). Set Role 설정 시 `KEY → id` 항목을 제거하고 `TARGET → label`만 유지해야 함. (→ [troubleshooting.md](docs/test/troubleshooting.md) 이슈 1)

---

## 모델

### LightGBM 이진 분류

> 상세 파라미터·마이그레이션 가이드: [docs/lightgbm.md](docs/lightgbm.md)

| 하이퍼파라미터 | 값 |
|--------------|-----|
| `num_iterations` | 3,000 |
| `max_depth` | 3 |
| `num_leaves` | 8 |
| `min_data_in_leaf` | 800 |
| `learning_rate` | 0.005 |
| `feature_fraction` | 0.3 |
| `lambda_l1` | 15 |
| `lambda_l2` | 200 |
| `min_gain_to_split` | 0.5 |
| `scale_pos_weight` | 240 |
| `seed` | 317 |

#### 구현 이력

| 버전 | 오퍼레이터 | 모델 파일 | 비고 |
|------|-----------|-----------|------|
| v1 (기존) | Python Learner (`python_scripting:python_learner`) | `261106_pyl_lightgbm.rmmodel` | AI Hub Python Extension 의존 → 이슈 4 발생 |
| v2 (현행) | LightGBM Extension (`lightgbm_extension-1.0.4-all 1.jar`) | `261109_ext_lightgbm.rmtabmod` | Python 의존성 없음, KEY를 id role로 학습, ✅ 운영 중 |

---

## 신용점수 산출

모델이 반환하는 `P(0)` (정상 확률)로부터 아래 공식으로 점수를 산출한다.

```
anchor = 640
pdo    = 80
factor = pdo / ln(2) ≈ 115.44

odds  = P(0) / P(1)
Score = anchor + factor × ln(odds)
Score = clip(0, 1000).round(0)
```

> 점수가 높을수록 우량 (정상 확률 높음). 640점 = odds 1:1 기준점.

AI Studio 구현 (`Generate Attributes`):

```
Score = max(0, min(1000, round(640 + 115.44 * ln(P(0) / P(1)), 0)))
```

---

## 엔드포인트

| 버전 | URL | 모델 | 상태 |
|------|-----|------|------|
| **v2** (현행) | `https://mlops.nice.plda-cloud.com/webapi/DEFAULT/api/v1/services/nice-scoring/deploy_scoring_process_v02` | LightGBM Extension | ✅ 운영 중 |
| v1 (구) | `https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/nice_score/deploy_scoring_process` | Python Learner | ⚠️ ExecutionError |

> 상세 명세: [docs/test/endpoint.md](docs/test/endpoint.md)

### 요청

```json
{
  "data": [{
    "KEY": "...",
    "R1_CBINQ_...": 0.0,
    ...
  }]
}
```

### 응답

| 필드 | 타입 | 설명 |
|------|------|------|
| `prediction(TARGET)` | string | "0" (정상) / "1" (불량) |
| `confidence(0)` | float | 정상 확률 P(0), 0–1 |
| `confidence(1)` | float | 불량 확률 P(1), 0–1 |
| `Score` | float | 신용점수, 0–1000 |

---

## AI Studio 프로세스 구성

### 학습 (`model/create_lightgbm_process.rmp`)

```
Read CSV (train_data.txt)
→ Numerical to Polynominal (TARGET)
→ Set Role (TARGET → label)
→ Python Learner (LightGBM)
→ Store (261106_pyl_lightgbm)
```

### 로컬 테스트 (`model/test_scoring_process.rmp`)

```
Read CSV (train_data.txt)
→ [Sample 1,000행 — 필요 시 비활성화]
→ Numerical to Polynominal (TARGET)
→ Set Role (TARGET → label)
→ Apply Model ← Retrieve (261106_pyl_lightgbm)
→ Generate Attributes (Score 계산)
```

### 배포 (`deploy/deploy_scoring_process_v0.2.rmp`)

```
외부 입력 (TARGET 없는 피처 48개, KEY 포함)
→ Set Role (KEY → id)
→ Apply Model ← Retrieve (../model/261109_ext_lightgbm)
→ Generate Attributes (Score 계산)
→ result
```

---

## 알려진 이슈

| # | 상태 | 내용 |
|---|------|------|
| 1 | ✅ | Python Learner — missing label (헤더 공백 문제) |
| 2 | ✅ | Python Learner — lightgbm 미설치 |
| 3 | ✅ | AI Hub 배포 후 한글 주석·numpy 인코딩 에러 |
| 4 | ✅ | AI Hub 서버 Python Extension 미구성 → LightGBM Extension으로 전환 완료 |
| 5 | ✅ | AI Hub LightGBM Extension JAR 미설치 → 서버 설치 완료 |
| 6 | ✅ | KEY 속성 타입 불일치 (Real vs Integer) → 재학습 + 배포 Set Role 추가 |
| 7 | ✅ | confidence 컬럼명 불일치 → 수식 수정 (`confidence(0)`, `confidence(1)`) |
| 8 | ✅ | Score 수식 줄바꿈 → `1e-10` 단축 표기로 해결 |

> 상세 내용: [docs/test/troubleshooting.md](docs/test/troubleshooting.md)

---

## 주의

`.rmp`, `.rmmodel`, `.rmhdf5table` 파일은 `.gitignore`에 의해 추적 제외됨.  
모델 파일은 로컬 AI Studio Repository에서 관리.
