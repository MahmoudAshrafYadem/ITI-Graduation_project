# ============================================================
# LTE KPI Degradation Analyzer - Data Quality
# ============================================================
# Three responsibilities:
#   1. validate_columns(): flag values that violate their unit criteria
#      (negative counters, % outside 0-100, positive dBm, vendor sentinels),
#      record them for the operator, and null them so they cannot poison the
#      averages.
#   2. compute_baseline_imputed(): for the BASELINE window only, fill a cell's
#      missing days with the median of the same weekday over the previous N
#      weeks. Recent window is never imputed (that could hide a real outage).
#   3. compute_baseline_fallback_from_history(): for cells with NaN
#      baseline average, use SAME-WEEKDAY per-weekday medians (NOT pooled
#      across all weekdays) from the previous N weeks. This preserves the
#      weekly seasonality pattern (weekends stay low, weekdays stay high)
#      and is robust to outliers within each weekday group.
# All return tidy frames so the pipeline stays auditable.
# ============================================================

import numpy as np
import pandas as pd

from KPI_Configuration import (
    SENTINEL_VALUES,
    IMPUTATION_CONFIG,
    classify_unit,
)


# ------------------------------------------------------------
# 1. Unit validation / quarantine
# ------------------------------------------------------------
def _invalid_mask_and_reason(values: pd.Series, unit: str):
    """Return (boolean invalid-mask, reason Series) for a numeric series."""
    v = pd.to_numeric(values, errors="coerce")
    reason = pd.Series(np.nan, index=v.index, dtype="object")

    sentinel = v.isin(list(SENTINEL_VALUES))
    reason[sentinel] = "vendor null/sentinel marker"

    if unit == "nonneg":
        bad = v < 0
        reason[bad & reason.isna()] = "negative value for non-negative metric"
    elif unit == "pct":
        low = v < 0
        high = v > 100
        reason[low & reason.isna()] = "percentage below 0"
        reason[high & reason.isna()] = "percentage above 100"
        bad = low | high
    elif unit == "dbm":
        bad = v > 0
        reason[bad & reason.isna()] = "positive dBm (received power should be <= 0)"
    else:  # 'db' -> cannot bound safely (SINR can be +/-), sentinels only
        bad = pd.Series(False, index=v.index)

    invalid = (sentinel | bad) & v.notna()
    return invalid, reason


def validate_columns(df, columns, kpi_name, cell_cols, date_col, log=None):
    """Null out invalid values and collect quarantine records.

    Returns (df_with_bad_values_nulled, quarantine_df).
    quarantine_df columns: cell_cols + [Date, kpi, counter, bad_value, reason].
    """
    df = df.copy()
    records = []
    for col in columns:
        if col not in df.columns:
            continue
        unit = classify_unit(col)
        invalid, reason = _invalid_mask_and_reason(df[col], unit)
        n_bad = int(invalid.sum())
        if n_bad:
            bad_rows = df.loc[invalid, cell_cols + [date_col]].copy()
            bad_rows["kpi"] = kpi_name
            bad_rows["counter"] = col
            bad_rows["bad_value"] = pd.to_numeric(df.loc[invalid, col], errors="coerce").values
            bad_rows["reason"] = reason[invalid].values
            records.append(bad_rows)
            df.loc[invalid, col] = np.nan  # null so it can't skew the mean
            if log:
                log(f"DQ: {n_bad} invalid value(s) quarantined in '{col}' ({unit})")
    if records:
        quarantine_df = pd.concat(records, ignore_index=True)
        quarantine_df = quarantine_df[cell_cols + [date_col, "kpi", "counter", "bad_value", "reason"]]
    else:
        quarantine_df = pd.DataFrame(
            columns=cell_cols + [date_col, "kpi", "counter", "bad_value", "reason"]
        )
    return df, quarantine_df


# ------------------------------------------------------------
# 2. Baseline gap imputation (same-weekday median over N weeks)
# ------------------------------------------------------------
def compute_baseline_imputed(
    daily_df,
    value_col,
    cell_cols,
    date_col,
    baseline_dates,
    lookback_weeks=None,
    min_samples=None,
):
    """Per-cell baseline aggregates with missing days filled by the median of
    the same weekday from the previous `lookback_weeks` weeks.

    `daily_df` must contain history BEFORE the baseline window (the lookback
    source). Returns a DataFrame indexed-reset on cell_cols with columns:
        baseline_avg, baseline_max, baseline_total,
        baseline_days_count, imputed_days_count
    """
    cfg = IMPUTATION_CONFIG
    lookback_weeks = cfg["lookback_weeks"] if lookback_weeks is None else lookback_weeks
    min_samples = cfg["min_impute_samples"] if min_samples is None else min_samples
    enable = cfg.get("enable_imputation", True)

    baseline_dates = sorted(pd.to_datetime(pd.Series(baseline_dates)).dt.normalize().unique())

    # cell x date matrix of values (mean collapses any duplicate cell/date)
    piv = daily_df.pivot_table(index=cell_cols, columns=date_col, values=value_col, aggfunc="mean")

    filled = pd.DataFrame(index=piv.index)   # baseline values after imputation
    imputed_flags = pd.DataFrame(index=piv.index)  # True where a day was imputed

    for d in baseline_dates:
        present = piv[d].copy() if d in piv.columns else pd.Series(np.nan, index=piv.index)
        imp_flag = pd.Series(False, index=piv.index)

        if enable:
            lookback_cols = [d - pd.Timedelta(days=7 * k) for k in range(1, lookback_weeks + 1)]
            lookback_cols = [c for c in lookback_cols if c in piv.columns]
            if lookback_cols:
                hist = piv[lookback_cols]
                med = hist.median(axis=1, skipna=True)
                cnt = hist.notna().sum(axis=1)
                need = present.isna() & (cnt >= min_samples)
                present = present.where(~need, med)
                imp_flag = need & present.notna()

        filled[d] = present
        imputed_flags[d] = imp_flag

    out = pd.DataFrame(index=piv.index)
    out["baseline_avg"] = filled.mean(axis=1, skipna=True)
    out["baseline_max"] = filled.max(axis=1, skipna=True)
    out["baseline_total"] = filled.sum(axis=1, skipna=True, min_count=1)
    out["baseline_days_count"] = filled.notna().sum(axis=1)
    out["imputed_days_count"] = imputed_flags.sum(axis=1)
    return out.reset_index()


# ------------------------------------------------------------
# 3. Baseline fallback from historical data (for NaN baselines)
# ------------------------------------------------------------
# Uses SAME-WEEKDAY matching (consistent with main degradation analysis
# and the anomaly_detection module):
#   - For each baseline day, look at the same weekday from previous N weeks
#   - Compute per-weekday MEDIAN values (robust to outliers)
#   - Average the per-weekday medians to get the final fallback value
# This avoids the previous bug of pooling all weekdays together, which
# pulled the median toward low-traffic weekend days.
# ------------------------------------------------------------
def compute_baseline_fallback_from_history(
    df,
    target_kpi,
    cell_cols,
    date_col,
    baseline_start,
    baseline_end,
    lookback_weeks=5,
    min_samples=1,
):
    """
    Compute fallback baseline values for cells with NaN baseline average.

    Uses SAME-WEEKDAY per-weekday medians (not pooled across all weekdays):
      1. For each baseline day, find same-weekday values from previous N weeks
      2. Take the median of each weekday's historical values
      3. Average the per-weekday medians across all baseline days
    This preserves the weekly seasonality pattern (e.g., weekends stay low,
    weekdays stay high) instead of pulling everything toward the pooled median.

    Edge cases handled:
      - If no historical data for any weekday → returns NaN (caller uses min_baseline_value)
      - If only some weekdays have history → uses medians from available weekdays
      - Uses median per weekday (robust to outliers within each weekday group)

    Args:
        df: Full DataFrame with all historical data.
        target_kpi: Column name of the KPI.
        cell_cols: List of columns identifying a cell.
        date_col: Name of date column.
        baseline_start: Start date of baseline period.
        baseline_end: End date of baseline period.
        lookback_weeks: How many weeks back to look per weekday (default 5).
        min_samples: Minimum samples needed per weekday for a valid median
                     (default 1).

    Returns:
        DataFrame with columns:
            cell_cols + ['baseline_fallback', 'fallback_weeks_back', 'fallback_samples']
        - baseline_fallback: average of per-weekday medians (NaN if no history)
        - fallback_weeks_back: how many weeks were looked back
        - fallback_samples: total number of valid samples used across all weekdays
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.normalize()

    baseline_dates = pd.date_range(baseline_start, baseline_end, freq='D')

    # Group baseline days by weekday (0=Monday, 6=Sunday)
    weekday_to_dates = {}
    for d in baseline_dates:
        wd = d.weekday()
        if wd not in weekday_to_dates:
            weekday_to_dates[wd] = []
        weekday_to_dates[wd].append(d)

    # For each weekday, collect same-weekday lookback dates
    weekday_lookback_dates = {}  # weekday -> list of dates
    for wd, dates in weekday_to_dates.items():
        lookback_set = set()
        for d in dates:
            for week in range(1, lookback_weeks + 1):
                lookback_set.add(d - pd.Timedelta(days=7 * week))
        weekday_lookback_dates[wd] = sorted(lookback_set)

    # Build the full set of lookback dates (all weekdays combined)
    all_lookback_dates = set()
    for dates in weekday_lookback_dates.values():
        all_lookback_dates.update(dates)
    all_lookback_dates = sorted(all_lookback_dates)

    if not all_lookback_dates:
        result = pd.DataFrame(
            columns=list(cell_cols) + ['baseline_fallback', 'fallback_weeks_back', 'fallback_samples']
        )
        return result

    # Filter to rows whose date is in the lookback set
    df_hist = df[df[date_col].isin(all_lookback_dates)].copy()

    if df_hist.empty:
        result = pd.DataFrame(
            columns=list(cell_cols) + ['baseline_fallback', 'fallback_weeks_back', 'fallback_samples']
        )
        return result

    # Coerce target KPI to numeric
    df_hist[target_kpi] = pd.to_numeric(df_hist[target_kpi], errors='coerce')

    # For each cell, compute per-weekday medians then average them
    result_list = []

    for cell_key, cell_df in df_hist.groupby(list(cell_cols)):
        # Group this cell's historical data by weekday
        cell_df = cell_df.copy()
        cell_df['_weekday'] = cell_df[date_col].dt.weekday

        weekday_medians = []
        total_samples = 0
        weekdays_with_data = 0

        for wd, lookback_dates in weekday_lookback_dates.items():
            # Get this cell's values for this weekday's lookback dates
            wd_data = cell_df[
                cell_df['_weekday'] == wd
            ][target_kpi].dropna()

            if len(wd_data) >= min_samples:
                wd_median = float(wd_data.median())
                weekday_medians.append(wd_median)
                total_samples += len(wd_data)
                weekdays_with_data += 1

        if weekday_medians:
            # Average the per-weekday medians (preserves seasonality pattern)
            fallback_value = float(np.mean(weekday_medians))
            sample_count = total_samples
        else:
            fallback_value = np.nan
            sample_count = 0

        row = dict(zip(cell_cols, cell_key))
        row['baseline_fallback'] = fallback_value
        row['fallback_weeks_back'] = lookback_weeks
        row['fallback_samples'] = sample_count
        result_list.append(row)

    if result_list:
        result_df = pd.DataFrame(result_list)
    else:
        result_df = pd.DataFrame(
            columns=list(cell_cols) + ['baseline_fallback', 'fallback_weeks_back', 'fallback_samples']
        )

    return result_df


def apply_baseline_fallback(
    comparison_df,
    df_full,
    target_kpi,
    cell_cols,
    date_col,
    baseline_start,
    baseline_end,
    min_baseline_value,
    lookback_weeks=5,
    min_samples=1,
    log_callback=None,
    is_ratio=False,
):
    """
    Apply baseline fallback for cells with NaN baseline average.

    For ratio KPIs (RRC SR %, Drop Rate %, HO SR %, etc.):
        - NaN baseline (no data): try historical fallback, then min_baseline_value
        - Zero baseline (actual 0): use 0.001 as fallback (avoids division by zero)

    For non-ratio KPIs (Traffic, Throughput, etc.):
        - NaN baseline (missing data): try historical fallback
        - Zero baseline (actual 0): try historical fallback first, then 0.001

    This function:
    1. Identifies cells with NaN baseline_avg_kpi
    2. For NaN: Attempts to get fallback from historical data (same weekday, N weeks ago)
    3. For zero (non-ratio): Uses min_baseline_value as last resort
    4. Flags cells where fallback was used for transparency

    Args:
        comparison_df: DataFrame with baseline_avg_kpi column
        df_full: Full DataFrame with all historical data
        target_kpi: Column name of the KPI
        cell_cols: List of columns identifying a cell
        date_col: Name of date column
        baseline_start: Start date of baseline period
        baseline_end: End date of baseline period
        min_baseline_value: Fallback value if no history available
        lookback_weeks: How many weeks back to look (default 5)
        min_samples: Minimum samples needed for valid median (default 1)
        log_callback: Optional logging function
        is_ratio: True for ratio KPIs (percentage values), False for volume/count KPIs

    Returns:
        DataFrame with updated baseline_avg_kpi and new flag columns:
        - baseline_fallback_used: True if fallback was applied
        - baseline_fallback_source: 'history', 'zero_fixed', or 'min_baseline_value'
        - baseline_fallback_value: The fallback value used
    """
    comparison_df = comparison_df.copy()

    # Initialize flag columns
    comparison_df['baseline_fallback_used'] = False
    comparison_df['baseline_fallback_source'] = None
    comparison_df['baseline_fallback_value'] = np.nan

    # Identify cells needing fallback (baseline is zero or NaN)
    is_zero = comparison_df['baseline_avg_kpi'] == 0
    is_nan = comparison_df['baseline_avg_kpi'].isna()
    needs_fallback = is_zero | is_nan

    if not needs_fallback.any():
        if log_callback:
            log_callback("No cells need baseline fallback")
        return comparison_df

    n_needs_fallback = needs_fallback.sum()
    if log_callback:
        log_callback(f"Attempting baseline fallback for {n_needs_fallback} cells with NaN baseline")

    # For NaN baseline, try historical fallback
    nan_mask = is_nan & needs_fallback
    if nan_mask.any():
        fallback_df = compute_baseline_fallback_from_history(
            df_full, target_kpi, cell_cols, date_col,
            baseline_start, baseline_end, lookback_weeks, min_samples
        )

        if not fallback_df.empty:
            comparison_df = comparison_df.merge(
                fallback_df[list(cell_cols) + ['baseline_fallback', 'fallback_weeks_back', 'fallback_samples']],
                on=list(cell_cols), how='left'
            )

            has_history = nan_mask & comparison_df['baseline_fallback'].notna()
            if has_history.any():
                comparison_df.loc[has_history, 'baseline_avg_kpi'] = comparison_df.loc[has_history, 'baseline_fallback']
                comparison_df.loc[has_history, 'baseline_fallback_used'] = True
                comparison_df.loc[has_history, 'baseline_fallback_source'] = 'history'
                comparison_df.loc[has_history, 'baseline_fallback_value'] = comparison_df.loc[has_history, 'baseline_fallback']
                if log_callback:
                    log_callback(f"  - {has_history.sum()} cells got fallback from historical data")

            still_nan = comparison_df['baseline_avg_kpi'].isna()
            if still_nan.any():
                comparison_df.loc[still_nan, 'baseline_avg_kpi'] = min_baseline_value
                comparison_df.loc[still_nan, 'baseline_fallback_used'] = True
                comparison_df.loc[still_nan, 'baseline_fallback_source'] = 'min_baseline_value'
                comparison_df.loc[still_nan, 'baseline_fallback_value'] = min_baseline_value
                if log_callback:
                    log_callback(f"  - {still_nan.sum()} cells using min_baseline_value ({min_baseline_value}) as fallback")

            cols_to_drop = ['baseline_fallback', 'fallback_weeks_back', 'fallback_samples']
            comparison_df = comparison_df.drop(columns=[c for c in cols_to_drop if c in comparison_df.columns], errors='ignore')
        else:
            still_nan = comparison_df['baseline_avg_kpi'].isna()
            if still_nan.any():
                comparison_df.loc[still_nan, 'baseline_avg_kpi'] = min_baseline_value
                comparison_df.loc[still_nan, 'baseline_fallback_used'] = True
                comparison_df.loc[still_nan, 'baseline_fallback_source'] = 'min_baseline_value'
                comparison_df.loc[still_nan, 'baseline_fallback_value'] = min_baseline_value
                if log_callback:
                    log_callback(f"  - {still_nan.sum()} cells using min_baseline_value ({min_baseline_value}) as fallback")

    # For non-ratio KPIs with zero baseline (not NaN), try historical fallback first
    if not is_ratio:
        zero_mask = is_zero & ~comparison_df['baseline_fallback_used']
        if zero_mask.any():
            fallback_df = compute_baseline_fallback_from_history(
                df_full, target_kpi, cell_cols, date_col,
                baseline_start, baseline_end, lookback_weeks, min_samples
            )

            if not fallback_df.empty:
                comparison_df = comparison_df.merge(
                    fallback_df[list(cell_cols) + ['baseline_fallback', 'fallback_weeks_back', 'fallback_samples']],
                    on=list(cell_cols), how='left'
                )

                has_history = is_zero & comparison_df['baseline_fallback'].notna()
                if has_history.any():
                    comparison_df.loc[has_history, 'baseline_avg_kpi'] = comparison_df.loc[has_history, 'baseline_fallback']
                    comparison_df.loc[has_history, 'baseline_fallback_used'] = True
                    comparison_df.loc[has_history, 'baseline_fallback_source'] = 'history'
                    comparison_df.loc[has_history, 'baseline_fallback_value'] = comparison_df.loc[has_history, 'baseline_fallback']
                    if log_callback:
                        log_callback(f"  - {has_history.sum()} zero-baseline cells got fallback from historical")

            # Any cell whose baseline is STILL zero here has no observed baseline
            # and no recoverable history. For a relative-% (non-ratio) KPI the
            # degradation is recent/baseline, which is undefined against a zero
            # reference. The previous 0.001 placeholder manufactured false
            # signals: a dead cell (recent 0) scored +100% degradation, and a
            # cell coming online (recent > 0) produced a large negative artifact
            # that polluted the aggregate statistics. Mark these cells with a NaN
            # baseline ("no usable reference") so the analysis layer excludes them
            # explicitly rather than fabricating a baseline. (BUG-04)
            still_zero = comparison_df['baseline_avg_kpi'].fillna(0) == 0
            if still_zero.any():
                comparison_df.loc[still_zero, 'baseline_avg_kpi'] = np.nan
                comparison_df.loc[still_zero, 'baseline_fallback_used'] = True
                comparison_df.loc[still_zero, 'baseline_fallback_source'] = 'no_usable_baseline'
                comparison_df.loc[still_zero, 'baseline_fallback_value'] = np.nan
                if log_callback:
                    log_callback(f"  - {still_zero.sum()} zero-baseline cells: no history, no usable reference -> excluded")

            cols_to_drop = ['baseline_fallback', 'fallback_weeks_back', 'fallback_samples']
            comparison_df = comparison_df.drop(columns=[c for c in cols_to_drop if c in comparison_df.columns], errors='ignore')

    return comparison_df
