"""
This module contains helper functions to classify student performance into categorical levels,
used across the Teacher Portal dashboard's value boxes, charts, and modals.

Two independent classification schemes live here:

1. Mastery level (via classify()) — based on a BKT mastery probability
   or score in [0, 1]:
       "Mastered"        : score >= mastery_threshold   (default 0.8)
       "Progressing"     : practice_threshold < score < mastery_threshold
       "Needs Practice"  : score <= practice_threshold   (default 0.2)

2. Practice level (via opp_status() / compute_opportunity_counts()) —
   based on a count of practice attempts (opportunities):
       "well practiced" : n_opportunities >= HIGH_OPP (15)
       "some practice"  : LOW_OPP (5) <= n_opportunities < HIGH_OPP (15)
       "low practice"   : 0 < n_opportunities < LOW_OPP (5)
       "not started"    : n_opportunities == 0

Typical usage:
    from src.classify import classify, opp_status, compute_opportunity_counts

    status     = classify(0.85)                          # "Mastered"
    opp_counts = compute_opportunity_counts(df_final)     # per student × KC
"""
import pandas as pd

# ── status thresholds ────────────────────────────────────────────────────────
LOW_OPP  = 5   # fewer than this = low practice
HIGH_OPP = 15   # more than this = well practiced


def classify(score, mastery_threshold=0.8, practice_threshold=0.2):
    """Classify a mastery score into "Mastered", "Progressing", or "Needs Practice".

    Parameters
    ----------
    score : float
        Mastery probability or score, typically in ``[0, 1]``.
    mastery_threshold : float, default 0.8
        Minimum ``score`` to classify as "Mastered".
    practice_threshold : float, default 0.2
        Maximum ``score`` to classify as "Needs Practice". Values strictly
        between ``practice_threshold`` and ``mastery_threshold`` are
        "Progressing".

    Returns
    -------
    str
        One of ``"Mastered"``, ``"Progressing"``, or ``"Needs Practice"``.
    """
    if score >= mastery_threshold:
        return "Mastered"
    elif score <= practice_threshold:
        return "Needs Practice" 
    else:
        return "Progressing"
    

def opp_status(n: int) -> str:
    """Classify a practice opportunity count into a practice level.

    Parameters
    ----------
    n : int
        Number of practice opportunities (attempts) a student has had on
        a given knowledge component.

    Returns
    -------
    str
        One of ``"not started"``, ``"low practice"``, ``"some practice"``,
        or ``"well practiced"``, based on ``LOW_OPP`` and ``HIGH_OPP``.
    """
    if n == 0:          return "not started"
    elif n >= HIGH_OPP: return "well practiced"
    elif n >= LOW_OPP:  return "some practice"
    else:               return "low practice"



def compute_opportunity_counts(data: pd.DataFrame) -> pd.DataFrame:
    """
    For each student × KC pair, compute the total number of practice
    opportunities. Missing combinations are filled with 0 / 'not started'.

    Parameters
    ----------
    data : DataFrame containing 'student_id', 'modeling_kc_id',
           'modeling_kc_label', and 'order_id' columns.

    Returns
    -------
    DataFrame with columns:
        student_id, modeling_kc_label, n_opportunities, status
    """
    # Opportunity number per student per KC
    data = data.copy()
    data['opportunity'] = (
        data
        .groupby(['student_id', 'modeling_kc_id'])
        .cumcount() + 1
    )

    # Max opportunity = total practice count
    opp_counts = (
        data
        .groupby(['student_id', 'modeling_kc_label'])['opportunity']
        .max()
        .reset_index()
        .rename(columns={'opportunity': 'n_opportunities'})
    )

    # Fill in every student × KC combination (including not started)
    all_students = opp_counts['student_id'].unique()
    all_kcs      = opp_counts['modeling_kc_label'].unique()

    full_index = pd.MultiIndex.from_product(
        [all_students, all_kcs],
        names=['student_id', 'modeling_kc_label']
    )

    opp_counts = (
        opp_counts
        .set_index(['student_id', 'modeling_kc_label'])
        .reindex(full_index)
        .reset_index()
    )

    opp_counts['n_opportunities'] = opp_counts['n_opportunities'].fillna(0).astype(int)
    opp_counts['status']          = opp_counts['n_opportunities'].apply(opp_status)

    return opp_counts