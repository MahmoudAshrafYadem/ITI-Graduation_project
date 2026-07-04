"""Regression suite for the remaining KPI-analyzer bugs (BUG-05..BUG-10 + the
residual of BUG-04).

Each test is written so that it FAILS against the pre-fix source and PASSES
against the fixed source. They build real-shaped frames with kpi_test_utils so
the production code paths are exercised directly (no logic is stubbed).

Run:  pytest -q test_kpi_bugs.py
"""
import os
import re
import warnings

import numpy as np
import pandas as pd
import pytest

from KPI_Configuration import (
    SITE_COL, CELL_COL, LOCAL_CELL_COL, DATE_COL, KPI_CONFIGS,
)
from clean_excel_and_helpers import (
    perform_ttest, calculate_degradation, DEGRADATION_PCT_CAP,
)
from main_function_for_selected_kpi import (
    analyze_selected_kpi, compute_day_by_day_degradation,
)
from cause_detect_functions import find_degradation_causes_vectorized
from anomaly_detection import detect_kpi_anomalies_last_day
from kpi_test_utils import build_frame, target_col

ANCHOR = pd.Timestamp("2024-03-14")  # Thursday


# --------------------------------------------------------------------------- #
# BUG-06 — perform_ttest must not return t=NaN for constant-but-different data
# --------------------------------------------------------------------------- #
def test_bug06_constant_but_different_returns_finite_signed_t():
    recent = pd.Series([5.0, 5.0, 5.0])
    baseline = pd.Series([10.0, 10.0, 10.0])
    is_sig, p, t = perform_ttest(recent, baseline)
    assert is_sig is True
    assert p == 0.0
    # The bug returned np.nan here, poisoning every downstream numeric op.
    assert not np.isnan(t), "t-statistic must not be NaN for different constants"
    assert np.isinf(t) and t < 0, "sign must follow (recent - baseline) < 0"

    # Same constant -> genuinely no difference.
    is_sig2, p2, t2 = perform_ttest(pd.Series([5.0, 5.0]), pd.Series([5.0, 5.0]))
    assert is_sig2 is False and p2 == 1.0 and t2 == 0.0


# --------------------------------------------------------------------------- #
# BUG-05 — significance test must key on the FULL identity (incl. LocalCell Id),
# not pool rows that merely share eNodeB + Cell Name.
# --------------------------------------------------------------------------- #
def test_bug05_ttest_keyed_on_localcell_id():
    kpi = "DL Traffic"  # non-ratio, bad_direction = low
    # Two cells share site+cell but differ ONLY in LocalCell Id.
    #   A (local=0): clear 80% drop, internally constant -> per-cell t-test is
    #                significant, so A is a genuine Degraded cell.
    #   B (local=1): the mirror image (improvement), constant.
    # Pooled by (site, cell) the two recent series become {1x7, 5x7} and the two
    # baseline series become {5x7, 1x7} -> identical distributions -> the pooled
    # t-test is NOT significant. So the OLD code (which pooled by site+cell) would
    # wrongly mark A as not-significant and DROP it from the degraded set. The
    # fixed code keys on LocalCell Id and keeps A.
    cells = [
        {"site": "S1", "cell": "C1", "local": 0,
         "recent": [1.0] * 7, "baseline": [5.0] * 7},   # real 80% degradation
        {"site": "S1", "cell": "C1", "local": 1,
         "recent": [5.0] * 7, "baseline": [1.0] * 7},   # improvement (Normal)
    ]
    df = build_frame(cells, kpi, anchor=ANCHOR)
    out, _ = analyze_selected_kpi(
        df, kpi, num_days=7, degradation_threshold=10.0,
        require_complete_days=True, baseline_mode="last_week",
        enable_significance_test=True,
    )
    locals_out = set(zip(out[SITE_COL], out[CELL_COL], out[LOCAL_CELL_COL]))
    assert ("S1", "C1", 0) in locals_out, (
        "the genuinely-degraded LocalCell Id=0 cell must survive significance "
        "gating; if it is missing, its t-test was pooled across LocalCell Ids "
        "(BUG-05) and washed out"
    )
    assert ("S1", "C1", 1) not in locals_out, "the improving cell must stay Normal"


# --------------------------------------------------------------------------- #
# BUG-07 — anomaly z-score must use a robust (MAD) scale, so a real spike is not
# hidden by a std denominator inflated by an unrelated historical outlier.
# --------------------------------------------------------------------------- #
def test_bug07_robust_mad_zscore_catches_spike_std_misses():
    kpi = "DL Traffic"
    tgt = target_col(kpi)
    site, cell, local = "S1", "C1", 0
    rows = []
    # 24 days of tight history (99/101) PLUS one large outlier that inflates std
    # but barely moves the MAD.
    hist_vals = ([99.0, 101.0] * 11) + [99.0, 500.0]   # 24 values, median 100
    for k, v in enumerate(hist_vals, start=1):
        rows.append({SITE_COL: site, CELL_COL: cell, LOCAL_CELL_COL: local,
                     DATE_COL: ANCHOR - pd.Timedelta(days=k), tgt: v})
    # Last day: a clear ~10% departure from the median of 100.
    rows.append({SITE_COL: site, CELL_COL: cell, LOCAL_CELL_COL: local,
                 DATE_COL: ANCHOR, tgt: 110.0})
    df = pd.DataFrame(rows)

    res = detect_kpi_anomalies_last_day(df, output_path=None, spike_z_threshold=3.0)
    spikes = res[(res["KPI_Name"] == kpi) & (res["Anomaly_Type"] == "Spike")]
    assert len(spikes) == 1, "robust z-score should flag the last-day departure"

    row = spikes.iloc[0]
    # Prove the *old* std-based z-score would have MISSED it: with the outlier
    # inflating std, (value - median)/std stays well under the threshold.
    z_std = abs((110.0 - row["Historical_Median"]) / row["Historical_Std"])
    assert z_std < 3.0, "this case only fires under a robust (MAD) scale"
    assert "MAD" in row["Description"] or "robust" in row["Description"].lower()


def test_bug07_log_no_longer_claims_same_weekday():
    # The lookback uses ALL 24 days; the log must not claim same-weekday matching.
    msgs = []
    df = build_frame(
        [{"site": "S1", "cell": "C1", "local": 0,
          "recent": [10.0], "baseline": [10.0]}],
        "DL Traffic", anchor=ANCHOR,
    )
    detect_kpi_anomalies_last_day(df, output_path=None, log_callback=msgs.append)
    joined = "\n".join(msgs)
    assert "SAME WEEKDAY" not in joined.upper(), (
        "log must not claim same-weekday matching while using all 24 days"
    )


# --------------------------------------------------------------------------- #
# BUG-08 — vectorized day-by-day degradation must equal a brute-force scalar
# reference (the refactor is performance-only; numbers must not move).
# --------------------------------------------------------------------------- #
def _scalar_reference(recent_df, baseline_df, target_kpi, cell_cols, date_col,
                      bad_direction, recent_dates, baseline_dates, is_ratio,
                      baseline_mode="last_week"):
    """Independent, deliberately naive per-cell/per-day reimplementation."""
    rcells = recent_df[cell_cols].drop_duplicates()
    bcells = baseline_df[cell_cols].drop_duplicates()
    allc = rcells.merge(bcells, on=cell_cols, how="inner")
    out = []
    mapping = {recent_dates[i]: baseline_dates[i] for i in range(len(recent_dates))}
    for _, cr in allc.iterrows():
        rmask = np.logical_and.reduce([recent_df[c] == cr[c] for c in cell_cols])
        bmask = np.logical_and.reduce([baseline_df[c] == cr[c] for c in cell_cols])
        rday = recent_df[rmask].groupby(recent_df[rmask][date_col].dt.normalize())[target_kpi].mean()
        bday = baseline_df[bmask].groupby(baseline_df[bmask][date_col].dt.normalize())[target_kpi].mean()
        degs, rvals, bvals = [], [], []
        for rd in recent_dates:
            rd = pd.Timestamp(rd).normalize()
            if rd not in rday.index or pd.isna(rday.get(rd)):
                continue
            rvals.append(rday[rd])
            bd = pd.Timestamp(mapping[rd]).normalize()
            if bd in bday.index and not pd.isna(bday[bd]):
                bvals.append(bday[bd])
                d = calculate_degradation(rday[rd], bday[bd], bad_direction, is_ratio)
                if not pd.isna(d):
                    degs.append(d)
        if not rvals:
            continue
        out.append({
            **{c: cr[c] for c in cell_cols},
            "recent_avg_kpi": np.mean(rvals),
            "baseline_avg_kpi": np.mean(bvals) if bvals else np.nan,
            "kpi_degradation_ratio_%": np.median(degs) if degs else np.nan,
            "days_compared": len(degs),
            "recent_days_count": len(rvals),
            "baseline_days_count": len(bvals),
        })
    return pd.DataFrame(out)


def test_bug08_vectorized_matches_scalar_reference():
    kpi = "DL Traffic"
    cells = [
        {"site": "S1", "cell": "C1", "local": 0,                 # healthy degrade
         "recent": [2, 2, 2, 2, 2, 2, 2], "baseline": [5, 5, 5, 5, 5, 5, 5]},
        {"site": "S1", "cell": "C2", "local": 0,                 # missing days
         "recent": {0: 3, 2: 3, 4: 3}, "baseline": {0: 6, 2: 6, 4: 6}},
        {"site": "S2", "cell": "C1", "local": 0,                 # outage to zero
         "recent": [0, 0, 0, 0, 0, 0, 0], "baseline": [8, 8, 8, 8, 8, 8, 8]},
        {"site": "S2", "cell": "C2", "local": 0,                 # tiny baseline -> cap
         "recent": [0.9] * 7, "baseline": [0.0096] * 7},
    ]
    df = build_frame(cells, kpi, anchor=ANCHOR)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL]).dt.normalize()
    tgt = target_col(kpi)
    cfg = KPI_CONFIGS[kpi]
    cell_cols = [SITE_COL, CELL_COL, LOCAL_CELL_COL]
    rdates = list(pd.date_range(ANCHOR - pd.Timedelta(days=6), ANCHOR, freq="D"))
    bdates = list(pd.date_range(ANCHOR - pd.Timedelta(days=13), ANCHOR - pd.Timedelta(days=7), freq="D"))
    recent_df = df[(df[DATE_COL] >= rdates[0]) & (df[DATE_COL] <= rdates[-1])]
    base_df = df[(df[DATE_COL] >= bdates[0]) & (df[DATE_COL] <= bdates[-1])]

    kw = dict(target_kpi=tgt, cell_cols=cell_cols, date_col=DATE_COL,
              bad_direction=cfg["bad_direction"], recent_dates=rdates,
              baseline_dates=bdates, baseline_mode="last_week",
              is_ratio=cfg.get("is_ratio", False))
    got = compute_day_by_day_degradation(recent_df, base_df, **kw)
    ref = _scalar_reference(recent_df, base_df, **kw)

    keys = cell_cols
    got = got.sort_values(keys).reset_index(drop=True)
    ref = ref.sort_values(keys).reset_index(drop=True)
    assert len(got) == len(ref) == 4
    for col in ["recent_avg_kpi", "baseline_avg_kpi", "kpi_degradation_ratio_%",
                "days_compared", "recent_days_count", "baseline_days_count"]:
        a = pd.to_numeric(got[col]).to_numpy(float)
        b = pd.to_numeric(ref[col]).to_numpy(float)
        assert np.allclose(a, b, equal_nan=True), f"{col} mismatch vs scalar reference"


# --------------------------------------------------------------------------- #
# BUG-09 — requirements.txt must list what the app actually imports, and must
# NOT pin xlrd (xlrd>=2.0 cannot read .xlsx).
# --------------------------------------------------------------------------- #
def test_bug09_requirements_complete_and_no_xlrd():
    path = os.path.join(os.path.dirname(__file__), "requirements.txt")
    text = open(path).read().lower()
    for pkg in ["streamlit", "plotly", "scikit-learn", "xgboost", "statsmodels"]:
        assert pkg in text, f"requirements.txt is missing {pkg}"
    # xlrd must not be a dependency (it can't open the .xlsx data).
    assert not re.search(r"(?m)^\s*xlrd\b", text), "xlrd must not be required"


# --------------------------------------------------------------------------- #
# BUG-10 — perform_ttest must not SILENTLY swallow unexpected errors.
# --------------------------------------------------------------------------- #
def test_bug10_unexpected_error_is_surfaced_not_swallowed():
    class Boom:
        def dropna(self):
            raise RuntimeError("unexpected internal failure")

    with pytest.warns(RuntimeWarning):
        is_sig, p, t = perform_ttest(Boom(), Boom())
    assert is_sig is False and np.isnan(p) and np.isnan(t)


# --------------------------------------------------------------------------- #
# Residual of BUG-04 — a near-zero (but > 0) baseline must not produce an
# explosive relative-% artifact (e.g. -8743%); it is winsorized.
# --------------------------------------------------------------------------- #
def test_residual_bug04_tiny_baseline_is_capped():
    # 0.84 GB recent vs 0.0096 GB baseline would be ~ -8650% uncapped.
    d = calculate_degradation(0.84, 0.0096, "low", is_ratio=False)
    assert abs(d) <= DEGRADATION_PCT_CAP, "tiny-baseline artifact must be capped"
    assert d == -DEGRADATION_PCT_CAP

    # Normal magnitudes are untouched.
    assert calculate_degradation(1.0, 5.0, "low", is_ratio=False) == 80.0
    # Ratio KPIs use a signed difference and are never capped here.
    assert calculate_degradation(98.0, 99.5, "low", is_ratio=True) == pytest.approx(1.5)


def test_baseline_imputation_is_used_by_main_analysis():
    kpi = "DL Traffic"
    tgt = target_col(kpi)
    site, cell, local = "S1", "C1", 0
    rows = []
    recent_dates = pd.date_range(ANCHOR - pd.Timedelta(days=6), ANCHOR, freq="D")
    baseline_dates = pd.date_range(ANCHOR - pd.Timedelta(days=13), ANCHOR - pd.Timedelta(days=7), freq="D")

    for d in recent_dates:
        rows.append({SITE_COL: site, CELL_COL: cell, LOCAL_CELL_COL: local, DATE_COL: d, tgt: 5.0})

    missing_baseline = {baseline_dates[1], baseline_dates[3]}
    for d in baseline_dates:
        if d not in missing_baseline:
            rows.append({SITE_COL: site, CELL_COL: cell, LOCAL_CELL_COL: local, DATE_COL: d, tgt: 10.0})

    for d in missing_baseline:
        for weeks_back in (1, 2):
            rows.append({
                SITE_COL: site, CELL_COL: cell, LOCAL_CELL_COL: local,
                DATE_COL: d - pd.Timedelta(days=7 * weeks_back), tgt: 10.0,
            })

    out, _ = analyze_selected_kpi(
        pd.DataFrame(rows), kpi, num_days=7, degradation_threshold=10.0,
        require_complete_days=True, baseline_mode="last_week",
        enable_significance_test=False,
    )
    assert out.shape[0] == 1
    row = out.iloc[0]
    assert row["kpi_degradation_ratio_%"] == pytest.approx(50.0)
    assert row["analysis_confidence"] in {"Medium", "High"}


def test_significance_is_advisory_not_hard_gate():
    kpi = "DL Traffic"
    df = build_frame(
        [{"site": "S1", "cell": "C1", "local": 0, "recent": [1.0], "baseline": [10.0]}],
        kpi,
        anchor=ANCHOR,
    )
    out, _ = analyze_selected_kpi(
        df, kpi, num_days=1, degradation_threshold=10.0,
        require_complete_days=True, baseline_mode="last_week",
        enable_significance_test=True,
    )
    assert out.shape[0] == 1
    row = out.iloc[0]
    assert row["kpi_degradation_ratio_%"] == pytest.approx(90.0)
    assert row["stat_significant"] is False or row["stat_significant"] == False
    assert "Advisory only" in row["significance_note"]


def test_rf_aware_cause_ranking_prioritizes_service_critical_cause():
    df = pd.DataFrame({
        "recent_L.Traffic.ActiveUser.Dl.Avg": [20.0],
        "baseline_L.Traffic.ActiveUser.Dl.Avg": [100.0],
        "recent_Availability": [97.0],
        "baseline_Availability": [99.0],
    })
    rules = [
        {
            "feature": "L.Traffic.ActiveUser.Dl.Avg",
            "bad_direction": "low",
            "threshold": 20,
            "severity": 1,
            "category": "Traffic Demand Drop",
            "reason": "DL active users decreased.",
            "recommended_action": "Validate demand.",
        },
        {
            "feature": "Availability",
            "bad_direction": "low",
            "threshold": 1,
            "severity": 5,
            "category": "Availability Issue",
            "reason": "Cell availability decreased.",
            "recommended_action": "Check alarms and site availability.",
        },
    ]
    result = find_degradation_causes_vectorized(df, rules)
    assert result.loc[0, "main_cause_counter_or_kpi"] == "Availability"
    assert result.loc[0, "rca_pattern"] == "Outage"
    assert "site availability" in result.loc[0, "next_investigation_steps"].lower()


def test_rca_pattern_classifies_throughput_congestion():
    df = pd.DataFrame({
        "selected_kpi_name": ["DL Throughput"],
        "recent_(HU) DL PRB Utilization(%)": [95.0],
        "baseline_(HU) DL PRB Utilization(%)": [55.0],
        "recent_L.Traffic.ActiveUser.Dl.Avg": [120.0],
        "baseline_L.Traffic.ActiveUser.Dl.Avg": [70.0],
    })
    rules = [
        {
            "feature": "(HU) DL PRB Utilization(%)",
            "bad_direction": "high",
            "threshold": 20,
            "severity": 3,
            "category": "DL Congestion",
            "reason": "DL PRB utilization increased while DL throughput decreased.",
            "recommended_action": "Check congestion and capacity.",
        },
        {
            "feature": "L.Traffic.ActiveUser.Dl.Avg",
            "bad_direction": "high",
            "threshold": 20,
            "severity": 2,
            "category": "High User Load",
            "reason": "Active DL users increased.",
            "recommended_action": "Validate demand and load.",
        },
    ]
    result = find_degradation_causes_vectorized(df, rules)
    assert result.loc[0, "rca_pattern"] == "Congestion"
    assert "PRB" in result.loc[0, "supporting_evidence"]
    assert "capacity" in result.loc[0, "next_investigation_steps"].lower()


def test_analyzer_output_includes_rca_columns():
    kpi = "DL Traffic"
    tgt = target_col(kpi)
    rel = "(HU) DL PRB Utilization(%)"
    rows = []
    recent_dates = pd.date_range(ANCHOR - pd.Timedelta(days=6), ANCHOR, freq="D")
    baseline_dates = pd.date_range(ANCHOR - pd.Timedelta(days=13), ANCHOR - pd.Timedelta(days=7), freq="D")
    for d in recent_dates:
        rows.append({
            SITE_COL: "S1", CELL_COL: "C1", LOCAL_CELL_COL: 0,
            DATE_COL: d, tgt: 4.0, rel: 90.0,
        })
    for d in baseline_dates:
        rows.append({
            SITE_COL: "S1", CELL_COL: "C1", LOCAL_CELL_COL: 0,
            DATE_COL: d, tgt: 10.0, rel: 50.0,
        })

    out, _ = analyze_selected_kpi(
        pd.DataFrame(rows), kpi, num_days=7, degradation_threshold=10.0,
        require_complete_days=True, baseline_mode="last_week",
        enable_significance_test=False,
    )
    assert out.shape[0] == 1
    for col in ["rca_pattern", "supporting_evidence", "next_investigation_steps"]:
        assert col in out.columns
    assert out.iloc[0]["rca_pattern"] == "Congestion"
