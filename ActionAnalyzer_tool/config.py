"""
config.py — Persistent KPI Optimization Configuration.

Manages reading and writing `kpi_config.json`, which stores the
user-defined polarity ("higher" | "lower") for each discovered KPI.

If the file does not exist on first run, it is auto-generated with
sensible defaults inferred from column name keywords.
"""

import json
import os
from pathlib import Path

# ── Location of the config file (same directory as this script) ────────
CONFIG_PATH = Path(__file__).parent / "kpi_config.json"

# ── Keywords that indicate "Lower is Better" polarity ──────────────────
LOWER_IS_BETTER_KEYWORDS = {
    "drop",
    "error",
    "fail",
    "loss",
    "latency",
    "delay",
    "bler",
    "interference",
    "noise",
    "outage",
    "congestion",
    "retransmit",
    "retry",
    "nack",
    "rach_fail",
}


def _infer_polarity(kpi_name: str) -> str:
    """Return 'lower' if the KPI name contains a degradation keyword, else 'higher'."""
    name_lower = kpi_name.lower()
    for kw in LOWER_IS_BETTER_KEYWORDS:
        if kw in name_lower:
            return "lower"
    return "higher"


def load_config(kpi_columns: list[str]) -> dict[str, str]:
    """
    Load polarity config from kpi_config.json.

    - If the file exists, parse it and fill in any newly-discovered KPIs
      that are not yet present in the file (using inferred defaults).
    - If the file does not exist, create it with all inferred defaults.

    Returns:
        dict mapping kpi_name → "higher" | "lower"
    """
    existing: dict[str, str] = {}

    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
        except (json.JSONDecodeError, OSError):
            # Corrupted file — start fresh
            existing = {}

    # Merge: keep saved values, infer defaults for new KPIs
    merged: dict[str, str] = {}
    changed = False
    for kpi in kpi_columns:
        if kpi in existing and existing[kpi] in ("higher", "lower"):
            merged[kpi] = existing[kpi]
        else:
            merged[kpi] = _infer_polarity(kpi)
            changed = True  # new KPI found — save updated file

    # Persist if anything changed or file was missing
    if changed or not CONFIG_PATH.exists():
        save_config(merged)

    return merged


def save_config(polarity_map: dict[str, str]) -> None:
    """
    Serialise the polarity map to kpi_config.json.
    Creates the file if it does not exist.
    """
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(polarity_map, fh, indent=2)


def config_path_str() -> str:
    """Return the absolute path of the config file as a string."""
    return str(CONFIG_PATH.resolve())


# ══════════════════════════════════════════════════════════════════════
#  PARAMETER ⇄ KPI RELATIONSHIP MAP
#  Records which tunable parameters are believed to affect which KPIs.
#  Stored as { parameter_name: [kpi_name, kpi_name, ...] }
# ══════════════════════════════════════════════════════════════════════

PARAM_KPI_MAP_PATH = Path(__file__).parent / "param_kpi_map.json"

# Best-effort default wiring so the UI isn't empty on first run.
_DEFAULT_PARAM_KPI_HINTS: dict[str, list[str]] = {
    "antenna_tilt_deg": ["throughput_dl_mbps", "sinr_db", "avg_cqi", "drop_rate_pct"],
    "tx_power_dbm": ["throughput_dl_mbps", "sinr_db", "prb_utilization_pct"],
    "ca_band_combo": ["throughput_dl_mbps", "throughput_ul_mbps"],
    "rach_root_seq": ["rach_success_rate_pct", "latency_ms"],
    "ho_a3_offset": ["handover_success_rate_pct", "drop_rate_pct"],
    "sched_weight": ["prb_utilization_pct", "throughput_dl_mbps"],
    "mimo_rank": ["throughput_dl_mbps", "sinr_db"],
    "qos_profile": ["latency_ms", "throughput_ul_mbps"],
}


def _infer_param_kpis(param_name: str, kpi_columns: list[str]) -> list[str]:
    hinted = _DEFAULT_PARAM_KPI_HINTS.get(param_name)
    if hinted:
        return [k for k in hinted if k in kpi_columns]
    return []


def load_param_kpi_map(
    param_names: list[str], kpi_columns: list[str]
) -> dict[str, list[str]]:
    """
    Load the parameter → affected-KPIs map, filling in defaults for any
    newly-discovered parameter that isn't in the saved file yet.
    """
    existing: dict[str, list[str]] = {}
    if PARAM_KPI_MAP_PATH.exists():
        try:
            with open(PARAM_KPI_MAP_PATH, "r", encoding="utf-8") as fh:
                existing = json.load(fh)
        except (json.JSONDecodeError, OSError):
            existing = {}

    merged: dict[str, list[str]] = {}
    changed = False
    for p in param_names:
        if p in existing and isinstance(existing[p], list):
            merged[p] = [k for k in existing[p] if k in kpi_columns]
        else:
            merged[p] = _infer_param_kpis(p, kpi_columns)
            changed = True

    if changed or not PARAM_KPI_MAP_PATH.exists():
        save_param_kpi_map(merged)

    return merged


def save_param_kpi_map(param_kpi_map: dict[str, list[str]]) -> None:
    with open(PARAM_KPI_MAP_PATH, "w", encoding="utf-8") as fh:
        json.dump(param_kpi_map, fh, indent=2)


# ══════════════════════════════════════════════════════════════════════
#  KPI GROUPS  — sets of strongly-related KPIs
#  Stored as { group_name: [kpi_name, ...] }
# ══════════════════════════════════════════════════════════════════════

KPI_GROUPS_PATH = Path(__file__).parent / "kpi_groups.json"


def load_kpi_groups() -> dict[str, list[str]]:
    if KPI_GROUPS_PATH.exists():
        try:
            with open(KPI_GROUPS_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_kpi_groups(groups: dict[str, list[str]]) -> None:
    with open(KPI_GROUPS_PATH, "w", encoding="utf-8") as fh:
        json.dump(groups, fh, indent=2)


# ══════════════════════════════════════════════════════════════════════
#  PARAMETER GROUPS  — sets of parameters that are always changed together
#  Stored as { group_name: [parameter_name, ...] }
# ══════════════════════════════════════════════════════════════════════

PARAM_GROUPS_PATH = Path(__file__).parent / "param_groups.json"


def load_param_groups() -> dict[str, list[str]]:
    if PARAM_GROUPS_PATH.exists():
        try:
            with open(PARAM_GROUPS_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_param_groups(groups: dict[str, list[str]]) -> None:
    with open(PARAM_GROUPS_PATH, "w", encoding="utf-8") as fh:
        json.dump(groups, fh, indent=2)
