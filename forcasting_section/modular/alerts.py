"""Alert generation for LTE KPIs based on configurable thresholds."""
import numpy as np
import pandas as pd

from config import KPI_THRESHOLDS


def generate_cell_alerts(cell_df, target_col=None):
    """Generate alert status for every KPI column present in cell_df.

    Parameters
    ----------
    cell_df : pd.DataFrame
        DataFrame for a single cell, indexed by Date, with internal KPI column names.
    target_col : str, optional
        The currently-selected target KPI (gets a "forecasting" note).

    Returns
    -------
    dict
        {internal_name: {"status": str, "message": str}}
    """
    alerts = {}
    for col in cell_df.columns:
        if col not in KPI_THRESHOLDS:
            continue

        series = cell_df[col].dropna()
        if series.empty:
            alerts[col] = {"status": "N/A", "message": "No data available."}
            continue

        low_thr, high_thr, direction = KPI_THRESHOLDS[col]
        latest = series.iloc[-1]
        mean_7d = series.tail(7).mean()
        mean_30d = series.tail(30).mean() if len(series) >= 30 else mean_7d

        status = "Normal"
        messages = []

        # Threshold checks
        if low_thr is not None and latest < low_thr:
            status = "Warning"
            messages.append(f"Below threshold ({latest:.2f} < {low_thr})")
        if high_thr is not None and latest > high_thr:
            status = "Warning"
            messages.append(f"Above threshold ({latest:.2f} > {high_thr})")

        # Recent degradation check (7d vs 30d trend)
        if mean_30d != 0 and not np.isnan(mean_30d):
            pct_change = (mean_7d - mean_30d) / abs(mean_30d) * 100
            if abs(pct_change) >= 5:
                if direction == "higher_is_better" and pct_change < -5:
                    if status == "Normal":
                        status = "Degrading"
                    messages.append(f"Recent decline ({pct_change:+.1f}% vs 30d avg)")
                elif direction == "lower_is_better" and pct_change > 5:
                    if status == "Normal":
                        status = "Degrading"
                    messages.append(f"Recent increase ({pct_change:+.1f}% vs 30d avg)")

        # Volatility check (coefficient of variation)
        cv = series.tail(14).std() / series.tail(14).mean() if len(series) >= 7 else 0
        if cv > 0.3:
            messages.append(f"High volatility (CV={cv:.2f})")

        # Target KPI note
        if col == target_col:
            messages.append("Currently selected for forecasting")

        alerts[col] = {
            "status": status,
            "message": "; ".join(messages) if messages else "Within normal range",
        }

    return alerts
