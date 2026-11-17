# AI Studio

Altair AI Studio(구 RapidMiner Studio)는 코드 없이 드래그 앤 드롭으로 ML 파이프라인을 구성하는 노코드/로우코드 ML 플랫폼입니다.

---

## 1. 핵심 개념

### 오퍼레이터(Operator)

AI Studio의 모든 작업 단위입니다. 캔버스에 오퍼레이터를 올려놓고 포트를 연결해 파이프라인을 구성합니다.

```
[Read CSV] ──▶ [Filter Examples] ──▶ [Set Role] ──▶ [GBT] ──▶ [Write Model]
```

자주 쓰는 오퍼레이터:

| 오퍼레이터 | 역할 |
|-----------|------|
| Read CSV / Read HDF5 | 데이터 불러오기 |
| Filter Examples | 결측치 제거, 조건 필터 |
| Set Role | 타겟(label), 식별자(id) 등 컬럼 역할 지정 |
| Select Attributes | 사용할 컬럼 선택 |
| Split Data | train/test 분할 |
| Gradient Boosted Trees (GBT) | GBT 학습 |
| Apply Model | 학습된 모델로 예측 |
| Cross Validation | 교차 검증 |
| Optimize Parameters (Grid) | 하이퍼파라미터 그리드 탐색 |
| Generate Attributes | 새 컬럼 계산식 추가 |
| Write Model | 모델 파일 저장 |

### 프로세스(Process)

오퍼레이터 연결 그래프 전체를 하나의 `.rmp` 파일로 저장합니다.  
실행하면 왼쪽 → 오른쪽 순서로 각 오퍼레이터가 순차 실행됩니다.

### 서브프로세스(Sub-process)

Cross Validation, Optimize Parameters 같은 오퍼레이터는 내부에 중첩된 프로세스를 갖습니다.  
더블클릭하면 안쪽 캔버스로 들어가 편집할 수 있습니다.

---

## 2. 화면 구성

```
┌──────────┬────────────────────────────┬──────────────┐
│ Operators│        Canvas              │  Parameters  │
│ (검색창) │  [오퍼레이터] → [오퍼레이터] │  (우측 패널) │
│          │                            │              │
│          │                            │              │
├──────────┴────────────────────────────┴──────────────┤
│                   Results (하단)                      │
│  모델 성능, 미리보기 테이블, 플롯 등                   │
└───────────────────────────────────────────────────────┘
```

- **Operators 패널**: 오퍼레이터를 검색해 캔버스로 드래그
- **Canvas**: 오퍼레이터를 연결하는 작업 공간. 포트(삼각형) 간 연결선으로 데이터 흐름 표현
- **Parameters 패널**: 선택한 오퍼레이터의 세부 설정
- **Results 패널**: 실행 결과 (성능 지표, 데이터 미리보기)

---

## 3. 학습 프로세스 예시

### 3-1. GBT 회귀 (결함률 예측)

> **참고 프로젝트**: `hd-modeling/` — `01_regression_gbt_optimization.rmp`

```
[Read HDF5]
  defect_pred_input.rmhdf5table
       │
       ▼
[Filter Examples]  — 결측 행 제거
       │
       ▼
[Select Attributes]  — 불필요 컬럼 제거
  (lot_no, work_order_id, item_id, item_revision_id,
   production_date, data_origin, defect_count, high_defect_flag)
       │
       ▼
[Set Role]  — dataset_split → 분할 기준
             defect_rate_pct → label
       │
       ▼
[Optimize Parameters (Grid)]
  ┌─────────────────────────────────────┐
  │ [Split Data] → [GBT] → [Apply] → [Performance] │
  └─────────────────────────────────────┘
  탐색 범위:
    number_of_trees: 50 ~ 500
    maximal_depth:   3 ~ 15
    learning_rate:   0.001 ~ 0.1
       │
       ▼
[Write Model]  — strore-regression-gbt
```

**평가 지표**: RMSE, Absolute Error, R²

---

### 3-2. GBT 분류 (고위험 판별)

> **참고 프로젝트**: `hd-modeling/` — `02_classification_gbt_optimization.rmp`

```
[Read HDF5]
  ICX_train_classification_final.rmhdf5table
       │
       ▼
[Filter Examples] → [Select Attributes] → [Set Role]
  (high_defect_flag → label)
       │
       ▼
[Optimize Parameters (Grid)]
  ┌─────────────────────────────────────┐
  │ [Split Data] → [GBT] → [Apply] → [Performance] │
  └─────────────────────────────────────┘
  탐색 범위:
    number_of_trees: 50 ~ 150
    maximal_depth:   3 ~ 10
    learning_rate:   0.01 ~ 0.05
       │
       ▼
[Write Model]  — strore-classification-gbt
```

**평가 지표**: Accuracy, RMSE, R²

---

### 3-3. LightGBM Extension (Python 의존성 없는 배포)

> **참고 프로젝트**: `nice-modeling/` — `create_lightgbm_process_v0.2.rmp`

v0.1은 `python_scripting:python_learner`를 사용해 Python pickle로 모델을 저장했습니다.  
v0.2는 `lightgbm:lightgbm` Extension을 사용해 AI Hub에 Python 없이 배포할 수 있는 `.rmtabmod`를 생성합니다.

```
[Read CSV] → [Set Role (KEY → id)] → [LightGBM Extension]
                                              │
                                       [Write Model]
                                        261109_ext_lightgbm.rmtabmod
```

| 항목 | v0.1 (Python Learner) | v0.2 (LightGBM Extension) |
|------|-----------------------|---------------------------|
| 오퍼레이터 | `python_scripting:python_learner` | `lightgbm:lightgbm` |
| 출력 파일 | `.rmmodel` (Base64 pickle) | `.rmtabmod` (Extension 자체 포맷) |
| AI Hub 배포 | Python 환경 필요 | Python 의존성 없음 |

---

## 4. 배포 프로세스(Deploy Process)

AI Hub에 올릴 프로세스는 학습 프로세스와 별도로 만듭니다.  
외부에서 받은 입력을 저장된 모델에 통과시켜 결과를 돌려주는 역할입니다.

### 회귀 배포 프로세스

> **참고 프로젝트**: `hd-modeling/deploy_process/deploy.rmp`

```
외부 입력 (공정 변수 12개)
       │  {"data": [{12개 필드}]}
       ▼
[Read Input]  — AI Hub가 제공하는 입력 포트
       │
       ▼
[Apply Model]  ←── Retrieve Model (strore-regression-gbt-v0.2)
       │
       ▼
응답: {"data": [{...입력 에코..., "prediction(defect_rate_pct)": 1.65}]}
```

### 최적화 배포 프로세스

> **참고 프로젝트**: `hd-modeling/deploy_process/deploy-optimization.rmp`

```
외부 입력 (매크로 target: "0" 또는 "1")
       │
       ▼
[Read HDF5]  — 학습 데이터 로드 (ICX_train_classification_final)
       │
       ▼
[Apply Model]  ←── Retrieve Model (strore-classification-gbt-v0.3)
       │
       ▼
[Prescriptive Analytics (Evolutionary)]  — target 방향으로 최적 조건 탐색
       │
       ▼
응답: {"data": [{12개 최적 조건, "confidence(1)": 0.02, "prediction(high_defect_flag)": "0"}]}
```

---

## 5. 파일 형식

| 확장자 | 역할 | 포맷 |
|--------|------|------|
| `.rmp` | 프로세스(워크플로우) 정의 | XML |
| `.rmmodel` | Python Learner 모델 (pickle → Base64 → JSON) | JSON |
| `.rmtabmod` | LightGBM Extension 모델 (자체 바이너리 → Base64 → JSON) | JSON |
| `.rmhdf5table` | AI Studio 전용 데이터 테이블 | HDF5 기반 |

> `.rmp`, `.rmmodel`, `.rmhdf5table` 파일은 `.gitignore`에 의해 버전 관리에서 제외합니다. AI Studio Repository 또는 로컬에서 별도 보관합니다.

### `.rmp` XML 구조 (요약)

```xml
<process version="12.1.001">
  <context>...</context>
  <operator class="process">
    <operator class="read_hdf5" name="Read HDF5">
      <parameter key="file" value="./data/defect_pred_input.rmhdf5table"/>
    </operator>
    <operator class="gradient_boosted_trees" name="GBT">
      <parameter key="number_of_trees" value="200"/>
      <parameter key="maximal_depth" value="6"/>
    </operator>
    <connect from_op="Read HDF5" from_port="output"
             to_op="GBT"         to_port="training set"/>
  </operator>
</process>
```

### `.rmtabmod` JSON 구조 (요약)

```json
{
  "rm_object_type": "com.rapidminer.extension.lightgbm.model.LightGBMModel",
  "rm_object_version": "12.1.1",
  "headerTable": { "columns": [...] },
  "parameters": {
    "boosting": "gbdt",
    "num_leaves": 8,
    "learning_rate": 0.005,
    "objective": "binary"
  },
  "iterations": 3000,
  "model": "z:<Base64 인코딩된 LightGBM 바이너리>"
}
```

---

## 6. 주요 팁

- **Grid 탐색은 시간이 많이 걸립니다.** 처음엔 범위를 좁게 잡고 먼저 실행해 감을 잡으세요.
- **dataset_split 컬럼**: 데이터에 `train`/`validation`/`test` 값이 있으면 `Split Data` 오퍼레이터 없이 Set Role로 역할을 지정해 분할할 수 있습니다.
- **Write Model 경로**: `store/` 하위 폴더에 버전명을 붙여 저장하면 이전 버전과 병행 보관이 편합니다 (예: `strore-regression-gbt-v0.2`).
- **Prescriptive Analytics(Evolutionary)**는 학습 데이터를 함께 로드해야 합니다. 배포 프로세스에서 데이터 경로가 절대 경로면 AI Hub 환경에서 깨질 수 있으니 Repository 경로를 사용하세요.
