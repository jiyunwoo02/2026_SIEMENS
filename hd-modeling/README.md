# hd-modeling

공정 데이터 기반 결함 예측 ML 모델링 프로젝트.  
GBT(Gradient Boosted Trees) 회귀·분류 모델을 학습하고 AI Hub에 배포한다.

---

## 프로젝트 구조

```
hd-modeling/
├── data/                                        — 학습·검증용 데이터
│   ├── ICX_train_classification.rmhdf5table
│   ├── ICX_train_classification_final.rmhdf5table
│   ├── defect_pred_input.rmhdf5table
│   ├── make-classification-data.rmp
│   └── make-regression-data.rmp
├── model/                                       — 학습 완료 모델
│   ├── strore-regression-gbt-v0.2.rmmodel       ← 현행 회귀 모델
│   ├── strore-classification-gbt-v0.3.rmmodel   ← 현행 분류 모델
│   ├── strore-classification-rf-v0.1.rmmodel    (실험용)
│   └── pre-version/                             (이전 버전 보관)
├── optimization/                                — 최적화 탐색 프로세스 (실험)
│   ├── optimization-yes.rmp
│   └── 최적화프로세스_draft.rmp
├── deploy_process/                              — AI Hub 배포 프로세스
│   ├── deploy.rmp                               ← 회귀 배포
│   └── deploy-optimization.rmp                  ← 분류+최적화 배포
└── docs/                                        — 문서
    ├── architecture.md
    ├── logic.md
    └── html/
        ├── guide-regression.html
        ├── guide-classification.html
        └── guide-optimization.html
```

---

## 모델 개요

| 모델 | 파일 | 입력 | 출력 |
|-----|------|------|------|
| GBT 회귀 | `strore-regression-gbt-v0.2.rmmodel` | 공정 변수 12개 | `defect_rate_pct` (%) |
| GBT 분류 | `strore-classification-gbt-v0.3.rmmodel` | 공정 변수 12개 | `high_defect_flag` (0/1) |

---

## AI Hub 엔드포인트

| 용도 | 메서드 | URL |
|-----|-------|-----|
| 결함률 예측 (회귀) | POST | `https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_rate_pred/deploy` |
| 최적 공정조건 추천 (분류+최적화) | GET | `https://43-200-118-70.sslip.io/webapi/DEFAULT/api/v1/services/defect_flag_classification/deploy-optimization` |

---

## 활용 프로젝트

| 프로젝트 | 사용 모델 | 역할 |
|---------|---------|-----|
| **defect-predictor** | GBT 회귀 | 한국어 질의 → 결함률 예측 |
| **defect-advisor** | GBT 회귀 + GBT 분류(최적화) | 결함률 예측 + 최적 공정조건 추천 |

---

## 도구

- **학습·배포**: Altair AI Studio (RapidMiner)
- **서빙**: Altair AI Hub
- **대시보드**: Altair Panopticon (`defect-dashboard/`)

---

## 주의

`.rmp`, `.rmmodel`, `.rmhdf5table` 파일은 `.gitignore`에 의해 추적 제외됨.  
모델 파일은 별도 스토리지(AI Studio Repository 또는 로컬)에서 관리.

## 변경 이력

- **2026-11-13**: 폴더 구조 갱신 — `docs/` 하위 HTML 가이드 3종(`guide-regression.html`, `guide-classification.html`, `guide-optimization.html`)을 `docs/html/`로 이동 반영.
