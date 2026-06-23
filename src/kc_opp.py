"""
This module contains helper functions to summarise how many attempts students have had on each KC, averaged
across the class.

Used to surface which KCs are under-practiced (lowest opportunity average)
or over-practiced (highest opportunity average), or to look up the
opportunity average for a specific list of KCs.

Expects an opp_counts DataFrame with at minimum these columns:
    modeling_kc_label : knowledge component display label
    n_opportunities    : number of attempts a student has had on that KC

Typical usage :
    from src.kc_opp import kc_opp_lowest, kc_opp_highest, kc_opp_rank

    lowest_5  = kc_opp_lowest(opp_counts, n=5)
    highest_5 = kc_opp_highest(opp_counts, n=5)
    selected  = kc_opp_rank(["Probability Rules", "Confidence Intervals"], opp_counts)
"""
import pandas as pd
def kc_opp_lowest(opp_counts : pd.DataFrame, n: int = 5):
        """Lowest n KCs by opportunity average."""
        return (
            opp_counts
            .groupby('modeling_kc_label')['n_opportunities']
            .mean()
            .reset_index()
            .rename(columns={'n_opportunities': 'avg_opportunities'})
            .sort_values('avg_opportunities')
            .head(n)
            .reset_index(drop=True)
        )


def kc_opp_highest(opp_counts : pd.DataFrame, n: int = 5):
    """Highest n KCs by opportunity average."""
    return (
        opp_counts
        .groupby('modeling_kc_label')['n_opportunities']
        .mean()
        .reset_index()
        .rename(columns={'n_opportunities': 'avg_opportunities'})
        .sort_values('avg_opportunities', ascending=False)
        .head(n)
        .reset_index(drop=True)
    )


def kc_opp_rank(kc_list_rank, opp_counts : pd.DataFrame):
    """n highest ranking KCs and their opportunity average."""
    avg_opp = (
        opp_counts
        .groupby('modeling_kc_label')['n_opportunities']
        .mean()
        .reset_index()
        .rename(columns={'n_opportunities': 'avg_opportunities'})
        .sort_values('avg_opportunities', ascending=False)
        .reset_index(drop=True)
    )

    return avg_opp[avg_opp['modeling_kc_label'].isin(kc_list_rank)]