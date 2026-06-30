# ============================================================
# LTE KPI Degradation Analyzer - Clean Excel and Helper Functions
# ============================================================
# This file contains helper functions for data cleaning and processing.
# ============================================================

import warnings
import numpy as np
import pandas as pd
from scipy import stats


# ============================================================
# DATA CLEANING FUNCTIONS
# ============================================================

def clean_excel_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean Excel column names from spaces and hidden line breaks.
    
    Args:
        df: DataFrame with potentially dirty column names
        
    Returns:
        DataFrame with cleaned column names
    """
    df = df.copy()
    cleaned_columns = []
    for col in df.columns:
        col = str(col)
        col = col.replace(chr(10), " ")
        col = col.replace(chr(13), " ")
        col = col.strip()
        cleaned_columns.append(col)
    df.columns = cleaned_columns
    return df


def normalize_column_name(col) -> str:
    """
    Normalize column names for smart matching.
    Removes spaces, underscores, hyphens, and special characters.
    
    Args:
        col: Column name to normalize
        
    Returns:
        Normalized column name (lowercase, no special chars)
    """
    col = str(col).lower()
    col = col.replace(" ", "")
    col = col.replace("_", "")
    col = col.replace("-", "")
    col = col.replace(chr(10), "")
    col = col.replace(chr(13), "")
    col = col.strip()
    return col


def find_matching_column(df: pd.DataFrame, wanted_col: str):
    """
    Find real Excel column even if spaces/newlines are different.
    
    Uses a three-step matching process:
    1. Exact match
    2. Stripped match
    3. Normalized match (ignoring spaces, underscores, etc.)
    
    Args:
        df: DataFrame to search in
        wanted_col: Column name to find
        
    Returns:
        Actual column name from DataFrame, or None if not found
    """
    if wanted_col in df.columns:
        return wanted_col
    for col in df.columns:
        if str(col).strip() == str(wanted_col).strip():
            return col
    wanted_norm = normalize_column_name(wanted_col)
    for col in df.columns:
        if normalize_column_name(col) == wanted_norm:
            return col
    return None


def clean_numeric_series(series: pd.Series) -> pd.Series:
    """
    Convert mixed numeric/text column to numeric.
    
    Handles common Excel data issues:
    - Percentage signs
    - Commas in numbers
    - N/A, #DIV/0!, #N/A, NIL values
    - Whitespace
    
    Args:
        series: Series to clean
        
    Returns:
        Cleaned numeric Series
    """
    return pd.to_numeric(
        series.astype(str)
        .str.replace("%", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace("N/A", "", regex=False)
        .str.replace("#DIV/0!", "", regex=False)
        .str.replace("#N/A", "", regex=False)
        .str.replace("NIL", "", regex=False)
        .str.strip()
        .replace({"": np.nan, "nan": np.nan, "None": np.nan}),
        errors="coerce",
    )


# ============================================================
# CALCULATION FUNCTIONS
# ============================================================

def calculate_degradation(recent_value, baseline_value, bad_direction, is_ratio=False):
    """
    Calculate degradation percentage.

    Positive result means degradation (worse performance).

    For ratio KPIs (RRC SR %, Drop Rate %, HO SR %, etc.):
        - Values are already percentages (e.g., 99.5%)
        - Degradation = absolute difference in percentage points
        - (recent - base) or (base - recent) depending on bad_direction

    For non-ratio KPIs (Traffic, Throughput, etc.):
        - Degradation = ((baseline - recent) / baseline) * 100

    Args:
        recent_value: Current period value
        baseline_value: Baseline period value
        bad_direction: 'low' or 'high' - direction that indicates worse performance
        is_ratio: True for ratio KPIs (percentage values), False for volume/count KPIs

    Returns:
        Degradation percentage (positive = worse), or np.nan if cannot calculate
    """
    if pd.isna(recent_value) or pd.isna(baseline_value):
        return np.nan
    if bad_direction == "low":
        if is_ratio:
            return baseline_value - recent_value
        if baseline_value == 0:
            return np.nan
        return ((baseline_value - recent_value) / baseline_value) * 100
    if bad_direction == "high":
        if is_ratio:
            return recent_value - baseline_value
        if baseline_value == 0:
            return np.nan
        return ((recent_value - baseline_value) / baseline_value) * 100
    return np.nan


def perform_ttest(recent_values, baseline_values):
    """
    Perform Welch's t-test between recent and baseline periods.
    
    Uses Welch's t-test (unequal variance) to determine if the
    difference between periods is statistically significant.
    
    Handles edge cases:
    - Near-identical data (precision loss warning)
    - Zero variance data
    - Insufficient samples
    
    Args:
        recent_values: Series of values from recent period
        baseline_values: Series of values from baseline period
        
    Returns:
        Tuple of (is_significant, p_value, t_statistic)
        - is_significant: True if p < 0.05
        - p_value: Statistical p-value
        - t_statistic: T-test statistic
    """
    try:
        recent_clean = recent_values.dropna()
        baseline_clean = baseline_values.dropna()
        
        if len(recent_clean) < 2 or len(baseline_clean) < 2:
            return False, np.nan, np.nan
        
        # Check for near-zero variance (data nearly identical)
        # This prevents "Precision loss" warnings from scipy
        recent_std = recent_clean.std()
        baseline_std = baseline_clean.std()
        
        # If both have near-zero variance, data is nearly identical
        # No statistical test needed - there's no real difference
        if recent_std < 1e-10 and baseline_std < 1e-10:
            # Data is essentially constant in both periods
            # Check if means are different
            if abs(recent_clean.mean() - baseline_clean.mean()) < 1e-10:
                # Same constant value - no difference, not significant
                return False, 1.0, 0.0
            else:
                # Different constants in both periods -> a real, definite shift.
                # With zero variance in both groups the pooled standard error is
                # 0, so the t-statistic's limit is a *signed* infinity and the
                # p-value -> 0. scipy's ttest_ind returns NaN here (0/0), and the
                # old fallback propagated that NaN, which then poisoned every
                # downstream numeric comparison/format on t_statistic. Return the
                # mathematically correct signed infinity instead so the result is
                # usable: sign follows (recent - baseline). (BUG-06)
                mean_diff = recent_clean.mean() - baseline_clean.mean()
                t_stat = np.inf if mean_diff > 0 else -np.inf
                return True, 0.0, t_stat
        
        # Suppress precision loss warnings for near-identical data
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning,
                                   message=".*Precision loss.*")
            warnings.filterwarnings("ignore", category=RuntimeWarning,
                                   message=".*catastrophic cancellation.*")
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            t_stat, p_value = stats.ttest_ind(recent_clean, baseline_clean, equal_var=False)
        
        # Check for invalid results (nan or inf)
        if np.isnan(p_value) or np.isinf(p_value):
            return False, np.nan, np.nan
        
        # Significant if p < 0.05
        is_significant = p_value < 0.05
        return is_significant, p_value, t_stat
        
    except (ValueError, FloatingPointError, ZeroDivisionError):
        # Expected degenerate-input failures (e.g. everything NaN after dropna,
        # or pathological variance). These genuinely mean "no usable test".
        return False, np.nan, np.nan
    except Exception as exc:  # pragma: no cover - defensive
        # BUG-10: the old bare `except Exception: return ...` swallowed
        # EVERYTHING silently, so a real programming error (wrong dtype, bad
        # shape) was indistinguishable from a benign degenerate sample and
        # vanished without a trace. Surface anything unexpected via a warning
        # while still returning a safe, non-significant result so one odd cell
        # cannot abort an entire batch run.
        warnings.warn(
            f"perform_ttest: unexpected error treated as non-significant: {exc!r}",
            RuntimeWarning,
            stacklevel=2,
        )
        return False, np.nan, np.nan


def get_periods_enhanced(df, date_col, num_days, baseline_mode, 
                          custom_baseline_start=None, custom_baseline_end=None):
    """
    Get analysis periods with configurable baseline window.
    
    Supports three baseline modes:
    - BASELINE_MODE_LAST_WEEK: Same N days from last week
    - BASELINE_MODE_4WEEK_AVG: 4-week rolling average
    - BASELINE_MODE_CUSTOM: User-defined date range
    
    Args:
        df: DataFrame with date column
        date_col: Name of date column
        num_days: Number of days for recent period
        baseline_mode: Baseline calculation mode
        custom_baseline_start: Custom baseline start date (for CUSTOM mode)
        custom_baseline_end: Custom baseline end date (for CUSTOM mode)
        
    Returns:
        Tuple of (last_date, recent_start, recent_end, baseline_start, baseline_end)
    """
    from KPI_Configuration import (
        BASELINE_MODE_LAST_WEEK,
        BASELINE_MODE_4WEEK_AVG,
        BASELINE_MODE_CUSTOM,
    )
    
    # Normalize to date level for hourly data
    last_date = df[date_col].dt.normalize().max()
    recent_start = last_date - pd.Timedelta(days=num_days - 1)
    recent_end = last_date
    
    if baseline_mode == BASELINE_MODE_LAST_WEEK:
        baseline_start = recent_start - pd.Timedelta(days=7)
        baseline_end = recent_end - pd.Timedelta(days=7)
        
    elif baseline_mode == BASELINE_MODE_4WEEK_AVG:
        baseline_start = recent_start - pd.Timedelta(days=28)
        baseline_end = recent_start - pd.Timedelta(days=1)
        
    elif baseline_mode == BASELINE_MODE_CUSTOM:
        if custom_baseline_start and custom_baseline_end:
            baseline_start = pd.Timestamp(custom_baseline_start)
            baseline_end = pd.Timestamp(custom_baseline_end)
        else:
            baseline_start = recent_start - pd.Timedelta(days=7)
            baseline_end = recent_end - pd.Timedelta(days=7)
    else:
        baseline_start = recent_start - pd.Timedelta(days=7)
        baseline_end = recent_end - pd.Timedelta(days=7)
    
    return last_date, recent_start, recent_end, baseline_start, baseline_end
