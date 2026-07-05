"""Baseline Resolution Specification Tests (from design document)."""
import numpy as np
import pandas as pd
import pytest

from KPI_Configuration import (
    SITE_COL, CELL_COL, LOCAL_CELL_COL, DATE_COL, KPI_CONFIGS,
)
from main_function_for_selected_kpi import analyze_selected_kpi
from kpi_test_utils import target_col

ANCHOR = pd.Timestamp("2024-03-14")


def test_baseline_resolution_ratio_nan_baseline():
    """Ratio KPI with NaN baseline should apply fallback to history/min_baseline."""
    kpi = "Availability"
    tgt = target_col(kpi)
    
    rows = []
    hist_dates = pd.date_range(ANCHOR - pd.Timedelta(days=56), ANCHOR - pd.Timedelta(days=29), freq="D")
    for d in hist_dates:
        rows.append({SITE_COL: "S1", CELL_COL: "C1", LOCAL_CELL_COL: 0, DATE_COL: d, tgt: 99.5})
    
    recent_dates = pd.date_range(ANCHOR - pd.Timedelta(days=6), ANCHOR, freq="D")
    for d in recent_dates:
        rows.append({SITE_COL: "S1", CELL_COL: "C1", LOCAL_CELL_COL: 0, DATE_COL: d, tgt: 95.0})
    
    out, _ = analyze_selected_kpi(
        pd.DataFrame(rows), kpi, num_days=7, degradation_threshold=1.0,
        require_complete_days=False, baseline_mode="last_week",
        enable_significance_test=False,
    )
    assert out.shape[0] >= 1, "Ratio KPI with NaN baseline should use fallback"


def test_baseline_resolution_nonratio_zero_baseline_recent_positive():
    """Non-ratio KPI with baseline=0, recent>0 should stay Normal (not degraded)."""
    kpi = "DL Traffic"
    tgt = target_col(kpi)
    
    rows = []
    recent_dates = pd.date_range(ANCHOR - pd.Timedelta(days=6), ANCHOR, freq="D")
    for d in recent_dates:
        rows.append({SITE_COL: "S1", CELL_COL: "C1", LOCAL_CELL_COL: 0, DATE_COL: d, tgt: 5.0})
    
    baseline_dates = pd.date_range(ANCHOR - pd.Timedelta(days=13), ANCHOR - pd.Timedelta(days=7), freq="D")
    for d in baseline_dates:
        rows.append({SITE_COL: "S1", CELL_COL: "C1", LOCAL_CELL_COL: 0, DATE_COL: d, tgt: 0.0})
    
    out, _ = analyze_selected_kpi(
        pd.DataFrame(rows), kpi, num_days=7, degradation_threshold=10.0,
        require_complete_days=False, baseline_mode="last_week",
        enable_significance_test=False,
    )
    assert out.shape[0] == 0, "Non-ratio KPI with baseline=0, recent>0 should be Normal, not degraded"


def test_baseline_resolution_ratio_zero_baseline_recent_positive():
    """Ratio KPI with baseline=0, recent>0 should stay Normal (recovered cell)."""
    kpi = "RRC Setup SR"
    tgt = target_col(kpi)
    
    rows = []
    recent_dates = pd.date_range(ANCHOR - pd.Timedelta(days=6), ANCHOR, freq="D")
    for d in recent_dates:
        rows.append({SITE_COL: "S1", CELL_COL: "C1", LOCAL_CELL_COL: 0, DATE_COL: d, tgt: 98.0})
    
    baseline_dates = pd.date_range(ANCHOR - pd.Timedelta(days=13), ANCHOR - pd.Timedelta(days=7), freq="D")
    for d in baseline_dates:
        rows.append({SITE_COL: "S1", CELL_COL: "C1", LOCAL_CELL_COL: 0, DATE_COL: d, tgt: 0.0})
    
    out, _ = analyze_selected_kpi(
        pd.DataFrame(rows), kpi, num_days=7, degradation_threshold=5.0,
        require_complete_days=False, baseline_mode="last_week",
        enable_significance_test=False,
    )
    assert out.shape[0] == 0, "Ratio KPI with baseline=0, recent>0 should be Normal (recovered)"


def test_baseline_resolution_nonratio_zero_baseline_recent_zero():
    """Non-ratio KPI with baseline=0, recent=0 should apply fallback."""
    kpi = "DL Traffic"
    tgt = target_col(kpi)
    
    rows = []
    # Historical data for same weekdays as baseline period (days 7-13 before anchor)
    baseline_dates = pd.date_range(ANCHOR - pd.Timedelta(days=13), ANCHOR - pd.Timedelta(days=7), freq="D")
    for d in baseline_dates:
        # Add 5 weeks of historical data for each baseline date
        for week in range(1, 6):
            rows.append({SITE_COL: "S1", CELL_COL: "C1", LOCAL_CELL_COL: 0, 
                       DATE_COL: d - pd.Timedelta(days=7 * week), tgt: 10.0})
    
    # Recent and baseline periods both zeros (dead cell)
    recent_dates = pd.date_range(ANCHOR - pd.Timedelta(days=6), ANCHOR, freq="D")
    for d in recent_dates:
        rows.append({SITE_COL: "S1", CELL_COL: "C1", LOCAL_CELL_COL: 0, DATE_COL: d, tgt: 0.0})
    for d in baseline_dates:
        rows.append({SITE_COL: "S1", CELL_COL: "C1", LOCAL_CELL_COL: 0, DATE_COL: d, tgt: 0.0})
    
    out, _ = analyze_selected_kpi(
        pd.DataFrame(rows), kpi, num_days=7, degradation_threshold=10.0,
        require_complete_days=False, baseline_mode="last_week",
        enable_significance_test=False,
    )
    assert out.shape[0] >= 1, "Non-ratio KPI with zero+zero should apply fallback"


def test_baseline_resolution_ratio_both_zero_uses_historical_fallback():
    """Ratio KPI with baseline=0, recent=0 should apply historical fallback (if enabled)."""
    kpi = "HO Success Rate"
    tgt = target_col(kpi)
    
    rows = []
    baseline_dates = pd.date_range(ANCHOR - pd.Timedelta(days=13), ANCHOR - pd.Timedelta(days=7), freq="D")
    for d in baseline_dates:
        # Add 5 weeks of historical data for each baseline date
        for week in range(1, 6):
            rows.append({SITE_COL: "S1", CELL_COL: "C1", LOCAL_CELL_COL: 0, 
                       DATE_COL: d - pd.Timedelta(days=7 * week), tgt: 98.0})
    
    # Recent and baseline periods both zeros
    recent_dates = pd.date_range(ANCHOR - pd.Timedelta(days=6), ANCHOR, freq="D")
    for d in recent_dates:
        rows.append({SITE_COL: "S1", CELL_COL: "C1", LOCAL_CELL_COL: 0, DATE_COL: d, tgt: 0.0})
    for d in baseline_dates:
        rows.append({SITE_COL: "S1", CELL_COL: "C1", LOCAL_CELL_COL: 0, DATE_COL: d, tgt: 0.0})
    
    out, _ = analyze_selected_kpi(
        pd.DataFrame(rows), kpi, num_days=7, degradation_threshold=1.0,
        require_complete_days=False, baseline_mode="last_week",
        enable_significance_test=False,
    )
    assert out.shape[0] >= 1, "Ratio KPI with zero+zero should use historical fallback"


def test_baseline_resolution_valid_positive_baseline():
    """Both metric types with valid baseline (>0) should use it directly."""
    # Ratio KPI with valid baseline
    kpi_ratio = "RRC Setup SR"
    tgt_ratio = target_col(kpi_ratio)
    rows_ratio = []
    recent_dates = pd.date_range(ANCHOR - pd.Timedelta(days=6), ANCHOR, freq="D")
    for d in recent_dates:
        rows_ratio.append({SITE_COL: "S1", CELL_COL: "C1", LOCAL_CELL_COL: 0, DATE_COL: d, tgt_ratio: 95.0})
    baseline_dates = pd.date_range(ANCHOR - pd.Timedelta(days=13), ANCHOR - pd.Timedelta(days=7), freq="D")
    for d in baseline_dates:
        rows_ratio.append({SITE_COL: "S1", CELL_COL: "C1", LOCAL_CELL_COL: 0, DATE_COL: d, tgt_ratio: 99.0})
    
    out_ratio, _ = analyze_selected_kpi(
        pd.DataFrame(rows_ratio), kpi_ratio, num_days=7, degradation_threshold=2.0,
        require_complete_days=False, baseline_mode="last_week",
        enable_significance_test=False,
    )
    assert out_ratio.shape[0] == 1, "Ratio KPI with valid baseline should be analyzed"
    assert out_ratio.iloc[0]["baseline_avg_kpi"] == 99.0, "Should use original baseline value"
    assert out_ratio.iloc[0]["kpi_degradation_ratio_%"] == pytest.approx(4.0), "Degradation should be baseline - recent for ratio"
    
    # Non-ratio KPI with valid baseline - use high threshold so improvement doesn't trigger
    kpi_nonratio = "DL Traffic"
    tgt_nonratio = target_col(kpi_nonratio)
    rows_nonratio = []
    for d in recent_dates:
        rows_nonratio.append({SITE_COL: "S2", CELL_COL: "C2", LOCAL_CELL_COL: 0, DATE_COL: d, tgt_nonratio: 5.0})
    for d in baseline_dates:
        rows_nonratio.append({SITE_COL: "S2", CELL_COL: "C2", LOCAL_CELL_COL: 0, DATE_COL: d, tgt_nonratio: 10.0})
    
    out_nonratio, _ = analyze_selected_kpi(
        pd.DataFrame(rows_nonratio), kpi_nonratio, num_days=7, degradation_threshold=60.0,
        require_complete_days=False, baseline_mode="last_week",
        enable_significance_test=False,
    )
    # With threshold 60%, 50% improvement is Normal (not degraded)
    assert out_nonratio.shape[0] == 0, "Non-ratio KPI with recovery should be Normal (50% improvement below 60% threshold)"


def test_baseline_resolution_nonratio_nan_baseline():
    """Non-ratio KPI with NaN baseline should apply fallback to history/min_baseline."""
    kpi = "DL Traffic"
    tgt = target_col(kpi)
    
    rows = []
    # Historical data (5 weeks before baseline)
    hist_dates = pd.date_range(ANCHOR - pd.Timedelta(days=56), ANCHOR - pd.Timedelta(days=29), freq="D")
    for d in hist_dates:
        rows.append({SITE_COL: "S1", CELL_COL: "C1", LOCAL_CELL_COL: 0, DATE_COL: d, tgt: 10.0})
    
    # Recent period with traffic
    recent_dates = pd.date_range(ANCHOR - pd.Timedelta(days=6), ANCHOR, freq="D")
    for d in recent_dates:
        rows.append({SITE_COL: "S1", CELL_COL: "C1", LOCAL_CELL_COL: 0, DATE_COL: d, tgt: 5.0})
    
    out, _ = analyze_selected_kpi(
        pd.DataFrame(rows), kpi, num_days=7, degradation_threshold=30.0,
        require_complete_days=False, baseline_mode="last_week",
        enable_significance_test=False,
    )
    assert out.shape[0] >= 1, "Non-ratio KPI with NaN baseline should use fallback"


def test_baseline_resolution_drop_rate_both_zero_no_fallback():
    """E-RAB Drop Rate with baseline=0, recent=0 should NOT apply fallback."""
    kpi = "E-RAB Drop Rate"
    tgt = target_col(kpi)
    
    rows = []
    baseline_dates = pd.date_range(ANCHOR - pd.Timedelta(days=13), ANCHOR - pd.Timedelta(days=7), freq="D")
    for d in baseline_dates:
        rows.append({SITE_COL: "S1", CELL_COL: "C1", LOCAL_CELL_COL: 0, DATE_COL: d, tgt: 0.0})
    
    # Recent and baseline periods both zeros
    recent_dates = pd.date_range(ANCHOR - pd.Timedelta(days=6), ANCHOR, freq="D")
    for d in recent_dates:
        rows.append({SITE_COL: "S1", CELL_COL: "C1", LOCAL_CELL_COL: 0, DATE_COL: d, tgt: 0.0})
    
    out, meta = analyze_selected_kpi(
        pd.DataFrame(rows), kpi, num_days=7, degradation_threshold=0.5,
        require_complete_days=False, baseline_mode="last_week",
        enable_significance_test=False,
    )
    assert out.shape[0] == 0, "Drop rate with 0,0 should not be flagged as degraded (use_historical_fallback=False)"