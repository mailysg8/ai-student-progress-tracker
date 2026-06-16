"""
save.py
---------
Save functions for the student KC pipeline.

Handles validation and writing of the final merged DataFrame to disk.
All output paths are resolved from environment variables — never hardcoded.

Environment variables (set via .env):
    PROCESSED_PATH : Directory where the final CSV will be written.

Example:
    from pipeline.save import save_final_output

    save_final_output(df_final)
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()


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