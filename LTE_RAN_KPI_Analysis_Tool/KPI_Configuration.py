# ============================================================
# LTE KPI Degradation Analyzer - KPI Configuration
# ============================================================
# This file contains all KPI definitions, thresholds, and rules.
# Edit this file to add new KPIs or modify existing thresholds.
# Last Updated: RF-Optimized thresholds, enhanced interference handling
# ============================================================

import re
import logging

# Configure logging for this module
logger = logging.getLogger(__name__)


# ============================================================
# GLOBAL COLUMN NAMES
# ============================================================

DATE_COL = "Date"
SITE_COL = "eNodeB Name"
CELL_COL = "Cell Name"
LOCAL_CELL_COL = "LocalCell Id"

CELL_ID_COLS = [
    SITE_COL,
    CELL_COL,
    LOCAL_CELL_COL,
]

# Baseline window modes
BASELINE_MODE_LAST_WEEK = "last_week"
BASELINE_MODE_4WEEK_AVG = "4week_rolling_avg"
BASELINE_MODE_CUSTOM = "custom_range"

# ============================================================
# NEGATIVE VALUE POLICY (unit-aware)
# ============================================================
# Negatives are valid only for signal/power metrics (dBm/dB: RSRP, RSRQ,
# SINR, interference). For counters/volumes/%/throughput a negative is a
# data glitch and should be filtered. Decision is by column name, so it is
# correct whether a column is a target or a related feature.

_LAST_PAREN_RE = re.compile(r"\(([^()]+)\)[^()]*$")

# Exact-name overrides for cases the heuristic gets wrong. column -> bool.
NEGATIVE_VALUE_OVERRIDES = {
    # "Some Signed Counter": True,
}


def classify_unit(column_name: str) -> str:
    """Classify a column by physical unit: 'dbm' | 'db' | 'pct' | 'nonneg'.

    Used by both the negative-value filter and the data-quality validator.
    """
    if not isinstance(column_name, str):
        logger.warning(f"Non-string column name: {column_name}, defaulting to 'nonneg'")
        return "nonneg"
    low = column_name.lower()
    if "rsrq" in low or "sinr" in low:
        return "db"
    if "rsrp" in low or "rssi" in low or "interference" in low:
        return "dbm"
    m = _LAST_PAREN_RE.search(column_name)
    if m:
        tok = m.group(1).strip().lower()
        if tok == "dbm":
            return "dbm"
        if tok == "db":
            return "db"
        if tok == "%":
            return "pct"
    if "%" in column_name:
        return "pct"
    return "nonneg"


def allows_negative(column_name: str) -> bool:
    """True if negative values are physically valid for this column."""
    if isinstance(column_name, str) and column_name in NEGATIVE_VALUE_OVERRIDES:
        return NEGATIVE_VALUE_OVERRIDES[column_name]
    return classify_unit(column_name) in ("dbm", "db")


# ============================================================
# DATA QUALITY POLICY
# ============================================================
# Vendor "no data / not measured" markers. Kept to UNAMBIGUOUS large markers
# only, so we never null a real value (e.g. -1 could be a real SINR in dB).
# Add others (e.g. 9999) ONLY after confirming them in your OSS export.
SENTINEL_VALUES = (4294967295, 4294967294)

# Missing-day imputation (baseline window only). See data_quality.py.
IMPUTATION_CONFIG = {
    "enable_imputation": True,   # master switch
    "lookback_weeks": 4,         # how many prior same-weekday samples to consider
    "min_impute_samples": 2,     # need at least this many to impute a day
}


# ============================================================
# KPI CONFIGURATION VALIDATION
# ============================================================

REQUIRED_KPI_FIELDS = [
    "target_kpi", "bad_direction", "default_threshold",
    "category", "output_prefix", "min_baseline_value", "related_rules"
]

REQUIRED_RULE_FIELDS = [
    "feature", "bad_direction", "threshold", "severity",
    "category", "reason", "recommended_action"
]


def validate_kpi_configs():
    """Validate all KPI configurations at startup.

    Returns:
        bool: True if valid, raises ValueError if errors found.
    """
    errors = []

    for kpi_name, config in KPI_CONFIGS.items():
        # Check required KPI fields
        for field in REQUIRED_KPI_FIELDS:
            if field not in config:
                errors.append(f"KPI '{kpi_name}' missing required field: {field}")

        # Validate min_baseline_value
        min_val = config.get("min_baseline_value")
        if min_val is None:
            errors.append(f"KPI '{kpi_name}' missing min_baseline_value")
        elif not isinstance(min_val, (int, float)):
            errors.append(f"KPI '{kpi_name}' min_baseline_value must be numeric")

        # Validate bad_direction
        if config.get("bad_direction") not in ("low", "high"):
            errors.append(f"KPI '{kpi_name}' bad_direction must be 'low' or 'high'")

        # Validate related_rules
        for idx, rule in enumerate(config.get("related_rules", [])):
            for field in REQUIRED_RULE_FIELDS:
                if field not in rule:
                    errors.append(f"KPI '{kpi_name}' rule[{idx}] missing: {field}")

            # Validate severity range
            severity = rule.get("severity")
            if severity is not None and not (1 <= severity <= 5):
                errors.append(f"KPI '{kpi_name}' rule[{idx}] severity should be 1-5")

    if errors:
        error_msg = "KPI Configuration Errors:\n" + "\n".join(errors)
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.info(f"KPI Configuration validated: {len(KPI_CONFIGS)} KPIs, all valid")
    return True


# ============================================================
# KPI CONFIGURATION
# ============================================================
# Each KPI has:
# - target_kpi: The main KPI column name to analyze
# - bad_direction: "low" or "high" - direction indicating degradation
# - default_threshold: Default degradation threshold percentage
# - category: KPI category (Traffic, Integrity, Accessibility, etc.)
# - output_prefix: Prefix for output file names
# - min_baseline_value: FALLBACK value when baseline is zero/NaN and no
#   historical data available (same weekday from 5 weeks ago).
#   NOTE: This is NO LONGER an exclusion threshold! All cells are now
#   included in analysis. This value is only used as a last resort when:
#   1. baseline_avg_kpi = 0 or NaN, AND
#   2. No historical data from 5 weeks ago available
#   Recommended: Set to a "typical healthy" value for the KPI.
# - related_rules: List of related counters for root cause detection
# ============================================================

KPI_CONFIGS = {
    "DL Traffic": {
        "target_kpi": "(HU) DL Traffic Volume (GBytes)",
        "bad_direction": "low",
        "default_threshold": 30.0,
        "category": "Traffic",
        "output_prefix": "dl_traffic",
        "min_baseline_value": 1.0,
        "related_rules": [
            # === Original Throughput & Capacity Rules ===
            {"feature": "(HU) Cell DL Average Throughput (Mbps)", "bad_direction": "low", "threshold": 20, "severity": 3, "category": "DL Throughput Degradation", "reason": "Cell DL throughput decreased.", "recommended_action": "Check DL scheduler, bandwidth, CA activation, load balancing, and congestion."},
            {"feature": "(HU) User DL Average Throughput (Mbps)", "bad_direction": "low", "threshold": 20, "severity": 3, "category": "User Throughput Degradation", "reason": "User DL throughput decreased.", "recommended_action": "Check radio quality, PRB load, scheduler behavior, and user distribution."},
            {"feature": "(HU) DL PRB Utilization(%)", "bad_direction": "high", "threshold": 20, "severity": 2, "category": "Capacity / Congestion", "reason": "DL PRB utilization increased.", "recommended_action": "Check load balancing, CA usage, bandwidth, traffic distribution, and capacity expansion."},
            {"feature": "DL Average CQI", "bad_direction": "low", "threshold": 15, "severity": 3, "category": "Radio Quality Issue", "reason": "DL CQI decreased.", "recommended_action": "Check interference, PCI conflict/confusion, antenna tilt, azimuth, and coverage."},
            {"feature": "(HU) DL IBLER(%)", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "DL Radio Quality Issue", "reason": "DL IBLER increased.", "recommended_action": "Check interference, CQI, MCS, antenna tilt, and DL power."},
            {"feature": "DL RBLER", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "DL Radio Failure", "reason": "DL RBLER increased.", "recommended_action": "Check DL interference, poor coverage, CQI, MCS, and radio conditions."},
            {"feature": "(HU) PDSCH MCS", "bad_direction": "low", "threshold": 15, "severity": 2, "category": "Poor Modulation Efficiency", "reason": "PDSCH MCS decreased.", "recommended_action": "Check CQI, SINR, interference, antenna direction, and coverage."},
            {"feature": "Availability", "bad_direction": "low", "threshold": 1, "severity": 5, "category": "Availability Issue", "reason": "Cell availability decreased.", "recommended_action": "Check alarms, S1 issue, manual outage, system outage, and site availability."},
            {"feature": "(HU) Cell Unavail Time (s)", "bad_direction": "high", "threshold": 20, "severity": 5, "category": "Cell Unavailability", "reason": "Cell unavailable time increased.", "recommended_action": "Check site outage, power issue, transmission issue, S1 failure, and alarms."},
            {"feature": "L.Traffic.ActiveUser.Dl.Avg", "bad_direction": "low", "threshold": 20, "severity": 1, "category": "Traffic Demand Drop", "reason": "DL active users decreased.", "recommended_action": "Validate if traffic drop is normal demand behavior before RF optimization."},
            {"feature": "MAC CA Traffic Ratio", "bad_direction": "low", "threshold": 20, "severity": 2, "category": "Carrier Aggregation Issue", "reason": "CA traffic ratio decreased.", "recommended_action": "Check CA activation, SCell availability, CA bands, and CA parameters."},
            {"feature": "DL Traffic QCI-9", "bad_direction": "low", "threshold": 20, "severity": 2, "category": "Default Bearer Traffic Drop", "reason": "QCI-9 DL traffic decreased.", "recommended_action": "Check packet data service, APN/data service, user demand, and internet traffic trend."},
            {"feature": "DL_CCE_AllocFail (%)", "bad_direction": "high", "threshold": 10, "severity": 4, "category": "Control Channel Congestion", "reason": "DL CCE allocation failure increased - directly blocks scheduling.", "recommended_action": "Check PDCCH/CCE utilization, control channel capacity, CCE aggregation level, and scheduler configuration. CCE failure >10% is critical."},

            # === NEW: TA Distribution (Coverage Analysis) ===
            {"feature": "6.6-14 km", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "Extended Coverage Issue", "reason": "High TA bin indicates users at cell edge or beyond planned coverage.", "recommended_action": "Check coverage extension, overshooting, pilot pollution, and cell size."},
            {"feature": "3.5-6.6 km", "bad_direction": "high", "threshold": 20, "severity": 2, "category": "Cell Edge Users Increase", "reason": "Users at cell edge increased.", "recommended_action": "Check coverage, cell dominance, and neighbor relationships."},
            {"feature": "TA Weighted Avg (meter)", "bad_direction": "high", "threshold": 20, "severity": 2, "category": "Average Distance Increase", "reason": "Average user distance from site increased.", "recommended_action": "Check coverage shift, antenna tilt, and traffic migration."},

            # === NEW: CEU (Cell Edge User) Metrics ===
            {"feature": "(HU)CEU Cell Downlink Average Throughput", "bad_direction": "low", "threshold": 20, "severity": 3, "category": "Cell Edge Throughput", "reason": "Cell edge user throughput degraded.", "recommended_action": "Check CEU scheduling, cell edge SINR, and coverage."},
            {"feature": "(HU)CEU User Downlink Average Througput", "bad_direction": "low", "threshold": 20, "severity": 3, "category": "CEU User Experience", "reason": "Cell edge user experience degraded.", "recommended_action": "Check CEU parameters, ICIC, and edge coverage."},
            {"feature": "L.Traffic.User.BorderUE.Avg", "bad_direction": "high", "threshold": 20, "severity": 2, "category": "Border UE Increase", "reason": "Border/cell edge users increased.", "recommended_action": "Check coverage overlap, handover zones, and cell dominance."},

            # === NEW: CA Enhanced ===
            {"feature": "L.CA.UE.Avg", "bad_direction": "low", "threshold": 20, "severity": 2, "category": "CA User Drop", "reason": "Average CA users decreased.", "recommended_action": "Check CA activation, SCell availability, and CA parameters."},
            {"feature": "L.CA.DLSCell.Act.Att", "bad_direction": "low", "threshold": 20, "severity": 2, "category": "SCell Activation Issue", "reason": "SCell activation attempts decreased.", "recommended_action": "Check SCell configuration, CA licensing, and secondary carriers."},
            {"feature": "L.CA.DLSCell.Add.Att", "bad_direction": "low", "threshold": 20, "severity": 2, "category": "SCell Addition Issue", "reason": "SCell addition attempts decreased.", "recommended_action": "Check CA configuration and inter-frequency measurements."},
            {"feature": "3CC DL PDCP CA Traffic Volume GB", "bad_direction": "low", "threshold": 20, "severity": 2, "category": "3CC CA Traffic Drop", "reason": "3-carrier aggregation traffic decreased.", "recommended_action": "Check 3CC CA bands, SCell availability, and CA configuration."},
            {"feature": "DL PDCP FDDTDD CA Traffic Volume GB", "bad_direction": "low", "threshold": 20, "severity": 2, "category": "FDD-TDD CA Traffic Drop", "reason": "FDD-TDD carrier aggregation traffic decreased.", "recommended_action": "Check FDD-TDD CA configuration and cross-mode scheduling."},
        ],
    },

    "UL Traffic": {
        "target_kpi": "(HU) UL Traffic Volume (GBytes)",
        "bad_direction": "low",
        "default_threshold": 30.0,
        "category": "Traffic",
        "output_prefix": "ul_traffic",
        "min_baseline_value": 0.1,
        "related_rules": [
            # === Original Rules ===
            {"feature": "(HU) Cell UL Average Throughput (Mbps)", "bad_direction": "low", "threshold": 20, "severity": 3, "category": "UL Throughput Degradation", "reason": "Cell UL throughput decreased.", "recommended_action": "Check UL scheduler, UL PRB utilization, uplink interference, and power control."},
            {"feature": "(HU) User UL Average Throughput (Mbps)", "bad_direction": "low", "threshold": 20, "severity": 3, "category": "UL User Throughput Degradation", "reason": "User UL throughput decreased.", "recommended_action": "Check UL radio quality, UL interference, PUSCH MCS, and UL PRB load."},
            {"feature": "(HU)UL PRB Utilization(%)", "bad_direction": "high", "threshold": 20, "severity": 2, "category": "UL Capacity / Congestion", "reason": "UL PRB utilization increased.", "recommended_action": "Check UL capacity, UL scheduling, uplink load, and traffic distribution."},
            # === CRITICAL: UL Interference (dBm) uses ABSOLUTE threshold, NOT percentage ===
            # For dBm values, a 5% degradation is meaningless. We use ABSOLUTE degradation:
            # Example: -110 dBm baseline -> -105 dBm measured = 5 dB degradation = CRITICAL
            # Threshold of 3 dB means: if interference rises by 3 dB or more, flag as issue
            {"feature": "(HU) Avg UL Interference(dBm)", "bad_direction": "high", "threshold": 3, "severity": 5, "category": "UL Interference Issue", "reason": "UL interference increased by >= 3 dB (ABSOLUTE, not percentage). A 3 dB rise is significant for interference.", "recommended_action": "Check external interference, PIM, neighboring cells, uplink noise rise. CRITICAL: This is an ABSOLUTE dB threshold - baseline -110 dBm rising to -107 dBm is a 3 dB degradation."},
            {"feature": "L.UpPTS.Interference.Avg(dBm)", "bad_direction": "high", "threshold": 3, "severity": 4, "category": "UL Interference Issue", "reason": "UpPTS interference increased by >= 3 dB (ABSOLUTE, not percentage).", "recommended_action": "Check uplink interference source, TDD interference, and guard band configuration. Uses ABSOLUTE dB threshold."},
            {"feature": "(HU) UL IBLER(%)", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "UL Radio Quality Issue", "reason": "UL IBLER increased.", "recommended_action": "Check UL interference, PUSCH MCS, UE power, and coverage."},
            {"feature": "UL RBLER", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "UL Radio Failure", "reason": "UL RBLER increased.", "recommended_action": "Check UL interference, coverage, UE power, and uplink radio conditions."},
            {"feature": "(HU) PUSCH MCS", "bad_direction": "low", "threshold": 15, "severity": 2, "category": "UL Modulation Efficiency Issue", "reason": "PUSCH MCS decreased.", "recommended_action": "Check UL SINR, interference, UE power control, and uplink coverage."},
            {"feature": "L.Traffic.ActiveUser.UL.Avg", "bad_direction": "low", "threshold": 20, "severity": 1, "category": "UL Traffic Demand Drop", "reason": "UL active users decreased.", "recommended_action": "Validate traffic trend before applying RF action."},

            # === NEW: TA Distribution ===
            {"feature": "6.6-14 km", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "UL Coverage Extension", "reason": "UL users at extended range.", "recommended_action": "Check UL coverage, UE power, and path balance."},
            {"feature": "TA Weighted Avg (meter)", "bad_direction": "high", "threshold": 20, "severity": 2, "category": "UL Distance Increase", "reason": "UL users average distance increased.", "recommended_action": "Check UL coverage and path balance."},

            # === NEW: CEU Metrics ===
            {"feature": "(HU)CEU Cell Uplink Average Throughput", "bad_direction": "low", "threshold": 20, "severity": 3, "category": "UL Cell Edge Throughput", "reason": "Cell edge UL throughput degraded.", "recommended_action": "Check UL CEU scheduling and edge coverage."},
            {"feature": "(HU)CEU User Uplink Average Throughput", "bad_direction": "low", "threshold": 20, "severity": 3, "category": "UL CEU User Experience", "reason": "Cell edge UL user experience degraded.", "recommended_action": "Check UL power control and CEU parameters."},
        ],
    },

    "DL Throughput": {
        "target_kpi": "(HU) User DL Average Throughput (Mbps)",
        "bad_direction": "low",
        "default_threshold": 20.0,
        "category": "Integrity",
        "output_prefix": "dl_throughput",
        "min_baseline_value": 5.0,
        "related_rules": [
            # === Original Rules ===
            {"feature": "(HU) DL PRB Utilization(%)", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "DL Congestion", "reason": "DL PRB utilization increased while DL throughput decreased.", "recommended_action": "Check congestion, load balancing, CA, bandwidth, scheduler, and capacity expansion."},
            {"feature": "DL Average CQI", "bad_direction": "low", "threshold": 15, "severity": 4, "category": "Poor Radio Quality", "reason": "CQI decreased while DL throughput degraded.", "recommended_action": "Check interference, PCI, antenna tilt, azimuth, and coverage."},
            {"feature": "(HU) DL IBLER(%)", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "High DL Retransmission", "reason": "DL IBLER increased while DL throughput degraded.", "recommended_action": "Check BLER, CQI, MCS, DL power, and interference."},
            {"feature": "DL RBLER", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "DL Radio Block Errors", "reason": "DL RBLER increased while DL throughput degraded.", "recommended_action": "Check interference, radio quality, and coverage."},
            {"feature": "(HU) PDSCH MCS", "bad_direction": "low", "threshold": 15, "severity": 3, "category": "Low DL Modulation", "reason": "PDSCH MCS decreased while DL throughput degraded.", "recommended_action": "Check CQI, SINR, interference, and coverage."},
            {"feature": "MAC CA Traffic Ratio", "bad_direction": "low", "threshold": 20, "severity": 2, "category": "Low CA Usage", "reason": "CA traffic ratio decreased while DL throughput degraded.", "recommended_action": "Check CA activation, SCell availability, and CA configuration."},
            {"feature": "L.Traffic.ActiveUser.Dl.Avg", "bad_direction": "high", "threshold": 20, "severity": 2, "category": "High User Load", "reason": "DL active users increased while DL throughput decreased.", "recommended_action": "Check load, scheduling, congestion, and user distribution."},

            # === NEW: TA Distribution ===
            {"feature": "6.6-14 km", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "Cell Edge Impact on Throughput", "reason": "Distant users impacting throughput.", "recommended_action": "Check coverage, user distribution, and edge scheduling."},
            {"feature": "0-156 m", "bad_direction": "low", "threshold": 20, "severity": 2, "category": "Near Users Drop", "reason": "Near-cell users decreased.", "recommended_action": "Check traffic distribution and near-cell coverage."},

            # === NEW: CEU Metrics ===
            {"feature": "(HU)CEU Cell Downlink Average Throughput", "bad_direction": "low", "threshold": 20, "severity": 4, "category": "CEU Throughput Impact", "reason": "Cell edge throughput impacting overall.", "recommended_action": "Check CEU scheduling and SINR."},
            {"feature": "(HU)CEU User Downlink Average Througput", "bad_direction": "low", "threshold": 20, "severity": 4, "category": "CEU User Impact", "reason": "CEU user throughput degraded.", "recommended_action": "Check CEU parameters and coverage."},

            # === NEW: MIMO/Rank ===
            {"feature": "Reported rank 2 (%)", "bad_direction": "low", "threshold": 15, "severity": 2, "category": "MIMO Efficiency Drop", "reason": "Rank 2 (MIMO) usage decreased.", "recommended_action": "Check MIMO conditions, correlation, and rank adaptation."},
            {"feature": "CQI_CW0", "bad_direction": "low", "threshold": 15, "severity": 3, "category": "CQI Codeword 0 Drop", "reason": "CQI on codeword 0 degraded.", "recommended_action": "Check channel conditions and reporting."},
            {"feature": "CQI_CW1", "bad_direction": "low", "threshold": 15, "severity": 3, "category": "CQI Codeword 1 Drop", "reason": "CQI on codeword 1 (MIMO) degraded.", "recommended_action": "Check MIMO channel conditions."},

            # === NEW: RSRP/SINR Signal Quality (EXPERT FEEDBACK) ===
            # Critical for RF diagnosis - missing in original config
            {"feature": "Avg RSRP (dBm)", "bad_direction": "low", "threshold": 3, "severity": 5, "category": "RSRP Degradation", "reason": "Average RSRP decreased by >= 3 dB - indicates coverage or interference issue. Uses ABSOLUTE dB threshold.", "recommended_action": "Check antenna tilt, azimuth, coverage, interference, PCI confusion/conflict. RSRP drop >3 dB is significant for RF quality."},
            {"feature": "Avg RSRQ (dB)", "bad_direction": "low", "threshold": 3, "severity": 4, "category": "RSRQ Degradation", "reason": "Average RSRQ decreased by >= 3 dB - indicates interference issue. Uses ABSOLUTE dB threshold.", "recommended_action": "Check interference, cell overlap, pilot pollution. RSRQ degradation indicates interference more than coverage."},
            {"feature": "Avg DL SINR (dB)", "bad_direction": "low", "threshold": 3, "severity": 5, "category": "SINR Degradation", "reason": "Average DL SINR decreased by >= 3 dB - directly impacts throughput and MCS. Uses ABSOLUTE dB threshold.", "recommended_action": "Check interference, coverage, CQI, and radio conditions. SINR is key for throughput and scheduling."},
        ],
    },

    "UL Throughput": {
        "target_kpi": "(HU) User UL Average Throughput (Mbps)",
        "bad_direction": "low",
        "default_threshold": 20.0,
        "category": "Integrity",
        "output_prefix": "ul_throughput",
        "min_baseline_value": 2.0,
        "related_rules": [
            # === Original Rules ===
            {"feature": "(HU)UL PRB Utilization(%)", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "UL Congestion", "reason": "UL PRB utilization increased while UL throughput degraded.", "recommended_action": "Check UL load, UL scheduler, and uplink capacity."},
            # === CRITICAL: UL Interference uses ABSOLUTE dB threshold ===
            {"feature": "(HU) Avg UL Interference(dBm)", "bad_direction": "high", "threshold": 3, "severity": 5, "category": "UL Interference Issue", "reason": "UL interference increased by >= 3 dB while UL throughput degraded. Uses ABSOLUTE dB threshold.", "recommended_action": "Check external interference, PIM, uplink noise rise. A 3 dB interference rise with throughput drop indicates significant uplink degradation."},
            {"feature": "(HU) UL IBLER(%)", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "High UL Retransmission", "reason": "UL IBLER increased while UL throughput degraded.", "recommended_action": "Check UL BLER, interference, PUSCH MCS, and UE power."},
            {"feature": "UL RBLER", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "UL Radio Block Errors", "reason": "UL RBLER increased while UL throughput degraded.", "recommended_action": "Check UL coverage, interference, and UE power limitation."},
            {"feature": "(HU) PUSCH MCS", "bad_direction": "low", "threshold": 15, "severity": 3, "category": "Low UL Modulation", "reason": "PUSCH MCS decreased while UL throughput degraded.", "recommended_action": "Check uplink SINR, interference, and power control."},
            {"feature": "L.Traffic.ActiveUser.UL.Avg", "bad_direction": "high", "threshold": 20, "severity": 2, "category": "High UL User Load", "reason": "UL active users increased while UL throughput decreased.", "recommended_action": "Check uplink scheduling, congestion, and load distribution."},

            # === NEW: TA Distribution ===
            {"feature": "6.6-14 km", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "UL Distance Impact", "reason": "Distant UL users impacting throughput.", "recommended_action": "Check UL path loss and power headroom."},

            # === NEW: CEU Metrics ===
            {"feature": "(HU)CEU Cell Uplink Average Throughput", "bad_direction": "low", "threshold": 20, "severity": 4, "category": "UL CEU Impact", "reason": "Cell edge UL throughput impacting overall.", "recommended_action": "Check UL CEU scheduling."},

            # === NEW: RSRP/SINR Signal Quality (EXPERT FEEDBACK) ===
            # UL SINR and RSRP are critical for UL throughput diagnosis
            {"feature": "Avg UL SINR (dB)", "bad_direction": "low", "threshold": 3, "severity": 5, "category": "UL SINR Degradation", "reason": "Average UL SINR decreased by >= 3 dB - directly impacts UL throughput and MCS. Uses ABSOLUTE dB threshold.", "recommended_action": "Check UL interference, coverage, UE power, and uplink radio conditions. UL SINR is key for UL throughput."},
            {"feature": "Avg RSRP (dBm)", "bad_direction": "low", "threshold": 3, "severity": 4, "category": "RSRP Degradation", "reason": "Average RSRP decreased - affects UL path loss and UE power headroom. Uses ABSOLUTE dB threshold.", "recommended_action": "Check coverage, antenna settings, and path loss. Low RSRP reduces UE power headroom for UL."},
        ],
    },

    "RRC Setup SR": {
        "target_kpi": "(TE) RRC Setup SR%",
        "bad_direction": "low",
        "default_threshold": 5.0,
        "category": "Accessibility",
        "output_prefix": "rrc_setup_sr",
        "min_baseline_value": 90.0,
        "related_rules": [
            {"feature": "L.RRC.ConnReq.Att", "bad_direction": "high", "threshold": 20, "severity": 2, "category": "High RRC Attempts", "reason": "RRC attempts increased.", "recommended_action": "Check RACH load, access parameters, admission control, and overload."},
            {"feature": "RRC Setup Failure Time", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "RRC Failure Increase", "reason": "RRC setup failures increased.", "recommended_action": "Check RACH failures, no reply, rejection, admission control, and radio quality."},
            {"feature": "L.RRC.SetupFail.NoReply", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "RRC No Reply", "reason": "RRC no-reply failures increased.", "recommended_action": "Check coverage, interference, RACH configuration, and UE access conditions."},
            {"feature": "L.RRC.SetupFail.Rej", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "RRC Rejection", "reason": "RRC rejection failures increased.", "recommended_action": "Check admission control, overload, forbidden access, and MME overload."},
            {"feature": "L.RRC.SetupFail.Rej.MMEOverload", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "MME Overload", "reason": "RRC rejection due to MME overload increased.", "recommended_action": "Check MME/S1 signaling, core side load, and S1 interface."},
            {"feature": "L.RRC.SetupFail.ResFail", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "Radio Resource Failure", "reason": "RRC setup failures due to resource failure increased.", "recommended_action": "Check radio resources, PRB load, admission control, and congestion."},
            {"feature": "RACH Contention-Based Failures", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "RACH Failure", "reason": "RACH contention failures increased.", "recommended_action": "Check PRACH configuration, root sequence planning, preamble load, and coverage."},

            # === NEW: RACH Enhanced ===
            {"feature": "RACH Non-Contention-Based SR", "bad_direction": "low", "threshold": 5, "severity": 3, "category": "Non-Contention RACH Issue", "reason": "Non-contention RACH SR degraded.", "recommended_action": "Check HO-related RACH and dedicated preambles."},
        ],
    },

    "ERAB Setup SR": {
        "target_kpi": "ERAB Setup Success Rate",
        "bad_direction": "low",
        "default_threshold": 5.0,
        "category": "Accessibility",
        "output_prefix": "erab_setup_sr",
        "min_baseline_value": 95.0,
        "related_rules": [
            {"feature": "L.E-RAB.AttEst", "bad_direction": "high", "threshold": 20, "severity": 2, "category": "High ERAB Attempts", "reason": "E-RAB setup attempts increased.", "recommended_action": "Check access load, service attempts, and admission control."},
            {"feature": "ERAB Setup Failure Times", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "ERAB Failure Increase", "reason": "E-RAB setup failures increased.", "recommended_action": "Check ERAB failure reason counters, MME, TNL, RNL, and radio resources."},
            {"feature": "L.E-RAB.FailEst.NoRadioRes", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "No Radio Resource", "reason": "E-RAB failures due to no radio resources increased.", "recommended_action": "Check PRB load, admission control, congestion, and capacity."},
            {"feature": "L.E-RAB.FailEst.NoReply", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "No Reply Failure", "reason": "E-RAB no-reply failures increased.", "recommended_action": "Check radio quality, signaling, and UE response issues."},
            {"feature": "L.E-RAB.FailEst.MME", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "MME Related Failure", "reason": "E-RAB setup failures related to MME increased.", "recommended_action": "Check MME/core side, S1 signaling, and core load."},
            {"feature": "L.E-RAB.FailEst.TNL", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "Transport Network Failure", "reason": "E-RAB setup failures related to TNL increased.", "recommended_action": "Check transmission, backhaul, S1-U/S1-C, and transport path."},
        ],
    },

    "Drop Rate": {
        "target_kpi": "E-RAB Drop Rate (E-NodeB + MME) %",
        "bad_direction": "high",
        "default_threshold": 20.0,
        "category": "Retainability",
        "output_prefix": "drop_rate",
        "min_baseline_value": 0.1,  # Fixed: was 0.0, now 0.1 to avoid division issues
        "related_rules": [
            # === Original Rules ===
            {"feature": "L.E-RAB.AbnormRel", "bad_direction": "high", "threshold": 20, "severity": 5, "category": "Abnormal Release Increase", "reason": "E-RAB abnormal releases increased.", "recommended_action": "Check drop reason counters, radio quality, HO failures, and TNL/MME causes."},
            {"feature": "L.E-RAB.AbnormRel.Radio", "bad_direction": "high", "threshold": 20, "severity": 5, "category": "Radio Drop Issue", "reason": "Radio abnormal releases increased.", "recommended_action": "Check coverage, interference, CQI, BLER, and antenna settings."},
            {"feature": "L.E-RAB.AbnormRel.Radio.ULSyncFail", "bad_direction": "high", "threshold": 20, "severity": 5, "category": "UL Sync Failure", "reason": "Drops due to UL synchronization failure increased.", "recommended_action": "Check uplink coverage, UL interference, UE power, and timing advance."},
            {"feature": "L.E-RAB.AbnormRel.Radio.UuNoReply", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "Uu No Reply", "reason": "Drops due to Uu no-reply increased.", "recommended_action": "Check coverage holes, interference, and radio link quality."},
            {"feature": "L.E-RAB.AbnormRel.TNL", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "Transport Drop Issue", "reason": "Transport-related abnormal releases increased.", "recommended_action": "Check backhaul, transmission alarms, packet loss, and transport congestion."},
            {"feature": "L.E-RAB.AbnormRel.MME", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "MME Drop Issue", "reason": "MME-related abnormal releases increased.", "recommended_action": "Check core network, MME, S1 signaling, and S1 reset counters."},
            {"feature": "L.E-RAB.AbnormRel.HOFailure", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "HO Related Drop", "reason": "Abnormal releases related to HO failure increased.", "recommended_action": "Check neighbors, missing neighbors, A3 offset, CIO, TTT, and PCI issues."},
            {"feature": "RRC Connection Drop Rate%", "bad_direction": "high", "threshold": 20, "severity": 5, "category": "RRC Drop Issue", "reason": "RRC connection drop rate increased.", "recommended_action": "Check radio quality, coverage, interference, re-establishment, and mobility."},

            # === NEW: RRC Re-establishment ===
            {"feature": "(HU) RRC Reestablish Ratio(%)", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "High Re-establishment", "reason": "RRC re-establishment ratio increased.", "recommended_action": "Check radio link failures and re-establishment triggers."},
            {"feature": "RRC Reestablish Failures(times)", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "Re-establishment Failures", "reason": "RRC re-establishment failures increased.", "recommended_action": "Check coverage and RLF causes."},
            {"feature": "L.RRC.ReEstFail.NoReply", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "Re-establishment No Reply", "reason": "Re-establishment no reply failures.", "recommended_action": "Check coverage and signaling."},
            {"feature": "L.RRC.ReEstFail.Rej", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "Re-establishment Rejection", "reason": "Re-establishment rejections increased.", "recommended_action": "Check network admission and context."},

            # === NEW: Additional Drop Reasons ===
            {"feature": "L.E-RAB.AbnormRel.eNBTot.UEAbnormal", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "UE Abnormal Release", "reason": "UE abnormal releases increased.", "recommended_action": "Check UE behavior and radio conditions."},
            {"feature": "L.E-RAB.AbnormRel.Radio.DRBReset", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "DRB Reset", "reason": "DRB reset drops increased.", "recommended_action": "Check DRB integrity and radio link."},
            {"feature": "L.E-RAB.AbnormRel.Radio.SRBReset", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "SRB Reset", "reason": "SRB reset drops increased.", "recommended_action": "Check signaling radio bearer issues."},

            # === NEW: MaxRetx and RLF Counters (EXPERT FEEDBACK) ===
            # MaxRetx failures indicate UE reached maximum retransmissions - critical for drop analysis
            {"feature": "L.E-RAB.AbnormRel.Radio.MaxRetx", "bad_direction": "high", "threshold": 20, "severity": 5, "category": "Max Retransmission Drops", "reason": "Drops due to maximum retransmissions reached - indicates persistent radio link issues.", "recommended_action": "Check DL/UL BLER, MCS adaptation, SINR, coverage, and interference. MaxRetx drops indicate UE exhausted retransmissions due to poor radio conditions."},
            {"feature": "L.RLF.MaxRetx.DL", "bad_direction": "high", "threshold": 20, "severity": 5, "category": "DL Max Retx RLF", "reason": "RLF triggered by DL max retransmissions.", "recommended_action": "Check DL radio quality, BLER, CQI, interference, and coverage. DL MaxRetx RLF is a strong indicator of downlink degradation."},
            {"feature": "L.RLF.MaxRetx.UL", "bad_direction": "high", "threshold": 20, "severity": 5, "category": "UL Max Retx RLF", "reason": "RLF triggered by UL max retransmissions.", "recommended_action": "Check UL radio quality, UL BLER, UL interference, UE power, and uplink coverage. UL MaxRetx RLF indicates uplink issues."},
            {"feature": "L.RLF.T310Expiry", "bad_direction": "high", "threshold": 20, "severity": 5, "category": "RLF T310 Expiry", "reason": "RLF due to T310 timer expiry - radio link monitoring failure.", "recommended_action": "Check coverage, signal strength (RSRP/RSRQ), SINR, and radio conditions. T310 expiry indicates sustained poor radio quality."},
            {"feature": "L.RLF.Others", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "Other RLF Causes", "reason": "Other RLF causes increased.", "recommended_action": "Investigate RLF details in trace/log for specific cause."},

            # === NEW: RSRP/SINR Signal Quality (EXPERT FEEDBACK) ===
            # Critical for drop root cause - low RSRP/SINR leads to drops
            {"feature": "Avg RSRP (dBm)", "bad_direction": "low", "threshold": 3, "severity": 5, "category": "RSRP Degradation - Drop Cause", "reason": "Average RSRP decreased by >= 3 dB - can cause radio drops. Uses ABSOLUTE dB threshold.", "recommended_action": "Check coverage, antenna settings, interference. RSRP < -110 dBm is critical for drop risk."},
            {"feature": "Avg RSRQ (dB)", "bad_direction": "low", "threshold": 3, "severity": 4, "category": "RSRQ Degradation - Drop Cause", "reason": "Average RSRQ decreased by >= 3 dB - indicates interference leading to drops. Uses ABSOLUTE dB threshold.", "recommended_action": "Check interference, pilot pollution. RSRQ < -15 dB indicates interference issues."},
            {"feature": "Avg DL SINR (dB)", "bad_direction": "low", "threshold": 3, "severity": 5, "category": "SINR Degradation - Drop Cause", "reason": "Average DL SINR decreased by >= 3 dB - directly correlates with drops. Uses ABSOLUTE dB threshold.", "recommended_action": "Check interference, coverage. SINR < 0 dB indicates severe radio degradation leading to drops."},
        ],
    },

    "HO Success Rate": {
        "target_kpi": "HO SR% Overall",
        "bad_direction": "low",
        "default_threshold": 5.0,
        "category": "Mobility",
        "output_prefix": "ho_success_rate",
        "min_baseline_value": 90.0,
        "related_rules": [
            # === Original Rules ===
            {"feature": "Intra_Freq HO Prepare Failed Times", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "Intra-Frequency HO Preparation Failure", "reason": "Intra-frequency HO preparation failures increased.", "recommended_action": "Check neighbor relations, target cell availability, admission control, and HO prep failure reasons."},
            {"feature": "Intra_Freq HO Execution Failed Times", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "Intra-Frequency HO Execution Failure", "reason": "Intra-frequency HO execution failures increased.", "recommended_action": "Check radio quality, A3 offset, TTT, CIO, PCI, and target cell coverage."},
            {"feature": "Inter_Freq HO Prepare Failed Times", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "Inter-Frequency HO Preparation Failure", "reason": "Inter-frequency HO preparation failures increased.", "recommended_action": "Check inter-frequency neighbors, measurement configuration, frequency priority, and target availability."},
            {"feature": "Inter_Freq HO Execution Failed Times", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "Inter-Frequency HO Execution Failure", "reason": "Inter-frequency HO execution failures increased.", "recommended_action": "Check A3/A5 thresholds, TTT, CIO, target cell coverage, and PCI conflicts."},
            {"feature": "S1 HO Execution Failed Times", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "S1 HO Failure", "reason": "S1 HO execution failures increased.", "recommended_action": "Check S1 handover path, MME, transport, and target eNodeB response."},
            {"feature": "X2 Intra-Freq Failure", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "X2 Intra-Frequency HO Failure", "reason": "X2 intra-frequency HO failures increased.", "recommended_action": "Check X2 links, neighbor relation, target cell, and mobility parameters."},
            {"feature": "X2 Inter-Freq Failure", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "X2 Inter-Frequency HO Failure", "reason": "X2 inter-frequency HO failures increased.", "recommended_action": "Check X2 links, inter-frequency neighbors, and target frequency settings."},
            {"feature": "L.HHO.PingPongHo", "bad_direction": "high", "threshold": 5, "severity": 3, "category": "Ping-Pong HO Issue", "reason": "Ping-pong handovers increased - causes user-visible drops. FIXED: Threshold reduced to 5% (was 10%) per expert feedback.", "recommended_action": "Tune hysteresis, TTT, CIO, A3 offset, and neighbor priorities. Ping-pong >5% already impacts user experience. Check A3/A5 event parameters and measurement configuration."},

            # === NEW: HO Preparation Details ===
            {"feature": "L.HHO.Prep.FailOut.NoReply", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "HO Prep No Reply", "reason": "HO preparation no reply failures.", "recommended_action": "Check X2/S1 connectivity and target cell."},
            {"feature": "L.HHO.Prep.FailOut.PrepFailure", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "HO Prep Failure", "reason": "HO preparation failures.", "recommended_action": "Check neighbor relations and target admission."},
            {"feature": "L.HHO.Prep.FailOut.TNL", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "HO Prep TNL Failure", "reason": "HO preparation TNL failures.", "recommended_action": "Check transport network for HO signaling."},
            {"feature": "L.HHO.X2.Prep.FailOut.PrepFailure", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "X2 HO Prep Failure", "reason": "X2 HO preparation failures.", "recommended_action": "Check X2 interface and neighbor relations."},

            # === NEW: A3/A5 Measurement Visibility (EXPERT FEEDBACK) ===
            # Measurement gaps and event reporting are critical for HO diagnosis
            {"feature": "L.HHO.MrA3.Trig", "bad_direction": "low", "threshold": 20, "severity": 2, "category": "A3 Event Triggers", "reason": "A3 event triggers decreased - may indicate measurement or neighbor issues.", "recommended_action": "Check A3 event configuration, measurement gaps, neighbor definitions. Low A3 triggers suggest UEs not detecting neighbors properly."},
            {"feature": "L.HHO.MrA5.Trig", "bad_direction": "low", "threshold": 20, "severity": 2, "category": "A5 Event Triggers", "reason": "A5 event triggers decreased - may indicate coverage edge or measurement issues.", "recommended_action": "Check A5 event configuration, coverage, inter-frequency neighbors. A5 triggers at coverage edge (serving cell poor, neighbor good)."},
            {"feature": "L.HHO.MeasGap.Succ", "bad_direction": "low", "threshold": 20, "severity": 3, "category": "Measurement Gap Issues", "reason": "Measurement gap success decreased - affects inter-frequency HO.", "recommended_action": "Check measurement gap configuration, gap pattern, and inter-frequency HO success."},
            {"feature": "L.HHO.MobilityEst.Err", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "Mobility Estimation Error", "reason": "Mobility estimation errors increased.", "recommended_action": "Check neighbor cell measurements and RSRP/RSRQ reporting quality."},

            # === NEW: FDD-TDD HO ===
            {"feature": "Inter-Freq. FDD TDD HO_Failures (Prep)", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "FDD-TDD HO Prep Failure", "reason": "FDD-TDD HO preparation failures.", "recommended_action": "Check FDD-TDD HO configuration."},
            {"feature": "Inter-Freq. FDD TDD HO_Failures (EXec)", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "FDD-TDD HO Exec Failure", "reason": "FDD-TDD HO execution failures.", "recommended_action": "Check FDD-TDD HO parameters and targets."},

            # === NEW: RSRP/SINR Signal Quality (EXPERT FEEDBACK) ===
            # RSRP/SINR critical for HO success - low values cause HO failures
            {"feature": "Avg RSRP (dBm)", "bad_direction": "low", "threshold": 3, "severity": 4, "category": "RSRP Degradation - HO Impact", "reason": "Average RSRP decreased by >= 3 dB - affects HO measurement and success. Uses ABSOLUTE dB threshold.", "recommended_action": "Check coverage and cell dominance. Low RSRP affects HO measurement accuracy and target cell detection."},
            {"feature": "Avg DL SINR (dB)", "bad_direction": "low", "threshold": 3, "severity": 4, "category": "SINR Degradation - HO Impact", "reason": "Average DL SINR decreased by >= 3 dB - affects HO execution. Uses ABSOLUTE dB threshold.", "recommended_action": "Check interference and radio quality. Low SINR causes HO execution failures due to poor radio conditions."},
        ],
    },

    "Availability": {
        "target_kpi": "Availability",
        "bad_direction": "low",
        "default_threshold": 1.0,
        "category": "Availability",
        "output_prefix": "availability",
        "min_baseline_value": 99.0,
        "related_rules": [
            {"feature": "(HU) Cell Unavail Time (s)", "bad_direction": "high", "threshold": 20, "severity": 5, "category": "Cell Unavailable Time Increase", "reason": "Cell unavailable time increased.", "recommended_action": "Check outage, alarms, power, transmission, and site status."},
            {"feature": "L.Cell.Unavail.Dur.Sys(s)", "bad_direction": "high", "threshold": 20, "severity": 5, "category": "System Unavailability", "reason": "System unavailability duration increased.", "recommended_action": "Check system faults, board alarms, transmission, and eNodeB health."},
            {"feature": "L.Cell.Unavail.Dur.Manual(s)", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "Manual Unavailability", "reason": "Manual unavailability duration increased.", "recommended_action": "Check manual lock, planned work, maintenance activity, and cell administrative state."},
            {"feature": "L.Cell.Unavail.Dur.Sys.S1Fail(s)", "bad_direction": "high", "threshold": 20, "severity": 5, "category": "S1 Failure Unavailability", "reason": "S1 failure unavailability duration increased.", "recommended_action": "Check S1 link, MME connection, transmission, and core network alarms."},
        ],
    },

    "RACH Success Rate": {
        "target_kpi": "(HU) RACH Success Rate(%)",
        "bad_direction": "low",
        "default_threshold": 5.0,
        "category": "Accessibility",
        "output_prefix": "rach_success_rate",
        "min_baseline_value": 95.0,
        "related_rules": [
            {"feature": "RACH Setup Failed Number", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "RACH Setup Failures", "reason": "RACH setup failures increased.", "recommended_action": "Check PRACH parameters, root sequence planning, coverage, interference, and access load."},
            {"feature": "RACH Contention-Based Failures", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "Contention-Based RACH Failure", "reason": "Contention-based RACH failures increased.", "recommended_action": "Check preamble congestion, PRACH configuration, root sequence, and access load."},
            {"feature": "RACH_att", "bad_direction": "high", "threshold": 20, "severity": 2, "category": "High RACH Attempts", "reason": "RACH attempts increased.", "recommended_action": "Check access load, coverage, PRACH capacity, and random access configuration."},
            {"feature": "RACH Contention-Based SR", "bad_direction": "low", "threshold": 5, "severity": 3, "category": "Contention-Based RACH SR Drop", "reason": "Contention-based RACH success rate decreased.", "recommended_action": "Check PRACH configuration, root sequence planning, and access congestion."},
            {"feature": "RACH Non-Contention-Based SR", "bad_direction": "low", "threshold": 5, "severity": 3, "category": "Non-Contention RACH SR Drop", "reason": "Non-contention RACH success rate decreased.", "recommended_action": "Check HO-related RACH, target cell access, and PRACH settings."},
        ],
    },

    "CSFB KPI": {
        "target_kpi": "CSFB SR%",
        "bad_direction": "low",
        "default_threshold": 5.0,
        "category": "CSFB / Voice Accessibility",
        "output_prefix": "csfb_kpi",
        "min_baseline_value": 90.0,
        "related_rules": [
            {"feature": "CSFB Failure Times", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "CSFB Failure Increase", "reason": "CSFB failure times increased.", "recommended_action": "Check CSFB failure reasons, MME/S1 signaling, RRC redirection, and target 2G/3G availability."},
            {"feature": "L.CSFB.PrepAtt", "bad_direction": "high", "threshold": 20, "severity": 2, "category": "High CSFB Preparation Attempts", "reason": "CSFB preparation attempts increased, which may increase CSFB load.", "recommended_action": "Check CSFB traffic demand, MME load, S1 signaling, and whether the increase is normal voice demand."},
            # === FIXED: CSFB Redirection clarity (EXPERT FEEDBACK) ===
            # These counters track CSFB redirection METHOD (not success/failure)
            # A drop in redirection + stable CSFB SR = migration to flash CSFB (GOOD)
            # A drop in redirection + low CSFB SR = target network unavailable (BAD)
            {"feature": "L.RRCRedirection.E2W.CSFB", "bad_direction": "low", "threshold": 20, "severity": 3, "category": "E2W CSFB Redirection Method Change", "reason": "LTE-to-WCDMA CSFB redirection method changed (decreased). Could be positive (flash CSFB adoption) OR negative (WCDMA target unavailable).", "recommended_action": "CORRELATE WITH CSFB SR: If CSFB SR is stable/good -> likely flash CSFB migration (acceptable). If CSFB SR degraded -> check WCDMA neighbor config, 3G coverage, and target availability."},
            {"feature": "L.RRCRedirection.E2G.CSFB", "bad_direction": "low", "threshold": 20, "severity": 3, "category": "E2G CSFB Redirection Method Change", "reason": "LTE-to-GSM CSFB redirection method changed (decreased). Could be positive (flash CSFB/3G migration) OR negative (GSM target unavailable).", "recommended_action": "CORRELATE WITH CSFB SR: If CSFB SR is stable/good -> likely migration to flash CSFB or 3G (acceptable). If CSFB SR degraded -> check GSM neighbor config, 2G coverage, and target availability."},
            {"feature": "CSFB Redirection Failure", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "CSFB Redirection Failure", "reason": "CSFB redirection failures increased - direct indication of target network issues.", "recommended_action": "Check target 2G/3G cell availability, neighbor definitions, and coverage. Redirection failures directly indicate fallback path issues."},
            {"feature": "(TE) RRC Setup SR%", "bad_direction": "low", "threshold": 5, "severity": 4, "category": "LTE RRC Access Issue", "reason": "RRC setup success rate decreased, which can affect CSFB before fallback starts.", "recommended_action": "Check LTE RRC accessibility, RACH, RRC setup failures, admission control, and radio quality."},
            {"feature": "ERAB Setup Success Rate", "bad_direction": "low", "threshold": 5, "severity": 3, "category": "E-RAB Setup Issue", "reason": "E-RAB setup success rate decreased, indicating possible access or core signaling issue affecting services.", "recommended_action": "Check E-RAB setup failures, MME/TNL/RNL causes, admission control, radio resources, and S1 signaling."},

            # === NEW: CSFB Enhanced ===
            {"feature": "L.FlashCSFB.E2W", "bad_direction": "low", "threshold": 20, "severity": 2, "category": "Flash CSFB to WCDMA", "reason": "Flash CSFB to WCDMA decreased.", "recommended_action": "Check flash CSFB configuration."},
            {"feature": "Flash CSFB Ratio", "bad_direction": "low", "threshold": 20, "severity": 2, "category": "Flash CSFB Ratio", "reason": "Flash CSFB ratio decreased.", "recommended_action": "Check flash CSFB optimization."},
            {"feature": "L.RRCRedirection.E2W.Blind", "bad_direction": "low", "threshold": 20, "severity": 2, "category": "Blind Redirection to WCDMA", "reason": "Blind redirection to WCDMA decreased.", "recommended_action": "Check blind redirection settings."},
        ],
    },

    "VoLTE KPIs": {
        "target_kpi": "BA_Voice E2E VQI",
        "bad_direction": "low",
        "default_threshold": 5.0,
        "category": "VoLTE",
        "output_prefix": "volte_kpis",
        "min_baseline_value": 3.5,
        "related_rules": [
            {"feature": "VoLTE Traffic (Erl)(Erl)", "bad_direction": "low", "threshold": 20, "severity": 3, "category": "VoLTE Traffic Drop", "reason": "VoLTE traffic decreased.", "recommended_action": "Check VoLTE user demand, IMS service, VoLTE coverage, and QCI-1 traffic."},
            {"feature": "L.Traffic.User.VoIP.Avg", "bad_direction": "low", "threshold": 20, "severity": 2, "category": "VoIP User Drop", "reason": "Average VoIP users decreased.", "recommended_action": "Check VoLTE traffic demand, service availability, and IMS registration behavior."},
            {"feature": "DL Traffic QCI-1", "bad_direction": "low", "threshold": 20, "severity": 3, "category": "QCI-1 DL Traffic Drop", "reason": "QCI-1 DL traffic decreased.", "recommended_action": "Check VoLTE bearer traffic, IMS service, and VoLTE user behavior."},
            {"feature": "E-RAB Drop(ENB+MME)_Tot", "bad_direction": "high", "threshold": 20, "severity": 5, "category": "VoLTE Retainability Risk", "reason": "Total E-RAB drops increased.", "recommended_action": "Check VoLTE drops, radio quality, TNL/MME causes, and mobility."},
            {"feature": "E-RAB Drop Rate QCI 7", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "QCI-7 Drop Issue", "reason": "QCI-7 (ViLTE/Video) drop rate increased. NOTE: QCI-7 is video, not voice - for VoLTE voice, check QCI-1.", "recommended_action": "Check ViLTE/video bearer retainability and radio quality. For VoLTE voice, also check DL Traffic QCI-1."},
            {"feature": "BA_Overall SRVCC HO Execution Success Rate (%)", "bad_direction": "low", "threshold": 5, "severity": 4, "category": "SRVCC Execution Degradation", "reason": "SRVCC HO execution success rate decreased.", "recommended_action": "Check SRVCC neighbors, 2G/3G target cells, IMS/SRVCC configuration, and mobility parameters."},
            {"feature": "BA_Overall SRVCC HO Preparation Success Rate (%)", "bad_direction": "low", "threshold": 5, "severity": 3, "category": "SRVCC Preparation Degradation", "reason": "SRVCC HO preparation success rate decreased.", "recommended_action": "Check SRVCC preparation, target availability, MSC/MME coordination, and neighbor definitions."},

            # === NEW: VoLTE Enhanced ===
            {"feature": "L.E-RAB.FailEst.MME.VoIP", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "VoIP ERAB MME Failure", "reason": "VoIP ERAB MME failures.", "recommended_action": "Check MME for VoIP bearers."},
            {"feature": "L.E-RAB.FailEst.RNL.VoIP", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "VoIP ERAB RNL Failure", "reason": "VoIP ERAB RNL failures.", "recommended_action": "Check radio network for VoIP."},
            {"feature": "L.E-RAB.FailEst.TNL.VoIP", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "VoIP ERAB TNL Failure", "reason": "VoIP ERAB TNL failures.", "recommended_action": "Check transport for VoIP."},
            {"feature": "L.E-RAB.FailEst.PoorCover.VoIP", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "VoIP Poor Coverage", "reason": "VoIP poor coverage failures.", "recommended_action": "Check VoLTE coverage."},
            {"feature": "L.E-RAB.FailEst.NoRadioRes.VoIP", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "VoIP No Radio Resource", "reason": "VoIP no radio resource failures.", "recommended_action": "Check resources for VoIP bearers."},
            {"feature": "DL user Thrpt Mbps QCI 7", "bad_direction": "low", "threshold": 20, "severity": 3, "category": "QCI-7 Throughput", "reason": "QCI-7 (ViLTE/Video) throughput degraded. NOTE: QCI-7 is video, not voice.", "recommended_action": "Check ViLTE/video bearer quality. For VoLTE voice throughput, check QCI-1 metrics."},
            {"feature": "L.Traffic.ActiveUser.DL.QCI.7", "bad_direction": "low", "threshold": 20, "severity": 2, "category": "QCI-7 Active Users", "reason": "QCI-7 active users decreased.", "recommended_action": "Check VoLTE user demand."},

            # === NEW: QCI-1 Packet Loss for VoLTE Voice (EXPERT FEEDBACK) ===
            # Packet loss is critical for VoLTE voice quality - QCI-1 is the voice bearer
            {"feature": "DL PDCP SDU Loss QCI 1", "bad_direction": "high", "threshold": 1, "severity": 5, "category": "QCI-1 DL Packet Loss", "reason": "QCI-1 DL PDCP SDU loss increased - directly impacts VoLTE voice quality. Threshold 1% is critical for voice.", "recommended_action": "Check DL radio quality, BLER, scheduling, and transport for QCI-1 voice bearer. Packet loss >1% degrades voice MOS."},
            {"feature": "UL PDCP SDU Loss QCI 1", "bad_direction": "high", "threshold": 1, "severity": 5, "category": "QCI-1 UL Packet Loss", "reason": "QCI-1 UL PDCP SDU loss increased - directly impacts VoLTE voice quality. Threshold 1% is critical for voice.", "recommended_action": "Check UL radio quality, UL BLER, UL interference, and scheduling for QCI-1 voice bearer."},
            {"feature": "DL PDCP Packet Loss Rate QCI 1", "bad_direction": "high", "threshold": 1, "severity": 5, "category": "QCI-1 DL Packet Loss Rate", "reason": "QCI-1 DL packet loss rate increased.", "recommended_action": "Check PDCP statistics, DL quality, transport for voice bearer."},
            {"feature": "UL PDCP Packet Loss Rate QCI 1", "bad_direction": "high", "threshold": 1, "severity": 5, "category": "QCI-1 UL Packet Loss Rate", "reason": "QCI-1 UL packet loss rate increased.", "recommended_action": "Check PDCP statistics, UL quality, transport for voice bearer."},
            {"feature": "DL user Thrpt Mbps QCI 1", "bad_direction": "low", "threshold": 20, "severity": 3, "category": "QCI-1 Throughput", "reason": "QCI-1 (VoLTE Voice) throughput degraded.", "recommended_action": "Check QCI-1 bearer scheduling, radio quality, and resources. QCI-1 is voice - low throughput may indicate scheduling or radio issues."},
            {"feature": "L.Traffic.ActiveUser.DL.QCI.1", "bad_direction": "low", "threshold": 20, "severity": 2, "category": "QCI-1 Active Users", "reason": "QCI-1 active users decreased.", "recommended_action": "Check VoLTE voice user demand and IMS registration."},
            {"feature": "E-RAB Drop Rate QCI 1", "bad_direction": "high", "threshold": 5, "severity": 5, "category": "QCI-1 Drop Rate", "reason": "QCI-1 (VoLTE Voice) drop rate increased - directly impacts voice retainability.", "recommended_action": "Check VoLTE voice bearer drops, radio quality, and mobility. QCI-1 drops directly affect voice calls."},
        ],
    },

    # === NEW KPI: RRC Re-establishment ===
    "RRC Re-establishment": {
        "target_kpi": "RRC Reestablish Setup Success Rate(%)",
        "bad_direction": "low",
        "default_threshold": 10.0,
        "category": "Mobility",
        "output_prefix": "rrc_reestablishment",
        "min_baseline_value": 90.0,  # Fixed: 80% baseline is already degraded; healthy is >95%
        "related_rules": [
            {"feature": "RRC Reestablish Failures(times)", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "Re-establishment Failure", "reason": "RRC re-establishment failures increased.", "recommended_action": "Check RLF causes, coverage, and re-establishment parameters."},
            {"feature": "L.RRC.ReEstFail.NoReply", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "Re-establishment No Reply", "reason": "No reply during re-establishment.", "recommended_action": "Check target cell coverage and signaling."},
            {"feature": "L.RRC.ReEstFail.Rej", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "Re-establishment Rejection", "reason": "Re-establishment rejected.", "recommended_action": "Check context availability and network admission."},
            {"feature": "L.RRC.ReEstFail.NoCntx", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "No Context", "reason": "No context for re-establishment.", "recommended_action": "Check context retention and source cell."},
            {"feature": "L.RRC.ReEstFail.ResFail", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "Resource Failure", "reason": "Resource failure during re-establishment.", "recommended_action": "Check target cell resources."},
            {"feature": "RRC Connection Drop Rate%", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "RRC Drop Issue", "reason": "RRC drops triggering re-establishment.", "recommended_action": "Check RRC drop causes."},
            {"feature": "L.E-RAB.AbnormRel.Radio", "bad_direction": "high", "threshold": 20, "severity": 4, "category": "Radio Link Failure", "reason": "Radio failures causing RLF.", "recommended_action": "Check radio quality and coverage."},
            {"feature": "(HU) RRC Reestablish Ratio(%)", "bad_direction": "high", "threshold": 20, "severity": 3, "category": "High Re-establishment Ratio", "reason": "RRC re-establishment ratio increased.", "recommended_action": "Check RLF triggers and mobility."},
        ],
    },
}


# ============================================================
# RUN VALIDATION ON MODULE LOAD
# ============================================================
# Uncomment the following line to enable validation at startup:
# validate_kpi_configs()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_kpi_config(kpi_name: str) -> dict:
    """Get KPI configuration by name.

    Args:
        kpi_name: Name of the KPI (e.g., "DL Traffic")

    Returns:
        dict: KPI configuration

    Raises:
        KeyError: If KPI name not found
    """
    if kpi_name not in KPI_CONFIGS:
        available = list(KPI_CONFIGS.keys())
        raise KeyError(f"KPI '{kpi_name}' not found. Available KPIs: {available}")
    return KPI_CONFIGS[kpi_name]


def get_all_target_kpis() -> list:
    """Get list of all target KPI column names.

    Returns:
        list: List of target KPI column names
    """
    return [config["target_kpi"] for config in KPI_CONFIGS.values()]


def get_kpi_categories() -> dict:
    """Get KPI names grouped by category.

    Returns:
        dict: Category -> list of KPI names
    """
    categories = {}
    for kpi_name, config in KPI_CONFIGS.items():
        cat = config.get("category", "Unknown")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(kpi_name)
    return categories


def get_related_features_for_kpi(kpi_name: str) -> list:
    """Get list of related feature names for a KPI.

    Args:
        kpi_name: Name of the KPI

    Returns:
        list: List of feature column names
    """
    config = get_kpi_config(kpi_name)
    return [rule["feature"] for rule in config.get("related_rules", [])]


def count_rules_per_kpi() -> dict:
    """Count number of related rules for each KPI.

    Returns:
        dict: KPI name -> rule count
    """
    return {
        kpi_name: len(config.get("related_rules", []))
        for kpi_name, config in KPI_CONFIGS.items()
    }


# ============================================================
# STATISTICS
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("KPI CONFIGURATION STATISTICS")
    print("=" * 60)
    print(f"Total KPIs: {len(KPI_CONFIGS)}")
    print()

    print("KPIs by Category:")
    for cat, kpis in get_kpi_categories().items():
        print(f"  {cat}: {len(kpis)} KPI(s)")
    print()

    print("Rules per KPI:")
    for kpi_name, count in count_rules_per_kpi().items():
        print(f"  {kpi_name}: {count} rules")
    print()

    total_rules = sum(count_rules_per_kpi().values())
    print(f"Total Related Rules: {total_rules}")
