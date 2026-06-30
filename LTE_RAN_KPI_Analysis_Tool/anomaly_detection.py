# ============================================================
# LTE KPI Degradation Analyzer - Anomaly Detection
# ============================================================
# Detects KPI anomalies on the LAST DAY of the recent period:
#   1. Zero anomaly: KPI value is 0 on last day, but was consistently
#      non-zero in the last 24 days.
#   2. Spike anomaly: KPI value on last day is abnormally different
#      from the 24-day historical baseline.
#
# HISTORICAL BASELINE LOGIC:
#   - Uses ALL DAYS from the previous 24 days (not same-weekday matching)
#   - Robust z-score: (value - median) / (1.4826 * MAD) of the last 24 days
#     (MAD = median absolute deviation; resistant to the spikes being detected;
#      falls back to std when the history is majority-constant and MAD == 0)
#   - Requires at least 2 samples for z-score; falls back to % change
#     with 1 sample
#
# Output: Excel file with 4 sheets (All, Zero, Spike, Summary) or CSV.
# ============================================================

import numpy as np
import pandas as pd

from KPI_Configuration import (
    DATE_COL,
    CELL_ID_COLS,
    SITE_COL,
    CELL_COL,
    KPI_CONFIGS,
    classify_unit,
)
from clean_excel_and_helpers import (
    clean_excel_columns,
    clean_numeric_series,
    find_matching_column,
)


def date_first(df):
    """Return a view/copy with Date as the first column when present."""
    if df is None or DATE_COL not in df.columns:
        return df
    return df[[DATE_COL] + [col for col in df.columns if col != DATE_COL]]


# ------------------------------------------------------------
# Historical baseline computation (last N days, all weekdays)
# ------------------------------------------------------------
def _get_last_n_days_historical_values(
    df_full,
    target_kpi,
    cell_cols,
    date_col,
    target_date,
    lookback_days,
    cell_values,
):
    """
    Collect ALL historical values for a cell within the last N days.

    Used for z-score spike/zero anomaly detection: compares last-day value
    against the full distribution of values from the previous N days
    (regardless of weekday).

    Args:
        df_full: Full DataFrame with all history.
        target_kpi: Column name of the KPI.
        cell_cols: List of cell identifier columns.
        date_col: Name of date column.
        target_date: The date we're checking (last day).
        lookback_days: How many days back to look (e.g., 24 for ~4 weeks).
        cell_values: Tuple of cell identifier values.

    Returns:
        List of historical values from the last N days.
    """
    target_date = pd.Timestamp(target_date).normalize()

    lookback_dates = [
        target_date - pd.Timedelta(days=day)
        for day in range(1, lookback_days + 1)
    ]

    cell_filter = True
    for col, val in zip(cell_cols, cell_values):
        cell_filter = cell_filter & (df_full[col] == val)

    cell_history = df_full[cell_filter].copy()
    cell_history[date_col] = pd.to_datetime(cell_history[date_col]).dt.normalize()

    values = []
    for ld in lookback_dates:
        day_data = cell_history[cell_history[date_col] == ld]
        if not day_data.empty:
            val = pd.to_numeric(day_data[target_kpi], errors="coerce").iloc[0]
            if not pd.isna(val):
                values.append(float(val))

    return values


# ------------------------------------------------------------
# Main anomaly detection function
# ------------------------------------------------------------
def detect_kpi_anomalies_last_day(
    df,
    output_path=None,
    lookback_weeks=4,
    spike_z_threshold=3.0,
    spike_pct_threshold=50.0,
    min_history_samples=1,
    log_callback=None,
):
    """
    Detect KPI anomalies (zero values and spikes) on the LAST DAY of the data.

    Historical baseline uses ALL DAYS from the previous 4 weeks (24 days):
      - Compares last-day value against the full distribution of the last 24 days
      - Uses z-score (|value - median| / std) for spike detection
      - Requires at least 2 historical samples for z-score; falls back to
        absolute % change when only 1 sample is available

    Two types of anomalies are detected:
      1. Zero anomaly: KPI value is exactly 0 on the last day, but historical
         values in the last 24 days were consistently non-zero.
      2. Spike anomaly: KPI value on the last day differs significantly from
         the 24-day historical baseline.

    Spike detection method depends on available samples:
      - With 1 sample: use absolute % change threshold
        (|value - history| / |history|) >= spike_pct_threshold/100
      - With 2+ samples: use z-score (|value - median| / std) >=
        spike_z_threshold

    Args:
        df: Input DataFrame with all cell data (must include DATE_COL and
            CELL_ID_COLS, plus the KPI columns defined in KPI_CONFIGS).
        output_path: Path to save one file containing all anomaly types.
            If None, the DataFrame is returned but not saved.
         lookback_weeks: Kept for backward compatibility; always uses 4 weeks.
        spike_z_threshold: Absolute z-score threshold for spike detection
            (used when 2+ historical samples are available).
            Default 3.0 (≈99.7% confidence if normally distributed).
        spike_pct_threshold: Absolute percentage change threshold for spike
             detection (used when only 1 historical sample is available).
             Default 50.0 (50% change).
        min_history_samples: Minimum number of valid historical samples
            required before an anomaly can be flagged. Default 1.
        log_callback: Optional function for progress logging.

    Returns:
        DataFrame with one row per anomaly, containing:
        - CELL_ID_COLS (eNodeB Name, Cell Name, LocalCell Id)
        - Date (last day)
        - KPI_Name (config name, e.g. "DL Traffic")
        - KPI_Column (actual column name in DataFrame)
        - Value (last day value)
        - Historical_Median (median of last 24 days values)
        - Historical_Mean (mean of last 24 days values, for reference)
        - Historical_Std (std of last 24 days values; NaN if only 1 sample)
        - Historical_Days (count of valid historical samples)
        - Anomaly_Type ('Zero' or 'Spike')
        - Z_Score (for spike with 2+ samples; NaN otherwise)
        - Pct_Change (for spike with 1 sample; NaN otherwise)
        - Direction ('high' or 'low')
        - Severity (Critical / High / Medium / Low)
        - Baseline_Mode ('4week_rolling_avg')
        - Description (human-readable summary)
    """
    def log_msg(msg):
        if log_callback:
            log_callback(msg)

    log_msg("=" * 60)
    log_msg("Detecting KPI anomalies on LAST DAY of recent period...")
    log_msg("=" * 60)

    # ---- Validate lookback_weeks ----
    if lookback_weeks < 1:
        raise ValueError("lookback_weeks must be >= 1")
    baseline_mode_label = "4week_rolling_avg"

    log_msg(f"Baseline mode: {baseline_mode_label}")
    log_msg(f"  → Spike baseline: ALL DAYS in the previous 4 weeks (24-day lookback, not same-weekday)")
    log_msg(f"  → Spike detection: robust z-score = (value − median) / (1.4826·MAD), "
            f"threshold {spike_z_threshold}; requires ≥2 of the last 24 days")

    # ---- Prepare data ----
    df = clean_excel_columns(df.copy())
    df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce").dt.normalize()
    df = df.dropna(subset=[DATE_COL])

    if df.empty:
        log_msg("ERROR: No valid date rows in input DataFrame")
        return pd.DataFrame()

    # ---- Determine last day ----
    last_date = df[DATE_COL].max()
    last_weekday_name = last_date.strftime("%A")

    log_msg(f"Last day (analysis target): {last_date.date()} ({last_weekday_name})")

    # ---- Identify all KPI columns from config ----
    kpi_columns = []
    for kpi_name, config in KPI_CONFIGS.items():
        target_col = config["target_kpi"]
        actual_col = find_matching_column(df, target_col)
        if actual_col and actual_col not in [k[1] for k in kpi_columns]:
            kpi_columns.append((
                kpi_name,
                actual_col,
                config.get("bad_direction"),
                config.get("min_baseline_value", 0.0),
            ))

    log_msg(f"Found {len(kpi_columns)} KPI columns to check")

    # ---- Clean numeric values for all KPI columns upfront ----
    for _, kpi_col, _, _ in kpi_columns:
        if kpi_col in df.columns:
            df[kpi_col] = clean_numeric_series(df[kpi_col])

    # ---- Split data: last day vs full history (for 24-day lookup) ----
    last_day_df = df[df[DATE_COL] == last_date].copy()

    log_msg(f"Last day records: {len(last_day_df)}")

    if last_day_df.empty:
        log_msg("WARNING: No data found for the last day")
        return pd.DataFrame()

    # ---- Detect anomalies ----
    anomalies = []
    cells_checked = 0
    kpis_checked = 0

    for kpi_name, kpi_col, bad_direction, min_baseline_value in kpi_columns:
        log_msg(f"\nChecking KPI: {kpi_name} ({kpi_col})")

        # Iterate over each cell on the last day
        last_day_cells = last_day_df[CELL_ID_COLS].drop_duplicates()
        for _, cell_row in last_day_cells.iterrows():
            cells_checked += 1

            # Get the last-day value for this cell + KPI
            cell_last_day_filter = True
            for col in CELL_ID_COLS:
                cell_last_day_filter = cell_last_day_filter & (
                    last_day_df[col] == cell_row[col]
                )
            cell_last_day = last_day_df[cell_last_day_filter]

            if cell_last_day.empty:
                continue

            last_value_raw = cell_last_day[kpi_col].iloc[0]
            if pd.isna(last_value_raw):
                continue

            last_value = float(last_value_raw)

            # ---- Get last 24 days historical values (all weekdays) ----
            cell_values = tuple(cell_row[col] for col in CELL_ID_COLS)
            history_values = _get_last_n_days_historical_values(
                df_full=df,
                target_kpi=kpi_col,
                cell_cols=CELL_ID_COLS,
                date_col=DATE_COL,
                target_date=last_date,
                lookback_days=24,
                cell_values=cell_values,
            )

            if len(history_values) < min_history_samples:
                continue  # not enough history to judge

            kpis_checked += 1

            # Compute historical statistics
            hist_median = float(np.median(history_values))
            hist_mean = float(np.mean(history_values))
            hist_std = float(np.std(history_values)) if len(history_values) >= 2 else np.nan
            hist_days = len(history_values)

            # Robust dispersion for spike detection (BUG-07). 1.4826*MAD is a
            # consistent estimator of sigma under normality, but unlike plain
            # std it is NOT inflated by the very spikes we are trying to detect
            # — so a single large outlier no longer hides itself by blowing up
            # the denominator. std is retained for reporting/fallback only.
            if hist_days >= 2:
                hist_mad = float(np.median(np.abs(np.asarray(history_values, dtype="float64") - hist_median)))
                robust_scale = 1.4826 * hist_mad
            else:
                hist_mad = np.nan
                robust_scale = np.nan

            # ---- ZERO ANOMALY DETECTION ----
            # KPI is 0 on last day, but historical values were non-zero.
            if last_value == 0:
                non_zero_history = [v for v in history_values if v != 0]
                if (len(non_zero_history) >= min_history_samples
                        and hist_median > 0):
                    # Severity based on how far historical median was above zero
                    floor = max(min_baseline_value, 1e-6)
                    if hist_median >= 10 * floor:
                        severity = "Critical"
                    elif hist_median >= 5 * floor:
                        severity = "High"
                    else:
                        severity = "Medium"

                    anomalies.append({
                        **{col: cell_row[col] for col in CELL_ID_COLS},
                        "Date": last_date,
                        "KPI_Name": kpi_name,
                        "KPI_Column": kpi_col,
                        "Value": last_value,
                        "Historical_Median": hist_median,
                        "Historical_Mean": hist_mean,
                        "Historical_Std": hist_std,
                        "Historical_Days": hist_days,
                        "Anomaly_Type": "Zero",
                        "Z_Score": np.nan,
                        "Pct_Change": -100.0,  # 100% drop to zero
                        "Direction": "zero",
                        "Severity": severity,
                        "Baseline_Mode": baseline_mode_label,
                        "Description": (
                            f"KPI dropped to 0 on last day "
                            f"(24-day historical median: {hist_median:.2f}, "
                            f"{len(non_zero_history)}/{hist_days} days were non-zero "
                            f"in 24-day lookback)"
                        ),
                    })
                    # Don't also flag as spike — zero is its own anomaly
                    continue

            # ---- SPIKE ANOMALY DETECTION ----
            # Method depends on number of historical samples available
            is_spike = False
            z_score = np.nan
            pct_change = np.nan
            spike_method = ""

            if hist_days == 1:
                # Only 1 sample — use absolute % change threshold
                # Cannot compute z-score with single sample
                historical_value = history_values[0]
                if abs(historical_value) > 1e-10:
                    pct_change = ((last_value - historical_value) /
                                  abs(historical_value)) * 100
                    if abs(pct_change) >= spike_pct_threshold:
                        is_spike = True
                        spike_method = f"%change (1-week, threshold {spike_pct_threshold}%)"

            else:
                # 2+ samples — ROBUST z-score against the median (BUG-07).
                # Scale = 1.4826*MAD. If the history is majority-constant the
                # MAD is 0, so fall back to std to avoid divide-by-zero while
                # still flagging a divergent last-day value.
                scale = robust_scale
                if pd.isna(scale) or scale <= 1e-10:
                    scale = hist_std
                    scale_kind = "std-fallback"
                else:
                    scale_kind = "MAD"
                if not pd.isna(scale) and scale > 1e-10:
                    z_score = (last_value - hist_median) / scale
                    if abs(z_score) >= spike_z_threshold:
                        is_spike = True
                        spike_method = f"robust z-score ({scale_kind}, threshold {spike_z_threshold})"

            if is_spike:
                # Determine direction
                if hist_days == 1:
                    direction = "high" if pct_change > 0 else "low"
                    magnitude = abs(pct_change)
                else:
                    direction = "high" if z_score > 0 else "low"
                    magnitude = abs(z_score)

                # Determine impact (degradation vs enhancement)
                if bad_direction == "low":
                    impact = "degradation" if direction == "low" else "enhancement"
                elif bad_direction == "high":
                    impact = "degradation" if direction == "high" else "enhancement"
                else:
                    impact = "unknown"

                # Severity
                if hist_days == 1:
                    # Severity by % change magnitude
                    if magnitude >= 100:
                        severity = "Critical"
                    elif magnitude >= 75:
                        severity = "High"
                    elif magnitude >= 50:
                        severity = "Medium"
                    else:
                        severity = "Low"
                else:
                    # Severity by z-score magnitude
                    if magnitude >= 5:
                        severity = "Critical"
                    elif magnitude >= 4:
                        severity = "High"
                    elif magnitude >= 3:
                        severity = "Medium"
                    else:
                        severity = "Low"

                 # Build description
                if hist_days == 1:
                     desc = (
                         f"KPI spike on last day: value={last_value:.2f} vs "
                          f"historical value={history_values[0]:.2f} "
                         f"(change={pct_change:+.1f}%, impact={impact}, method={spike_method})"
                     )
                else:
                     desc = (
                         f"KPI spike on last day: value={last_value:.2f} vs "
                         f"24-day median={hist_median:.2f} "
                         f"(z-score={z_score:+.2f}, impact={impact}, method={spike_method})"
                     )

                anomalies.append({
                    **{col: cell_row[col] for col in CELL_ID_COLS},
                    "Date": last_date,
                    "KPI_Name": kpi_name,
                    "KPI_Column": kpi_col,
                    "Value": last_value,
                    "Historical_Median": hist_median,
                    "Historical_Mean": hist_mean,
                    "Historical_Std": hist_std,
                    "Historical_Days": hist_days,
                    "Anomaly_Type": "Spike",
                    "Z_Score": z_score,
                    "Pct_Change": pct_change,
                    "Direction": direction,
                    "Severity": severity,
                    "Baseline_Mode": baseline_mode_label,
                    "Description": desc,
                })

    # ---- Build output DataFrame ----
    output_columns = CELL_ID_COLS + [
        "Date", "KPI_Name", "KPI_Column", "Value",
        "Historical_Median", "Historical_Mean", "Historical_Std", "Historical_Days",
        "Anomaly_Type", "Z_Score", "Pct_Change", "Direction", "Severity",
        "Baseline_Mode", "Description",
    ]

    if anomalies:
        anomalies_df = pd.DataFrame(anomalies)
        # Ensure all columns exist
        for col in output_columns:
            if col not in anomalies_df.columns:
                anomalies_df[col] = np.nan
        anomalies_df = anomalies_df[output_columns]
        # Sort by severity (Critical first)
        severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        anomalies_df["_severity_order"] = anomalies_df["Severity"].map(severity_order)
        anomalies_df = anomalies_df.sort_values(
            ["_severity_order", "KPI_Name", SITE_COL, CELL_COL]
        ).drop(columns=["_severity_order"]).reset_index(drop=True)
    else:
        anomalies_df = pd.DataFrame(columns=output_columns)

    # ---- Log summary ----
    log_msg("\n" + "=" * 60)
    log_msg("ANOMALY DETECTION SUMMARY")
    log_msg("=" * 60)
    log_msg(f"Last day analyzed: {last_date.date()} ({last_weekday_name})")
    log_msg(f"Baseline mode: {baseline_mode_label} (4 weeks)")
    log_msg(f"Cells checked: {len(last_day_cells)}")
    log_msg(f"KPI × cell checks performed: {kpis_checked}")
    log_msg(f"Total anomalies found: {len(anomalies_df)}")

    if not anomalies_df.empty:
        zero_count = int((anomalies_df["Anomaly_Type"] == "Zero").sum())
        spike_count = int((anomalies_df["Anomaly_Type"] == "Spike").sum())
        log_msg(f"  - Zero anomalies:  {zero_count}")
        log_msg(f"  - Spike anomalies: {spike_count}")

        log_msg("\nSeverity breakdown:")
        for sev in ["Critical", "High", "Medium", "Low"]:
            count = int((anomalies_df["Severity"] == sev).sum())
            if count > 0:
                log_msg(f"  - {sev}: {count}")

        log_msg("\nTop 5 anomalies:")
        for _, row in anomalies_df.head(5).iterrows():
            log_msg(f"  [{row['Severity']}] {row['Anomaly_Type']:5s} | "
                    f"{row[SITE_COL]}/{row[CELL_COL]} | "
                    f"{row['KPI_Name']} | {row['Description']}")

    # ---- Save to file ----
    if output_path:
        _save_anomalies_to_file(anomalies_df, output_path, last_date,
                                lookback_weeks, baseline_mode_label, log_msg)

    return anomalies_df


# ------------------------------------------------------------
# File saving helper
# ------------------------------------------------------------
def _save_anomalies_to_file(anomalies_df, output_path, last_date,
                            lookback_weeks, baseline_mode_label, log_msg):
    """Save anomalies DataFrame to one Excel sheet or CSV."""

    if output_path.endswith(".xlsx"):
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:

            # Sheet 1: All anomalies
            date_first(anomalies_df).to_excel(writer, sheet_name="All_Anomalies", index=False)

            # Sheet 2: Zero anomalies only
            zero_df = anomalies_df[anomalies_df["Anomaly_Type"] == "Zero"]
            date_first(zero_df).to_excel(writer, sheet_name="Zero_Anomalies", index=False)

            # Sheet 3: Spike anomalies only
            spike_df = anomalies_df[anomalies_df["Anomaly_Type"] == "Spike"]
            date_first(spike_df).to_excel(writer, sheet_name="Spike_Anomalies", index=False)

            # Sheet 4: Summary
            summary_data = {
                "Last_Day_Analyzed": [last_date],
                "Last_Day_Weekday": [last_date.strftime("%A")],
                "Baseline_Mode": [baseline_mode_label],
                "Lookback_Weeks": [4],
                "Total_Anomalies": [len(anomalies_df)],
                "Zero_Anomalies": [len(zero_df)],
                "Spike_Anomalies": [len(spike_df)],
                "Critical_Severity": [
                    int((anomalies_df["Severity"] == "Critical").sum())
                    if not anomalies_df.empty else 0
                ],
                "High_Severity": [
                    int((anomalies_df["Severity"] == "High").sum())
                    if not anomalies_df.empty else 0
                ],
                "Medium_Severity": [
                    int((anomalies_df["Severity"] == "Medium").sum())
                    if not anomalies_df.empty else 0
                ],
                "Low_Severity": [
                    int((anomalies_df["Severity"] == "Low").sum())
                    if not anomalies_df.empty else 0
                ],
            }

            # Per-KPI breakdown
            if not anomalies_df.empty:
                kpi_breakdown = anomalies_df.groupby(
                    ["KPI_Name", "Anomaly_Type"]
                ).size().reset_index(name="Count")
                kpi_breakdown = kpi_breakdown.sort_values(
                    ["Anomaly_Type", "Count"], ascending=[True, False]
                )
            else:
                kpi_breakdown = pd.DataFrame(
                    columns=["KPI_Name", "Anomaly_Type", "Count"]
                )

            summary_df = pd.DataFrame(summary_data)
            date_first(summary_df).to_excel(writer, sheet_name="Summary", index=False)

            # Write KPI breakdown starting 3 rows below summary
            date_first(kpi_breakdown).to_excel(
                writer, sheet_name="Summary", index=False,
                startrow=4, startcol=0,
            )

        log_msg(f"\n✅ Anomalies Excel saved to: {output_path}")
        log_msg(f"   Sheets: All_Anomalies, Zero_Anomalies, Spike_Anomalies, Summary")

    elif output_path.endswith(".csv"):
        date_first(anomalies_df).to_csv(output_path, index=False, encoding="utf-8-sig")
        log_msg(f"\n✅ Anomalies CSV saved to: {output_path}")

    else:
        # Default to CSV
        date_first(anomalies_df).to_csv(output_path, index=False, encoding="utf-8-sig")
        log_msg(f"\n✅ Anomalies saved to: {output_path}")
