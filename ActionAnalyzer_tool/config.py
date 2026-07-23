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
