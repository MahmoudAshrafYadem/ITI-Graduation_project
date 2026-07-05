# ============================================================
# LTE KPI Degradation Analyzer - Cause Detection Functions
# ============================================================
# This file contains functions for detecting root causes of KPI degradation.
# ============================================================

import numpy as np
import pandas as pd
from KPI_Configuration import CELL_ID_COLS, SITE_COL, CELL_COL, DATE_COL, classify_unit
from clean_excel_and_helpers import (
    clean_excel_columns,
    clean_numeric_series,
    find_matching_column,
    calculate_degradation,
)

def detect_cell_outage(row, dl_traffic_col, ul_traffic_col):
    """
    Classifies cell health based on traffic counters for a single cell (row).
    """
    recent_dl_col = f"recent_{dl_traffic_col}"
    recent_ul_col = f"recent_{ul_traffic_col}"

    if recent_dl_col not in row.index or recent_ul_col not in row.index:
        return {"cell_health": "UNKNOWN", "confidence": "LOW", "reason": "Traffic counters not available."}

    dl_traffic = row[recent_dl_col]
    ul_traffic = row[recent_ul_col]

    if pd.notna(dl_traffic) and pd.notna(ul_traffic) and dl_traffic == 0 and ul_traffic == 0:
        # Also check availability if present
        availability = row.get('recent_avg_kpi', -1)
        if 'availability' in str(row.get('selected_kpi_name', '')).lower() and availability == 0:
            confidence = "VERY HIGH"
        else:
            confidence = "HIGH"
        
        return {
            "cell_health": "DEAD",
            "confidence": confidence,
            "reason": "Cell has zero DL and UL traffic during the recent period."
        }
    
    return {"cell_health": "ALIVE", "confidence": "HIGH", "reason": "Cell is carrying traffic."}


def generate_outage_rca(dead_cell_row, dl_traffic_col, ul_traffic_col):
    """
    Generates the specific RCA output for a cell classified as DEAD.
    """
    evidence = [
        "DL Traffic = 0",
        "UL Traffic = 0",
    ]
    if 'recent_avg_kpi' in dead_cell_row and 'availability' in str(dead_cell_row.get('selected_kpi_name', '')).lower():
        evidence.append(f"Availability = {dead_cell_row['recent_avg_kpi']:.2f}%")

    evidence.append("No service observed during recent period.")
    
    baseline_traffic_col = f"baseline_{dl_traffic_col}"
    baseline_traffic = dead_cell_row.get(baseline_traffic_col, np.nan)

    return pd.Series({
        "main_cause_counter_or_kpi": "Cell Outage",
        "main_cause_recent_value": 0,
        "main_cause_baseline_value": baseline_traffic,
        "main_cause_change_%": 100.0,
        "main_root_cause_category": "Cell Outage",
        "main_degradation_reason": "Cell has zero DL and UL traffic during the recent period. Degradation is consistent with a complete service outage. Related counters remain at zero because the cell is not carrying traffic.",
        "main_recommended_action": "Check: Site power, Transmission, Transport connectivity, Node alarms, Cell lock state, Backhaul.",
        "number_of_detected_causes": 1,
        "multi_cause_flag": "No",
        "all_detected_causes": "Cell Outage (zero traffic)",
        "all_cause_categories": "Cell Outage",
        "all_recommended_actions": "Check: Site power, Transmission, Transport connectivity, Node alarms, Cell lock state, Backhaul.",
        "rca_pattern": "Outage",
        "supporting_evidence": " | ".join(evidence),
        "next_investigation_steps": RCA_INVESTIGATION_STEPS["Outage"],
    })


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


def _rf_priority_bonus(category, feature):
    """RF-aware priority bonus used for ranking competing detected causes."""
    text = f"{category} {feature}".lower()
    critical_terms = [
        "availability", "unavailable", "outage", "interference", "packet loss",
        "qci-1", "drop", "failure", "fail", "rach", "access", "s1",
    ]
    medium_terms = [
        "congestion", "prb", "bler", "cqi", "mcs", "coverage", "cell edge",
        "handover", "mobility", "srvcc",
    ]
    demand_terms = ["active user", "traffic demand", "user drop", "traffic drop"]
    if any(term in text for term in critical_terms):
        return 80.0
    if any(term in text for term in medium_terms):
        return 40.0
    if any(term in text for term in demand_terms):
        return -20.0
    return 0.0


def _cause_score(change_value, threshold, severity, category, feature):
    """Rank causes by severity, RF criticality, and threshold excess.

    The old score (change * severity) tended to over-rank huge low-value
    demand swings. This keeps the magnitude signal, but caps it and gives
    direct RF/service-impact causes a stronger voice in the ranking.
    """
    if pd.isna(change_value):
        return np.nan
    threshold = max(float(threshold), 1e-9)
    threshold_excess = max(0.0, (float(change_value) - threshold) / threshold)
    magnitude_points = min(float(change_value), 100.0) * 0.2
    return (
        float(severity) * 35.0
        + _rf_priority_bonus(category, feature)
        + min(threshold_excess, 5.0) * 15.0
        + magnitude_points
    )


RCA_INVESTIGATION_STEPS = {
    "Outage": (
        "Check cell/site availability, active alarms, administrative state, "
        "power, transmission, S1, and planned work before RF tuning."
    ),
    "Congestion": (
        "Check PRB/CCE utilization, active users, admission/resource failures, "
        "load balancing, CA, scheduler settings, and capacity expansion options."
    ),
    "Radio Quality": (
        "Check CQI/SINR/BLER/MCS, interference indicators, PCI issues, antenna "
        "azimuth/tilt, coverage dominance, and recent physical changes."
    ),
    "Coverage": (
        "Check TA distribution, cell-edge users, overshooting, weak coverage, "
        "antenna tilt/azimuth, neighbor dominance, and coverage holes."
    ),
    "Interference": (
        "Check UL/DL interference trend, noise rise, PIM/external sources, "
        "neighbor leakage, TDD guard configuration, and affected neighboring cells."
    ),
    "Mobility": (
        "Check neighbor definitions, HO preparation/execution counters, RACH on "
        "target cells, PCI confusion, reselection/HO parameters, and target availability."
    ),
    "Demand": (
        "Validate user/traffic demand trend, seasonality, holidays/events, traffic "
        "migration to neighbors, and commercial/service changes before RF action."
    ),
    "Unknown": (
        "Review raw counters, alarms, recent parameter changes, neighbor cells, "
        "and OSS logs manually; current evidence is not strong enough for a pattern."
    ),
}


def _contains(text, terms):
    return any(term in text for term in terms)


def _patterns_from_text(text):
    patterns = []
    if _contains(text, ["availability", "unavail", "outage", "s1 failure", "manual lock"]):
        patterns.append("Outage")
    if _contains(text, ["interference", "noise rise", "pim", "uppts"]):
        patterns.append("Interference")
    if _contains(text, ["congestion", "prb", "cce", "capacity", "no radio resource", "resource failure", "admission"]):
        patterns.append("Congestion")
    if _contains(text, ["ta ", "cell edge", "border ue", "coverage", "overshooting", "poor cover", "distance"]):
        patterns.append("Coverage")
    if _contains(text, ["cqi", "bler", "mcs", "sinr", "rsrp", "rsrq", "modulation", "radio quality"]):
        patterns.append("Radio Quality")
    if _contains(text, ["handover", " ho ", "srvcc", "reestablish", "neighbor", "mobility", "rach on target"]):
        patterns.append("Mobility")
    if _contains(text, ["active user", "traffic demand", "user drop", "traffic drop", "attempts decreased"]):
        patterns.append("Demand")
    return patterns


def _choose_kpi_pattern(kpi_name, patterns):
    """Choose final RCA pattern using KPI-specific RF triage order."""
    kpi = str(kpi_name).lower()
    if not patterns:
        return "Unknown"

    if "availability" in kpi:
        order = ["Outage", "Congestion", "Interference", "Coverage", "Radio Quality", "Mobility", "Demand"]
    elif "throughput" in kpi or "traffic" in kpi:
        order = ["Outage", "Interference", "Congestion", "Coverage", "Radio Quality", "Mobility", "Demand"]
    elif "rrc" in kpi or "erab" in kpi or "rach" in kpi:
        order = ["Outage", "Congestion", "Interference", "Coverage", "Radio Quality", "Mobility", "Demand"]
    elif "drop" in kpi or "re-establishment" in kpi or "reestablishment" in kpi:
        order = ["Outage", "Interference", "Coverage", "Radio Quality", "Mobility", "Congestion", "Demand"]
    elif "ho " in f" {kpi} " or "handover" in kpi:
        order = ["Outage", "Mobility", "Coverage", "Interference", "Radio Quality", "Congestion", "Demand"]
    else:
        order = ["Outage", "Interference", "Congestion", "Coverage", "Radio Quality", "Mobility", "Demand"]

    for pattern in order:
        if pattern in patterns:
            return pattern
    return patterns[0]


def _classify_rca_pattern(kpi_name, cell_causes):
    """Convert detected rule evidence into a real-world RF RCA pattern."""
    if cell_causes is None or len(cell_causes) == 0:
        return {
            "rca_pattern": "Unknown",
            "supporting_evidence": "No related counter passed its RCA threshold.",
            "next_investigation_steps": RCA_INVESTIGATION_STEPS["Unknown"],
        }

    text_parts = []
    evidence_parts = []
    for _, row in cell_causes.head(5).iterrows():
        feature = str(row["feature"])
        category = str(row["category"])
        text_parts.append(f"{feature} {category} {row.get('reason', '')}".lower())
        evidence_parts.append(
            f"{category}: {feature} changed by {row['change_pct']:.2f}"
        )

    patterns = _patterns_from_text(" ".join(text_parts))
    pattern = _choose_kpi_pattern(kpi_name, patterns)
    return {
        "rca_pattern": pattern,
        "supporting_evidence": " | ".join(evidence_parts) if evidence_parts else "No strong evidence.",
        "next_investigation_steps": RCA_INVESTIGATION_STEPS.get(pattern, RCA_INVESTIGATION_STEPS["Unknown"]),
    }


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
        unit = classify_unit(feature)
        is_ratio = _is_ratio_feature(feature)
        use_signed_diff = (unit in ('dbm', 'db')) or is_ratio
        
        # Vectorized calculation using numpy arrays
        with np.errstate(divide='ignore', invalid='ignore'):
            if use_signed_diff:
                # Signed difference — for dB/dBm and ratio/percentage features
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
                # Non-ratio non-db: relative % change
                if bad_direction == "low":
                    change_pct = np.where(
                        baseline_values != 0,
                        ((baseline_values - recent_values) / baseline_values) * 100,
                        0.0
                    )
                else:  # high
                    change_pct = np.where(
                        baseline_values != 0,
                        ((recent_values - baseline_values) / baseline_values) * 100,
                        0.0
                    )
        
        # Create mask for cells passing threshold
        mask = change_pct >= threshold
        mask = mask & ~np.isnan(change_pct)
        
        if mask.any():
            score = np.array([
                _cause_score(change_pct[pos], threshold, severity, rule["category"], feature)
                for pos in range(len(change_pct))
            ])
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
        "rca_pattern": "Unknown",
        "supporting_evidence": "No related counter passed its RCA threshold.",
        "next_investigation_steps": RCA_INVESTIGATION_STEPS["Unknown"],
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
            kpi_name = df_work.loc[row_pos, "selected_kpi_name"] if "selected_kpi_name" in df_work.columns else ""
            rca = _classify_rca_pattern(kpi_name, cell_causes)
            
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
                **rca,
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
            is_ratio=(classify_unit(feature) in ('dbm', 'db')) or _is_ratio_feature(feature),
        )
        
        if pd.isna(change_pct):
            continue
        
        if change_pct >= rule["threshold"]:
            severity = rule.get("severity", 3)
            score = _cause_score(
                change_pct, rule["threshold"], severity, rule["category"], feature
            )
            detected_causes.append({
                "feature": feature,
                "recent_value": recent_value,
                "baseline_value": baseline_value,
                "change_pct": change_pct,
                "severity": severity,
                "score": score,
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
            "rca_pattern": "Unknown",
            "supporting_evidence": "No related counter passed its RCA threshold.",
            "next_investigation_steps": RCA_INVESTIGATION_STEPS["Unknown"],
        })
    
    # Sort by severity-weighted score
    detected_causes = sorted(detected_causes, key=lambda x: x["score"], reverse=True)
    main_cause = detected_causes[0]
    rca = _classify_rca_pattern(row.get("selected_kpi_name", ""), pd.DataFrame(detected_causes))
    
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
        **rca,
    })
