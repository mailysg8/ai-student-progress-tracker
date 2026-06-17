import pandas as pd
import random
import numpy as np
from pyBKT.models import Model
from src.preprocess import preprocess
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

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

    kc_map_slim = kc_map.drop_duplicates()

    obs_slim = obs

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

    weights_slim = weights

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
        class_plan,
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_KC_COL = "modeling_kc_id"
DEFAULT_SEED = 42
DEFAULT_NUM_FITS = 10


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def run_bkt_predictions(
    data: pd.DataFrame,
    kc_col: str = DEFAULT_KC_COL,
    seed: int = DEFAULT_SEED,
    num_fits: int = DEFAULT_NUM_FITS,
) -> pd.DataFrame:
    """
    Fit a BKT model and return per-observation mastery predictions.

    Args:
        data:     Preprocessed student observations DataFrame. Must contain
                  at least the column 'correct', 'score', 'primary_kc_id', 
                  'student_id', 'skill_name', 'observation_id'.
        kc_col:   Name of the column identifying knowledge components.
                  Defaults to 'modeling_kc_id'.
        seed:     Random seed passed to both numpy, Python's random module,
                  and the pyBKT Model for reproducibility. Defaults to 42.
        num_fits: Number of random restarts when fitting the BKT model.
                  Higher values reduce the risk of converging to a local
                  optimum but increase runtime linearly. Defaults to 10.

    Returns:
        DataFrame of BKT predictions with one row per observation.
        Columns include those from the input plus pyBKT-added columns such
        as 'correct_predictions' and 'state_predictions' (mastery probability).

    Raises:
        ValueError: If kc_col is not present in data.
        RuntimeError: If pyBKT model fitting fails (e.g. degenerate data
                      for a KC with only one response value).

    Example:
        >>> preds = run_bkt_predictions(df, kc_col="modeling_kc_id", seed=0)
        >>> preds[["student_id", "modeling_kc_id", "state_predictions"]].head()
    """
    if kc_col not in data.columns:
        raise ValueError(
            f"kc_col '{kc_col}' not found in data. "
            f"Available columns: {data.columns.tolist()}"
        )

    if data.empty:
        raise ValueError("data is empty — nothing to fit.")

    # Seed both libraries so results are fully reproducible
    random.seed(seed)
    np.random.seed(seed)

    processed_data = preprocess(data, kc_col)

    model = Model(seed=seed, num_fits=num_fits)
    model.fit(data=processed_data)
    predictions = model.predict(data=processed_data)

    return predictions


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUTPUT_FILENAME = "final_student_kc_data.csv"

# Columns that must be present in the final DataFrame before saving.
FINAL_OUTPUT_COLS = [
    # --- From observations ---
    "student_id",
    "assignment_id",
    "observation_id",
    "source_question",
    "primary_kc_id",
    "score",
    "correct",
    # --- From KC mapping ---
    "modeling_kc_id",
    "modeling_kc_label",
    "modeling_unit",
    # --- From weights ---
    "weight",
    # --- From class plan ---
    "class_date",
    # --- From BKT predictions ---
    "order_id",
    "kc_attempt",
    "correct_predictions",
    "state_predictions",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def resolve_output_dir() -> Path:
    """
    Resolve the output directory from the PROCESSED_PATH environment variable.

    Returns:
        Resolved Path object pointing to the output directory.

    Raises:
        EnvironmentError: If PROCESSED_PATH is not set.
    """
    raw = os.environ.get("PROCESSED_PATH")
    if raw is None:
        raise EnvironmentError(
            "Required environment variable 'PROCESSED_PATH' is not set. "
            "Add it to your .env file. See .env.example for reference."
        )
    return Path(raw).resolve()


def validate_final_df(df: pd.DataFrame) -> None:
    """
    Validate the final DataFrame before writing to disk.

    Checks for:
        - Required columns being present.
        - Non-empty DataFrame.
        - No null values in critical identifier columns.

    Args:
        df: Final merged DataFrame to validate.

    Raises:
        ValueError: If any validation check fails.
    """
    if df.empty:
        raise ValueError("df_final is empty — nothing to save.")

    missing = [c for c in FINAL_OUTPUT_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            f"[save] Final DataFrame missing expected column(s): {missing}. "
            f"Found: {df.columns.tolist()}"
        )

    # Critical identifiers must never be null — a null here means a
    # join earlier in the pipeline silently dropped or corrupted rows.
    critical = ["student_id", "modeling_kc_id", "order_id"]
    for col in critical:
        n_null = df[col].isna().sum()
        if n_null > 0:
            raise ValueError(
                f"[save] Critical column '{col}' has {n_null} null values. "
                f"Check the merge steps for key mismatches."
            )


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def save_final_output(df: pd.DataFrame, filename: str = OUTPUT_FILENAME) -> Path:
    """
    Validate and write the final student KC DataFrame to a CSV file.

    Resolves the output directory from the PROCESSED_PATH environment
    variable, validates the DataFrame schema and critical columns, creates
    the output directory if it does not exist, then writes to CSV.

    Args:
        df:       Final merged DataFrame produced by merge_bkt_predictions().
                  Must contain all columns listed in FINAL_OUTPUT_COLS.
        filename: Output CSV filename. Defaults to 'final_student_kc_data.csv'.

    Returns:
        Path object pointing to the written file, so callers (e.g. main.py
        or tests) can confirm the file exists without re-resolving the path.

    Raises:
        EnvironmentError: If PROCESSED_PATH is not set.
        ValueError:       If the DataFrame fails schema or null validation.

    Example:
        >>> output_path = save_final_output(df_final)
        >>> print(f"Saved to {output_path}")
    """
    output_dir = resolve_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    validate_final_df(df)

    output_path = output_dir / filename
    df.to_csv(output_path, index=False)

    print(f"File saved to {output_path} ({len(df):,} rows, {len(df.columns)} columns).")

    return output_path