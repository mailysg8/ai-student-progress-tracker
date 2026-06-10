import pandas as pd
from pathlib import Path

from src.bkt import bkt


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_PATH = Path().resolve().parent
FILE_PATH = BASE_PATH / "data" / "raw"
OUTPUT_PATH = BASE_PATH / "data" / "output"
PROCESSED_PATH = BASE_PATH / "data" / "processed"

STELLAR_FILE = FILE_PATH / "Stellar_edu_MDS_ap_stats_dataset - v1.9.xlsx"
KC_MAP_FILE = FILE_PATH / "mkc_mapping_pack_v1.0..xlsx"
WEIGHTS_FILE = FILE_PATH / "mkc_weights_dataset.xlsx"


# ---------------------------------------------------------------------------
# Load raw data
# ---------------------------------------------------------------------------

obs = pd.read_excel(STELLAR_FILE, sheet_name="Student_Observations")
class_plan = pd.read_excel(STELLAR_FILE, sheet_name="Class_Plan")

kc_map = pd.read_excel(KC_MAP_FILE, sheet_name="FineKC_to_ModelingKC_Map")
weights = pd.read_excel(WEIGHTS_FILE, sheet_name="MKC_Weights")


# ---------------------------------------------------------------------------
# Build slim KC mapping
# ---------------------------------------------------------------------------

KC_MAP_COLS = [
    "fine_kc_id",
    "fine_kc_label",
    "modeling_kc_id",
    "modeling_kc_label",
    "modeling_unit",
    "fine_reporting_group",
]

kc_map_slim = kc_map[KC_MAP_COLS].drop_duplicates()


# ---------------------------------------------------------------------------
# Merge observations with KC mapping and weights
# ---------------------------------------------------------------------------

df = obs.merge(
    kc_map_slim,
    left_on="primary_kc_id",
    right_on="fine_kc_id",
    how="left",
)

df = df.merge(
    weights,
    on=["modeling_kc_id", "modeling_kc_label"],
    how="left",
)

df = pd.merge(
    df,
    class_plan[["class_date", "homework_id"]],
    left_on="assignment_id",
    right_on="homework_id",
).drop(columns="homework_id")


# ---------------------------------------------------------------------------
# BKT predictions
# ---------------------------------------------------------------------------

bkt_preds = bkt(df, "modeling_kc_id")

bkt_renamed = bkt_preds.rename(
    columns={
        "user_id": "student_id",
        "skill_name": "modeling_kc_id",
    }
)

# Count cumulative attempts per student / KC pair
bkt_renamed["kc_attempt"] = (
    bkt_renamed
    .groupby(["student_id", "modeling_kc_id"])
    .cumcount() + 1
)


# ---------------------------------------------------------------------------
# Final merge and export
# ---------------------------------------------------------------------------

df["order_id"] = df.groupby("student_id").cumcount()

df_final = df.merge(
    bkt_renamed,
    on=["order_id", "student_id", "modeling_kc_id", "correct"],
    how="left",
)

df_final.to_csv(PROCESSED_PATH / "final_student_kc_data.csv", index=False)