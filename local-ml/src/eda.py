# src/eda.py
import pandas as pd
from config import TARGET_COL, LEAKAGE_COLS

def run_eda(csv_path: str):
    df = pd.read_csv(csv_path)

    print("=" * 60)
    print("1. 기본 정보")
    print("=" * 60)
    print(f"전체 행 수: {len(df)}")
    print(f"컬럼: {list(df.columns)}")
    print(f"\n결측치:\n{df.isnull().sum()[df.isnull().sum() > 0]}")

    print("\n" + "=" * 60)
    print("2. dataset_split 분포")
    print("=" * 60)
    print(df["dataset_split"].value_counts())

    print("\n" + "=" * 60)
    print("3. data_origin 분포 (전부 SYNTHETIC이어야 정상)")
    print("=" * 60)
    print(df["data_origin"].value_counts())

    print("\n" + "=" * 60)
    print("4. 타겟 분포")
    print("=" * 60)
    print(df[TARGET_COL].describe())

    print("\n" + "=" * 60)
    print("5. high_defect_flag 클래스 불균형")
    print("=" * 60)
    print(df["high_defect_flag"].value_counts(normalize=True))

    print("\n" + "=" * 60)
    print("6. high_defect_flag가 defect_rate_pct의 임계값 파생인지 확인")
    print("=" * 60)
    flag1_min = df.loc[df["high_defect_flag"] == 1, TARGET_COL].min()
    flag0_max = df.loc[df["high_defect_flag"] == 0, TARGET_COL].max()
    print(f"flag=1 그룹의 최소 defect_rate_pct: {flag1_min:.4f}")
    print(f"flag=0 그룹의 최대 defect_rate_pct: {flag0_max:.4f}")
    if flag1_min >= flag0_max:
        threshold = (flag1_min + flag0_max) / 2
        print(f"→ 두 그룹이 완전히 분리됨. 추정 임계값 ≈ {threshold:.3f}%")
        print("→ high_defect_flag는 defect_rate_pct의 단순 임계값 파생 변수임이 확인됨")
        print("→ 따라서 반드시 피처에서 제외해야 함 (리키지)")
    else:
        print("→ 두 그룹이 겹침. 단순 임계값 파생이 아닐 수 있음 (추가 확인 필요)")

    print("\n" + "=" * 60)
    print("7. 범주형 변수 고유값")
    print("=" * 60)
    for col in ["production_line", "shift", "supplier_code"]:
        print(f"{col}: {df[col].unique()}")

    return df

if __name__ == "__main__":
    run_eda("../data/ML_data.csv")
