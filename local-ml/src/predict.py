# src/predict.py
import joblib
import pandas as pd
from config import NUMERIC_FEATURES, CATEGORICAL_FEATURES

RISK_THRESHOLDS = {"low": 1.0, "medium": 2.0}  # %, 데모 가정값 (eda.py 결과로 조정 권장)


def load_model(model_path: str):
    bundle = joblib.load(model_path)
    return bundle["pipeline"], bundle["model_name"], bundle["version"]


def to_risk_grade(pred_rate: float) -> str:
    if pred_rate < RISK_THRESHOLDS["low"]:
        return "LOW"
    elif pred_rate < RISK_THRESHOLDS["medium"]:
        return "MEDIUM"
    return "HIGH"


def predict_defect_rate(pipeline, version: str, request: dict) -> dict:
    """
    request 예시 (PPT 13페이지 시연 시나리오 4, 5번 대응):
    {
        "production_line": "LINE-BPR-01",
        "shift": "DAY",
        "supplier_code": "SIM-SUP-A",
        "planned_quantity": 500,
        "ambient_humidity_pct": 55.0,
        "incoming_material_quality_score": 90.0,
        "coating_target_thickness_um": 90.0,
        "weld_energy_setting_pct": 100.0,
        "fixture_alignment_offset_mm": 0.3,
        "process_setting_deviation_pct": 3.0,
        "tool_wear_pct": 20.0,
        "days_since_maintenance": 15,
    }
    """
    X = pd.DataFrame([request])[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    pred_rate = float(pipeline.predict(X)[0])

    model_step = pipeline.named_steps["model"]
    feature_names = pipeline.named_steps["preprocess"].get_feature_names_out()
    importances = pd.Series(model_step.feature_importances_, index=feature_names)
    top_factors = importances.sort_values(ascending=False).head(3).index.tolist()

    return {
        "predicted_defect_rate_pct": round(pred_rate, 3),
        "risk_grade": to_risk_grade(pred_rate),
        "model_version": version,
        "top_influencing_factors": top_factors,
    }


def what_if_compare(pipeline, version: str, base_request: dict, changed_request: dict) -> dict:
    """PPT 13페이지 시연 5번: 코팅 두께 변경 전후 비교"""
    base = predict_defect_rate(pipeline, version, base_request)
    changed = predict_defect_rate(pipeline, version, changed_request)
    return {
        "before": base,
        "after": changed,
        "improvement_pct_point": round(
            base["predicted_defect_rate_pct"] - changed["predicted_defect_rate_pct"], 3
        ),
    }


if __name__ == "__main__":
    pipeline, model_name, version = load_model("../models/defect_rate_model_v1.0.0.pkl")

    base_req = {
        "production_line": "LINE-BPR-01", "shift": "DAY", "supplier_code": "SIM-SUP-A",
        "planned_quantity": 500, "ambient_humidity_pct": 55.0,
        "incoming_material_quality_score": 90.0, "coating_target_thickness_um": 90.0,
        "weld_energy_setting_pct": 100.0, "fixture_alignment_offset_mm": 0.3,
        "process_setting_deviation_pct": 3.0, "tool_wear_pct": 20.0,
        "days_since_maintenance": 15,
    }
    changed_req = {**base_req, "coating_target_thickness_um": 110.0}

    print(what_if_compare(pipeline, version, base_req, changed_req))
