# nice-modeling

NICE평가정보 신용평가 데이터 기반 LightGBM 이진 분류 모델.  
AI Studio(RapidMiner)로 학습하고 AI Hub를 통해 REST API로 서빙한다.  
예측 결과로부터 신용점수(0–1000)를 산출한다.

---

## 프로젝트 구조

```
nice-modeling/
├── data/
│   ├── train_data.txt                    — 학습 데이터 (CSV, 875,624행)
│   ├── test_data.txt                     — 테스트 데이터 (JSON Lines, 245,614건)
│   └── test_to_csv.py                    — JSON Lines → CSV 변환 스크립트
├── model/
│   ├── 261106_pyl_lightgbm.rmmodel       — v1 학습 모델 (Python Learner)
│   ├── 261109_ext_lightgbm.rmtabmod      ← 현행 학습 완료 모델 (LightGBM Extension)
│   ├── create_lightgbm_process_v0.1.rmp  — v1 모델 학습 프로세스
│   ├── create_lightgbm_process_v0.2.rmp  — v2 모델 학습 프로세스 (현행)
│   ├── test_scoring_process.rmp          — 로컬 테스트용 스코어링 프로세스
│   └── docs/
│       └── ai_studio_file_structure.md   — AI Studio 파일 구조 가이드
├── deploy/
│   ├── deploy_scoring_process_v0.1.rmp   — v1 배포 프로세스
│   └── deploy_scoring_process_v0.2.rmp   — v2 배포 프로세스 (현행)
├── docs/
│   ├── endpoint.md                       — API 엔드포인트 명세
│   ├── initial_guide.md                  — AI Studio 모델 구축 가이드
│   ├── lightgbm.md                       — LightGBM 파라미터 · 마이그레이션 가이드
│   ├── logic.md                          — 프로젝트 동작 원리 & 프로세스 문서
│   ├── troubleshooting.md                — 트러블슈팅 기록
│   └── html/
│       ├── guide-nice-scoring.html       — 모델 전체 가이드 (HTML)
│       └── guide-panopticon-dashboard.html — 판옵티콘 대시보드 가이드 (HTML)
└── visualization/
    ├── docs/
    │   ├── Panopticon_dashboard_guide.md — 대시보드 사용 가이드
    │   └── unzip_dashboard_overview.md  — 익스포트 파일 구조 개요
    ├── html/
    │   └── nice_score_dashboard.html    — 대시보드 HTML 시각화
    ├── output/
    │   └── 261112_final_dashboard.exz   — 판옵티콘 대시보드 익스포트 파일
    └── unzip_dashboard/                 — 익스포트 압축 해제 결과물
        ├── server_version.txt           — 판옵티콘 서버 버전 (2609.1.0.36042)
        ├── DataLibrary/datatables/
        └── Workbooks/NICE____/261111_UI_______Workbook/
            ├── workbook.json            — 워크북 최상위 설정
            ├── metadata.json            — 워크북 UUID · 버전
            ├── dashboards/Dashboard1.json — 대시보드 레이아웃 · 파라미터
            ├── datatables/*.json        — DataTable (Python Transform 포함)
            ├── theme.json               — 색상 팔레트
            └── resources/thumbnail.png
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

> **주의**: `train_data.txt` 헤더의 `KEY` 컬럼명 앞에 공백이 있음 (` KEY`). Set Role 설정 시 `KEY → id` 항목을 제거하고 `TARGET → label`만 유지해야 함. (→ [troubleshooting.md](docs/troubleshooting.md) 이슈 1)

---

## 모델

### LightGBM 이진 분류

> 상세 파라미터·마이그레이션 가이드: [docs/lightgbm.md](docs/lightgbm.md)  
> AI Studio 파일 구조: [model/docs/ai_studio_file_structure.md](model/docs/ai_studio_file_structure.md)

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

> 상세 명세: [docs/endpoint.md](docs/endpoint.md)

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

## 시각화 (판옵티콘 대시보드)

> 구조 상세: [visualization/docs/unzip_dashboard_overview.md](visualization/docs/unzip_dashboard_overview.md)  
> 사용 가이드: [visualization/docs/Panopticon_dashboard_guide.md](visualization/docs/Panopticon_dashboard_guide.md)

`261112_final_dashboard.exz`를 판옵티콘 서버(v2609.1.0.36042)에 임포트하면 동작한다.

### 대시보드 구성

- **제목**: NICE평가정보: 신용점수 산출 대시보드
- **워크북**: NICE평가정보 / 261111_UI수정_게이지 Workbook
- **대시보드**: Dashboard1 (단일)

### 동작 방식

```
슬라이더 (47개 CB 변수 조작)
        ↓
Python Transform
(requests.post → v2 엔드포인트)
        ↓
응답: Score, prediction(TARGET), confidence
        ↓
Grade 계산 (최우수 / 우수 / 양호 / 보통 / 주의 / 위험)
Result 계산 (정상 / 불량)
```

슬라이더 범위는 모두 0–10이며, 47개 파라미터를 실시간으로 바꿔 가며 신용점수 변화를 확인할 수 있다.  
캐시 갱신 주기는 15분(900초)이다.

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

> 상세 내용: [docs/troubleshooting.md](docs/troubleshooting.md)

---

## 주의

`.rmp`, `.rmmodel`, `.rmhdf5table` 파일은 `.gitignore`에 의해 추적 제외됨.  
모델 파일은 로컬 AI Studio Repository에서 관리.

## 변경 이력

- **2026-11-13**: 문서 구조 갱신 반영. (1) `docs/test/` 하위 markdown 4종(`endpoint.md`, `initial_guide.md`, `logic.md`, `troubleshooting.md`)을 `docs/`로 이동. (2) HTML 가이드 2종을 `docs/html/`로 이동. (3) `visualization/Panopticon_dashboard_guide.md`를 `visualization/docs/`로 이동하고 `visualization/docs/unzip_dashboard_overview.md` 및 `visualization/html/nice_score_dashboard.html` 추가. (4) `model/docs/ai_studio_file_structure.md` 추가. (5) 깨진 링크 `docs/test/troubleshooting.md` → `docs/troubleshooting.md` 수정.
