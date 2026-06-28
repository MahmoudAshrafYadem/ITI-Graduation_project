# ============================================================
# LTE KPI Degradation Analyzer - Cause Detection Functions
# ============================================================
# This file contains functions for detecting root causes of KPI degradation.
# ============================================================

import numpy as np
import pandas as pd
import re

from KPI_Configuration import CELL_ID_COLS, SITE_COL, CELL_COL, DATE_COL
from clean_excel_and_helpers import (
    clean_excel_columns,
    clean_numeric_series,
    find_matching_column,
    calculate_degradation,
)

def _is_ratio_feature(feature_col):
    """Check if a feature column represents a ratio/percentage KPI.
    
    Percentage features are those with explicit % symbols or known percentage-based names.
    Counters (like HO Prepare Failed Times) use percentage change.
    """
    feature_lower = str(feature_col).lower()
    # Must have % symbol or be a known percentage success/counter rate
    pct_indicators = ["%", "availability", "setup success rate", "sr%", "contention-based sr",
                      "non-contention", "packet loss rate", "drop rate"]
    # Exclude counter features that aren't percentages
    non_pct_keywords = ["failed times", "failure time", "failure", "total", "times"]
    
    has_pct = any(ind in feature_lower for ind in pct_indicators)
    is_counter = any(kw in feature_lower for kw in non_pct_keywords)
    
    return has_pct and not is_counter


def find_degradation_causes_vectorized(df, rules):
    """
    Vectorized cause detection for performance optimization.
    
    Replaces row-by-row apply() with column-wise operations.
    Uses severity weighting for cause ranking.
    
    IMPORTANT: Reset index before calling this function to ensure proper alignment.
    
    Args:
        df: DataFrame with recent and baseline values for related features
        rules: List of detection rules with threshold, severity, etc.
        
    Returns:
        DataFrame with cause detection results for each row
    """
    # Reset index to ensure proper alignment
    df_work = df.reset_index(drop=True).copy()
    
    detected_causes_list = []
    
    for rule in rules:
        feature = rule["feature"]
        recent_col = f"recent_{feature}"
        baseline_col = f"baseline_{feature}"
        
        if recent_col not in df_work.columns or baseline_col not in df_work.columns:
            continue
        
        recent_values = df_work[recent_col].values
        baseline_values = df_work[baseline_col].values
        bad_direction = rule["bad_direction"]
        threshold = rule["threshold"]
        severity = rule.get("severity", 3)
        is_ratio = _is_ratio_feature(feature)
        
        # Vectorized calculation using numpy arrays
        with np.errstate(divide='ignore', invalid='ignore'):
            if is_ratio:
                # Ratio KPIs: absolute difference in percentage points
                if bad_direction == "low":
                    change_pct = np.where(
                        np.isfinite(recent_values) & np.isfinite(baseline_values),
                        baseline_values - recent_values,
                        np.nan
                    )
                else:  # high
                    change_pct = np.where(
                        np.isfinite(recent_values) & np.isfinite(baseline_values),
                        recent_values - baseline_values,
                        np.nan
                    )
            else:
                # Non-ratio KPIs: percentage change
                if bad_direction == "low":
                    change_pct = np.where(
                        baseline_values != 0,
                        ((baseline_values - recent_values) / baseline_values) * 100,
                        np.nan
                    )
                else:  # high
                    change_pct = np.where(
                        baseline_values != 0,
                        ((recent_values - baseline_values) / baseline_values) * 100,
                        np.nan
                    )
        
        # Create mask for cells passing threshold
        mask = change_pct >= threshold
        mask = mask & ~np.isnan(change_pct)
        
        if mask.any():
            score = change_pct * severity
            positions = np.where(mask)[0]
            
            for pos in positions:
                detected_causes_list.append({
                    "row_pos": pos,
                    "feature": feature,
                    "recent_value": recent_values[pos],
                    "baseline_value": baseline_values[pos],
                    "change_pct": change_pct[pos],
                    "severity": severity,
                    "score": score[pos],
                    "category": rule["category"],
                    "reason": rule["reason"],
                    "recommended_action": rule["recommended_action"],
                })
    
    # Default result columns
    default_cols = {
        "main_cause_counter_or_kpi": "No strong related counter detected",
        "main_cause_recent_value": np.nan,
        "main_cause_baseline_value": np.nan,
        "main_cause_change_%": np.nan,
        "main_root_cause_category": "Unknown",
        "main_degradation_reason": "Main KPI degraded, but no related counter passed its threshold.",
        "main_recommended_action": "Check raw counters, alarms, availability, recent changes, and nearby cells manually.",
        "number_of_detected_causes": 0,
        "multi_cause_flag": "No",
        "all_detected_causes": "None",
        "all_cause_categories": "Unknown",
        "all_recommended_actions": "Manual investigation needed",
    }
    
    # If no causes detected, return defaults for all rows
    if not detected_causes_list:
        result_df = pd.DataFrame(default_cols, index=range(len(df_work)))
        return result_df
    
    # Convert to DataFrame
    causes_df = pd.DataFrame(detected_causes_list)
    
    # Sort by score (severity-weighted) for each cell
    causes_df = causes_df.sort_values(["row_pos", "score"], ascending=[True, False])
    
    # Aggregate causes per cell using row position
    result_dict = {}
    
    for row_pos in range(len(df_work)):
        cell_causes = causes_df[causes_df["row_pos"] == row_pos].sort_values("score", ascending=False)
        
        if len(cell_causes) == 0:
            result_dict[row_pos] = default_cols.copy()
        else:
            main_cause = cell_causes.iloc[0]
            
            all_causes_text = " | ".join([
                f"{row['feature']}: recent={row['recent_value']:.2f}, baseline={row['baseline_value']:.2f}, change={row['change_pct']:.2f}%"
                for _, row in cell_causes.head(5).iterrows()
            ])
            all_categories_text = " | ".join(cell_causes["category"].head(5).tolist())
            all_actions_text = " | ".join(cell_causes["recommended_action"].head(5).tolist())
            
            result_dict[row_pos] = {
                "main_cause_counter_or_kpi": main_cause["feature"],
                "main_cause_recent_value": main_cause["recent_value"],
                "main_cause_baseline_value": main_cause["baseline_value"],
                "main_cause_change_%": main_cause["change_pct"],
                "main_root_cause_category": main_cause["category"],
                "main_degradation_reason": main_cause["reason"],
                "main_recommended_action": main_cause["recommended_action"],
                "number_of_detected_causes": len(cell_causes),
                "multi_cause_flag": "Yes" if len(cell_causes) > 1 else "No",
                "all_detected_causes": all_causes_text,
                "all_cause_categories": all_categories_text,
                "all_recommended_actions": all_actions_text,
            }
    
    result_df = pd.DataFrame.from_dict(result_dict, orient='index')
    
    return result_df


def find_degradation_causes_row(row, rules):
    """
    Row-by-row cause detection (fallback method).
    
    Used when vectorized detection fails.
    
    Args:
        row: DataFrame row with recent and baseline values
        rules: List of detection rules
        
    Returns:
        Series with cause detection results
    """
    detected_causes = []
    
    for rule in rules:
        feature = rule["feature"]
        recent_col = f"recent_{feature}"
        baseline_col = f"baseline_{feature}"
        
        if recent_col not in row.index or baseline_col not in row.index:
            continue
        
        recent_value = row[recent_col]
        baseline_value = row[baseline_col]
        
        change_pct = calculate_degradation(
            recent_value,
            baseline_value,
            rule["bad_direction"],
            is_ratio=_is_ratio_feature(feature),
        )
        
        if pd.isna(change_pct):
            continue
        
        if change_pct >= rule["threshold"]:
            severity = rule.get("severity", 3)
            detected_causes.append({
                "feature": feature,
                "recent_value": recent_value,
                "baseline_value": baseline_value,
                "change_pct": change_pct,
                "severity": severity,
                "score": change_pct * severity,
                "category": rule["category"],
                "reason": rule["reason"],
                "recommended_action": rule["recommended_action"],
            })
    
    if not detected_causes:
        return pd.Series({
            "main_cause_counter_or_kpi": "No strong related counter detected",
            "main_cause_recent_value": np.nan,
            "main_cause_baseline_value": np.nan,
            "main_cause_change_%": np.nan,
            "main_root_cause_category": "Unknown",
            "main_degradation_reason": "Main KPI degraded, but no related counter passed its threshold.",
            "main_recommended_action": "Check raw counters, alarms, availability, recent changes, and nearby cells manually.",
            "number_of_detected_causes": 0,
            "multi_cause_flag": "No",
            "all_detected_causes": "None",
            "all_cause_categories": "Unknown",
            "all_recommended_actions": "Manual investigation needed",
        })
    
    # Sort by severity-weighted score
    detected_causes = sorted(detected_causes, key=lambda x: x["score"], reverse=True)
    main_cause = detected_causes[0]
    
    all_causes_text = " | ".join([
        f"{c['feature']}: recent={c['recent_value']:.2f}, baseline={c['baseline_value']:.2f}, change={c['change_pct']:.2f}%"
        for c in detected_causes[:5]
    ])
    all_categories_text = " | ".join([c["category"] for c in detected_causes[:5]])
    all_actions_text = " | ".join([c["recommended_action"] for c in detected_causes[:5]])
    
    return pd.Series({
        "main_cause_counter_or_kpi": main_cause["feature"],
        "main_cause_recent_value": main_cause["recent_value"],
        "main_cause_baseline_value": main_cause["baseline_value"],
        "main_cause_change_%": main_cause["change_pct"],
        "main_root_cause_category": main_cause["category"],
        "main_degradation_reason": main_cause["reason"],
        "main_recommended_action": main_cause["recommended_action"],
        "number_of_detected_causes": len(detected_causes),
        "multi_cause_flag": "Yes" if len(detected_causes) > 1 else "No",
        "all_detected_causes": all_causes_text,
        "all_cause_categories": all_categories_text,
        "all_recommended_actions": all_actions_text,
    })
