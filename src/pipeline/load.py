"""
load.py
-------
Data loading functions for the student KC pipeline.

Reads raw Excel sources and returns typed DataFrames.
All file paths are resolved from environment variables — never hardcoded.

Environment variables (set via .env):
    STUDENT_OBS_FILE   : Path to the workbook containing Student Observations and Class Plan.
    KC_MAP_FILE    : Path to the fine-KC → modeling-KC mapping workbook.
    WEIGHTS_FILE   : Path to the MKC weights workbook.

Example:
    from pipeline.load import load_observations, load_kc_map, load_weights, load_class_plan

    obs        = load_observations()
    class_plan = load_class_plan()
    kc_map     = load_kc_map()
    weights    = load_weights()
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()


def _resolve(env_var: str) -> Path:
    """
    Resolve a file path from an environment variable.

    Args:
        env_var: Name of the environment variable holding the path.

    Returns:
        Resolved Path object.

    Raises:
        EnvironmentError: If the variable is not set.
        FileNotFoundError: If the resolved path does not exist on disk.
    """
    raw = os.environ.get(env_var)
    if raw is None:
        raise EnvironmentError(
            f"Required environment variable '{env_var}' is not set. "
            f"Add it to your .env file. See .env.example for reference."
        )
    path = Path(raw).resolve()
    if not path.exists():
        raise FileNotFoundError(
            f"File referenced by '{env_var}' not found: {path}"
        )
    return path


def load_observations() -> pd.DataFrame:
    """
    Load the Student_Observations sheet from the Student Observations and Class Plan workbook.

    Returns:
        DataFrame with one row per student observation event.

    Expected columns (non-exhaustive):
        student_id, assignment_id, primary_kc_id, correct, order_id
    """
    path = _resolve("STUDENT_OBS_FILE")
    df = pd.read_excel(path, sheet_name="Student_Observations")
    return df


def load_class_plan() -> pd.DataFrame:
    """
    Load the Class_Plan sheet from the Student Observations and Class Plan workbook.

    Returns:
        DataFrame mapping homework_id → class_date.

    Expected columns:
        class_date, homework_id
    """
    path = _resolve("STUDENT_OBS_FILE")
    df = pd.read_excel(path, sheet_name="Class_Plan")
    return df


def load_kc_map() -> pd.DataFrame:
    """
    Load the fine-KC to modeling-KC mapping table.

    Returns:
        DataFrame with one row per fine_kc_id → modeling_kc_id mapping.

    Expected columns (non-exhaustive):
        fine_kc_id, fine_kc_label, modeling_kc_id, modeling_kc_label,
        modeling_unit, fine_reporting_group
    """
    path = _resolve("KC_MAP_FILE")
    df = pd.read_excel(path, sheet_name="FineKC_to_ModelingKC_Map")
    return df


def load_weights() -> pd.DataFrame:
    """
    Load the MKC weights table.

    Returns:
        DataFrame with weight values per modeling KC.

    Expected columns (non-exhaustive):
        modeling_kc_id, modeling_kc_label, weight
    """
    path = _resolve("WEIGHTS_FILE")
    df = pd.read_excel(path, sheet_name="MKC_Weights")
    return df