""" ""
data.py — Pure-pandas data wrangling layer.

Responsibilities:
  1. build_action_hunks()           — day-level commit aggregation
  2. resolve_eval_window()          — rolling "After" window with next-hunk cap
  3. collect_comparison_periods()   — aggregate symmetric Before/After periods
  4. align_periods()                — normalise Before/After to minute_of_day index
"""

import re
from difflib import SequenceMatcher

import pandas as pd
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

_SEARCH_FIELDS = (
    "message",
    "committer",
    "parameter",
    "email",
    "commit_hash",
    "cell_id",
    "cell_group",
    "action_type",
    "optimizer",
    "from_val",
    "to_val",
)


def _fuzzy_token_matches(text: object, token: str, threshold: float = 0.62) -> bool:
    """
    Case-insensitive fuzzy token match.

    Exact substring matches always win. For typo-tolerant matching, compare
    the query token with each word-ish fragment in the searchable text.
    Very short tokens stay substring-only to avoid noisy false positives.
    """
    haystack = str(text or "").casefold()
    token = token.casefold().strip()
    if not token:
        return False
    if token in haystack:
        return True
    if len(token) < 3:
        return False

    words = re.findall(r"[a-z0-9]+", haystack)
    return any(
        SequenceMatcher(None, token, word).ratio() >= threshold for word in words
    )


def row_matches_search(row: pd.Series | dict, search_text: str | None) -> bool:
    """
    Match a commit row against a fuzzy query.

    Whitespace separates alternatives: ``power tilt`` means rows matching
    "power" OR "tilt", not one phrase containing both words.
    """
    if not search_text or not search_text.strip():
        return True
    tokens = [token for token in re.split(r"\s+", search_text.strip()) if token]
    return any(
        _fuzzy_token_matches(row.get(field, ""), token)
        for token in tokens
        for field in _SEARCH_FIELDS
    )


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
        df = df[df.apply(lambda row: row_matches_search(row, search_text), axis=1)]
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
    eval_days: int | None = None,
    comparison_weeks: int = 1,
) -> pd.DataFrame:
    """
    Compare the Before/After impact of several actions (hunks) on one KPI.

    ``comparison_weeks`` requests N weeks after each action and the matching
    N-week block immediately before it. If fewer days are available, the
    available span is used on both sides. ``eval_days`` remains as a
    backwards-compatible override for older callers.

    Returns a DataFrame with one row per action:
        cell_id, date, action_types, before_avg, after_avg, abs_change, pct_change
    """
    span_days = int(eval_days) if eval_days is not None else max(1, int(comparison_weeks)) * 7
    rows = []
    for action in actions:
        cell_id = action.get("cell_id")
        action_date = action["date"]
        after_end = (
            datetime.strptime(action_date, "%Y-%m-%d") + timedelta(days=span_days - 1)
        ).strftime("%Y-%m-%d")

        cell_kpi_df = (
            kpi_df[kpi_df["cell_id"] == cell_id] if cell_id and "cell_id" in kpi_df.columns else kpi_df
        )
        before_df, after_df, _, _ = collect_comparison_periods(
            cell_kpi_df, action_date, after_end
        )

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
    comparison_weeks: int = 1,
) -> tuple[str, str, str | None]:
    """
    Determine the requested N-week "After" evaluation window.

    Rules:
      - Window starts on selected_hunk_date.
      - Requested window lasts comparison_weeks * 7 days.
      - It is capped by the next action hunk and by today unless
        ignore_next_hunk is True (today remains the outer cap).

    Returns:
        (after_start, after_end, next_hunk_date_or_None)
    """
    today = date.today()
    after_start = selected_hunk_date
    start_dt = datetime.strptime(selected_hunk_date, "%Y-%m-%d").date()
    weeks = max(1, int(comparison_weeks or 1))
    requested_end = start_dt + timedelta(days=weeks * 7 - 1)

    later_hunks = [h for h in hunks if h["date"] > selected_hunk_date]
    next_hunk_date = later_hunks[0]["date"] if later_hunks else None

    effective_end = min(requested_end, today)
    if next_hunk_date and not ignore_next_hunk:
        cap_dt = datetime.strptime(next_hunk_date, "%Y-%m-%d").date() - timedelta(days=1)
        effective_end = min(effective_end, cap_dt)

    if effective_end < start_dt:
        effective_end = start_dt
    return after_start, effective_end.strftime("%Y-%m-%d"), next_hunk_date


# ══════════════════════════════════════════════════════════════════════
#  3. AGGREGATED WEEKDAY MATCHING ENGINE
# ══════════════════════════════════════════════════════════════════════


def _numeric_kpi_columns(df: pd.DataFrame) -> list[str]:
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
    return [
        c
        for c in df.columns
        if c not in non_numeric and pd.api.types.is_numeric_dtype(df[c])
    ]


def collect_comparison_periods(
    kpi_df: pd.DataFrame,
    after_start: str,
    after_end: str,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str]]:
    """
    Build averaged profiles for the available After span and an equally
    long Before span immediately preceding it.

    The caller chooses the requested N-week After window. This function
    trims both sides to the dates actually present in the data, so asking
    for four weeks with only two weeks of usable history compares the
    available two weeks after the action with the two weeks before it.

    Returns:
        (before_df, after_df, after_dates_used, before_dates_used)
        with both profiles indexed by minute_of_day (0–1439).
    """
    if kpi_df.empty:
        empty = pd.DataFrame()
        return empty, empty, [], []

    df = kpi_df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])
    if df.empty:
        empty = pd.DataFrame()
        return empty, empty, [], []

    df["date_str"] = df["timestamp"].dt.strftime("%Y-%m-%d")
    df["minute_of_day"] = df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute
    numeric_cols = _numeric_kpi_columns(df)

    requested_start = datetime.strptime(after_start, "%Y-%m-%d").date()
    requested_end = datetime.strptime(after_end, "%Y-%m-%d").date()
    if requested_end < requested_start:
        empty = pd.DataFrame()
        return empty, empty, [], []

    available_dates = sorted(df["date_str"].unique())
    after_dates = [
        d for d in available_dates if after_start <= d <= after_end
    ]
    if not after_dates:
        empty = pd.DataFrame()
        return empty, empty, [], []

    # Use the actual available span on both sides. For a complete N-week
    # window this is exactly the N weeks after the action versus the N
    # weeks immediately before it; for a capped/truncated window it is
    # the same number of available calendar days on both sides.
    effective_after_start = datetime.strptime(after_dates[0], "%Y-%m-%d").date()
    effective_after_end = datetime.strptime(after_dates[-1], "%Y-%m-%d").date()
    requested_span_days = (effective_after_end - effective_after_start).days + 1
    before_end = effective_after_start - timedelta(days=1)
    initial_before_start = before_end - timedelta(days=requested_span_days - 1)

    initial_before_dates = [
        d
        for d in available_dates
        if initial_before_start.strftime("%Y-%m-%d") <= d <= before_end.strftime("%Y-%m-%d")
    ]
    if not initial_before_dates:
        empty = pd.DataFrame()
        return empty, empty, [], []

    # Keep both sides symmetric when history is shorter than the requested
    # N weeks: the usable Before range determines how much After data is
    # included, and vice versa.
    first_before = datetime.strptime(initial_before_dates[0], "%Y-%m-%d").date()
    last_before = datetime.strptime(initial_before_dates[-1], "%Y-%m-%d").date()
    before_span_days = (last_before - first_before).days + 1
    span_days = min(requested_span_days, before_span_days)

    before_start = before_end - timedelta(days=span_days - 1)
    effective_after_end = effective_after_start + timedelta(days=span_days - 1)
    before_start_str = before_start.strftime("%Y-%m-%d")
    before_end_str = before_end.strftime("%Y-%m-%d")
    effective_after_end_str = effective_after_end.strftime("%Y-%m-%d")

    before_dates = [
        d for d in initial_before_dates if before_start_str <= d <= before_end_str
    ]
    after_dates = [
        d for d in after_dates if after_dates[0] <= d <= effective_after_end_str
    ]

    def _mean_over_dates(date_list: list[str]) -> pd.DataFrame:
        if not date_list:
            return pd.DataFrame()
        subset = df[df["date_str"].isin(date_list)]
        if subset.empty or not numeric_cols:
            return pd.DataFrame()
        return subset.groupby("minute_of_day")[numeric_cols].mean().sort_index()

    after_df = _mean_over_dates(after_dates)
    before_df = _mean_over_dates(before_dates)
    if after_df.empty or before_df.empty:
        return before_df, after_df, after_dates, before_dates

    common = after_df.index.intersection(before_df.index)
    after_df = after_df.loc[common]
    before_df = before_df.loc[common]
    return before_df, after_df, after_dates, before_dates


def collect_matching_weekdays(
    kpi_df: pd.DataFrame,
    after_start: str,
    after_end: str,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str]]:
    """
    Backwards-compatible name for the week-aware comparison collector.
    The window length now controls the immediately preceding baseline,
    rather than always looking exactly seven days back from each After day.
    """
    return collect_comparison_periods(kpi_df, after_start, after_end)


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
