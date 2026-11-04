# HD_결함률 프로젝트

공정 데이터 기반 결함률 예측 및 최적 공정조건 추천 플랫폼 개발.
Altair AI Studio(RapidMiner) + AI Hub + Panopticon 스택 활용.

---

## 프로젝트 구조

```
HD_결함률/
├── 01 Data/          — 학습/예측용 데이터 (.rmhdf5table)
├── 02 Process/       — AI Studio 학습 프로세스 (.rmp)
│   └── store/        — 학습된 모델 (.rmmodel)
├── 03 Deploy/        — 배포용 모델 및 프로세스
│   ├── model/        — 배포 모델 (.rmmodel)
│   └── process/      — 배포 프로세스 (.rmp)
├── 04 Panopticon/    — Panopticon 대시보드 파일 및 시각화용 데이터
└── 자료/             — 참고 문서
```

---

## 데이터

### 입력변수 (12개)

| 변수명 | 타입 | 설명 | 범위 |
|--------|------|------|------|
| `production_line` | 범주형 | 생산 라인 | LINE-BPR-01, LINE-BPR-02 |
| `shift` | 범주형 | 근무 교대 | DAY, NIGHT |
| `supplier_code` | 범주형 | 공급업체 | SIM-SUP-A, SIM-SUP-B, SIM-SUP-C |
| `planned_quantity` | 정수형 | 계획 생산량 | 440 ~ 561 |
| `ambient_humidity_pct` | 실수형 | 주변 습도 (%) | 28 ~ 86 |
| `incoming_material_quality_score` | 실수형 | 입고 자재 품질 점수 | 70.8 ~ 99 |
| `coating_target_thickness_um` | 실수형 | 코팅 목표 두께 (μm) | 62 ~ 121 |
| `weld_energy_setting_pct` | 실수형 | 용접 에너지 설정값 (%) | 76 ~ 118 |
| `fixture_alignment_offset_mm` | 실수형 | 지그 정렬 편차 (mm) | 0.02 ~ 1.6 |
| `process_setting_deviation_pct` | 실수형 | 공정 설정 편차 (%) | 0.05 ~ 16 |
| `tool_wear_pct` | 실수형 | 공구 마모율 (%) | 2 ~ 83.9 |
| `days_since_maintenance` | 정수형 | 마지막 정비 후 경과일 | 1 ~ 60 |

### 출력변수 (모델별)

| 모델 | 출력변수 | 타입 | 데이터 행 수 |
|------|----------|------|-------------|
| Regression | `defect_rate_pct` (결함률 %) | 연속형 | 2,400행 |
| Classification | `high_defect_flag` (0=정상, 1=비정상) | 범주형 | 2,040행 |

### 원본 CSV 컬럼 (전체)
`lot_no`, `work_order_id`, `item_id`, `item_revision_id`, `production_date`,
`production_line`, `shift`, `supplier_code`, `planned_quantity`,
`ambient_humidity_pct`, `incoming_material_quality_score`,
`coating_target_thickness_um`, `weld_energy_setting_pct`,
`fixture_alignment_offset_mm`, `process_setting_deviation_pct`,
`tool_wear_pct`, `days_since_maintenance`,
`defect_count`, `defect_rate_pct`, `high_defect_flag`,
`data_origin`, `dataset_split`

---

## AI Studio 학습 프로세스 (02 Process)

### 01_regression_gbt_optimization.rmp
- **목표**: `defect_rate_pct` 예측 (GBT 회귀)
- **전처리**: 결측 필터링 → ID/불필요 컬럼 제거 (lot_no, work_order_id, item_id, item_revision_id, production_date, data_origin, defect_count, high_defect_flag)
- **데이터 분할**: `dataset_split` 컬럼 기준 (train/validation → 학습, test → 평가)
- **Grid 탐색**: number_of_trees [50~500], maximal_depth [3~15], learning_rate [0.001~0.1]
- **평가지표**: RMSE, Absolute Error, Relative Error, R²
- **저장 경로**: `store/strore-regression-gbt`

### 02_classification_gbt_optimization.rmp
- **목표**: `high_defect_flag` 분류 (GBT 분류, binominal)
- **전처리**: 결측 필터링 → ID/불필요 컬럼 제거 (lot_no, work_order_id, item_id, item_revision_id, production_date, data_origin, defect_count, defect_rate_pct)
- **데이터 분할**: `dataset_split` 컬럼 기준
- **Grid 탐색**: number_of_trees [50~150], maximal_depth [3~10], learning_rate [0.01~0.05]
- **평가지표**: Accuracy, RMSE, R²
- **저장 경로**: `store/strore-classification-gbt`

### 03_classification_gbt_optimization.rmp
- 최적화 프로세스 작업 중 (미완성) — Prescriptive Optimization (Evolutionary) 오퍼레이터 배치

---

## 배포 프로세스 (03 Deploy)

### deploy-gbt-prediction(regression).rmp
- **동작**: 외부 입력(12개 변수) → GBT 회귀 모델 적용 → `defect_rate_pct` 반환
- **모델**: `model/strore-regression-gbt-v0.2`

### deploy-gbt-optimization(classification).rmp
- **동작**: 학습 데이터 로드 → GBT 분류 모델 + Prescriptive Analytics → 최적 공정조건 반환
- **모델**: `model/strore-classification-gbt-v0.3`
- **매크로 `target`**: 외부 API로 주입 (1=abnormal 조건 최적화, 0=normal 조건 최적화)
- **레이블 매핑**: high_defect_flag 0→normal, 1→abnormal

---

## AI Hub 엔드포인트 URL

| 모델 | 용도 | URL |
|------|------|-----|
| GBT 회귀 | `defect_rate_pct` 예측 | `https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_rate_pred/deploy` |
| GBT 분류 최적화 | 최적 공정조건 반환 | `https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_flag_classification/deploy-optimization` |

---

## 전체 아키텍처

```
[AI Studio]                [AI Hub]               [Panopticon]
학습 프로세스 (.rmp)  →   스냅샷 배포        →   REST API 호출
GBT 모델 생성              엔드포인트 생성         대시보드 시각화
                           REST API 제공
```

### 예상 Panopticon 대시보드 구성
1. **결함률 예측 대시보드** (Regression)
   - 12개 공정변수 입력 (슬라이더/드롭다운)
   - REST API 호출 → `defect_rate_pct` 예측값 출력
2. **최적 공정조건 추천 대시보드** (Classification 최적화)
   - target 선택 (0=정상 조건 / 1=비정상 조건)
   - REST API 호출 → 최적 공정 파라미터 조합 출력

---

## 참고: HT_목상해 프로젝트 (멘토 예시)
동일 폴더(`HT_목상해/HT_목상해/`) 내 완성된 참고 프로젝트.
- 목상해 성능 4종 예측 GBT 모델 + Panopticon 대시보드
- 판옵티콘 사용자 매뉴얼: `자료/판옵티콘 사용자 매뉴얼_트랜시스(목상해).pptx`
- Panopticon 파이썬 코드 패턴, 데이터 테이블 생성 방법 등 참고 가능
