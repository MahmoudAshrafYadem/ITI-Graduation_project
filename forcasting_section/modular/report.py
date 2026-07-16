"""
report.py — Generates an LLM-ready, copy/paste text report summarizing all
KPIs for a single cell: current status, recent trend, backtest accuracy,
7-day forecast, and any active alerts.

Designed to be pasted directly into an LLM (Claude, ChatGPT, etc.) for
RF / network optimization reasoning — the output is a full prompt, not
just a data dump: it opens with role + task framing, then the KPI data,
then explicit analysis instructions.

Usage (minimal, just a dataframe):
    from report import generate_cell_report
    prompt_text = generate_cell_report(df, cell_name="Cell_042")

Usage (full, wired into your XGBoost/Holt-Winters/alerting outputs):
    prompt_text = generate_cell_report(
        df, cell_name="Cell_042",
        kpi_map=config.KPI_REVERSE_MAP,          # {internal_name: display_name}
        forecasts=forecast_results,                # {internal_name: {"forecast": [...], "dates": [...]}}
        alerts=alert_results,                     # {internal_name: {"status": "...", "message": "..."}}
    )
"""

from datetime import datetime
import numpy as np
import pandas as pd


# --- KPI directionality: used to phrase trend as "improving" / "degrading" ---
HIGHER_IS_BETTER = {
    "RRC_Setup_SR", "Intra_HO_SR", "Inter_HO_SR", "DL_CQI",
    "DL_Throughput", "User_DL_Throughput", "DL_Traffic",
    "Avg_UE_Number", "Active_Users",
}
LOWER_IS_BETTER = {"ERAB_Drop_Rate", "DL_IBLER"}
NEUTRAL = {"DL_PRB_Util"}  # depends on target operating range, no universal "better"

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
    """Compares the mean of the last `window` days vs the prior `window` days."""
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


def build_kpi_block(internal_name, display_name, series, forecast_info=None, alert_info=None):
    """Builds one KPI's text block: current value, trend, forecast, alert status."""
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

    if alert_info:
        status = alert_info.get("status", "unknown")
        message = alert_info.get("message", "")
        lines.append(f"- Alert status: **{status}**" + (f" — {message}" if message else ""))

    return "\n".join(lines) + "\n"


def generate_cell_report(
    df: pd.DataFrame,
    cell_name: str,
    date_col: str = "Date",
    cell_col: str = "Cell Name",
    kpi_map: dict = None,
    forecasts: dict = None,
    alerts: dict = None,
    lookback_days: int = 30,
) -> str:
    """
    Builds the full LLM-ready prompt for one cell, covering every KPI
    present in the dataframe.

    kpi_map: optional {internal_name: display_name}. If omitted, uses
             DEFAULT_KPI_ORDER and falls back to raw column names for
             anything not in that list but present in df.
    forecasts: optional {internal_name: {"forecast": [...], "dates": [...],
               "mae": float, "mape": float}}
    alerts: optional {internal_name: {"status": str, "message": str}}
    """
    cell_df = df[df[cell_col] == cell_name].copy()
    if cell_df.empty:
        raise ValueError(f"No rows found for cell '{cell_name}'")

    cell_df[date_col] = pd.to_datetime(cell_df[date_col])
    cell_df = cell_df.sort_values(date_col).tail(lookback_days)

    if kpi_map:
        kpi_items = list(kpi_map.items())
    else:
        kpi_items = [(k, k) for k in DEFAULT_KPI_ORDER if k in cell_df.columns]
        # include anything else numeric that wasn't in the default list
        extra = [
            c for c in cell_df.columns
            if c not in (date_col, cell_col) and c not in dict(kpi_items)
            and pd.api.types.is_numeric_dtype(cell_df[c])
        ]
        kpi_items += [(c, c) for c in extra]

    date_start = cell_df[date_col].min().strftime("%Y-%m-%d")
    date_end = cell_df[date_col].max().strftime("%Y-%m-%d")
    n_days = cell_df[date_col].nunique()

    kpi_blocks = []
    active_alerts = []
    for internal_name, display_name in kpi_items:
        if internal_name not in cell_df.columns:
            continue
        series = cell_df.set_index(date_col)[internal_name]
        fc = forecasts.get(internal_name) if forecasts else None
        al = alerts.get(internal_name) if alerts else None
        kpi_blocks.append(build_kpi_block(internal_name, display_name, series, fc, al))
        if al and al.get("status", "").lower() not in ("ok", "normal", "", "none", "n/a"):
            active_alerts.append(f"- {display_name}: {al.get('status')} — {al.get('message', '')}")

    alert_summary = (
        "\n".join(active_alerts) if active_alerts else "No active alerts flagged for this cell."
    )

    header = f"""You are an RF / telecom network optimization engineer. Analyze the LTE KPI data below for a single cell and provide a diagnostic assessment.

**Cell:** {cell_name}
**Data window:** {date_start} to {date_end} ({n_days} days)
**Report generated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}

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

    return header + "\n".join(kpi_blocks) + footer


def generate_report_for_streamlit(df, cell_name, **kwargs):
    """
    Thin wrapper for app.py. Returns the report text; the caller is
    expected to render it with st.code(text, language=None) so Streamlit's
    built-in copy button appears automatically — no custom clipboard JS needed.
    """
    return generate_cell_report(df, cell_name, **kwargs)
