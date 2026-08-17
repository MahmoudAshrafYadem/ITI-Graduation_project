"""
config.py — Persistent application configuration.

All user-managed settings live in a single ``config.json`` file next to
this module:

{
  "kpi_polarity":  { kpi_name: "higher" | "lower" },
  "param_kpi_map": { parameter_name: [kpi_name, ...] },
  "kpi_groups":    { group_name: [kpi_name, ...] },
  "param_groups":  { group_name: [parameter_name, ...] }
}

The loader also migrates the legacy split files (kpi_config.json,
param_kpi_map.json, kpi_groups.json and param_groups.json) on first use.
"""

import json
from pathlib import Path
from typing import Any

# ── Unified config file ────────────────────────────────────────────────
CONFIG_PATH = Path(__file__).parent / "config.json"

# Legacy locations retained only for one-way migration.
LEGACY_CONFIG_PATH = Path(__file__).parent / "kpi_config.json"
LEGACY_PARAM_KPI_MAP_PATH = Path(__file__).parent / "param_kpi_map.json"
LEGACY_KPI_GROUPS_PATH = Path(__file__).parent / "kpi_groups.json"
LEGACY_PARAM_GROUPS_PATH = Path(__file__).parent / "param_groups.json"

# Backwards-compatible aliases: all sections now resolve to config.json.
PARAM_KPI_MAP_PATH = CONFIG_PATH
KPI_GROUPS_PATH = CONFIG_PATH
PARAM_GROUPS_PATH = CONFIG_PATH

_SETTING_KEYS = ("kpi_polarity", "param_kpi_map", "kpi_groups", "param_groups")

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


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def _empty_settings() -> dict[str, dict]:
    return {key: {} for key in _SETTING_KEYS}


def _load_settings() -> dict[str, dict]:
    """
    Read the unified config, migrating legacy split files when present.

    A legacy flat polarity file copied to config.json is also accepted for
    backwards compatibility.
    """
    settings = _empty_settings()
    raw = _read_json(CONFIG_PATH)

    if isinstance(raw, dict):
        if any(key in raw for key in _SETTING_KEYS):
            for key in _SETTING_KEYS:
                value = raw.get(key)
                if isinstance(value, dict):
                    settings[key] = value
        else:
            # Backwards compatibility: config.json used to be a flat
            # polarity map in early versions.
            settings["kpi_polarity"] = raw

    legacy_sources = {
        "kpi_polarity": LEGACY_CONFIG_PATH,
        "param_kpi_map": LEGACY_PARAM_KPI_MAP_PATH,
        "kpi_groups": LEGACY_KPI_GROUPS_PATH,
        "param_groups": LEGACY_PARAM_GROUPS_PATH,
    }
    for key, path in legacy_sources.items():
        if settings[key]:
            continue
        legacy_value = _read_json(path)
        if isinstance(legacy_value, dict):
            settings[key] = legacy_value

    return settings


def _save_settings(settings: dict[str, dict]) -> None:
    clean = _empty_settings()
    for key in _SETTING_KEYS:
        value = settings.get(key, {})
        clean[key] = value if isinstance(value, dict) else {}
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(clean, fh, indent=2)


def _update_section(section: str, value: dict) -> None:
    settings = _load_settings()
    settings[section] = value
    _save_settings(settings)


def _infer_polarity(kpi_name: str) -> str:
    """Return 'lower' if the KPI name contains a degradation keyword, else 'higher'."""
    name_lower = kpi_name.lower()
    for kw in LOWER_IS_BETTER_KEYWORDS:
        if kw in name_lower:
            return "lower"
    return "higher"


def load_config(kpi_columns: list[str]) -> dict[str, str]:
    """
    Load KPI polarity from config.json, filling newly-discovered KPIs with
    inferred defaults and persisting the merged result.
    """
    existing = _load_settings()["kpi_polarity"]

    merged: dict[str, str] = {}
    changed = False
    for kpi in kpi_columns:
        if existing.get(kpi) in ("higher", "lower"):
            merged[kpi] = existing[kpi]
        else:
            merged[kpi] = _infer_polarity(kpi)
            changed = True

    if changed or not CONFIG_PATH.exists():
        save_config(merged)

    return merged


def save_config(polarity_map: dict[str, str]) -> None:
    """Persist KPI polarity while preserving all other config.json sections."""
    _update_section("kpi_polarity", polarity_map)


def config_path_str() -> str:
    """Return the absolute path of config.json as a string."""
    return str(CONFIG_PATH.resolve())


# ══════════════════════════════════════════════════════════════════════
#  PARAMETER ⇄ KPI RELATIONSHIP MAP
# ══════════════════════════════════════════════════════════════════════


def _infer_param_kpis(param_name: str, kpi_columns: list[str]) -> list[str]:
    hinted = _DEFAULT_PARAM_KPI_HINTS.get(param_name)
    if hinted:
        return [k for k in hinted if k in kpi_columns]
    return []


def load_param_kpi_map(
    param_names: list[str], kpi_columns: list[str]
) -> dict[str, list[str]]:
    """Load parameter → affected-KPIs mappings from config.json."""
    existing = _load_settings()["param_kpi_map"]

    merged: dict[str, list[str]] = {}
    changed = False
    for parameter in param_names:
        saved = existing.get(parameter)
        if isinstance(saved, list):
            cleaned = [k for k in saved if k in kpi_columns]
            merged[parameter] = cleaned
            if cleaned != saved:
                changed = True
        else:
            merged[parameter] = _infer_param_kpis(parameter, kpi_columns)
            changed = True

    if changed or not CONFIG_PATH.exists():
        save_param_kpi_map(merged)

    return merged


def save_param_kpi_map(param_kpi_map: dict[str, list[str]]) -> None:
    _update_section("param_kpi_map", param_kpi_map)


# ══════════════════════════════════════════════════════════════════════
#  KPI / PARAMETER GROUPS
# ══════════════════════════════════════════════════════════════════════


def load_kpi_groups() -> dict[str, list[str]]:
    groups = _load_settings()["kpi_groups"]
    return {str(name): list(members) for name, members in groups.items() if isinstance(members, list)}


def save_kpi_groups(groups: dict[str, list[str]]) -> None:
    _update_section("kpi_groups", groups)


def load_param_groups() -> dict[str, list[str]]:
    groups = _load_settings()["param_groups"]
    return {str(name): list(members) for name, members in groups.items() if isinstance(members, list)}


def save_param_groups(groups: dict[str, list[str]]) -> None:
    _update_section("param_groups", groups)
