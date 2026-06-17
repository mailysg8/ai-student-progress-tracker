
"""
preprocess.py
-------------
Preprocessing step that transforms raw student observation data into the
format expected by pyBKT's Model.fit() and Model.predict() methods.

pyBKT expects a DataFrame with at minimum these columns:
    user_id    : unique student identifier
    skill_name : knowledge component label
    correct    : binary response (1 = correct, 0 = incorrect)
    order_id   : cumulative attempt index per student (0-based)

Typical usage (called internally by predict.py):
    from pipeline.preprocess import preprocess

    processed = preprocess(df, kc_col="modeling_kc_id")
"""

import pandas as pd


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_KC_COL = "modeling_kc_id"

# Scores treated as incorrect. 0.5 (partial credit) is collapsed to 0
# because BKT requires a strictly binary correct/incorrect signal.
PARTIAL_CREDIT_SCORES = [0.5]

# Columns required in the input DataFrame
REQUIRED_INPUT_COLS = ["student_id", "score", "observation_id"]

# Columns returned in the output DataFrame (pyBKT contract)
OUTPUT_COLS = ["user_id", "skill_name", "correct", "order_id"]


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def preprocess(data: pd.DataFrame, kc_col: str = DEFAULT_KC_COL) -> pd.DataFrame:
    """
    Transform raw student observations into pyBKT-compatible format.

    Does three things:
        1. Binarises the 'score' column — partial credit (0.5) is treated
           as incorrect (0) because BKT requires a strictly binary signal.
        2. Renames columns to match pyBKT's expected schema
           (user_id, skill_name, correct, order_id).
        3. Recomputes order_id as a per-student cumulative attempt counter
           (0-based) so attempt ordering is consistent regardless of the
           original observation_id values.

    Args:
        data:   Raw student observations DataFrame. Must contain:
                    student_id    : unique student identifier
                    score         : numeric score (expected values: 0, 0.5, 1)
                    observation_id: original observation identifier
                and the column named by kc_col.
        kc_col: Name of the column identifying knowledge components.
                Will be renamed to 'skill_name' for pyBKT.
                Defaults to 'modeling_kc_id'.

    Returns:
        DataFrame with exactly these columns, ready for pyBKT:
            user_id    : student identifier
            skill_name : knowledge component label
            correct    : binary int (0 or 1)
            order_id   : 0-based cumulative attempt index per student

    Raises:
        ValueError: If required columns (student_id, score, observation_id,
                    or kc_col) are missing from data.
        ValueError: If data is empty.
        ValueError: If 'correct' column contains values other than 0 or 1
                    after binarisation.

    Example:
        >>> processed = preprocess(df, kc_col="modeling_kc_id")
        >>> processed.columns.tolist()
        ['user_id', 'skill_name', 'correct', 'order_id']
    """
    # --- Input validation ---
    if data.empty:
        raise ValueError("data is empty — nothing to preprocess.")

    required = REQUIRED_INPUT_COLS + [kc_col]
    missing = [c for c in required if c not in data.columns]
    if missing:
        raise ValueError(
            f"preprocess() missing required column(s): {missing}. "
            f"Found: {data.columns.tolist()}"
        )

    # --- Work on a copy to avoid mutating the caller's DataFrame ---
    obs = data.copy()

    # --- Binarise score ---
    # case_when replaces partial credit scores with 0; all other values
    # (already 0 or 1) are left unchanged.
    conditions = [(obs["score"] == s, 0) for s in PARTIAL_CREDIT_SCORES]
    obs["correct"] = obs["score"].case_when(conditions).astype(int)

    # Guard: after binarisation, correct must only contain 0 or 1
    unexpected = set(obs["correct"].unique()) - {0, 1}
    if unexpected:
        raise ValueError(
            f"'correct' contains unexpected values after binarisation: {unexpected}. "
            f"Check the 'score' column for values outside {{0, 0.5, 1}}."
        )

    # --- Rename and select pyBKT columns ---
    obs = obs.rename(
        columns={
            "student_id": "user_id",
            kc_col: "skill_name",
            "observation_id": "order_id",
        }
    )[OUTPUT_COLS].reset_index(drop=True)

    # --- Recompute order_id as cumulative attempt per student ---
    obs["order_id"] = obs.groupby("user_id").cumcount()

    return obs