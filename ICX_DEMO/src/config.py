# src/config.py

# 식별자 및 메타 컬럼 (피처 제외)
ID_COLS = ["lot_no", "work_order_id", "item_id", "item_revision_id",
           "production_date", "data_origin", "dataset_split"]

# 타겟 및 리키지 위험 컬럼 (반드시 피처에서 제외!)
TARGET_COL = "defect_rate_pct"
LEAKAGE_COLS = ["defect_count", "high_defect_flag"]

# 범주형 피처
CATEGORICAL_FEATURES = ["production_line", "shift", "supplier_code"]

# 수치형 피처 (실제 공정 조건)
NUMERIC_FEATURES = [
    "planned_quantity",
    "ambient_humidity_pct",
    "incoming_material_quality_score",
    "coating_target_thickness_um",
    "weld_energy_setting_pct",
    "fixture_alignment_offset_mm",
    "process_setting_deviation_pct",
    "tool_wear_pct",
    "days_since_maintenance",
]

RANDOM_STATE = 42
MODEL_VERSION = "v1.0.0"
