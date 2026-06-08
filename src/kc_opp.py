import pandas as pd
def kc_opp_lowest(opp_counts : pd.DataFrame, n: int = 5):
        """Lowest n KCs by opportunity average."""
        return (
            opp_counts
            .groupby('modeling_kc_label_x')['n_opportunities']
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
        .groupby('modeling_kc_label_x')['n_opportunities']
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
        .groupby('modeling_kc_label_x')['n_opportunities']
        .mean()
        .reset_index()
        .rename(columns={'n_opportunities': 'avg_opportunities'})
        .sort_values('avg_opportunities', ascending=False)
        .reset_index(drop=True)
    )

    return avg_opp[avg_opp['modeling_kc_label_x'].isin(kc_list_rank)]