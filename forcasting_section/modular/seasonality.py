"""STL-based weekly seasonality strength diagnostics."""
import numpy as np
import streamlit as st
from statsmodels.tsa.seasonal import STL


def compute_seasonality_strength(series, period=7):
    """
    STL-based seasonality strength (Hyndman & Athanasopoulos definition):
        F_seasonal = max(0, 1 - Var(residual) / Var(seasonal + residual))
    Returns None if there isn't enough data to fit STL reliably.
    """
    series = series.dropna()
    if len(series) < 2 * period:
        return None
    try:
        stl = STL(series, period=period, robust=True).fit()
        resid = stl.resid
        seasonal = stl.seasonal
        denom = np.var(seasonal + resid)
        if denom == 0:
            return 0.0
        strength = max(0.0, 1 - np.var(resid) / denom)
        return float(strength)
    except Exception:
        return None


@st.cache_data
def compute_all_cell_seasonality(df, target_col, period=7):
    """Seasonality strength per cell for the given KPI column, used to sort
    the cell dropdown."""
    strengths = {}
    for cell, group in df.groupby("Cell Name"):
        series = group.sort_values("Date")[target_col].reset_index(drop=True)
        strengths[cell] = compute_seasonality_strength(series, period=period)
    return strengths
