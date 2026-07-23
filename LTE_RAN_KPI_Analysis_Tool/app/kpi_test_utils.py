"""
Shared helpers for the paired-comparison test suites.

These utilities build synthetic LTE KPI frames in exactly the shape
`analyze_selected_kpi` expects, so the tests exercise the *real* code in
main_function_for_selected_kpi.py (no stubbing of the logic under test).

Drop this file next to main_function_for_selected_kpi.py.
"""
import numpy as np
import pandas as pd

from KPI_Configuration import (
    SITE_COL,
    CELL_COL,
    LOCAL_CELL_COL,
    DATE_COL,
    KPI_CONFIGS,
)

# A fixed anchor date used across tests. 2024-03-14 is a Thursday, which
# gives us a clean mix of weekdays/weekends inside a 7-day window.
ANCHOR = pd.Timestamp("2024-03-14")


def target_col(kpi_name):
    """Return the Excel target-KPI column name for a configured KPI."""
    return KPI_CONFIGS[kpi_name]["target_kpi"]


def build_frame(cells, kpi_name, anchor=ANCHOR):
    """Build a long-format KPI DataFrame from a compact cell spec.

    Parameters
    ----------
    cells : list[dict]
        Each dict describes one cell:
          {
            "site": "S1",                  # eNodeB Name
            "cell": "C1",                  # Cell Name (optional, default "C")
            "local": 0,                    # LocalCell Id (optional, default 0)
            "recent": {offset: value, ...} # offset 0 == anchor, 1 == anchor-1d
                  OR  [v0, v1, ...]        # list -> offsets 0..n-1
            "baseline": {offset: value}    # offset measured from (anchor - 7d)
                  OR  [v0, v1, ...]        # list -> 7-day baseline twins
            "baseline_abs": {date: value}  # OPTIONAL absolute dates (Timestamp)
          }
        Any value of None / np.nan is simply not emitted (missing day).
    kpi_name : str
        Key into KPI_CONFIGS (e.g. "DL Throughput", "E-RAB Drop Rate").
    """
    tgt = target_col(kpi_name)
    rows = []

    def _emit(site, cell, local, date, val):
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return
        rows.append({
            SITE_COL: site, CELL_COL: cell, LOCAL_CELL_COL: local,
            DATE_COL: date, tgt: val,
        })

    for spec in cells:
        site = spec["site"]
        cell = spec.get("cell", "C")
        local = spec.get("local", 0)

        recent = spec.get("recent", {})
        if isinstance(recent, (list, tuple)):
            recent = {i: v for i, v in enumerate(recent)}
        for off, val in recent.items():
            _emit(site, cell, local, anchor - pd.Timedelta(days=off), val)

        baseline = spec.get("baseline", {})
        if isinstance(baseline, (list, tuple)):
            baseline = {i: v for i, v in enumerate(baseline)}
        b_anchor = anchor - pd.Timedelta(days=7)
        for off, val in baseline.items():
            _emit(site, cell, local, b_anchor - pd.Timedelta(days=off), val)

        for date, val in spec.get("baseline_abs", {}).items():
            _emit(site, cell, local, pd.Timestamp(date), val)

    return pd.DataFrame(rows)


def one_row(out):
    """Assert the output has exactly one cell and return it as a Series."""
    assert out.shape[0] == 1, f"expected 1 output row, got {out.shape[0]}"
    return out.iloc[0]


def parse_daily_ratios(value):
    """daily_ratios is stored as a stringified Python list -> parse it back."""
    import ast
    return ast.literal_eval(value)
