"""
This module splits raw student observation data into train / validation / test sets,
then runs each split through preprocess() to produce pyBKT-ready DataFrames.

Typical usage:
    from src.split import split

    train_data, test_data, val_data = split(df, kc_col="modeling_kc_id")
"""
from sklearn.model_selection import train_test_split

from src.pipeline.preprocess import preprocess


def split(data, kc_col='primary_kc_id'):
    """Split data into train, validation, and test sets, then preprocess each.

    Parameters
    ----------
    data : pd.DataFrame
        Raw student observations. Must contain whatever columns
        ``preprocess()`` requires (e.g. 'student_id', 'score',
        'observation_id', and ``kc_col``).
    kc_col : str, default 'primary_kc_id'
        Name of the column identifying knowledge components, passed
        through to ``preprocess()``.

    Returns
    -------
    tuple of pd.DataFrame
        ``(train_data, test_data, val_data)`` 

    Examples
    --------
    >>> train_data, test_data, val_data = split(df, kc_col="modeling_kc_id")
    """
    train_data, test_data = train_test_split(data, test_size=0.3, random_state=42)
    val_data, test_data = train_test_split(test_data, test_size=0.3, random_state=42)

    train_data = preprocess(train_data, kc_col)
    test_data = preprocess(test_data, kc_col)
    val_data = preprocess(val_data, kc_col)

    return train_data, test_data, val_data