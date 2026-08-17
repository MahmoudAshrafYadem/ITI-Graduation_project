""" ""
data.py — Pure-pandas data wrangling layer.

Responsibilities:
  1. build_action_hunks()           — day-level commit aggregation
  2. resolve_eval_window()          — rolling "After" window with next-hunk cap
  3. collect_matching_weekdays()    — aggregate all matching historical weekdays
  4. align_periods()                — normalise Before/After to minute_of_day index
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date


# ══════════════════════════════════════════════════════════════════════
#  1. ACTION HUNK BUILDER
# ══════════════════════════════════════════════════════════════════════


def build_action_hunks(log_df: pd.DataFrame) -> list[dict]:
    """
    Group Dolt commit-log rows by calendar date into "Action Hunks".

    Each commit on the same calendar day is bundled into one hunk.
    Commits on different days form separate hunks.

    Args:
        log_df : DataFrame with at least columns [date, message, commit_hash]

    Returns a sorted list of dicts:
        {
          "date"    : "YYYY-MM-DD",
          "label"   : "2024-06-10  (Mon)  ·  3 commits",
          "commits" : [list of row dicts — all values are plain Python types],
          "n"       : int
        }
    """
    if log_df.empty:
        return []

    df = log_df.copy()

    # Parse to datetime for sorting
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    df = df.dropna(subset=["date"]).sort_values("date")
    df["date_str"] = df["date"].dt.strftime("%Y-%m-%d")

    # Stringify ALL datetime columns so to_dict("records") never returns
    # Timestamp objects (they are not subscriptable like strings).
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S")

    hunks = []
    for date_str, group in df.groupby("date_str", sort=True):
        weekday = datetime.strptime(date_str, "%Y-%m-%d").strftime("%a")
        n = len(group)
        commit_word = "commit" if n == 1 else "commits"
        label = f"{date_str}  ({weekday})  ·  {n} {commit_word}"
        hunks.append(
            {
                "date": date_str,
                "label": label,
                "commits": group.to_dict("records"),
                "n": n,
            }
        )

    hunks.sort(key=lambda h: h["date"])
    return hunks


# ══════════════════════════════════════════════════════════════════════
#  1b. PER-CELL ACTION HUNKS  (for filtering / comparison)
# ══════════════════════════════════════════════════════════════════════


def build_action_hunks_by_cell(log_df: pd.DataFrame) -> list[dict]:
    """
    Like build_action_hunks(), but grouped by (cell_id, calendar date)
    instead of date alone, so each hunk unambiguously belongs to one
    cell. Used for cross-cell / cross-action comparison and for
    cell-scoped filtering, independent of the network-wide timeline.

    Each dict adds: "cell_id", "cell_group", "action_types" (sorted
    unique action types in the hunk), "optimizers" (sorted unique
    optimizer values).
    """
    if log_df.empty or "cell_id" not in log_df.columns:
        return []

    df = log_df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")
    df["date_str"] = df["date"].dt.strftime("%Y-%m-%d")

    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S")

    hunks = []
    for (cell_id, date_str), group in df.groupby(["cell_id", "date_str"], sort=True):
        weekday = datetime.strptime(date_str, "%Y-%m-%d").strftime("%a")
        n = len(group)
        commit_word = "commit" if n == 1 else "commits"
        action_types = sorted(set(group.get("action_type", pd.Series(dtype=str)).dropna()))
        optimizers = sorted(set(group.get("optimizer", pd.Series(dtype=str)).dropna()))
        cell_group = group.get("cell_group", pd.Series([""])).iloc[0] if "cell_group" in group else ""
        label = (
            f"{cell_id}  ·  {date_str}  ({weekday})  ·  {n} {commit_word}"
            f"  ·  {', '.join(action_types) if action_types else '—'}"
        )
        hunks.append(
            {
                "date": date_str,
                "cell_id": cell_id,
                "cell_group": cell_group,
                "action_types": action_types,
                "optimizers": optimizers,
                "label": label,
                "commits": group.to_dict("records"),
                "n": n,
            }
        )

    hunks.sort(key=lambda h: (h["date"], h["cell_id"]))
    return hunks


# ══════════════════════════════════════════════════════════════════════
#  1c. LOG / HUNK FILTERING
# ══════════════════════════════════════════════════════════════════════


def filter_log_df(
    log_df: pd.DataFrame,
    cell_groups: list[str] | None = None,
    cell_ids: list[str] | None = None,
    optimizers: list[str] | None = None,
    action_types: list[str] | None = None,
    search_text: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> pd.DataFrame:
    """Apply optional filters to the raw commit-log DataFrame."""
    if log_df.empty:
        return log_df

    df = log_df.copy()

    if cell_groups and "cell_group" in df.columns:
        df = df[df["cell_group"].isin(cell_groups)]
    if cell_ids and "cell_id" in df.columns:
        df = df[df["cell_id"].isin(cell_ids)]
    if optimizers and "optimizer" in df.columns:
        df = df[df["optimizer"].isin(optimizers)]
    if action_types and "action_type" in df.columns:
        df = df[df["action_type"].isin(action_types)]
    if search_text:
        needle = search_text.lower()
        mask = df.apply(
            lambda r: needle in str(r.get("message", "")).lower()
            or needle in str(r.get("committer", "")).lower()
            or needle in str(r.get("parameter", "")).lower(),
            axis=1,
        )
        df = df[mask]
    if date_from:
        df = df[df["date"].astype(str) >= date_from]
    if date_to:
        df = df[df["date"].astype(str) <= date_to + " 23:59:59"]

    return df


# ══════════════════════════════════════════════════════════════════════
#  1d. CROSS-ACTION / CROSS-CELL COMPARISON
# ══════════════════════════════════════════════════════════════════════


def compare_actions(
    kpi_df: pd.DataFrame,
    actions: list[dict],
    kpi: str,
    eval_days: int = 1,
) -> pd.DataFrame:
    """
    Compare the Before/After impact of several actions (hunks) on the
    same KPI — either several actions on one cell, or the same/similar
    action type across several cells.

    Args:
        actions   : list of hunk dicts (must include "cell_id" and "date")
        kpi       : KPI column to evaluate
        eval_days : length of the After window starting at the action date

    Returns a DataFrame with one row per action:
        cell_id, date, action_types, before_avg, after_avg, abs_change, pct_change
    """
    rows = []
    for action in actions:
        cell_id = action.get("cell_id")
        action_date = action["date"]
        after_end = (
            datetime.strptime(action_date, "%Y-%m-%d") + timedelta(days=eval_days - 1)
        ).strftime("%Y-%m-%d")

        cell_kpi_df = (
            kpi_df[kpi_df["cell_id"] == cell_id] if cell_id and "cell_id" in kpi_df.columns else kpi_df
        )
        before_df, after_df, _, _ = collect_matching_weekdays(cell_kpi_df, action_date, after_end)

        if before_df.empty or after_df.empty or kpi not in before_df.columns or kpi not in after_df.columns:
            continue

        before_avg = float(before_df[kpi].mean())
        after_avg = float(after_df[kpi].mean())
        abs_change = after_avg - before_avg
        pct_change = (abs_change / abs(before_avg) * 100) if before_avg != 0 else 0.0

        rows.append(
            {
                "Label": action.get("label", f"{cell_id} · {action_date}"),
                "Cell": cell_id or "—",
                "Date": action_date,
                "Action Type": ", ".join(action.get("action_types", [])) or "—",
                "Before Avg": round(before_avg, 4),
                "After Avg": round(after_avg, 4),
                "Abs Change": round(abs_change, 4),
                "% Change": round(pct_change, 2),
            }
        )

    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════
#  2. ROLLING EVALUATION WINDOW RESOLVER
# ══════════════════════════════════════════════════════════════════════


def resolve_eval_window(
    hunks: list[dict],
    selected_hunk_date: str,
    ignore_next_hunk: bool = False,
) -> tuple[str, str, str | None]:
    """
    Determine the "After" evaluation window for the selected hunk.

    Rules:
      - Window starts on selected_hunk_date.
      - Window ends at today's date OR the start of the NEXT hunk,
        whichever comes first — unless ignore_next_hunk is True,
        in which case it always ends at today.

    Returns:
        (after_start, after_end, next_hunk_date_or_None)
        Both dates are "YYYY-MM-DD" strings.
    """
    today_str = date.today().strftime("%Y-%m-%d")
    after_start = selected_hunk_date

    # Find the next hunk after the selected one
    later_hunks = [h for h in hunks if h["date"] > selected_hunk_date]
    next_hunk_date = later_hunks[0]["date"] if later_hunks else None

    if next_hunk_date and not ignore_next_hunk:
        # Cap one day before the next hunk to avoid overlap
        cap_dt = datetime.strptime(next_hunk_date, "%Y-%m-%d") - timedelta(days=1)
        after_end = min(cap_dt.strftime("%Y-%m-%d"), today_str)
    else:
        after_end = today_str

    return after_start, after_end, next_hunk_date


# ══════════════════════════════════════════════════════════════════════
#  3. AGGREGATED WEEKDAY MATCHING ENGINE
# ══════════════════════════════════════════════════════════════════════


def collect_matching_weekdays(
    kpi_df: pd.DataFrame,
    after_start: str,
    after_end: str,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str]]:
    """
    Build averaged "After" and "Before" profiles by collecting all
    matching historical weekdays.

    For each unique (weekday, minute_of_day) in the After window:
      - After profile  = mean of all After-window days with that weekday
      - Before profile = mean of all matching weekdays 7 days *prior*
        to each After day (i.e., same day-of-week, one week back)

    This supports multi-week evaluation windows cleanly.

    Args:
        kpi_df      : Full KPI DataFrame with `timestamp` column
        after_start : "YYYY-MM-DD"
        after_end   : "YYYY-MM-DD"

    Returns:
        (before_df, after_df, after_dates_used, before_dates_used)
        both DataFrames indexed by minute_of_day (0–1439)
    """
    if kpi_df.empty:
        empty = pd.DataFrame()
        return empty, empty, [], []

    df = kpi_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])
    df["date_str"] = df["timestamp"].dt.strftime("%Y-%m-%d")
    df["minute_of_day"] = df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute

    non_numeric = {
        "timestamp",
        "date_str",
        "minute_of_day",
        "cell_id",
        "node_id",
        "site_id",
        "id",
        "region",
        "vendor",
    }
    numeric_cols = [
        c
        for c in df.columns
        if c not in non_numeric and pd.api.types.is_numeric_dtype(df[c])
    ]

    # ── Identify every distinct date in the After window ──────────────
    after_dates = sorted(
        [d for d in df["date_str"].unique() if after_start <= d <= after_end]
    )
    if not after_dates:
        empty = pd.DataFrame()
        return empty, empty, [], []

    # ── For each after_date, find its matching baseline date ───────────
    baseline_dates = []
    for ad in after_dates:
        bd = (datetime.strptime(ad, "%Y-%m-%d") - timedelta(days=7)).strftime(
            "%Y-%m-%d"
        )
        baseline_dates.append(bd)

    def _mean_over_dates(date_list: list[str]) -> pd.DataFrame:
        """Average all minute_of_day profiles across the given dates."""
        available = [d for d in date_list if d in df["date_str"].values]
        if not available:
            return pd.DataFrame()
        subset = df[df["date_str"].isin(available)]
        return subset.groupby("minute_of_day")[numeric_cols].mean().sort_index()

    after_df = _mean_over_dates(after_dates)
    before_df = _mean_over_dates(baseline_dates)

    if after_df.empty or before_df.empty:
        return before_df, after_df, after_dates, baseline_dates

    # Align to shared minute index
    common = after_df.index.intersection(before_df.index)
    after_df = after_df.loc[common]
    before_df = before_df.loc[common]

    return before_df, after_df, after_dates, baseline_dates


# ══════════════════════════════════════════════════════════════════════
#  4. PER-DAY INDIVIDUAL PROFILES (non-aggregated, grouped by weekday)
# ══════════════════════════════════════════════════════════════════════


def collect_individual_days(
    kpi_df: pd.DataFrame,
    after_start: str,
    after_end: str,
) -> dict[str, dict]:
    """
    Return individual (non-averaged) Before/After profiles for every
    after-window date, grouped by weekday name.

    Structure returned:
      {
        "Monday": {
            "after_days":  { "2024-06-10": DataFrame(minute_of_day index), ... },
            "before_days": { "2024-06-03": DataFrame(minute_of_day index), ... },
        },
        "Saturday": { ... },
        ...
      }

    Each day's DataFrame is indexed by minute_of_day (0–1439) and contains
    only numeric KPI columns.
    """
    if kpi_df.empty:
        return {}

    df = kpi_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])
    df["date_str"] = df["timestamp"].dt.strftime("%Y-%m-%d")
    df["minute_of_day"] = df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute

    non_numeric = {
        "timestamp",
        "date_str",
        "minute_of_day",
        "cell_id",
        "node_id",
        "site_id",
        "id",
        "region",
        "vendor",
    }
    numeric_cols = [
        c
        for c in df.columns
        if c not in non_numeric and pd.api.types.is_numeric_dtype(df[c])
    ]

    after_dates = sorted(
        [d for d in df["date_str"].unique() if after_start <= d <= after_end]
    )
    if not after_dates:
        return {}

    def _day_profile(date_str: str) -> pd.DataFrame:
        day = df[df["date_str"] == date_str]
        if day.empty:
            return pd.DataFrame()
        return day.groupby("minute_of_day")[numeric_cols].mean().sort_index()

    result: dict[str, dict] = {}

    for ad in after_dates:
        weekday = datetime.strptime(ad, "%Y-%m-%d").strftime("%A")
        bd = (datetime.strptime(ad, "%Y-%m-%d") - timedelta(days=7)).strftime(
            "%Y-%m-%d"
        )

        after_profile = _day_profile(ad)
        before_profile = _day_profile(bd)

        if after_profile.empty:
            continue  # skip days with no data

        if weekday not in result:
            result[weekday] = {"after_days": {}, "before_days": {}}

        result[weekday]["after_days"][ad] = after_profile
        result[weekday]["before_days"][bd] = before_profile

    return result


# ══════════════════════════════════════════════════════════════════════
#  5. SINGLE-DAY PERIOD ALIGNMENT (kept for backwards compatibility)
# ══════════════════════════════════════════════════════════════════════


def align_periods(
    kpi_df: pd.DataFrame,
    baseline_date: str,
    action_date: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Thin wrapper around collect_matching_weekdays for single-day use.
    Kept so existing callers don't break.
    """
    before_df, after_df, _, _ = collect_matching_weekdays(
        kpi_df, action_date, action_date
    )
    # Override before with the explicit single baseline date
    df = kpi_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])
    df["date_str"] = df["timestamp"].dt.strftime("%Y-%m-%d")
    df["minute_of_day"] = df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute

    non_numeric = {
        "timestamp",
        "date_str",
        "minute_of_day",
        "cell_id",
        "node_id",
        "site_id",
        "id",
        "region",
        "vendor",
    }
    numeric_cols = [
        c
        for c in df.columns
        if c not in non_numeric and pd.api.types.is_numeric_dtype(df[c])
    ]

    def _agg(date_str):
        day = df[df["date_str"] == date_str]
        if day.empty:
            return pd.DataFrame()
        return day.groupby("minute_of_day")[numeric_cols].mean().sort_index()

    before_df = _agg(baseline_date)
    after_df = _agg(action_date)

    if before_df.empty or after_df.empty:
        return before_df, after_df

    common = before_df.index.intersection(after_df.index)
    return before_df.loc[common], after_df.loc[common]
