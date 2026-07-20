"""Central configuration: column renames, KPI dropdown options, feature source columns."""

# Raw CSV column name -> internal short name
COLUMN_RENAME_MAP = {
    "(HU) Cell DL Average Throughput (Mbps)":         "DL_Throughput",
    "(HU) DL Traffic Volume (GBytes)":                "DL_Traffic",
    "(HU) Average UE Number":                         "Avg_UE_Number",
    "L.Traffic.ActiveUser.Avg":                       "Active_Users",
    "(TE) RRC Setup SR%":                             "RRC_Setup_SR",
    "E-RAB Drop Rate (E-NodeB + MME) %":              "ERAB_Drop_Rate",
    "Intra_Freq HO Success Rate in Execution Phase":  "Intra_HO_SR",
    "Inter_Freq HO Success Rate in Execution Phase":  "Inter_HO_SR",
    "DL Average CQI":                                 "DL_CQI",
    "(HU) DL IBLER(%)":                               "DL_IBLER",
    "(HU) DL PRB Utilization(%)":                     "DL_PRB_Util",
    "(HU) User DL Average Throughput (Mbps)":         "User_DL_Throughput",
}

# Columns that may arrive as strings (stray "%" signs, whitespace) and need
# numeric coercion after renaming.
NUMERIC_COERCE_COLS = [
    "RRC_Setup_SR", "ERAB_Drop_Rate", "Intra_HO_SR", "Inter_HO_SR",
    "DL_CQI", "DL_IBLER", "DL_PRB_Util", "User_DL_Throughput",
]

# Dropdown label -> internal column name
KPI_OPTIONS = {
    "DL Traffic Volume (GBytes)":        "DL_Traffic",
    "DL Average Throughput (Mbps)":      "DL_Throughput",
    "Average UE Number":                 "Avg_UE_Number",
    "Active Users":                      "Active_Users",
    "RRC Setup Success Rate (%)":        "RRC_Setup_SR",
    "E-RAB Drop Rate (%)":               "ERAB_Drop_Rate",
    "Intra-Freq HO Success Rate (%)":    "Intra_HO_SR",
    "Inter-Freq HO Success Rate (%)":    "Inter_HO_SR",
    "DL Average CQI":                    "DL_CQI",
    "DL IBLER (%)":                      "DL_IBLER",
    "DL PRB Utilization (%)":            "DL_PRB_Util",
    "User DL Avg Throughput (Mbps)":     "User_DL_Throughput",
}

# Internal column name -> human-readable display name (reverse of KPI_OPTIONS)
KPI_REVERSE_MAP = {v: k for k, v in KPI_OPTIONS.items()}

# All KPI columns that should be made available to build_features() as
# leakage-safe (lag-1) cross-KPI features when they are not the target.
REQUIRED_COLS = [
    "DL_Throughput", "DL_Traffic", "Avg_UE_Number", "Active_Users",
    "RRC_Setup_SR", "ERAB_Drop_Rate", "Intra_HO_SR", "Inter_HO_SR",
    "DL_CQI", "DL_IBLER", "DL_PRB_Util", "User_DL_Throughput",
]

# --- Threshold-based alerting defaults ---
# Format: {internal_name: (low_threshold, high_threshold, "direction")}
# direction: "higher_is_better" | "lower_is_better" | "neutral"
KPI_THRESHOLDS = {
    "DL_Throughput":        (None, None, "neutral"),
    "DL_Traffic":           (None, None, "neutral"),
    "Avg_UE_Number":        (None, None, "neutral"),
    "Active_Users":         (None, None, "neutral"),
    "RRC_Setup_SR":         (95.0, None, "higher_is_better"),   # < 95% is concerning
    "ERAB_Drop_Rate":       (None, 2.0, "lower_is_better"),     # > 2% is concerning
    "Intra_HO_SR":          (95.0, None, "higher_is_better"),
    "Inter_HO_SR":          (90.0, None, "higher_is_better"),
    "DL_CQI":               (8.0, None, "higher_is_better"),     # < 8 is poor
    "DL_IBLER":             (None, 10.0, "lower_is_better"),     # > 10% is concerning
    "DL_PRB_Util":          (None, 80.0, "neutral"),              # > 80% is congestion risk
    "User_DL_Throughput":   (None, None, "neutral"),
}
