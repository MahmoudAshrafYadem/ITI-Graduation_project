"""Model selection router — compares candidates and returns the best."""
from typing import List, Callable
import pandas as pd

from core.types import ForecastResult


def select_best_model(
    cell_df: pd.DataFrame,
    target_col: str,
    test_dates: pd.DatetimeIndex,
    actual_test: pd.Series,
    candidates: List[Callable],
    future_dates: pd.DatetimeIndex = None,
    **kwargs
) -> ForecastResult:
    """Run each candidate forecaster and return the one with the lowest MAE.

    Parameters
    ----------
    cell_df, target_col, test_dates, actual_test : standard
    candidates : list of callables
        Each callable must accept the standard signature and return a ForecastResult.
    future_dates : optional
        Passed through to candidates that support future forecasting.
    **kwargs : extra params (e.g. n_estimators, hw_trend) passed to candidates

    Returns
    -------
    ForecastResult
        The best candidate by hold-out MAE. If all fail, returns the first
        non-null result or raises if truly everything failed.
    """
    results = []
    for fn in candidates:
        try:
            result = fn(
                cell_df=cell_df,
                target_col=target_col,
                test_dates=test_dates,
                actual_test=actual_test,
                future_dates=future_dates,
                **kwargs
            )
            if result.forecast is not None:
                results.append(result)
        except Exception:
            continue

    if not results:
        raise RuntimeError("All candidate models failed to produce a forecast.")

    return min(results, key=lambda r: r.scores.mae)
