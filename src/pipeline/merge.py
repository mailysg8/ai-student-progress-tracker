"""
merge.py
--------
Merge functions for the student KC pipeline.

Each function performs one logical join step, validates its inputs and
outputs, and raises a descriptive error if something looks wrong.

Typical call order (orchestrated by data_pipeline.py):
    1. merge_kc_mapping(obs, kc_map)      → obs enriched with modeling KC cols
    2. merge_weights(df, weights)          → adds weight column
    3. merge_class_plan(df, class_plan)    → adds class_date
    4. merge_bkt_predictions(df, bkt_preds) → adds BKT mastery predictions

Example:
    from pipeline.merge import merge_kc_mapping, merge_weights, merge_class_plan, merge_bkt_predictions

    df = merge_kc_mapping(obs, kc_map)
    df = merge_weights(df, weights)
    df = merge_class_plan(df, class_plan)
    df = merge_bkt_predictions(df, bkt_preds)
"""

import pandas as pd

# ---------------------------------------------------------------------------
# Required Column Lists
# ---------------------------------------------------------------------------

STU_OBS_COLS = [
    "student_id",
    "assignment_id",
    "class_num",
    "observation_id",
    "source_question",
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

# Columns pyBKT returns that we want to carry into the final DataFrame.

BKT_PRED_COLS = [
    "user_id",
    "skill_name",
    "correct",
    "order_id",
    "correct_predictions",
    "state_predictions",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def warn_if_nulls(df: pd.DataFrame, columns: list[str], context: str) -> None:
    """
    Print a warning for any columns that contain null values after a merge.

    A high null rate after a left join usually indicates a key mismatch
    between the two DataFrames (e.g. trailing whitespace, type difference).

    Args:
        df:      DataFrame to check.
        columns: Columns to inspect for nulls.
        context: Label describing which merge step produced this DataFrame.
    """
    for col in columns:
        if col in df.columns:
            n_null = df[col].isna().sum()
            if n_null > 0:
                pct = 100 * n_null / len(df)
                print(
                    f"  WARNING [{context}] '{col}' has {n_null} nulls "
                    f"({pct:.1f}%) after merge — check join keys."
                )


# ---------------------------------------------------------------------------
# Merge steps
# ---------------------------------------------------------------------------

def merge_kc_mapping(obs: pd.DataFrame, kc_map: pd.DataFrame) -> pd.DataFrame:
    """
    Enrich observations with modeling-KC columns via a left join on KC id.

    Joins obs.primary_kc_id → kc_map.fine_kc_id.
    Duplicates in kc_map are dropped before the join to avoid row explosion.

    Args:
        obs:    Student observations DataFrame. Must contain 'primary_kc_id'.
        kc_map: Fine-KC to modeling-KC mapping DataFrame.
                Must contain all columns listed in KC_MAP_COLS.

    Returns:
        obs enriched with KC mapping columns. Row count equals len(obs).

    Raises:
        ValueError: If required columns are missing from either input.
    """

    kc_map_slim = kc_map[KC_MAP_COLS].drop_duplicates()

    obs_slim = obs[STU_OBS_COLS]

    df = obs_slim.merge(
        kc_map_slim,
        left_on="primary_kc_id",
        right_on="fine_kc_id",
        how="left",
    )

    warn_if_nulls(df, ["modeling_kc_id", "modeling_kc_label"], context="merge_kc_mapping")

    assert len(df) == len(obs), (
        f"merge_kc_mapping changed row count: {len(obs)} → {len(df)}. "
        "kc_map likely has duplicate fine_kc_id values after drop_duplicates."
    )

    return df


def merge_weights(df: pd.DataFrame, weights: pd.DataFrame) -> pd.DataFrame:
    """
    Attach MKC weight values to the observations DataFrame.

    Joins on ['modeling_kc_id', 'modeling_kc_label'].

    Args:
        df:      DataFrame produced by merge_kc_mapping.
                 Must contain 'modeling_kc_id' and 'modeling_kc_label'.
        weights: MKC weights DataFrame.
                 Must contain 'modeling_kc_id' and 'modeling_kc_label'.

    Returns:
        df with weight column(s) from the weights table appended.
        Row count is unchanged.

    Raises:
        ValueError: If required columns are missing from either input.
    """

    n_before = len(df)

    weights_slim = weights[WEIGHTS_COLS]

    df = df.merge(
        weights_slim,
        on=["modeling_kc_id", "modeling_kc_label"],
        how="left",
    )

    warn_if_nulls(df, [c for c in weights_slim.columns if c not in ("modeling_kc_id", "modeling_kc_label")],
                   context="merge_weights")

    assert len(df) == n_before, (
        f"merge_weights changed row count: {n_before} → {len(df)}. "
        "weights table likely has duplicate keys."
    )

    return df


def merge_class_plan(df: pd.DataFrame, class_plan: pd.DataFrame) -> pd.DataFrame:
    """
    Add class_date to observations by joining on assignment_id → homework_id.

    Args:
        df:         DataFrame produced by merge_weights.
                    Must contain 'assignment_id'.
        class_plan: Class plan DataFrame.
                    Must contain 'class_date' and 'homework_id'.

    Returns:
        df with 'class_date' column added and 'homework_id' dropped.

    Raises:
        ValueError: If required columns are missing from either input.
    """

    n_before = len(df)

    df = pd.merge(
        df,
        class_plan[CLASS_PLAN_COLS],
        left_on="assignment_id",
        right_on="homework_id",
    ).drop(columns="homework_id")

    n_dropped = n_before - len(df)
    if n_dropped > 0:
        print(
            f"  WARNING [merge_class_plan] {n_dropped} rows ({100 * n_dropped / n_before:.1f}%) "
            f"dropped — these assignment_ids had no match in class_plan."
        )

    return df


def merge_bkt_predictions(df: pd.DataFrame, bkt_preds: pd.DataFrame) -> pd.DataFrame:
    """
    Attach BKT mastery predictions to the observations DataFrame.

    Renames pyBKT output columns back to pipeline conventions, computes a
    per-student / per-KC cumulative attempt counter (kc_attempt), aligns
    on a per-student observation order index (order_id), then left-joins
    predictions onto the main DataFrame.

    Join key: ['order_id', 'student_id', 'modeling_kc_id']
        - order_id      : 0-based cumulative attempt index per student,
                          recomputed here to guarantee alignment with the
                          index produced in preprocess.py.
        - student_id    : unique student identifier.
        - modeling_kc_id: knowledge component identifier.

    Args:
        df:        DataFrame produced by merge_class_plan. Must contain
                   'student_id' and 'modeling_kc_id'.
        bkt_preds: Raw pyBKT predictions DataFrame as returned by
                   run_bkt_predictions(). Must contain 'user_id',
                   'skill_name', and 'correct'.

    Returns:
        df with BKT prediction columns appended (e.g. correct_predictions,
        state_predictions) and kc_attempt added. Row count equals len(df).

    Raises:
        ValueError: If required columns are missing from either input.
    """
    # --- Input validation ---
    missing_df = [c for c in ["student_id", "modeling_kc_id"] if c not in df.columns]
    if missing_df:
        raise ValueError(
            f"[merge_bkt_predictions] df missing column(s): {missing_df}. "
            f"Found: {df.columns.tolist()}"
        )

    missing_bkt = [c for c in ["user_id", "skill_name", "correct"] if c not in bkt_preds.columns]
    if missing_bkt:
        raise ValueError(
            f"[merge_bkt_predictions] bkt_preds missing column(s): {missing_bkt}. "
            f"Found: {bkt_preds.columns.tolist()}"
        )

    n_before = len(df)

    # --- Rename pyBKT columns back to pipeline conventions ---
    bkt_renamed = bkt_preds.rename(
        columns={
            "user_id": "student_id",
            "skill_name": "modeling_kc_id",
        }
    )

    # --- Cumulative attempt count per student / KC pair (1-based) ---
    bkt_renamed["kc_attempt"] = (
        bkt_renamed
        .groupby(["student_id", "modeling_kc_id"])
        .cumcount() + 1
    )

    # --- Recompute order_id on df to align with preprocess.py's index ---
    df["order_id"] = df.groupby("student_id").cumcount()

    # --- Left join: retain all observation rows ---
    df_final = df.merge(
        bkt_renamed,
        on=["order_id", "student_id", "modeling_kc_id"],
        how="left",
    )

    # Prediction nulls after a left join mean the BKT output had no row
    # for that student / KC / order_id combination 
    warn_if_nulls(
        df_final,
        ["correct_predictions", "state_predictions"],
        context="merge_bkt_predictions",
    )

    assert len(df_final) == n_before, (
        f"merge_bkt_predictions changed row count: {n_before} → {len(df_final)}. "
        "bkt_preds likely has duplicate (student_id, modeling_kc_id, order_id) keys."
    )

    return df_final