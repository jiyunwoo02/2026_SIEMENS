# 아키텍처

## 전체 구조

```
┌─────────────────────────────────────────────────────────────────────┐
│                         hd-modeling                                 │
│  ┌──────────┐  학습   ┌──────────────────────┐  배포   ┌─────────┐  │
│  │  data/   │ ──────► │       AI Studio       │ ──────► │ model/  │  │
│  │ (훈련    │         │  GBT 회귀 / 분류 학습  │         │ .rmmodel│  │
│  │  데이터) │         │  Grid 하이퍼파라미터   │         └────┬────┘  │
│  └──────────┘         │  최적화               │              │       │
│                       └──────────────────────┘              │       │
│                                                              ▼       │
│                       ┌──────────────────────┐  스냅샷  ┌────────┐  │
│                       │   deploy_process/    │ ──────► │AI Hub  │  │
│                       │  deploy.rmp          │          │        │  │
│                       │  deploy-opt.rmp      │          └───┬────┘  │
│                       └──────────────────────┘              │       │
└─────────────────────────────────────────────────────────────│───────┘
                                                              │ REST API
              ┌───────────────────────────────────────────────┤
              │                                               │
              ▼                                               ▼
   ┌─────────────────────┐                      ┌──────────────────────┐
   │   defect-predictor  │                      │    defect-advisor    │
   │                     │                      │                      │
   │  POST /deploy       │                      │  POST /deploy        │
   │  → defect_rate_pct  │                      │  → defect_rate_pct   │
   │                     │                      │                      │
   │  (회귀 모델 전용)   │                      │  GET /deploy-opt     │
   └─────────────────────┘                      │  → 최적 공정조건     │
                                                │                      │
                                                │  (회귀 + 분류+최적화)│
                                                └──────────────────────┘
```

---

## 컴포넌트 역할

### data/
- `ICX_train_classification*.rmhdf5table` — 분류 모델 학습 데이터 (ICX 공정, 최종본)
- `defect_pred_input.rmhdf5table` — 회귀 모델 입력 데이터
- `make-*.rmp` — 학습 데이터 생성 프로세스

### model/
- `strore-regression-gbt-v0.2` — 현행 회귀 모델 (defect-predictor, defect-advisor)
- `strore-classification-gbt-v0.3` — 현행 분류 모델 (defect-advisor)
- `pre-version/` — 이전 버전 보관 (v0.1, v0.2)

### optimization/
- `optimization-yes.rmp` — Prescriptive Analytics 탐색 (배포 전 실험)
- `최적화프로세스_draft.rmp` — 초안

### deploy_process/
- `deploy.rmp` — 회귀 배포: 외부 입력 12개 → `defect_rate_pct` 반환
- `deploy-optimization.rmp` — 분류+최적화 배포: 매크로 `target` → 최적 공정조건 1세트 반환

---

## 데이터 흐름

### 회귀 예측 흐름

```
클라이언트 (defect-predictor / defect-advisor)
  │  POST {endpoint}
  │  Body: {"data": [{12개 공정 변수}]}
  ▼
AI Hub (deploy.rmp)
  │  GBT 회귀 모델 적용
  ▼
응답: {"data": [{...입력 에코..., "prediction(defect_rate_pct)": 1.65}]}
```

### 최적화 흐름

```
클라이언트 (defect-advisor)
  │  GET {endpoint}?target={0|1}
  ▼
AI Hub (deploy-optimization.rmp)
  │  매크로 target 주입
  │  학습 데이터 로드 (ICX_train_classification_final)
  │  GBT 분류 + Prescriptive Analytics (Evolutionary)
  ▼
응답: {"data": [{12개 최적 조건, "confidence(1)": 0.02, "prediction(high_defect_flag)": "0"}]}
```

---

## 모델 버전 이력

| 버전 | 모델 | 비고 |
|-----|------|-----|
| v0.1 | 회귀 GBT | 초기 버전 |
| v0.2 | 회귀 GBT | 현행 (defect-predictor, defect-advisor 사용 중) |
| v0.1 | 분류 GBT | 초기 버전 |
| v0.2 | 분류 GBT | 중간 버전 |
| v0.3 | 분류 GBT | 현행 (defect-advisor 최적화에 사용 중) |
| v0.1 | 분류 RF  | 실험용, 미사용 |
