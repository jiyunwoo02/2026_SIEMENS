# src/train.py
import pandas as pd
import numpy as np
import joblib
from pathlib import Path

from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error

from config import (
    TARGET_COL, LEAKAGE_COLS, ID_COLS,
    CATEGORICAL_FEATURES, NUMERIC_FEATURES, RANDOM_STATE, MODEL_VERSION
)


def load_split(csv_path: str):
    df = pd.read_csv(csv_path)

    # 리키지 컬럼이 실수로 피처에 들어가지 않도록 명시적으로 분리
    feature_cols = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    assert not set(feature_cols) & set(LEAKAGE_COLS), "리키지 컬럼이 피처에 섞여 있습니다!"

    train_df = df[df["dataset_split"] == "train"].reset_index(drop=True)
    valid_df = df[df["dataset_split"] == "validation"].reset_index(drop=True)
    test_df  = df[df["dataset_split"] == "test"].reset_index(drop=True)

    def split_xy(d):
        X = d[feature_cols].copy()
        y = d[TARGET_COL].copy()
        return X, y

    return split_xy(train_df), split_xy(valid_df), split_xy(test_df)


def build_pipeline(model):
    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ],
        remainder="passthrough",  # 수치형은 트리 모델이므로 스케일링 불필요
    )
    return Pipeline(steps=[("preprocess", preprocessor), ("model", model)])


def evaluate(pipeline, X, y, label=""):
    pred = pipeline.predict(X)
    mae = mean_absolute_error(y, pred)
    rmse = np.sqrt(mean_squared_error(y, pred))
    print(f"[{label}] MAE={mae:.4f}, RMSE={rmse:.4f}")
    return mae, rmse, pred


def main():
    csv_path = "../data/ICX_P097548_synthetic_lot_training.csv"
    (X_train, y_train), (X_valid, y_valid), (X_test, y_test) = load_split(csv_path)

    candidates = {
        "RandomForest": RandomForestRegressor(
            n_estimators=300, max_depth=8, random_state=RANDOM_STATE, n_jobs=-1
        ),
        "GBT": GradientBoostingRegressor(
            n_estimators=300, max_depth=3, learning_rate=0.05, random_state=RANDOM_STATE
        ),
    }

    results = {}
    for name, model in candidates.items():
        pipe = build_pipeline(model)
        pipe.fit(X_train, y_train)
        mae, rmse, _ = evaluate(pipe, X_valid, y_valid, label=f"{name} / validation")
        results[name] = {"pipeline": pipe, "mae": mae, "rmse": rmse}

    # validation MAE 기준 최적 모델 선정
    best_name = min(results, key=lambda k: results[k]["mae"])
    best_pipeline = results[best_name]["pipeline"]
    print(f"\n>>> 최종 선정 모델: {best_name}")

    # 최종 성능은 test set으로 한 번만 확인 (튜닝에 재사용 금지)
    evaluate(best_pipeline, X_test, y_test, label=f"{best_name} / test (final)")

    # 변수 중요도 출력
    model_step = best_pipeline.named_steps["model"]
    feature_names = best_pipeline.named_steps["preprocess"].get_feature_names_out()
    importances = pd.Series(model_step.feature_importances_, index=feature_names)
    print("\n변수 중요도 Top 10:")
    print(importances.sort_values(ascending=False).head(10))

    # 모델 저장
    Path("../models").mkdir(exist_ok=True)
    joblib.dump(
        {"pipeline": best_pipeline, "model_name": best_name, "version": MODEL_VERSION},
        f"../models/defect_rate_model_{MODEL_VERSION}.pkl",
    )
    print(f"\n모델 저장 완료: models/defect_rate_model_{MODEL_VERSION}.pkl")


if __name__ == "__main__":
    main()
