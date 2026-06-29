# ============================================================
# LTE KPI Degradation Analyzer - Main Function for Selected KPI
# ============================================================
# Adds a data-quality layer:
#   * invalid counter values (unit violations / sentinels) are nulled and
#     recorded in metadata["quarantine_df"];
#   * baseline gaps are imputed from the same-weekday median over 4 weeks
#     (recent window is NOT imputed);
#   * cells with NaN baseline get fallback from historical data
#     (SAME-WEEKDAY per-weekday medians from N weeks ago — NOT pooled)
#     or min_baseline_value as last resort;
#   * DAY-BY-DAY COMPARISON: Each day in recent period is compared with its
#     corresponding day in baseline period, then the MEDIAN of per-day
#     degradations is used (robust to spike days);
#   * cells with incomplete/insufficient data are recorded in
#     metadata["incomplete_df"] instead of being silently dropped.
# Output columns include new "baseline_fallback_*" columns for transparency.
# ============================================================

import numpy as np
import pandas as pd

from KPI_Configuration import (
    DATE_COL,
    SITE_COL,
    CELL_COL,
    CELL_ID_COLS,
    KPI_CONFIGS,
)
from clean_excel_and_helpers import (
    clean_excel_columns,
    clean_numeric_series,
    find_matching_column,
    calculate_degradation,
    perform_ttest,
    get_periods_enhanced,
)
from cause_detect_functions import (
    find_degradation_causes_vectorized,
    find_degradation_causes_row,
)
from data_quality import validate_columns, compute_baseline_imputed, apply_baseline_fallback


def _empty_quarantine():
    return pd.DataFrame(columns=CELL_ID_COLS + [DATE_COL, "kpi", "counter", "bad_value", "reason"])


def _empty_incomplete():
    return pd.DataFrame(columns=CELL_ID_COLS + [
        "kpi", "recent_days_count", "baseline_days_count",
        "expected_recent_days", "expected_baseline_days", "reason"])


def compute_day_by_day_degradation(
    recent_df,
    baseline_df,
    target_kpi,
    cell_cols,
    date_col,
    bad_direction,
    recent_dates,
    baseline_dates,
    baseline_mode,
    is_ratio=False,
):
    """
    Compute day-by-day degradation for each cell.
    
    Instead of comparing period averages, this function:
    1. Matches each day in recent period with corresponding day in baseline
    2. Calculates degradation for each day pair
    3. Uses the MEDIAN of per-day degradations (robust to spike days)
    
    For "last_week" mode: Day 1 recent vs Day 1 baseline (same weekday)
    For "4week_rolling_avg" mode: Each recent day vs same weekday average from 4 weeks
    
    Args:
        is_ratio: True for ratio KPIs (percentage values like SR%), False for volume/count KPIs
    
    Returns DataFrame with columns:
        - cell_cols
        - recent_avg_kpi (average of recent daily values)
        - baseline_avg_kpi (average of baseline daily values)
        - kpi_degradation_ratio_% (MEDIAN of per-day degradations — robust to spikes)
        - day_by_day_degradations (list of per-day degradation values)
        - days_compared (number of day pairs compared)
    """
    results = []
    
    # Create day mapping based on baseline mode
    if baseline_mode == "last_week":
        # Direct day-to-day mapping: recent day i vs baseline day i (same weekday)
        day_mapping = {recent_dates[i]: baseline_dates[i] for i in range(len(recent_dates))}
    else:
        # For 4week_rolling_avg: map recent day to same weekday average from baseline period
        # Each recent day maps to multiple baseline days (same weekday from 4 weeks)
        day_mapping = None  # Will handle differently below
    
    # Get unique cells
    recent_cells = recent_df[cell_cols].drop_duplicates()
    baseline_cells = baseline_df[cell_cols].drop_duplicates()
    all_cells = recent_cells.merge(baseline_cells, on=cell_cols, how='inner')
    
    for _, cell_row in all_cells.iterrows():
        cell_filter = True
        for col in cell_cols:
            cell_filter = cell_filter & (recent_df[col] == cell_row[col])
        
        cell_recent = recent_df[cell_filter].copy()
        
        # Get baseline data for this cell
        cell_baseline_filter = True
        for col in cell_cols:
            cell_baseline_filter = cell_baseline_filter & (baseline_df[col] == cell_row[col])
        cell_baseline = baseline_df[cell_baseline_filter].copy()
        
        # Create date-indexed series
        recent_daily = cell_recent.set_index(date_col)[target_kpi]
        baseline_daily = cell_baseline.set_index(date_col)[target_kpi]
        
        day_degradations = []
        recent_values = []
        baseline_values = []
        
        for recent_day in recent_dates:
            recent_day = pd.Timestamp(recent_day).normalize()
            
            if recent_day not in recent_daily.index or pd.isna(recent_daily.get(recent_day)):
                continue
            
            recent_val = recent_daily[recent_day]
            recent_values.append(recent_val)
            
            if baseline_mode == "last_week":
                # Direct day mapping
                baseline_day = day_mapping.get(recent_day)
                if baseline_day is None:
                    continue
                baseline_day = pd.Timestamp(baseline_day).normalize()
                
                # NEW: Keep the cell even if baseline is NaN — record the
                # baseline value so apply_baseline_fallback() can recover it
                # later from historical data. calculate_degradation() will
                # return NaN for NaN baselines, which is fine: the
                # fallback at the aggregate level will patch baseline_avg_kpi
                # and we recompute the ratio afterwards.
                if baseline_day in baseline_daily.index:
                    baseline_val = baseline_daily[baseline_day]
                    if not pd.isna(baseline_val):
                        baseline_values.append(baseline_val)
                        deg = calculate_degradation(recent_val, baseline_val, bad_direction, is_ratio)
                        if not pd.isna(deg):
                            day_degradations.append(deg)
                # If baseline_day is missing or NaN, skip but keep the cell
            else:
                # 4week_rolling_avg: compare with same weekday average from baseline period
                # Get all same-weekday values from baseline
                same_weekday = recent_day.dayofweek
                same_weekday_dates = [d for d in baseline_dates if pd.Timestamp(d).dayofweek == same_weekday]
                
                baseline_vals_for_day = []
                for bd in same_weekday_dates:
                    bd = pd.Timestamp(bd).normalize()
                    if bd in baseline_daily.index and not pd.isna(baseline_daily.get(bd)):
                        baseline_vals_for_day.append(baseline_daily[bd])
                
                if baseline_vals_for_day:
                    baseline_val = np.mean(baseline_vals_for_day)
                    baseline_values.append(baseline_val)
                    
                    deg = calculate_degradation(recent_val, baseline_val, bad_direction, is_ratio)
                    if not pd.isna(deg):
                        day_degradations.append(deg)
        
        # NEW: Do NOT skip cells with empty day_degradations.
        # Cells with all-zero baseline (or all-missing baseline) will have
        # empty day_degradations but may still have valid recent_values.
        # We include them here with NaN kpi_degradation_ratio_% so that
        # apply_baseline_fallback() in the caller can recover their baseline
        # from historical data and recompute the ratio. Only cells with NO
        # recent values at all are skipped (nothing to compare).
        if not recent_values:
            continue
        
        result_row = dict(zip(cell_cols, [cell_row[c] for c in cell_cols]))
        result_row['recent_avg_kpi'] = np.mean(recent_values) if recent_values else np.nan
        result_row['baseline_avg_kpi'] = np.mean(baseline_values) if baseline_values else np.nan
        # MEDIAN (not mean) of per-day degradations — robust to spike days.
        # A single spike day (e.g., special event, counter glitch) would
        # drastically skew the mean; the median reflects the TYPICAL day's
        # degradation and is not pulled around by outliers.
        # If no day_degradations were computed (e.g., all baselines were zero),
        # kpi_degradation_ratio_% stays NaN. The fallback + recompute step
        # in the caller will fill this in if a historical baseline is found.
        result_row['kpi_degradation_ratio_%'] = np.median(day_degradations) if day_degradations else np.nan
        result_row['day_by_day_degradations'] = day_degradations
        result_row['days_compared'] = len(day_degradations)
        result_row['recent_days_count'] = len(recent_values)
        result_row['baseline_days_count'] = len(baseline_values)
        
        results.append(result_row)
    
    if results:
        return pd.DataFrame(results)
    else:
        return pd.DataFrame(columns=list(cell_cols) + [
            'recent_avg_kpi', 'baseline_avg_kpi', 'kpi_degradation_ratio_%',
            'day_by_day_degradations', 'days_compared', 'recent_days_count', 'baseline_days_count'
        ])


def analyze_selected_kpi(
    df,
    selected_kpi_name,
    num_days,
    degradation_threshold,
    require_complete_days=True,
    baseline_mode="last_week",
    custom_baseline_start=None,
    custom_baseline_end=None,
    enable_significance_test=True,
    log_callback=None,
):
    """Main analysis function for a single KPI. Returns (output_df, metadata).

    metadata additionally carries:
        quarantine_df  - invalid counter values (operator action needed)
        incomplete_df  - cells with missing/insufficient days
    """
    def log_msg(msg):
        if log_callback:
            log_callback(msg)

    config = KPI_CONFIGS[selected_kpi_name]
    df = clean_excel_columns(df)

    original_target_kpi = config["target_kpi"]
    target_kpi = find_matching_column(df, original_target_kpi)
    if target_kpi is None:
        raise ValueError(f"Target KPI column not found in Excel: {original_target_kpi}")

    bad_direction = config["bad_direction"]
    related_rules = config["related_rules"]
    min_baseline_value = config.get("min_baseline_value", 0.0)
    is_ratio = config.get("is_ratio", False)

    needed_cols = CELL_ID_COLS + [DATE_COL, target_kpi]
    missing_cols = [c for c in needed_cols if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    df_kpi = df[needed_cols].copy()
    df_kpi[DATE_COL] = pd.to_datetime(df_kpi[DATE_COL], errors="coerce").dt.normalize()
    df_kpi[target_kpi] = clean_numeric_series(df_kpi[target_kpi])
    df_kpi = df_kpi.dropna(subset=[DATE_COL])

    # ---- Data quality: validate target, quarantine invalid values (-> NaN) ----
    quarantine_frames = []
    df_kpi, q_target = validate_columns(
        df_kpi, [target_kpi], selected_kpi_name, CELL_ID_COLS, DATE_COL, log_msg)
    quarantine_frames.append(q_target)

    # Periods
    last_date, recent_start, recent_end, baseline_start, baseline_end = get_periods_enhanced(
        df_kpi, DATE_COL, num_days, baseline_mode, custom_baseline_start, custom_baseline_end)

    recent_dates = list(pd.date_range(recent_start, recent_end, freq="D"))
    baseline_dates = list(pd.date_range(baseline_start, baseline_end, freq="D"))
    expected_recent = len(recent_dates)
    expected_baseline = len(baseline_dates)

    target_obs = df_kpi.dropna(subset=[target_kpi])

    # Recent period data
    recent_df = target_obs[(target_obs[DATE_COL] >= recent_start) & (target_obs[DATE_COL] <= recent_end)].copy()

    # Baseline period data (with imputation)
    baseline_obs_df = target_obs[(target_obs[DATE_COL] >= baseline_start) & (target_obs[DATE_COL] <= baseline_end)].copy()
    
    # Also get historical data for baseline imputation
    baseline_with_imputation = compute_baseline_imputed(target_obs, target_kpi, CELL_ID_COLS, DATE_COL, baseline_dates)

    # ---- NEW: Day-by-day degradation calculation ----
    log_msg("Calculating day-by-day degradation...")
    
    day_by_day_results = compute_day_by_day_degradation(
        recent_df=recent_df,
        baseline_df=baseline_obs_df,
        target_kpi=target_kpi,
        cell_cols=CELL_ID_COLS,
        date_col=DATE_COL,
        bad_direction=bad_direction,
        recent_dates=recent_dates,
        baseline_dates=baseline_dates,
        baseline_mode=baseline_mode,
        is_ratio=is_ratio,
    )

    if day_by_day_results.empty:
        log_msg("No cells with valid day-by-day comparison")
        comparison = pd.DataFrame(columns=CELL_ID_COLS + [
            'recent_avg_kpi', 'baseline_avg_kpi', 'kpi_degradation_ratio_%',
            'day_by_day_degradations', 'days_compared', 'recent_days_count', 'baseline_days_count'
        ])
    else:
        comparison = day_by_day_results.copy()
        log_msg(f"Day-by-day comparison completed for {len(comparison)} cells")

    # ---- Track cells with incomplete data ----
    incomplete_records = []
    
    def _record(sub, reason):
        if sub.empty:
            return
        rec = sub[CELL_ID_COLS].copy()
        rec["kpi"] = selected_kpi_name
        rec["recent_days_count"] = sub.get("recent_days_count")
        rec["baseline_days_count"] = sub.get("baseline_days_count")
        rec["expected_recent_days"] = expected_recent
        rec["expected_baseline_days"] = expected_baseline
        rec["reason"] = reason
        incomplete_records.append(rec)

    # Track cells with incomplete days
    if not comparison.empty:
        inc_mask = (comparison["recent_days_count"] < expected_recent) | (comparison["baseline_days_count"] < expected_baseline)
        _record(comparison[inc_mask], "incomplete day count (recent or baseline)")

    # ---- NEW: Apply baseline fallback FIRST (before any exclusion) ----
    # For cells with NaN baseline_avg_kpi, try to recover a defensible
    # baseline from historical same-weekday data (Stage 1), and fall back to
    # min_baseline_value as last resort (Stage 2). This runs BEFORE the
    # "both zero" exclusion so recoverable cells are not silently dropped.
    if not comparison.empty:
        comparison = apply_baseline_fallback(
            comparison_df=comparison,
            df_full=df,
            target_kpi=target_kpi,
            cell_cols=CELL_ID_COLS,
            date_col=DATE_COL,
            baseline_start=baseline_start,
            baseline_end=baseline_end,
            min_baseline_value=min_baseline_value,
            lookback_weeks=5,
            min_samples=1,
            log_callback=log_msg,
            is_ratio=is_ratio,
        )

    # ---- NEW: Recompute kpi_degradation_ratio_% for cells that used fallback ----
    # When the day-by-day comparison couldn't compute a degradation ratio
    # (because the baseline was NaN), but the fallback recovered a
    # baseline, we recompute the ratio here using the patched baseline_avg_kpi
    # and the observed recent_avg_kpi. This gives those cells a fair chance
    # to be evaluated against the threshold.
    if not comparison.empty:
        fallback_mask = comparison.get("baseline_fallback_used", False) == True
        needs_recompute = fallback_mask & comparison["kpi_degradation_ratio_%"].isna()
        if needs_recompute.any():
            n_recompute = int(needs_recompute.sum())
            log_msg(f"Recomputing degradation ratio for {n_recompute} cells with fallback baseline")
            for idx in comparison[needs_recompute].index:
                recent_val = comparison.at[idx, "recent_avg_kpi"]
                baseline_val = comparison.at[idx, "baseline_avg_kpi"]
                deg = calculate_degradation(recent_val, baseline_val, bad_direction, is_ratio)
                comparison.at[idx, "kpi_degradation_ratio_%"] = deg
                # Update days_compared to reflect that we used aggregate comparison
                if pd.isna(comparison.at[idx, "days_compared"]) or comparison.at[idx, "days_compared"] == 0:
                    comparison.at[idx, "days_compared"] = comparison.at[idx, "recent_days_count"]

    # ---- Post-fallback exclusion: only drop cells that are truly unrecoverable ----
    # A cell is unrecoverable only if recent OR baseline is still NaN after
    # all fallback attempts (meaning no measurement exists at all).
    # A value of 0 is a valid real measurement (e.g., outage, 0% SR) and
    # must be kept for degradation calculation. Do NOT conflate NaN with 0.
    if not comparison.empty:
        recent_is_nan = comparison["recent_avg_kpi"].isna()
        baseline_is_nan = comparison["baseline_avg_kpi"].isna()
        unrecoverable = recent_is_nan | baseline_is_nan
        if unrecoverable.any():
            _record(
                comparison[unrecoverable],
                "unrecoverable after fallback (recent or baseline is NaN)"
            )
            comparison = comparison[~unrecoverable].copy()
            log_msg(
                f"INFO: {int(unrecoverable.sum())} cells excluded - "
                f"unrecoverable after baseline fallback "
                f"(recent_nan={int(recent_is_nan.sum())}, "
                f"baseline_nan={int(baseline_is_nan.sum())})"
            )

    # No min_baseline_value exclusion anymore (fallback handles it)
    excluded_by_min = 0

    # Require complete days if specified
    if require_complete_days and not comparison.empty:
        comparison = comparison[
            (comparison["recent_days_count"] == expected_recent) &
            (comparison["baseline_days_count"] == expected_baseline)].copy()

    incomplete_df = pd.concat(incomplete_records, ignore_index=True) if incomplete_records else _empty_incomplete()

    # If comparison is empty, return early
    if comparison.empty:
        debug_info = {
            "cells_after_merge": 0,
            "max_degradation": None,
            "min_degradation": None,
            "mean_degradation": None,
            "min_baseline_excluded": excluded_by_min,
            "incomplete_cells": int(incomplete_df.shape[0]),
            "quarantined_values": int(sum(f.shape[0] for f in quarantine_frames)),
            "baseline_fallback_used": 0,
            "baseline_fallback_from_history": 0,
            "baseline_fallback_from_min_value": 0,
        }
        metadata = {
            "last_date": last_date,
            "recent_start": recent_start, "recent_end": recent_end,
            "baseline_start": baseline_start, "baseline_end": baseline_end,
            "baseline_mode": baseline_mode,
            "available_related_features": [], "missing_related_features": [],
            "debug_info": debug_info,
            "quarantine_df": pd.concat(quarantine_frames, ignore_index=True) if quarantine_frames else _empty_quarantine(),
            "incomplete_df": incomplete_df,
        }
        return pd.DataFrame(), metadata

    # Significance test on OBSERVED values only
    if enable_significance_test and not comparison.empty:
        results = []
        for idx, row in comparison.iterrows():
            cid = (row[SITE_COL], row[CELL_COL])
            cr = recent_df[(recent_df[SITE_COL] == cid[0]) & (recent_df[CELL_COL] == cid[1])][target_kpi]
            cb = baseline_obs_df[(baseline_obs_df[SITE_COL] == cid[0]) & (baseline_obs_df[CELL_COL] == cid[1])][target_kpi]
            is_sig, p_val, t_stat = perform_ttest(cr, cb)
            results.append({"index": idx, "stat_significant": is_sig, "p_value": p_val, "t_statistic": t_stat})
        sig_df = pd.DataFrame(results).set_index("index")
        comparison["stat_significant"] = sig_df["stat_significant"].reindex(comparison.index).fillna(False)
        comparison["p_value"] = sig_df["p_value"].reindex(comparison.index)
        comparison["t_statistic"] = sig_df["t_statistic"].reindex(comparison.index)

    if enable_significance_test:
        comparison["kpi_status"] = np.where(
            (comparison["kpi_degradation_ratio_%"] >= degradation_threshold) &
            (comparison.get("stat_significant", False) == True), "Degraded", "Normal")
    else:
        comparison["kpi_status"] = np.where(
            comparison["kpi_degradation_ratio_%"] >= degradation_threshold, "Degraded", "Normal")

    comparison["selected_kpi_name"] = selected_kpi_name
    comparison["target_kpi_column"] = target_kpi
    comparison["kpi_category"] = config["category"]
    comparison["kpi_bad_direction"] = bad_direction
    comparison["selected_threshold_%"] = degradation_threshold
    comparison["recent_period"] = f"{recent_start.date()} to {recent_end.date()}"
    comparison["baseline_period"] = f"{baseline_start.date()} to {baseline_end.date()}"
    comparison["baseline_mode"] = baseline_mode

    degraded_cells = comparison[comparison["kpi_status"] == "Degraded"].copy()
    degraded_cells = degraded_cells.sort_values("kpi_degradation_ratio_%", ascending=False)

    # Count fallback usage for debug info
    fallback_used_count = int(comparison.get("baseline_fallback_used", pd.Series([False])).sum()) if "baseline_fallback_used" in comparison.columns else 0
    fallback_from_history = int((comparison.get("baseline_fallback_source", pd.Series()) == "history").sum()) if "baseline_fallback_source" in comparison.columns else 0
    fallback_from_min = int((comparison.get("baseline_fallback_source", pd.Series()) == "min_baseline_value").sum()) if "baseline_fallback_source" in comparison.columns else 0

    debug_info = {
        "cells_after_merge": comparison.shape[0],
        "max_degradation": comparison["kpi_degradation_ratio_%"].max() if not comparison.empty else None,
        "min_degradation": comparison["kpi_degradation_ratio_%"].min() if not comparison.empty else None,
        "mean_degradation": comparison["kpi_degradation_ratio_%"].mean() if not comparison.empty else None,
        "min_baseline_excluded": excluded_by_min,
        "incomplete_cells": int(incomplete_df.shape[0]),
        "quarantined_values": int(sum(f.shape[0] for f in quarantine_frames)),
        "baseline_fallback_used": fallback_used_count,
        "baseline_fallback_from_history": fallback_from_history,
        "baseline_fallback_from_min_value": fallback_from_min,
        "comparison_method": "day_by_day",
    }
    metadata = {
        "last_date": last_date,
        "recent_start": recent_start, "recent_end": recent_end,
        "baseline_start": baseline_start, "baseline_end": baseline_end,
        "baseline_mode": baseline_mode,
        "available_related_features": [], "missing_related_features": [],
        "debug_info": debug_info,
        "quarantine_df": _empty_quarantine(),
        "incomplete_df": incomplete_df,
    }

    if degraded_cells.empty:
        metadata["quarantine_df"] = pd.concat(quarantine_frames, ignore_index=True) if quarantine_frames else _empty_quarantine()
        return degraded_cells, metadata

    # ---- Related counters (cause detection) ----
    available_related_rules, missing_related_features = [], []
    for rule in related_rules:
        matched = find_matching_column(df, rule["feature"])
        if matched is not None:
            nr = rule.copy(); nr["feature"] = matched
            available_related_rules.append(nr)
        else:
            missing_related_features.append(rule["feature"])
    available_related_features = [r["feature"] for r in available_related_rules]
    metadata["available_related_features"] = available_related_features
    metadata["missing_related_features"] = missing_related_features

    if available_related_features:
        reason_cols = CELL_ID_COLS + [DATE_COL] + available_related_features
        df_reason = df[reason_cols].copy()
        df_reason[DATE_COL] = pd.to_datetime(df_reason[DATE_COL], errors="coerce").dt.normalize()
        for col in available_related_features:
            df_reason[col] = clean_numeric_series(df_reason[col])

        # validate + quarantine related counters
        df_reason, q_feat = validate_columns(
            df_reason, available_related_features, selected_kpi_name, CELL_ID_COLS, DATE_COL, log_msg)
        quarantine_frames.append(q_feat)

        # restrict to degraded cells for efficiency
        deg_keys = degraded_cells[CELL_ID_COLS].drop_duplicates()
        df_reason = df_reason.merge(deg_keys, on=CELL_ID_COLS, how="inner")

        recent_reason_df = df_reason[(df_reason[DATE_COL] >= recent_start) & (df_reason[DATE_COL] <= recent_end)].copy()

        recent_reason_agg = recent_reason_df.groupby(CELL_ID_COLS).agg(
            {c: ["mean", "max"] for c in available_related_features}).reset_index()
        rcols = CELL_ID_COLS.copy()
        for c in available_related_features:
            rcols += [f"recent_{c}_mean", f"recent_{c}_max"]
        recent_reason_agg.columns = rcols

        # imputed baseline per feature
        baseline_reason_agg = deg_keys.copy()
        for c in available_related_features:
            bi = compute_baseline_imputed(
                df_reason.dropna(subset=[c])[CELL_ID_COLS + [DATE_COL, c]], c,
                CELL_ID_COLS, DATE_COL, baseline_dates)
            bi = bi.rename(columns={"baseline_avg": f"baseline_{c}_mean", "baseline_max": f"baseline_{c}_max"})
            baseline_reason_agg = baseline_reason_agg.merge(
                bi[CELL_ID_COLS + [f"baseline_{c}_mean", f"baseline_{c}_max"]], on=CELL_ID_COLS, how="left")

        for c in available_related_features:
            recent_reason_agg[f"recent_{c}"] = recent_reason_agg[f"recent_{c}_mean"]
            baseline_reason_agg[f"baseline_{c}"] = baseline_reason_agg[f"baseline_{c}_mean"]

        degraded_with_causes = degraded_cells.merge(recent_reason_agg, on=CELL_ID_COLS, how="left")
        degraded_with_causes = degraded_with_causes.merge(baseline_reason_agg, on=CELL_ID_COLS, how="left")
        degraded_with_causes = degraded_with_causes.reset_index(drop=True)

        try:
            cause_results = find_degradation_causes_vectorized(degraded_with_causes, available_related_rules)
            degraded_with_causes = pd.concat([degraded_with_causes.reset_index(drop=True), cause_results.reset_index(drop=True)], axis=1)
        except Exception as vec_error:
            log_msg(f"Vectorized cause detection failed, using fallback: {vec_error}")
            cause_results = degraded_with_causes.apply(
                lambda row: find_degradation_causes_row(row, available_related_rules), axis=1)
            degraded_with_causes = pd.concat([degraded_with_causes, cause_results], axis=1)

        if 'main_root_cause_category' not in degraded_with_causes.columns:
            degraded_with_causes['main_root_cause_category'] = 'Unknown'
    else:
        degraded_with_causes = degraded_cells.copy()
        degraded_with_causes["main_cause_counter_or_kpi"] = "No related counters available in sheet"
        degraded_with_causes["main_cause_recent_value"] = np.nan
        degraded_with_causes["main_cause_baseline_value"] = np.nan
        degraded_with_causes["main_cause_change_%"] = np.nan
        degraded_with_causes["main_root_cause_category"] = "Unknown"
        degraded_with_causes["main_degradation_reason"] = "No related counters from the config were found in the uploaded sheet."
        degraded_with_causes["main_recommended_action"] = "Check KPI manually or update KPI_CONFIGS with available counters."
        degraded_with_causes["number_of_detected_causes"] = 0
        degraded_with_causes["multi_cause_flag"] = "No"
        degraded_with_causes["all_detected_causes"] = "None"
        degraded_with_causes["all_cause_categories"] = "Unknown"
        degraded_with_causes["all_recommended_actions"] = "Manual investigation needed"

    metadata["quarantine_df"] = pd.concat(quarantine_frames, ignore_index=True) if quarantine_frames else _empty_quarantine()

    final_cols = CELL_ID_COLS + [
        "selected_kpi_name", "target_kpi_column", "kpi_category",
        "selected_threshold_%", "recent_period", "baseline_period",
        "recent_avg_kpi", "baseline_avg_kpi", 
        "kpi_degradation_ratio_%",
        "number_of_detected_causes",
        "all_detected_causes", "main_root_cause_category",
        "main_cause_counter_or_kpi", "main_degradation_reason", "main_recommended_action", "all_recommended_actions"
    ]
    available_final_cols = [c for c in final_cols if c in degraded_with_causes.columns]
    return degraded_with_causes[available_final_cols].copy(), metadata
