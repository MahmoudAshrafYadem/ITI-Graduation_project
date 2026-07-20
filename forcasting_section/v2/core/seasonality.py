"""STL-based weekly seasonality strength diagnostics — pure functions."""
import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL

from core.types import SeasonalityResult


def compute_seasonality_strength(series: pd.Series, period: int = 7) -> SeasonalityResult:
    """STL-based seasonality strength (Hyndman & Athanasopoulos definition).

    F_seasonal = max(0, 1 - Var(residual) / Var(seasonal + residual))

    Parameters
    ----------
    series : pd.Series
        Single KPI time series for one cell.
    period : int
        Seasonal period (default 7 for weekly on daily data).

    Returns
    -------
    SeasonalityResult
    """
    series = series.dropna()
    if len(series) < 2 * period:
        return SeasonalityResult(strength=None, period=period)
    try:
        stl = STL(series, period=period, robust=True).fit()
        resid = stl.resid
        seasonal = stl.seasonal
        denom = np.var(seasonal + resid)
        if denom == 0:
            return SeasonalityResult(strength=0.0, period=period)
        strength = max(0.0, 1.0 - np.var(resid) / denom)
        return SeasonalityResult(strength=float(strength), period=period)
    except Exception:
        return SeasonalityResult(strength=None, period=period)


def compute_all_cell_seasonality(df: pd.DataFrame, target_col: str, period: int = 7) -> dict:
    """Seasonality strength per cell for the given KPI column.

    Returns
    -------
    dict
        {cell_name: SeasonalityResult}
    """
    strengths = {}
    for cell, group in df.groupby("Cell Name"):
        series = group.sort_values("Date")[target_col].reset_index(drop=True)
        strengths[cell] = compute_seasonality_strength(series, period=period)
    return strengths
