
import pandas as pd
from load import load_observations, load_kc_map, load_weights, load_class_plan


def check_required_columns(df: pd.DataFrame, required: list[str], label: str) -> None:
    """
    Raise a ValueError if any required columns are missing from a DataFrame.

    Args:
        df:       DataFrame to check.
        required: List of column names that must be present.
        label:    Human-readable name for the DataFrame (used in error messages).

    Raises:
        ValueError: If one or more required columns are absent.
    """
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"[{label}] missing required column(s): {missing}. "
            f"Found: {df.columns.tolist()}"
        )
    
# ---------------------------------------------------------------------------
# Load Data
# ---------------------------------------------------------------------------
obs        = load_observations()
class_plan = load_class_plan()
kc_map     = load_kc_map()
weights    = load_weights()

# ---------------------------------------------------------------------------
# Required Column Lists
# ---------------------------------------------------------------------------

STU_OBS_COLS = [
    "student_id",
    "assignment_id",
    "class_num",
    "observation_id",
    "primary_kc_id",
    "score",
    "max_score"
    ]

CLASS_PLAN_COLS = [
    "class_date",
    "homework_id"
    ]

KC_MAP_COLS = [
    "fine_kc_id",
    "fine_kc_label",
    "modeling_kc_id",
    "modeling_kc_label",
    "modeling_unit",
    ]

WEIGHTS_COLS = [
    'rank',
    'modeling_kc_id',
    'modeling_kc_label',
    'unit',
    'topic_group',
    'weight',
    'tier',
    'estimated_exam_share_pct'
    ]

# ---------------------------------------------------------------------------
# Run Checks
# ---------------------------------------------------------------------------

print('Checking the column requirements...')
check_required_columns(obs, STU_OBS_COLS, label="obs")
check_required_columns(class_plan, CLASS_PLAN_COLS, label="class_plan")
check_required_columns(kc_map, KC_MAP_COLS, label="kc_map")
check_required_columns(weights, WEIGHTS_COLS, label="weights")
print('All requirements passed!')