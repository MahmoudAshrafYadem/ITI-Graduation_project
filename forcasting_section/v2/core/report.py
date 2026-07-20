"""LLM-ready report generation — pure functions."""
from datetime import datetime
from typing import List, Dict, Optional, Any
import numpy as np
import pandas as pd

from core.types import Alert, AlertTier, ReportContext


# --- KPI directionality for trend phrasing ---
HIGHER_IS_BETTER = {
    "RRC_Setup_SR", "Intra_HO_SR", "Inter_HO_SR", "DL_CQI",
    "DL_Throughput", "User_DL_Throughput", "DL_Traffic",
    "Avg_UE_Number", "Active_Users",
}
LOWER_IS_BETTER = {"ERAB_Drop_Rate", "DL_IBLER"}
NEUTRAL = {"DL_PRB_Util"}

DEFAULT_KPI_ORDER = [
    "DL_Traffic", "DL_Throughput", "Avg_UE_Number", "Active_Users",
    "RRC_Setup_SR", "ERAB_Drop_Rate", "Intra_HO_SR", "Inter_HO_SR",
    "DL_CQI", "DL_IBLER", "DL_PRB_Util", "User_DL_Throughput",
]


def _fmt(value, decimals=2):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "N/A"
    return f"{value:.{decimals}f}"


def _trend_label(series: pd.Series, kpi_name: str, window: int = 7) -> str:
    s = series.dropna()
    if len(s) < window * 2:
        return "insufficient data for trend"
    recent = s.iloc[-window:].mean()
    prior = s.iloc[-2 * window:-window].mean()
    if prior == 0 or np.isnan(prior):
        return "insufficient data for trend"
    pct_change = (recent - prior) / abs(prior) * 100
    if abs(pct_change) < 2:
        direction = "stable"
    elif pct_change > 0:
        direction = "increasing"
    else:
        direction = "decreasing"
    if abs(pct_change) >= 2:
        if kpi_name in HIGHER_IS_BETTER:
            quality = "improving" if pct_change > 0 else "degrading"
        elif kpi_name in LOWER_IS_BETTER:
            quality = "improving" if pct_change < 0 else "degrading"
        else:
            quality = "shifting (direction-neutral KPI, review manually)"
        return f"{direction} ({pct_change:+.1f}% vs prior {window}d) — {quality}"
    return f"{direction} ({pct_change:+.1f}% vs prior {window}d)"


def build_kpi_block(
    internal_name: str,
    display_name: str,
    series: pd.Series,
    forecast_info: Optional[Dict[str, Any]] = None,
    alerts: Optional[List[Alert]] = None,
) -> str:
    s = series.dropna()
    if s.empty:
        return f"### {display_name} ({internal_name})\nNo data available.\n"

    latest = s.iloc[-1]
    mean_30 = s.tail(30).mean()
    min_30 = s.tail(30).min()
    max_30 = s.tail(30).max()
    trend = _trend_label(s, internal_name)

    lines = [f"### {display_name} ({internal_name})"]
    lines.append(f"- Latest value: {_fmt(latest)}")
    lines.append(f"- 30-day range: min {_fmt(min_30)}, mean {_fmt(mean_30)}, max {_fmt(max_30)}")
    lines.append(f"- Trend: {trend}")

    if forecast_info:
        fc_vals = forecast_info.get("forecast")
        fc_dates = forecast_info.get("dates")
        mae = forecast_info.get("mae")
        mape = forecast_info.get("mape")
        if fc_vals is not None and len(fc_vals) > 0:
            fc_str = ", ".join(
                f"{d}: {_fmt(v)}" for d, v in zip(fc_dates or range(len(fc_vals)), fc_vals)
            )
            lines.append(f"- 7-day forecast: {fc_str}")
        if mae is not None:
            lines.append(f"- Backtest accuracy: MAE {_fmt(mae)}, MAPE {_fmt(mape)}%")

    if alerts:
        status_str = ", ".join(f"**{a.status.value}** ({a.tier.value})" for a in alerts)
        msg_str = "; ".join(a.message for a in alerts)
        lines.append(f"- Alerts: {status_str} — {msg_str}")

    return "
".join(lines) + "
"


def generate_cell_report(
    df: pd.DataFrame,
    cell_name: str,
    context: ReportContext,
    date_col: str = "Date",
    cell_col: str = "Cell Name",
    lookback_days: int = 30,
) -> str:
    """Build the full LLM-ready prompt for one cell."""
    cell_df = df[df[cell_col] == cell_name].copy()
    if cell_df.empty:
        raise ValueError(f"No rows found for cell '{cell_name}'")

    cell_df[date_col] = pd.to_datetime(cell_df[date_col])
    cell_df = cell_df.sort_values(date_col).tail(lookback_days)

    kpi_map = context.kpi_map
    kpi_items = list(kpi_map.items()) if kpi_map else [
        (k, k) for k in DEFAULT_KPI_ORDER if k in cell_df.columns
    ]

    date_start = cell_df[date_col].min().strftime("%Y-%m-%d")
    date_end = cell_df[date_col].max().strftime("%Y-%m-%d")
    n_days = cell_df[date_col].nunique()

    # Group alerts by KPI
    alerts_by_kpi: Dict[str, List[Alert]] = {}
    for alert in context.alerts:
        alerts_by_kpi.setdefault(alert.kpi_internal, []).append(alert)

    kpi_blocks = []
    active_alert_lines = []
    for internal_name, display_name in kpi_items:
        if internal_name not in cell_df.columns:
            continue
        series = cell_df.set_index(date_col)[internal_name]
        fc = context.forecasts.get(internal_name)
        al = alerts_by_kpi.get(internal_name, [])
        kpi_blocks.append(build_kpi_block(internal_name, display_name, series, fc, al))
        for a in al:
            if a.status.value not in ("Normal", "Info"):
                active_alert_lines.append(f"- {display_name}: {a.status.value} — {a.message}")

    alert_summary = "
".join(active_alert_lines) if active_alert_lines else "No active alerts flagged for this cell."

    seasonality_note = ""
    if context.seasonality:
        seasonality_note = f"\n**Seasonality:** {context.seasonality.category} (strength={context.seasonality.strength:.2f})\n"

    header = f"""You are an RF / telecom network optimization engineer. Analyze the LTE KPI data below for a single cell and provide a diagnostic assessment.

**Cell:** {cell_name}
**Data window:** {date_start} to {date_end} ({n_days} days)
**Report generated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}{seasonality_note}

## Active alerts
{alert_summary}

## KPI details
"""

    footer = """
## Your task
Based on the KPI data above, please:
1. Identify which KPIs show signs of degradation and whether the trends are likely correlated (e.g. rising IBLER alongside falling CQI, or PRB utilization saturation coinciding with throughput drops).
2. Flag any KPI combination that suggests a specific root cause (e.g. interference, congestion, coverage hole, handover misconfiguration, hardware fault).
3. Note if any forecasted values are projected to cross typical operational thresholds within the next 7 days.
4. Recommend concrete next investigative or optimization steps, ordered by priority.
5. Call out anything that looks like a data quality issue rather than a genuine network problem (e.g. a KPI with too little history to trust its trend).

Keep the response structured and actionable — this will be used for real network optimization decisions.
"""

    return header + "
".join(kpi_blocks) + footer
