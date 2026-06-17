"""
predict.py
----------
BKT (Bayesian Knowledge Tracing) prediction step for the student KC pipeline.

Uses the pyBKT library to fit a BKT model per knowledge component and generate
per-observation mastery probability predictions.

Typical usage (orchestrated by data_pipeline.py):
    from pipeline.predict import run_bkt_predictions

    bkt_preds = run_bkt_predictions(df, kc_col="modeling_kc_id")
"""

import random

import numpy as np
import pandas as pd
from pyBKT.models import Model

from preprocess import preprocess


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