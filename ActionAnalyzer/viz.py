"""
viz.py — Plotly chart builders for the NetOps Impact Analyzer.

Charts:
  1. plot_action_timeline()  — interactive HUD timeline with commit metadata
  2. plot_kpi_trend()        — dual Before/After line chart
  3. plot_delta_bars()       — polarity-aware interval delta bars
  4. build_summary_table()   — KPI impact summary DataFrame
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ── Design tokens ──────────────────────────────────────────────────────
NAVY = "#0d1b2a"
PANEL = "#132338"
BORDER = "#1e3a5f"
CYAN = "#00c8ff"
CYAN_SOFT = "rgba(0,200,255,0.15)"
GREEN = "#00e599"
GREEN_SOFT = "rgba(0,229,153,0.20)"
RED = "#ff4d6d"
AMBER = "#ffb347"
AMBER_SOFT = "rgba(255,179,71,0.15)"
MUTED = "#6b8cae"
TEXT = "#dce8f0"
FONT = "'IBM Plex Mono', 'Courier New', monospace"


def _base_layout(**extra) -> dict:
    base = dict(
        paper_bgcolor=PANEL,
        plot_bgcolor=NAVY,
        font=dict(family=FONT, color=TEXT, size=11),
        margin=dict(l=60, r=30, t=50, b=50),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor=BORDER,
            borderwidth=1,
            font=dict(size=10, color=MUTED),
        ),
        xaxis=dict(
            gridcolor=BORDER,
            linecolor=BORDER,
            tickfont=dict(color=MUTED, size=9),
            title_font=dict(color=MUTED, size=10),
        ),
        yaxis=dict(
            gridcolor=BORDER,
            linecolor=BORDER,
            tickfont=dict(color=MUTED, size=9),
            title_font=dict(color=MUTED, size=10),
        ),
        hoverlabel=dict(
            bgcolor=PANEL,
            bordercolor=BORDER,
            font=dict(family=FONT, size=11, color=TEXT),
        ),
    )
    base.update(extra)
    return base


def _hhmm(minute_of_day: int) -> str:
    h, m = divmod(int(minute_of_day), 60)
    return f"{h:02d}:{m:02d}"


# ══════════════════════════════════════════════════════════════════════
#  CHART 1 — ENRICHED INTERACTIVE ACTION TIMELINE HUD
# ══════════════════════════════════════════════════════════════════════


def plot_action_timeline(hunks: list[dict]) -> go.Figure:
    """
    Horizontal timeline with per-hunk rich tooltips.

    Each marker encodes:
      - Size   → number of commits
      - Colour → commit count (gradient)

    Hover tooltip shows:
      - Hunk date + weekday
      - For each commit: hash (short), committer, email, timestamp, message
    """
    dates = [h["date"] for h in hunks]
    counts = [h["n"] for h in hunks]

    x_labels = []
    for d in dates:
        dt = datetime.strptime(d, "%Y-%m-%d")
        x_labels.append(dt.strftime("%b %d\n(%a)"))

    # ── Build rich HTML hover text per hunk ───────────────────────────
    hover_texts = []
    for h in hunks:
        dt = datetime.strptime(h["date"], "%Y-%m-%d")
        weekday = dt.strftime("%A")
        lines = [
            f"<b>{h['date']}  —  {weekday}</b>",
            f"<span style='color:{MUTED}'>{h['n']} commit(s)</span>",
            "─────────────────────────",
        ]
        for c in h["commits"]:
            short_hash = str(c.get("commit_hash", ""))[:10]
            committer = c.get("committer", "unknown")
            email = c.get("email", "")
            ts = str(c.get("date", ""))[:19]
            msg = c.get("message", "—")
            lines += [
                f"<b>{msg}</b>",
                f"<span style='color:{CYAN}'>{committer}</span>"
                f"  <span style='color:{MUTED}'>&lt;{email}&gt;</span>",
                f"<span style='color:{MUTED}'>{ts}  ·  #{short_hash}</span>",
                " ",
            ]
        hover_texts.append("<br>".join(lines))

    fig = go.Figure()

    # Connector line
    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=[0] * len(x_labels),
            mode="lines",
            line=dict(color=BORDER, width=1.5, dash="dot"),
            showlegend=False,
            hoverinfo="skip",
        )
    )

    # Hunk markers
    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=[0] * len(x_labels),
            mode="markers+text",
            marker=dict(
                size=[max(16, min(44, 12 + c * 6)) for c in counts],
                color=counts,
                colorscale=[[0, CYAN_SOFT], [0.5, CYAN], [1, "#a0e8ff"]],
                line=dict(color=CYAN, width=1.5),
                showscale=True,
                colorbar=dict(
                    title="Commits",
                    title_font=dict(color=MUTED, size=9),
                    tickfont=dict(color=MUTED, size=8),
                    thickness=10,
                    len=0.5,
                    x=1.02,
                ),
            ),
            text=[str(c) for c in counts],
            textfont=dict(color=NAVY, size=9, family=FONT),
            textposition="middle center",
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_texts,
            name="Action Hunk",
        )
    )

    fig.update_layout(
        **_base_layout(
            title=dict(
                text="Action Hunk Distribution — hover for commit details",
                font=dict(color=CYAN, size=13, family=FONT),
                x=0,
            ),
            height=220,
            yaxis=dict(
                visible=False, range=[-0.6, 0.6], gridcolor=BORDER, linecolor=BORDER
            ),
            xaxis=dict(
                gridcolor=BORDER,
                linecolor=BORDER,
                tickfont=dict(color=MUTED, size=9, family=FONT),
            ),
        )
    )
    return fig


# ══════════════════════════════════════════════════════════════════════
#  CHART 2 — KPI TREND (BEFORE vs AFTER, multi-week aware)
# ══════════════════════════════════════════════════════════════════════


def plot_kpi_trend(
    before_df: pd.DataFrame,
    after_df: pd.DataFrame,
    kpi: str,
    after_dates: list[str],
    before_dates: list[str],
    commits_in_window: list[dict] | None = None,
    time_range: tuple[int, int] | None = None,
) -> go.Figure:
    """
    Dual-line overlay of averaged Before and After profiles.
    Labels reflect the actual date ranges used.

    Args:
        commits_in_window : list of commit dicts to annotate as vertical lines.
                            Each dict must have 'date' and optionally 'message'.
        time_range        : (start_minute, end_minute) 0-1439 tuple to slice x-axis.
                            If None, the full day is shown.
    """
    # ── Apply time range slice ──────────────────────────────────────
    if time_range:
        start_m, end_m = time_range
        before_df = before_df.loc[
            (before_df.index >= start_m) & (before_df.index <= end_m)
        ]
        after_df = after_df.loc[(after_df.index >= start_m) & (after_df.index <= end_m)]

    if before_df.empty or after_df.empty or kpi not in before_df.columns:
        return go.Figure()

    x_ticks = [_hhmm(m) for m in before_df.index]

    after_label = _date_range_label(after_dates)
    before_label = _date_range_label(before_dates)

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=x_ticks,
            y=before_df[kpi].round(4),
            mode="lines",
            name=f"Before  ({before_label})",
            line=dict(color=MUTED, width=1.8, dash="dash"),
            hovertemplate=f"<b>Before</b><br>Time: %{{x}}<br>{kpi}: %{{y:.4f}}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_ticks,
            y=after_df[kpi].round(4),
            mode="lines",
            name=f"After   ({after_label})",
            line=dict(color=CYAN, width=2.5),
            fill="tonexty",
            fillcolor=CYAN_SOFT,
            hovertemplate=f"<b>After</b><br>Time: %{{x}}<br>{kpi}: %{{y:.4f}}<extra></extra>",
        )
    )

    window = max(4, len(after_df) // 24)
    ma = after_df[kpi].rolling(window=window, center=True).mean()
    fig.add_trace(
        go.Scatter(
            x=x_ticks,
            y=ma.round(4),
            mode="lines",
            name=f"MA({window}) After",
            line=dict(color=AMBER, width=1.2, dash="dot"),
            hovertemplate=f"<b>Moving Avg</b><br>Time: %{{x}}<br>{kpi}: %{{y:.4f}}<extra></extra>",
        )
    )

    # ── Commit annotations as vertical lines on the x-axis ─────────
    # Commits have a date but not a specific intra-day minute, so we
    # draw them at minute 0 of that date's label (x = "00:00").
    # We label them above the top of the chart using annotations.
    if commits_in_window:
        yvals = list(after_df[kpi].dropna())
        y_max = max(yvals) if yvals else 1
        y_min = min(yvals) if yvals else 0
        y_span = y_max - y_min or 1

        COMMIT_COLORS = [CYAN, GREEN, AMBER, "#a78bfa", "#f472b6"]

        for i, commit in enumerate(commits_in_window):
            c_date = str(commit.get("date", ""))[:10]
            c_msg = commit.get("message", "—")[:40]
            c_hash = str(commit.get("commit_hash", ""))[:8]
            c_who = commit.get("committer", "")
            color = COMMIT_COLORS[i % len(COMMIT_COLORS)]
            x_val = "00:00"  # anchor to start of day on the minute axis

            # vertical line shape
            fig.add_shape(
                type="line",
                x0=x_val,
                x1=x_val,
                y0=y_min - y_span * 0.05,
                y1=y_max + y_span * 0.15,
                line=dict(color=color, width=1.5, dash="dashdot"),
                xref="x",
                yref="y",
            )
            fig.add_annotation(
                x=x_val,
                y=y_max + y_span * (0.12 + i * 0.10),
                xref="x",
                yref="y",
                text=f"<b>{c_date}</b>  #{c_hash}<br>"
                f"<span style='color:{MUTED}'>{c_msg}</span>",
                showarrow=True,
                arrowhead=2,
                arrowcolor=color,
                arrowsize=0.8,
                arrowwidth=1,
                ax=30,
                ay=-30,
                font=dict(size=8, color=color, family=FONT),
                bgcolor=PANEL,
                bordercolor=color,
                borderwidth=1,
                borderpad=3,
                align="left",
            )

    title_suffix = f"[{len(after_dates)} day(s) aggregated]"
    if time_range:
        title_suffix += f"  ·  {_hhmm(time_range[0])}–{_hhmm(time_range[1])}"

    fig.update_layout(
        **_base_layout(
            title=dict(
                text=f"KPI Trend — {kpi}  {title_suffix}",
                font=dict(color=CYAN, size=13, family=FONT),
                x=0,
            ),
            height=420,
            xaxis=dict(
                title="Hour of Day",
                gridcolor=BORDER,
                linecolor=BORDER,
                tickfont=dict(color=MUTED, size=9),
                tickvals=x_ticks[::4],
                ticktext=x_ticks[::4],
            ),
            yaxis=dict(title=kpi, gridcolor=BORDER, linecolor=BORDER),
        )
    )
    return fig


def plot_kpi_trend_individual(
    weekday_data: dict[str, dict],
    kpi: str,
    time_range: tuple[int, int] | None = None,
    commits_in_window: list[dict] | None = None,
) -> dict[str, go.Figure]:
    """
    For each weekday group in weekday_data, produce a figure that overlays
    every individual After day vs its matched Before day.

    Returns a dict of { weekday_name: go.Figure }.
    """
    AFTER_PALETTE = [CYAN, GREEN, "#a78bfa", "#f472b6", "#fb923c", "#34d399"]
    BEFORE_PALETTE = [MUTED, "#4b6a8a", "#7c6fa0", "#a0638e", "#a07840", "#3d7060"]

    figures: dict[str, go.Figure] = {}

    for weekday, day_data in weekday_data.items():
        after_days = day_data.get("after_days", {})
        before_days = day_data.get("before_days", {})

        if not after_days:
            continue

        fig = go.Figure()

        all_y: list[float] = []

        for i, (after_date, after_df) in enumerate(sorted(after_days.items())):
            before_date = (
                datetime.strptime(after_date, "%Y-%m-%d") - timedelta(days=7)
            ).strftime("%Y-%m-%d")
            before_df = before_days.get(before_date, pd.DataFrame())

            # Apply time range
            if time_range:
                s, e = time_range
                after_df = (
                    after_df.loc[(after_df.index >= s) & (after_df.index <= e)]
                    if not after_df.empty
                    else after_df
                )
                before_df = (
                    before_df.loc[(before_df.index >= s) & (before_df.index <= e)]
                    if not before_df.empty
                    else before_df
                )

            if after_df.empty or kpi not in after_df.columns:
                continue

            x_ticks = [_hhmm(m) for m in after_df.index]
            color_a = AFTER_PALETTE[i % len(AFTER_PALETTE)]
            color_b = BEFORE_PALETTE[i % len(BEFORE_PALETTE)]

            # Before line (dashed, same colour family but muted)
            if not before_df.empty and kpi in before_df.columns:
                xb = [_hhmm(m) for m in before_df.index]
                fig.add_trace(
                    go.Scatter(
                        x=xb,
                        y=before_df[kpi].round(4),
                        mode="lines",
                        name=f"Before {before_date}",
                        line=dict(color=color_b, width=1.4, dash="dash"),
                        opacity=0.7,
                        legendgroup=after_date,
                        hovertemplate=(
                            f"<b>Before {before_date}</b><br>"
                            f"Time: %{{x}}<br>{kpi}: %{{y:.4f}}<extra></extra>"
                        ),
                    )
                )
                all_y.extend(before_df[kpi].dropna().tolist())

            # After line (solid)
            fig.add_trace(
                go.Scatter(
                    x=x_ticks,
                    y=after_df[kpi].round(4),
                    mode="lines",
                    name=f"After  {after_date}",
                    line=dict(color=color_a, width=2.2),
                    legendgroup=after_date,
                    hovertemplate=(
                        f"<b>After {after_date}</b><br>"
                        f"Time: %{{x}}<br>{kpi}: %{{y:.4f}}<extra></extra>"
                    ),
                )
            )
            all_y.extend(after_df[kpi].dropna().tolist())

        # ── Commit annotations ──────────────────────────────────────
        if commits_in_window and all_y:
            y_max = max(all_y)
            y_min = min(all_y)
            y_span = y_max - y_min or 1
            COMMIT_COLORS = [CYAN, GREEN, AMBER, "#a78bfa", "#f472b6"]

            for ci, commit in enumerate(commits_in_window):
                c_date = str(commit.get("date", ""))[:10]
                c_msg = commit.get("message", "—")[:40]
                c_hash = str(commit.get("commit_hash", ""))[:8]
                color = COMMIT_COLORS[ci % len(COMMIT_COLORS)]
                x_val = "00:00"

                fig.add_shape(
                    type="line",
                    x0=x_val,
                    x1=x_val,
                    y0=y_min - y_span * 0.05,
                    y1=y_max + y_span * 0.15,
                    line=dict(color=color, width=1.5, dash="dashdot"),
                    xref="x",
                    yref="y",
                )
                fig.add_annotation(
                    x=x_val,
                    y=y_max + y_span * (0.12 + ci * 0.10),
                    xref="x",
                    yref="y",
                    text=f"<b>{c_date}</b>  #{c_hash}<br>"
                    f"<span style='color:{MUTED}'>{c_msg}</span>",
                    showarrow=True,
                    arrowhead=2,
                    arrowcolor=color,
                    arrowsize=0.8,
                    arrowwidth=1,
                    ax=30,
                    ay=-30,
                    font=dict(size=8, color=color, family=FONT),
                    bgcolor=PANEL,
                    bordercolor=color,
                    borderwidth=1,
                    borderpad=3,
                    align="left",
                )

        n_after = len(after_days)
        title_suffix = f"[{n_after} day(s) individually]"
        if time_range:
            title_suffix += f"  ·  {_hhmm(time_range[0])}–{_hhmm(time_range[1])}"

        # Determine an x_ticks sample for axis ticks
        sample_after = next(iter(after_days.values()), pd.DataFrame())
        if time_range and not sample_after.empty:
            s, e = time_range
            sample_after = sample_after.loc[
                (sample_after.index >= s) & (sample_after.index <= e)
            ]
        x_all = [_hhmm(m) for m in sample_after.index] if not sample_after.empty else []

        fig.update_layout(
            **_base_layout(
                title=dict(
                    text=f"KPI Trend ({weekday}) — {kpi}  {title_suffix}",
                    font=dict(color=CYAN, size=13, family=FONT),
                    x=0,
                ),
                height=420,
                xaxis=dict(
                    title="Hour of Day",
                    gridcolor=BORDER,
                    linecolor=BORDER,
                    tickfont=dict(color=MUTED, size=9),
                    tickvals=x_all[::4] if x_all else [],
                    ticktext=x_all[::4] if x_all else [],
                ),
                yaxis=dict(title=kpi, gridcolor=BORDER, linecolor=BORDER),
            )
        )

        figures[weekday] = fig

    return figures


def _date_range_label(dates: list[str]) -> str:
    """Return 'May 22' or 'May 22 – Jun 17' depending on span."""
    if not dates:
        return "—"
    unique = sorted(set(dates))
    if len(unique) == 1:
        return datetime.strptime(unique[0], "%Y-%m-%d").strftime("%b %d")
    first = datetime.strptime(unique[0], "%Y-%m-%d").strftime("%b %d")
    last = datetime.strptime(unique[-1], "%Y-%m-%d").strftime("%b %d")
    return f"{first} – {last}"


# ══════════════════════════════════════════════════════════════════════
#  CHART 3 — DELTA BAR CHART (polarity-aware)
# ══════════════════════════════════════════════════════════════════════


def plot_delta_bars(
    before_df: pd.DataFrame,
    after_df: pd.DataFrame,
    kpi: str,
    polarity: str,  # "lower" | "higher"
) -> go.Figure:
    """Bar chart of (After − Before) per interval, colour-coded by polarity."""
    delta = (after_df[kpi] - before_df[kpi]).round(4)
    x_ticks = [_hhmm(m) for m in delta.index]

    def _color(d: float) -> str:
        return (
            GREEN
            if (polarity == "lower" and d < 0) or (polarity == "higher" and d > 0)
            else RED
        )

    colors = [_color(d) for d in delta]
    hover_texts = [
        f"Δ {kpi}: {d:+.4f}<br><b>{'Improved ✓' if c == GREEN else 'Degraded ✗'}</b>"
        for d, c in zip(delta, colors)
    ]

    fig = go.Figure(
        go.Bar(
            x=x_ticks,
            y=delta,
            marker_color=colors,
            marker_line_width=0,
            opacity=0.85,
            text=[
                f"{d:+.3f}" if abs(d) > delta.abs().max() * 0.3 else "" for d in delta
            ],
            textfont=dict(size=7, color=TEXT),
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_texts,
        )
    )

    fig.add_hline(y=0, line_color=MUTED, line_width=1)
    polarity_text = "Lower is Better ↓" if polarity == "lower" else "Higher is Better ↑"
    fig.add_annotation(
        x=0,
        y=1.06,
        xref="paper",
        yref="paper",
        text=(
            f"<span style='color:{GREEN}'>■ Improvement</span>"
            f"   <span style='color:{RED}'>■ Degradation</span>"
            f"   <span style='color:{MUTED}'>— Policy: {polarity_text}</span>"
        ),
        showarrow=False,
        font=dict(size=9, family=FONT),
        align="left",
    )

    fig.update_layout(
        **_base_layout(
            title=dict(
                text=f"Interval Delta (After − Before) — {kpi}",
                font=dict(color=CYAN, size=13, family=FONT),
                x=0,
            ),
            height=340,
            bargap=0.05,
            xaxis=dict(
                title="Hour of Day",
                gridcolor=BORDER,
                linecolor=BORDER,
                tickfont=dict(color=MUTED, size=9),
                tickvals=x_ticks[::4],
                ticktext=x_ticks[::4],
            ),
            yaxis=dict(
                title=f"Δ {kpi}", gridcolor=BORDER, linecolor=BORDER, zeroline=False
            ),
        )
    )
    return fig


# ══════════════════════════════════════════════════════════════════════
#  TABLE — KPI IMPACT SUMMARY
# ══════════════════════════════════════════════════════════════════════


def build_summary_table(
    before_df: pd.DataFrame,
    after_df: pd.DataFrame,
    kpi_columns: list[str],
    polarity_map: dict[str, str],
) -> pd.DataFrame:
    """One row per KPI: Before Avg, After Avg, Abs Change, % Change, Status."""
    rows = []
    for kpi in kpi_columns:
        if kpi not in before_df.columns or kpi not in after_df.columns:
            continue
        if before_df[kpi].isna().all() or after_df[kpi].isna().all():
            continue

        before_avg = float(before_df[kpi].mean())
        after_avg = float(after_df[kpi].mean())
        abs_change = after_avg - before_avg
        pct_change = (abs_change / abs(before_avg) * 100) if before_avg != 0 else 0.0

        polarity = polarity_map.get(kpi, "higher")
        improved = (polarity == "lower" and abs_change < -1e-9) or (
            polarity == "higher" and abs_change > 1e-9
        )
        no_change = abs(pct_change) < 0.01

        status = (
            "⚪ No Change"
            if no_change
            else ("🟢 Improved" if improved else "🔴 Degraded")
        )

        rows.append(
            {
                "KPI": kpi,
                "Before Avg": round(before_avg, 4),
                "After Avg": round(after_avg, 4),
                "Abs Change": round(abs_change, 4),
                "% Change": round(pct_change, 2),
                "Status": status,
            }
        )
    return pd.DataFrame(rows)
