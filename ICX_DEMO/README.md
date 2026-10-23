# ICX_DEMO

공정 조건 12개(범주형 3개 + 수치형 9개)로 결함률(`defect_rate_pct`, %)을 예측하는 모델을 로컬에서 탐색·학습·예측해 보는 데모입니다. 데이터는 합성(`SYNTHETIC`) 데이터를 전제로 합니다.
- 상세 ML 작업은 Altair AI Studio에서 수행합니다.

## 폴더 구조

```text
ICX_DEMO/
├── requirements.txt     현재 비어 있음 (아래 "설치" 참고)
├── data/
│   └── ML_data.csv      eda.py가 읽는 데이터
├── models/              train.py 실행 시 생성 (현재 저장소에는 없음)
└── src/
    ├── config.py        컬럼 구분, 타깃, 리키지 컬럼, 시드(42), 모델 버전(v1.0.0)
    ├── eda.py           데이터 탐색 (결측치, 분포, 리키지 점검)
    ├── train.py         RandomForest / GBT 학습, validation MAE 기준 선정, 모델 저장
    └── predict.py       저장된 모델로 예측, 위험 등급 부여, what-if 비교
```

## 설치

`requirements.txt`가 비어 있으므로, 소스가 import하는 패키지를 직접 설치합니다. 버전은 고정되어 있지 않습니다.

```bash
pip install pandas numpy scikit-learn joblib
```

## 실행

스크립트가 `../data`, `../models` 상대 경로를 사용하므로 **반드시 `src/`에서 실행**합니다.

```bash
cd ICX_DEMO/src
python eda.py       # ../data/ML_data.csv 탐색
python train.py     # 학습 → ../models/defect_rate_model_v1.0.0.pkl 저장
python predict.py   # 코팅 두께 90 → 110µm 변경 전후 비교 예시
```

## 동작 요약

- **피처**: 범주형 `production_line`, `shift`, `supplier_code` + 수치형 9개 (`src/config.py`)
- **리키지 제외**: `defect_count`, `high_defect_flag`는 피처에서 제외합니다. `eda.py`가 `high_defect_flag`가 타깃의 임계값 파생인지 확인합니다.
- **학습**: `dataset_split` 값(`train`/`validation`/`test`)으로 분할합니다. 후보 2종 중 validation MAE가 낮은 모델을 선정하고, test 지표는 최종 1회만 출력합니다.
- **예측**: 결과에 `predicted_defect_rate_pct`, `risk_grade`, `model_version`, `top_influencing_factors`가 포함됩니다.
- **위험 등급**: 1.0% 미만 `LOW`, 2.0% 미만 `MEDIUM`, 그 이상 `HIGH`. 코드 주석상 **데모 가정값**이며 확정 기준이 아닙니다.
- `top_influencing_factors`는 해당 예측의 개별 기여도가 아니라 모델 전체의 변수 중요도 상위 3개입니다.

## 알려진 불일치 (실행 전 확인)

| 항목 | 내용 |
|---|---|
| 학습 데이터 파일명 | `train.py`는 `../data/ICX_P097548_synthetic_lot_training.csv`를 읽지만 `data/`에는 `ML_data.csv`만 있습니다. 파일명을 맞추거나 `train.py`의 `csv_path`를 수정해야 합니다. |
| 데이터 컬럼 | `ML_data.csv`의 컬럼이 `config.py` 및 `dataset_split` 등과 일치하는지는 확인하지 못했습니다. `eda.py` 결과로 확인하세요. |
| 학습 성능 | 학습 결과(MAE/RMSE)는 이 저장소에 기록되어 있지 않습니다. `train.py` 실행 후 출력을 확인하세요. |

> 이 문서는 소스를 읽고 작성했으며, 스크립트를 실행해 확인하지는 않았습니다.
