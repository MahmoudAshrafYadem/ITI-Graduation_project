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

import warnings

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
    DEGRADATION_PCT_CAP,
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


def _safe_nanmean(a, axis):
    # np.nanmean warns ("Mean of empty slice") for all-NaN rows and returns
    # NaN, which is exactly the value we want for cells with no usable
    # baseline; suppress the noise rather than the (correct) NaN.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(a, axis=axis)


def _safe_nanmedian(a, axis):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmedian(a, axis=axis)


def _vectorized_degradation(recent, baseline, bad_direction, is_ratio):
    """Element-wise equivalent of calculate_degradation() over numpy arrays.

    Mirrors clean_excel_and_helpers.calculate_degradation exactly so the
    vectorized day-by-day path produces identical numbers to the old scalar
    loop: ratio/dB KPIs use a signed difference (no denominator); non-ratio
    KPIs use a relative %% change and yield NaN when the baseline is 0; NaN
    inputs propagate to NaN. (Supports BUG-08 vectorization.)
    """
    recent = np.asarray(recent, dtype="float64")
    baseline = np.asarray(baseline, dtype="float64")
    if bad_direction not in ("low", "high"):
        return np.full(recent.shape, np.nan)
    if is_ratio:
        return (baseline - recent) if bad_direction == "low" else (recent - baseline)
    with np.errstate(divide="ignore", invalid="ignore"):
        if bad_direction == "low":
            deg = (baseline - recent) / baseline * 100.0
        else:
            deg = (recent - baseline) / baseline * 100.0
    deg = np.where(baseline == 0, np.nan, deg)
    # Winsorize to match calculate_degradation's DEGRADATION_PCT_CAP so the
    # vectorized day-by-day path and the scalar path agree exactly, including on
    # the near-zero-baseline artifact tails (residual of BUG-04).
    return np.clip(deg, -DEGRADATION_PCT_CAP, DEGRADATION_PCT_CAP)


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
    cell_cols = list(cell_cols)
    out_cols = cell_cols + [
        "recent_avg_kpi", "baseline_avg_kpi", "kpi_degradation_ratio_%",
        "day_by_day_degradations", "days_compared",
        "recent_days_count", "baseline_days_count",
    ]

    if recent_df.empty:
        return pd.DataFrame(columns=out_cols)

    # ------------------------------------------------------------------ #
    # BUG-08 (performance): the previous implementation iterated every
    # cell and, for each one, rebuilt a full-frame boolean mask over the
    # entire recent_df and baseline_df (O(cells x rows)). On the real data
    # (~1,316 cells) that dominated runtime. This vectorized version does
    # the same arithmetic with two groupby/pivot passes (O(rows)) and
    # reproduces the old per-cell semantics exactly (verified frame-for-
    # frame against the original on the real dataset and on synthetic
    # edge cases). mean() per (cell, day) matches the old per-cell groupby
    # and is a no-op when the data is already one row per day (BUG-03).
    # ------------------------------------------------------------------ #
    rec = recent_df[cell_cols + [date_col, target_kpi]].copy()
    rec["_day"] = rec[date_col].dt.normalize()
    recent_daily = rec.groupby(cell_cols + ["_day"])[target_kpi].mean()
    R = recent_daily.unstack("_day")

    if baseline_df is None or baseline_df.empty:
        B = pd.DataFrame(index=pd.Index([], name=R.index.name))
    else:
        base = baseline_df[cell_cols + [date_col, target_kpi]].copy()
        base["_day"] = base[date_col].dt.normalize()
        baseline_daily = base.groupby(cell_cols + ["_day"])[target_kpi].mean()
        B = baseline_daily.unstack("_day")

    # Only cells present in BOTH windows are analysable (the old code took
    # the inner merge of recent_cells and baseline_cells).
    cells = R.index.intersection(B.index)
    if len(cells) == 0:
        return pd.DataFrame(columns=out_cols)

    rdates = [pd.Timestamp(d).normalize() for d in recent_dates]
    R = R.reindex(index=cells, columns=rdates)
    Rv = R.to_numpy(dtype="float64")
    recent_present = ~np.isnan(Rv)
    recent_days_count = recent_present.sum(axis=1)
    recent_avg = _safe_nanmean(np.where(recent_present, Rv, np.nan), axis=1)

    if baseline_mode == "last_week":
        # recent_dates[i] pairs with baseline_dates[i] (same weekday).
        bdates = [pd.Timestamp(d).normalize() for d in baseline_dates]
        Bv = B.reindex(index=cells, columns=bdates).to_numpy(dtype="float64")
        n = min(Rv.shape[1], Bv.shape[1])
        Rv_a, Bv_a, present_a = Rv[:, :n], Bv[:, :n], recent_present[:, :n]
    else:
        # 4week_rolling_avg: each recent day is compared with the mean of the
        # present same-weekday baseline daily values.
        bcols = list(B.columns)
        b_wd = np.array([pd.Timestamp(c).dayofweek for c in bcols], dtype=int)
        Ball = B.reindex(index=cells).to_numpy(dtype="float64")
        Bv_a = np.full(Rv.shape, np.nan, dtype="float64")
        for j, rdate in enumerate(rdates):
            sel = (b_wd == pd.Timestamp(rdate).dayofweek)
            if sel.any():
                Bv_a[:, j] = _safe_nanmean(Ball[:, sel], axis=1)
        Rv_a, present_a = Rv, recent_present

    # A baseline value counts only when its paired recent day is present AND
    # the baseline reference itself is present (the old nested guards).
    pair = present_a & ~np.isnan(Bv_a)
    deg = _vectorized_degradation(Rv_a, Bv_a, bad_direction, is_ratio)
    deg = np.where(pair, deg, np.nan)
    baseline_masked = np.where(pair, Bv_a, np.nan)

    baseline_days_count = (~np.isnan(baseline_masked)).sum(axis=1)
    baseline_avg = _safe_nanmean(baseline_masked, axis=1)
    days_compared = (~np.isnan(deg)).sum(axis=1)
    kpi_deg = _safe_nanmedian(deg, axis=1)
    day_lists = [list(row[~np.isnan(row)]) for row in deg]

    if isinstance(cells, pd.MultiIndex):
        result = pd.DataFrame(list(cells), columns=cell_cols)
    else:
        result = pd.DataFrame({cell_cols[0]: list(cells)})
    result["recent_avg_kpi"] = recent_avg
    result["baseline_avg_kpi"] = baseline_avg
    result["kpi_degradation_ratio_%"] = kpi_deg
    result["day_by_day_degradations"] = day_lists
    result["days_compared"] = days_compared
    result["recent_days_count"] = recent_days_count
    result["baseline_days_count"] = baseline_days_count
    return result



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

    # ---- Post-fallback exclusion: keep every analysable cell, drop the rest ----
    #
    # A cell is analysable only when it has BOTH a recent observation and a
    # *usable* baseline reference. We separate "no data" from "valid zero":
    #
    #   * recent_avg_kpi is NaN      -> no current measurement at all.
    #   * baseline_avg_kpi is NaN    -> no baseline survived the fallback chain
    #                                   (observation -> history -> min_value);
    #                                   marked NaN upstream when no reference exists.
    #   * baseline_avg_kpi <= 0 on a relative-% (non-ratio) KPI -> no usable
    #     reference: degradation = change / baseline is undefined at 0 and would
    #     otherwise fabricate a result (dead cell -> +100%, new cell -> huge
    #     negative). Ratio / dB KPIs compare via a *signed difference* with no
    #     denominator, so a zero baseline is perfectly valid for them and is kept.
    #
    # A *measured* recent value of 0 against a healthy baseline is NOT excluded:
    # it is a genuine outage (traffic -> 0, RRC/E-RAB Setup SR -> 0%) and must be
    # scored as the worst-case degradation it represents. (BUG-02)
    if not comparison.empty:
        recent_missing = comparison["recent_avg_kpi"].isna()
        baseline_missing = comparison["baseline_avg_kpi"].isna()
        if is_ratio:
            no_reference = baseline_missing
        else:
            no_reference = baseline_missing | (comparison["baseline_avg_kpi"] <= 0)
        unrecoverable = recent_missing | no_reference
        if unrecoverable.any():
            _record(
                comparison[unrecoverable],
                "excluded: no recent observation or no usable baseline reference"
            )
            comparison = comparison[~unrecoverable].copy()
            log_msg(
                f"INFO: {int(unrecoverable.sum())} cells excluded - no usable "
                f"recent/baseline (recent_missing={int(recent_missing.sum())}, "
                f"no_baseline_reference={int(no_reference.sum())}); "
                f"measured-zero cells with a healthy baseline are retained as outages"
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
        # Group observed recent/baseline values by the FULL cell identity
        # (eNodeB Name + Cell Name + LocalCell Id) exactly ONCE, then look each
        # cell up by key.
        #   * BUG-05: the previous code keyed only on (eNodeB Name, Cell Name),
        #     silently dropping LocalCell Id. That is harmless only while
        #     Cell<->LocalCell is 1:1 (as in this dataset); on any site where one
        #     Cell Name maps to multiple LocalCell Ids it pooled unrelated series
        #     into a single t-test. Keying on CELL_ID_COLS fixes that.
        #   * BUG-08: the previous code rebuilt a full-frame boolean mask for
        #     every comparison row (O(cells x rows)). One groupby is O(rows).
        recent_groups = {k: v for k, v in recent_df.groupby(CELL_ID_COLS)[target_kpi]}
        baseline_groups = {k: v for k, v in baseline_obs_df.groupby(CELL_ID_COLS)[target_kpi]}
        _empty = pd.Series([], dtype="float64")
        sig_vals, p_vals, t_vals = [], [], []
        for _, row in comparison.iterrows():
            key = tuple(row[c] for c in CELL_ID_COLS)
            cr = recent_groups.get(key, _empty)
            cb = baseline_groups.get(key, _empty)
            is_sig, p_val, t_stat = perform_ttest(cr, cb)
            sig_vals.append(is_sig)
            p_vals.append(p_val)
            t_vals.append(t_stat)
        comparison["stat_significant"] = pd.Series(sig_vals, index=comparison.index).fillna(False)
        comparison["p_value"] = pd.Series(p_vals, index=comparison.index)
        comparison["t_statistic"] = pd.Series(t_vals, index=comparison.index)

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
