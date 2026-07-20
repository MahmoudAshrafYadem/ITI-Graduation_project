"""Alert generation for LTE KPIs — pure functions returning typed Alert objects."""
from typing import List, Optional
import numpy as np
import pandas as pd

from config import KPI_THRESHOLDS, KPI_REVERSE_MAP
from core.types import Alert, AlertTier, AlertStatus


def evaluate_threshold(series: pd.Series, kpi: str) -> Optional[Alert]:
    """Check if the latest value breaches hard thresholds."""
    if kpi not in KPI_THRESHOLDS:
        return None
    low_thr, high_thr, direction = KPI_THRESHOLDS[kpi]
    latest = series.iloc[-1] if len(series) > 0 else np.nan
    if np.isnan(latest):
        return None

    messages = []
    status = AlertStatus.NORMAL

    if low_thr is not None and latest < low_thr:
        status = AlertStatus.WARNING
        messages.append(f"Below threshold ({latest:.2f} < {low_thr})")
    if high_thr is not None and latest > high_thr:
        status = AlertStatus.WARNING
        messages.append(f"Above threshold ({latest:.2f} > {high_thr})")

    if status == AlertStatus.NORMAL:
        return None

    return Alert(
        kpi_internal=kpi,
        kpi_display=KPI_REVERSE_MAP.get(kpi, kpi),
        tier=AlertTier.THRESHOLD,
        status=status,
        message="; ".join(messages),
        value=latest,
        threshold=low_thr if low_thr is not None else high_thr,
    )


def evaluate_trend(series: pd.Series, kpi: str, window: int = 7) -> Optional[Alert]:
    """Compare recent mean vs prior mean and flag degradation."""
    s = series.dropna()
    if len(s) < window * 2 or kpi not in KPI_THRESHOLDS:
        return None

    _, _, direction = KPI_THRESHOLDS[kpi]
    if direction == "neutral":
        return None

    recent = s.iloc[-window:].mean()
    prior = s.iloc[-2 * window:-window].mean()
    if prior == 0 or np.isnan(prior):
        return None

    pct_change = (recent - prior) / abs(prior) * 100
    if abs(pct_change) < 5:
        return None

    is_degrading = (
        (direction == "higher_is_better" and pct_change < -5) or
        (direction == "lower_is_better" and pct_change > 5)
    )
    if not is_degrading:
        return None

    return Alert(
        kpi_internal=kpi,
        kpi_display=KPI_REVERSE_MAP.get(kpi, kpi),
        tier=AlertTier.TREND,
        status=AlertStatus.WARNING,
        message=f"Recent decline ({pct_change:+.1f}% vs prior {window}d avg)",
        value=recent,
    )


def evaluate_volatility(series: pd.Series, kpi: str) -> Optional[Alert]:
    """Flag high coefficient of variation over the last 14 days."""
    s = series.tail(14).dropna()
    if len(s) < 7:
        return None
    mean_val = s.mean()
    if mean_val == 0 or np.isnan(mean_val):
        return None
    cv = s.std() / mean_val
    if cv <= 0.3:
        return None

    return Alert(
        kpi_internal=kpi,
        kpi_display=KPI_REVERSE_MAP.get(kpi, kpi),
        tier=AlertTier.VOLATILITY,
        status=AlertStatus.INFO,
        message=f"High volatility (CV={cv:.2f})",
        value=cv,
    )


def evaluate_alerts(cell_df: pd.DataFrame, target_col: Optional[str] = None) -> List[Alert]:
    """Run all alert evaluators on every KPI column in the cell dataframe.

    Returns a list of Alert dataclasses (empty list if nothing fires).
    """
    alerts = []
    for col in cell_df.columns:
        series = cell_df[col].dropna()
        if series.empty:
            continue

        for evaluator in (evaluate_threshold, evaluate_trend, evaluate_volatility):
            alert = evaluator(series, col)
            if alert is not None:
                alerts.append(alert)

    return alerts
