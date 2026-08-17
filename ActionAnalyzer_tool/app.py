""" ""
╔══════════════════════════════════════════════════════════════════════╗
║          Telecom Network Optimization Impact Analyzer                ║
║          Powered by Dolt (Version-Controlled DB) + Streamlit         ║
╚══════════════════════════════════════════════════════════════════════╝

Architecture:
  - db.py        → PyMySQL/Dolt connection + all SQL queries
  - data.py      → Pandas wrangling, hunk logic, matching engine
  - viz.py       → Plotly chart builders
  - app.py       → Streamlit UI orchestration (this file)
  - config.py    → Persistent KPI polarity config management

To connect to a real Dolt instance, update DB_CONFIG in db.py.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date, timedelta

# ── Local modules ──────────────────────────────────────────────────────
from db import (
    get_connection,
    discover_kpi_columns,
    discover_cell_groups,
    discover_parameters,
    get_current_param_value,
    fetch_kpi_data,
    fetch_dolt_log,
    fetch_dolt_diff,
    commit_action,
    rollback_action,
    create_parameter_sweep,
    advance_due_sweeps,
    get_sweeps,
    finalize_sweep,
    OPTIMIZER_TYPES,
)
from data import (
    build_action_hunks,
    build_action_hunks_by_cell,
    filter_log_df,
    compare_actions,
    resolve_eval_window,
    collect_matching_weekdays,
    collect_individual_days,
)
from viz import (
    plot_action_timeline,
    plot_kpi_trend,
    plot_kpi_trend_individual,
    plot_delta_bars,
    plot_action_comparison,
    build_summary_table,
)
from config import (
    load_config,
    save_config,
    config_path_str,
    load_param_kpi_map,
    save_param_kpi_map,
    load_kpi_groups,
    save_kpi_groups,
    load_param_groups,
    save_param_groups,
)

# ══════════════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ══════════════════════════════════════════════════════════════════════
if not st.session_state.get("_hub_mode", False):
    st.set_page_config(
        page_title="NetOps Impact Analyzer",
        page_icon="📡",
        layout="wide",
        initial_sidebar_state="expanded",
    )

# ── Inject custom CSS ──────────────────────────────────────────────────
st.markdown(
    """
<style>
:root {
    --navy:  #0d1b2a; --panel: #132338; --border: #1e3a5f;
    --cyan:  #00c8ff; --green: #00e599; --red:   #ff4d6d;
    --amber: #ffb347; --muted: #ffffff; --text:  #ffffff;
}
html, body, [data-testid="stAppViewContainer"] {
    background: var(--navy); color: var(--text);
    font-family: 'IBM Plex Mono', 'Courier New', monospace;
}
[data-testid="stSidebar"] {
    background: var(--panel) !important;
    border-right: 1px solid var(--border);
}
.section-header {
    font-size: .7rem; letter-spacing: .15em; text-transform: uppercase;
    color: var(--cyan); border-bottom: 1px solid var(--border);
    padding-bottom: 4px; margin-bottom: 12px;
}
.metric-tile {
    background: var(--panel); border: 1px solid var(--border);
    border-top: 3px solid var(--cyan); border-radius: 4px;
    padding: 16px 20px; margin-bottom: 8px;
}
.metric-tile .label {
    font-size: .65rem; letter-spacing: .12em; text-transform: uppercase;
    color: var(--muted);
}
.metric-tile .value { font-size: 1.5rem; font-weight: 700; color: var(--cyan); }
.alert-warn {
    background: rgba(255,200,0,.08); border: 1px solid rgba(255,200,0,.3);
    border-left: 4px solid #ffc800; border-radius: 4px;
    padding: 10px 16px; margin: 8px 0; font-size: .85rem; color: #ffc800;
}
.alert-info {
    background: rgba(0,200,255,.06); border: 1px solid rgba(0,200,255,.2);
    border-left: 4px solid var(--cyan); border-radius: 4px;
    padding: 10px 16px; margin: 8px 0; font-size: .85rem; color: var(--cyan);
}
.diff-table { width:100%; border-collapse:collapse; font-size:.8rem; }
.diff-table th {
    background: var(--border); color: var(--muted);
    padding: 4px 8px; text-align:left; font-weight:400;
    font-size:.65rem; letter-spacing:.1em; text-transform:uppercase;
}
.diff-table td { padding: 4px 8px; border-bottom: 1px solid var(--border); }
.diff-table .from { color: #ff4d6d; }
.diff-table .to   { color: #00e599; }
.save-badge {
    display:inline-block; background:rgba(0,229,153,.12);
    border:1px solid #00e599; color:#00e599; border-radius:3px;
    padding:2px 8px; font-size:.7rem; letter-spacing:.1em;
}
[data-testid="stPlotlyChart"] {
    border: 1px solid var(--border); border-radius: 4px;
}
[data-testid="stDataFrame"] { border: 1px solid var(--border) !important; }
label {
    color: var(--muted) !important; font-size: .75rem !important;
    letter-spacing: .08em; text-transform: uppercase;
}
#MainMenu, footer { visibility: hidden; }

    /* ── Global white text & readable sizes ── */
    .stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown div, .stMarkdown span,
    .stCaption, label, .stRadio, .stSelectbox, .stSlider, .stCheckbox,
    .stChatMessage, .stChatMessage p, .stChatMessage div {
        color: #ffffff !important;
    }
    .stDataFrame, .stDataFrame table, .stDataFrame td, .stDataFrame th {
        color: #ffffff !important;
        font-size: 0.9rem !important;
    }
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] .stMarkdown div,
    [data-testid="stSidebar"] .stCaption,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stRadio,
    [data-testid="stSidebar"] .stSelectbox,
    [data-testid="stSidebar"] .stSlider,
    [data-testid="stSidebar"] .stCheckbox,
    [data-testid="stSidebar"] .stChatMessage,
    [data-testid="stSidebar"] .stChatMessage p,
    [data-testid="stSidebar"] .stChatMessage div {
        color: #ffffff !important;
        font-size: 0.88rem !important;
    }
    .stChatMessage, .stChatMessage p, .stChatMessage div {
        font-size: 0.95rem !important;
    }
    .section-header { font-size: .85rem !important; }
    .metric-tile .label { font-size: .78rem !important; }
    .alert-warn, .alert-info { font-size: .9rem !important; }
</style>
""",
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════════════
#  CACHED LOADERS
# ══════════════════════════════════════════════════════════════════════


@st.cache_resource(show_spinner="Connecting to Dolt database…")
def _get_conn():
    return get_connection()


@st.cache_data(show_spinner="Discovering KPI schema…")
def _get_kpis(_conn):
    return discover_kpi_columns(_conn)


@st.cache_data(show_spinner="Reading Dolt commit log…")
def _get_log(_conn):
    return fetch_dolt_log(_conn)


@st.cache_data(show_spinner="Loading KPI time-series…")
def _get_kpi_data(_conn, start: str, end: str):
    return fetch_kpi_data(_conn, start, end)


@st.cache_data(show_spinner="Fetching diff metadata…")
def _get_diff(_conn, commit_hash: str, parent: str | None = None):
    return fetch_dolt_diff(_conn, commit_hash, parent)


@st.cache_data(show_spinner="Discovering cell topology…")
def _get_cell_groups(_conn):
    return discover_cell_groups(_conn)


def _get_parameters(_conn):
    # Not cached — parameter catalog is static but current values can
    # change after a commit/rollback within the same session.
    return discover_parameters(_conn)


# ══════════════════════════════════════════════════════════════════════
#  SIDEBAR — CONFIG + KPI POLARITY
# ══════════════════════════════════════════════════════════════════════


def render_sidebar(
    kpi_columns: list[str],
    saved_polarity: dict[str, str],
    param_names: list[str],
    saved_param_kpi_map: dict[str, list[str]],
    saved_kpi_groups: dict[str, list[str]],
    saved_param_groups: dict[str, list[str]],
):
    """
    Renders polarity controls loaded from kpi_config.json, plus editors
    for parameter⇄KPI relationships, KPI groups, and parameter groups.
    Detects changes and offers Save buttons per section.

    Returns: current_polarity_map
    """
    with st.sidebar:
        st.markdown("## 📡 NetOps Analyzer")

        # ── Connection info ────────────────────────────────────────────
        st.markdown(
            "<div class='section-header'>Database Connection</div>",
            unsafe_allow_html=True,
        )
        with st.expander("Connection config", expanded=False):
            st.code(
                "host : localhost\nport : 3306\nuser : root\ndb   : network_db",
                language="text",
            )

        st.markdown("---")

        # ── KPI Polarity ───────────────────────────────────────────────
        st.markdown(
            "<div class='section-header'>KPI Optimization Polarity</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "Loaded from `kpi_config.json`. Edit here and click **Save** "
            "to persist across restarts."
        )

        current_polarity: dict[str, str] = {}
        for kpi in kpi_columns:
            saved_val = saved_polarity.get(kpi, "higher")
            default_idx = 0 if saved_val == "lower" else 1
            choice = st.selectbox(
                label=kpi,
                options=["Lower is Better ↓", "Higher is Better ↑"],
                index=default_idx,
                key=f"polarity_{kpi}",
            )
            current_polarity[kpi] = "lower" if choice.startswith("Lower") else "higher"

        # ── Detect unsaved changes ─────────────────────────────────────
        has_changes = current_polarity != saved_polarity
        save_clicked = False

        if has_changes:
            st.markdown("---")
            st.markdown(
                "<div class='alert-warn'>⚠️  Unsaved polarity changes</div>",
                unsafe_allow_html=True,
            )
            save_clicked = st.button(
                "💾  Save Configuration",
                type="primary",
                width="stretch",
            )
            if save_clicked:
                save_config(current_polarity)
                st.markdown(
                    f"<div class='save-badge'>✓ Saved → {config_path_str()}</div>",
                    unsafe_allow_html=True,
                )
                st.rerun()
        else:
            st.markdown(
                f"<div style='font-size:.65rem;color:#1e3a5f;margin-top:8px'>"
                f"Config in sync · {config_path_str()}</div>",
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # ── Parameter ⇄ KPI relationships ────────────────────────────
        st.markdown(
            "<div class='section-header'>Parameter ⇄ KPI Relationships</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "Which KPIs each tunable parameter is believed to affect. "
            "Used to auto-suggest evaluation KPIs for commits & sweeps."
        )
        current_param_kpi_map: dict[str, list[str]] = {}
        with st.expander("Edit relationships", expanded=False):
            for p in param_names:
                current_param_kpi_map[p] = st.multiselect(
                    label=p,
                    options=kpi_columns,
                    default=[k for k in saved_param_kpi_map.get(p, []) if k in kpi_columns],
                    key=f"paramkpi_{p}",
                )
            if current_param_kpi_map != saved_param_kpi_map:
                if st.button("💾 Save Parameter⇄KPI Map", width="stretch"):
                    save_param_kpi_map(current_param_kpi_map)
                    st.rerun()

        # ── KPI groups ────────────────────────────────────────────────
        st.markdown(
            "<div class='section-header'>KPI Groups</div>", unsafe_allow_html=True
        )
        st.caption("Bundle strongly-related KPIs so they can be reviewed together.")
        with st.expander("Edit KPI groups", expanded=False):
            new_kpi_groups = dict(saved_kpi_groups)
            for gname, members in list(new_kpi_groups.items()):
                new_kpi_groups[gname] = st.multiselect(
                    label=f"Group: {gname}",
                    options=kpi_columns,
                    default=[k for k in members if k in kpi_columns],
                    key=f"kpigrp_{gname}",
                )
            with st.form("new_kpi_group_form", clear_on_submit=True):
                ng_name = st.text_input("New KPI group name")
                ng_members = st.multiselect("KPIs in group", options=kpi_columns)
                if st.form_submit_button("➕ Add Group") and ng_name:
                    new_kpi_groups[ng_name] = ng_members
                    save_kpi_groups(new_kpi_groups)
                    st.rerun()
            if new_kpi_groups != saved_kpi_groups:
                if st.button("💾 Save KPI Groups", width="stretch"):
                    save_kpi_groups(new_kpi_groups)
                    st.rerun()

        # ── Parameter groups ─────────────────────────────────────────
        st.markdown(
            "<div class='section-header'>Parameter Groups</div>", unsafe_allow_html=True
        )
        st.caption("Bundle parameters that are always changed together.")
        with st.expander("Edit parameter groups", expanded=False):
            new_param_groups = dict(saved_param_groups)
            for gname, members in list(new_param_groups.items()):
                new_param_groups[gname] = st.multiselect(
                    label=f"Group: {gname}",
                    options=param_names,
                    default=[p for p in members if p in param_names],
                    key=f"paramgrp_{gname}",
                )
            with st.form("new_param_group_form", clear_on_submit=True):
                npg_name = st.text_input("New parameter group name")
                npg_members = st.multiselect("Parameters in group", options=param_names)
                if st.form_submit_button("➕ Add Group") and npg_name:
                    new_param_groups[npg_name] = npg_members
                    save_param_groups(new_param_groups)
                    st.rerun()
            if new_param_groups != saved_param_groups:
                if st.button("💾 Save Parameter Groups", width="stretch"):
                    save_param_groups(new_param_groups)
                    st.rerun()

        st.markdown("---")
        st.markdown("<div class='section-header'>About</div>", unsafe_allow_html=True)
        st.caption(
            "Rolling evaluation window compared against aggregated "
            "same-weekday baselines. Commit hunks grouped by calendar date."
        )

    return current_polarity


# ══════════════════════════════════════════════════════════════════════
#  COMMIT DIFF PANEL  (Feature 3 — Metadata HUD)
# ══════════════════════════════════════════════════════════════════════


def render_hunk_hud(hunk: dict, conn) -> None:
    """
    Expandable panel below the hunk selector showing:
      - Full commit metadata (committer, email, time, hash)
      - dolt_diff table for each commit in the hunk
    """
    commits = hunk["commits"]
    with st.expander(
        f"🔍  Hunk Metadata & Diff — {hunk['date']}  ({hunk['n']} commit(s))",
        expanded=False,
    ):
        for idx, c in enumerate(commits):
            short = str(c.get("commit_hash", ""))[:10]
            ts = str(c.get("date", ""))[:19]
            committer = c.get("committer", "unknown")
            email = c.get("email", "—")
            msg = c.get("message", "—")

            st.markdown(
                f"**`{short}`**  ·  {ts}  ·  "
                f"<span style='color:#00c8ff'>{committer}</span>  "
                f"<span style='color:#6b8cae'>&lt;{email}&gt;</span>",
                unsafe_allow_html=True,
            )
            st.markdown(f"> {msg}")

            # Fetch diff for this commit
            parent = commits[idx - 1].get("commit_hash") if idx > 0 else None
            diff_rows = _get_diff(conn, c.get("commit_hash", ""), parent)

            if diff_rows:
                rows_html = "".join(
                    f"<tr>"
                    f"<td>{r.get('table', '—')}</td>"
                    f"<td>{r.get('column', '—')}</td>"
                    f"<td class='from'>{r.get('from_val', '—')}</td>"
                    f"<td class='to'>{r.get('to_val', '—')}</td>"
                    f"</tr>"
                    for r in diff_rows
                )
                st.markdown(
                    f"<table class='diff-table'>"
                    f"<tr><th>Table</th><th>Column</th>"
                    f"<th>From</th><th>To</th></tr>"
                    f"{rows_html}</table>",
                    unsafe_allow_html=True,
                )
            if idx < len(commits) - 1:
                st.markdown(
                    "<hr style='border-color:#1e3a5f;margin:12px 0'>",
                    unsafe_allow_html=True,
                )


# ══════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════


def main():
    # ── Header ────────────────────────────────────────────────────────
    col_title, col_tag = st.columns([4, 1])
    with col_title:
        st.markdown("# 📡 Network Optimization Impact Analyzer")
        st.caption(
            "Version-controlled telecom KPI analysis — "
            "powered by **Dolt** + **Streamlit**  ·  v2"
        )
    with col_tag:
        st.markdown(
            "<div style='text-align:right;padding-top:24px;"
            "font-size:.7rem;color:#6b8cae;letter-spacing:.1em'>"
            "DOLT · PYMYSQL · PLOTLY</div>",
            unsafe_allow_html=True,
        )
    st.markdown("---")

    # ── Connect ───────────────────────────────────────────────────────
    try:
        conn = _get_conn()
    except Exception as exc:
        st.error(f"**Cannot connect to Dolt database.**\n\n`{exc}`")
        st.stop()

    # ── Discover KPIs ─────────────────────────────────────────────────
    try:
        kpi_columns = _get_kpis(conn)
    except Exception as exc:
        st.error(f"**Schema discovery failed.**\n\n`{exc}`")
        st.stop()

    if not kpi_columns:
        st.warning("No numeric KPI columns found in `network_kpis`.")
        st.stop()

    # ── Load persisted polarity config ────────────────────────────────
    saved_polarity = load_config(kpi_columns)

    # ── Discover cells, parameters, and relationship configs ──────────
    cell_groups_map = _get_cell_groups(conn)
    all_cell_ids = sorted({c for cells in cell_groups_map.values() for c in cells})
    param_catalog = _get_parameters(conn)
    param_names = sorted(param_catalog.keys())

    saved_param_kpi_map = load_param_kpi_map(param_names, kpi_columns)
    saved_kpi_groups = load_kpi_groups()
    saved_param_groups = load_param_groups()

    # ── Advance any due parameter-sweep steps (automated commitments) ──
    advanced = advance_due_sweeps(conn)
    if advanced:
        _get_log.clear()
        _get_kpi_data.clear()
        for sw in advanced:
            if sw["status"] == "completed":
                st.toast(
                    f"✅ Sweep on {sw['cell_id']} · {sw['parameter']} finished — "
                    f"best value {sw['best_value']}",
                    icon="🎯",
                )
            else:
                st.toast(f"⚙️ Sweep step auto-committed on {sw['cell_id']} · {sw['parameter']}", icon="⚙️")

    # ── Sidebar (returns live UI state) ───────────────────────────────
    polarity_map = render_sidebar(
        kpi_columns, saved_polarity, param_names,
        saved_param_kpi_map, saved_kpi_groups, saved_param_groups,
    )

    # ── Load commit log ───────────────────────────────────────────────
    try:
        log_df_full = _get_log(conn)
    except Exception as exc:
        st.error(f"**Could not read `dolt_log`.**\n\n`{exc}`")
        st.stop()

    if log_df_full.empty:
        st.markdown(
            "<div class='alert-warn'>⚠️ No commits found in the Dolt log.</div>",
            unsafe_allow_html=True,
        )
        st.stop()

    # ════════════════════════════════════════════════════════════════
    #  FILTER BAR — cell group / cell / optimizer / action type / search
    # ════════════════════════════════════════════════════════════════
    st.markdown(
        "<div class='section-header'>🔎 Filters — Cell Group · Optimizer · Action Type</div>",
        unsafe_allow_html=True,
    )
    fc1, fc2, fc3, fc4, fc5 = st.columns([2, 2, 2, 2, 2])
    with fc1:
        f_cell_groups = st.multiselect(
            "Cell Group", options=sorted(cell_groups_map.keys())
        )
    with fc2:
        available_cells = (
            sorted({c for g in f_cell_groups for c in cell_groups_map.get(g, [])})
            if f_cell_groups else all_cell_ids
        )
        f_cell_ids = st.multiselect("Cell ID", options=available_cells)
    with fc3:
        f_optimizers = st.multiselect(
            "Optimizer", options=sorted(log_df_full.get("optimizer", pd.Series(dtype=str)).dropna().unique())
        )
    with fc4:
        f_action_types = st.multiselect(
            "Action Type", options=sorted(log_df_full.get("action_type", pd.Series(dtype=str)).dropna().unique())
        )
    with fc5:
        f_search = st.text_input("Search message / committer / parameter")

    log_df = filter_log_df(
        log_df_full,
        cell_groups=f_cell_groups or None,
        cell_ids=f_cell_ids or None,
        optimizers=f_optimizers or None,
        action_types=f_action_types or None,
        search_text=f_search or None,
    )

    if log_df.empty:
        st.markdown(
            "<div class='alert-warn'>⚠️ No commits match the current filters.</div>",
            unsafe_allow_html=True,
        )
        st.stop()

    hunks = build_action_hunks(log_df)
    if not hunks:
        st.markdown(
            "<div class='alert-warn'>⚠️ Could not build action hunks.</div>",
            unsafe_allow_html=True,
        )
        st.stop()

    # ════════════════════════════════════════════════════════════════
    #  SECTION 1 — ACTION TIMELINE (filterable, browsable)
    # ════════════════════════════════════════════════════════════════
    st.markdown(
        "<div class='section-header'>① Action Timeline — Commit Hunk Distribution</div>",
        unsafe_allow_html=True,
    )
    fig_timeline = plot_action_timeline(hunks)
    st.plotly_chart(fig_timeline, width="stretch")
    st.caption("Hover over a marker to see committer, timestamp, and message details.")

    with st.expander("📋 Browse commits (sortable / searchable table)", expanded=False):
        browse_df = log_df.copy()
        cols_order = [
            c for c in ["date", "cell_id", "cell_group", "action_type", "optimizer",
                        "committer", "parameter", "from_val", "to_val", "message", "commit_hash"]
            if c in browse_df.columns
        ]
        st.dataframe(
            browse_df[cols_order].sort_values("date", ascending=False),
            width="stretch",
            height=320,
        )

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════
    #  SECTION 2 — HUNK SELECTOR + EVAL WINDOW CONTROLS
    # ════════════════════════════════════════════════════════════════
    st.markdown(
        "<div class='section-header'>② Select Action Hunk & Evaluation Window</div>",
        unsafe_allow_html=True,
    )

    col_hunk, col_kpi, col_toggle = st.columns([2, 2, 1])

    with col_hunk:
        hunk_labels = [h["label"] for h in hunks]
        selected_label = st.selectbox(
            "Action Hunk (grouped by calendar date)",
            options=hunk_labels,
            index=len(hunk_labels) - 1,
        )
        selected_hunk = next(h for h in hunks if h["label"] == selected_label)
        action_date = selected_hunk["date"]
        is_last_hunk = selected_hunk is hunks[-1]

    with col_kpi:
        selected_kpi = st.selectbox("KPI to analyse", options=kpi_columns)
        polarity_label = (
            "↓ Lower is Better"
            if polarity_map[selected_kpi] == "lower"
            else "↑ Higher is Better"
        )
        st.markdown(
            f"<div class='alert-info'>Optimization target for <b>{selected_kpi}</b>: "
            f"<b>{polarity_label}</b></div>",
            unsafe_allow_html=True,
        )

    with col_toggle:
        st.markdown("<br>", unsafe_allow_html=True)
        ignore_next = st.checkbox(
            "Ignore Next Action Hunk",
            value=False,
            help=(
                "When checked, the evaluation window extends to today even if "
                "a later hunk exists, bypassing the automatic commit boundary cap."
            ),
        )

    # ── Resolve the rolling evaluation window ─────────────────────────
    after_start, after_end, next_hunk_date = resolve_eval_window(
        hunks, action_date, ignore_next_hunk=ignore_next
    )

    # ── Info tiles ────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f"<div class='metric-tile'><div class='label'>Action Date</div>"
            f"<div class='value'>{action_date}</div></div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"<div class='metric-tile'><div class='label'>After Window End</div>"
            f"<div class='value'>{after_end}</div></div>",
            unsafe_allow_html=True,
        )
    with c3:
        boundary_txt = (
            next_hunk_date if (next_hunk_date and not ignore_next) else "None (today)"
        )
        boundary_col = "#ffb347" if (next_hunk_date and not ignore_next) else "#6b8cae"
        st.markdown(
            f"<div class='metric-tile'><div class='label'>Next Hunk Cap</div>"
            f"<div class='value' style='color:{boundary_col};font-size:1.1rem'>"
            f"{boundary_txt}</div></div>",
            unsafe_allow_html=True,
        )
    with c4:
        weekday_name = datetime.strptime(action_date, "%Y-%m-%d").strftime("%A")
        st.markdown(
            f"<div class='metric-tile'><div class='label'>Matched Weekday</div>"
            f"<div class='value'>{weekday_name}</div></div>",
            unsafe_allow_html=True,
        )

    # ── Metadata HUD (Feature 3) ───────────────────────────────────────
    render_hunk_hud(selected_hunk, conn)

    # ── Fetch KPI data covering baseline window + after window ─────────
    # Baseline needs data 7 days before after_start (earliest possible)

    fetch_start = (
        datetime.strptime(after_start, "%Y-%m-%d") - timedelta(days=7)
    ).strftime("%Y-%m-%d")

    try:
        kpi_df = _get_kpi_data(conn, start=fetch_start, end=after_end)
    except Exception as exc:
        st.error(f"**KPI data fetch failed.**\n\n`{exc}`")
        st.stop()

    if kpi_df.empty:
        st.markdown(
            "<div class='alert-warn'>⚠️ No KPI data found in the selected window.</div>",
            unsafe_allow_html=True,
        )
        st.stop()

    # ── Restrict to the cell(s) currently in scope (filter bar / hunk) ─
    scope_cells = f_cell_ids or ([selected_hunk["cell_id"]] if "cell_id" in selected_hunk else available_cells)
    if "cell_id" in kpi_df.columns and scope_cells:
        kpi_df = kpi_df[kpi_df["cell_id"].isin(scope_cells)]

    if kpi_df.empty:
        st.markdown(
            "<div class='alert-warn'>⚠️ No KPI data for the selected cell(s).</div>",
            unsafe_allow_html=True,
        )
        st.stop()

    # ── Aggregate matching weekdays (Feature 2) ────────────────────────
    try:
        before_df, after_df, after_dates, before_dates = collect_matching_weekdays(
            kpi_df, after_start, after_end
        )
    except Exception as exc:
        st.error(f"**Period alignment failed.**\n\n`{exc}`")
        st.stop()

    if before_df.empty:
        st.markdown(
            f"<div class='alert-warn'>⚠️ No baseline data found for the matching "
            f"weekdays before <b>{after_start}</b>.</div>",
            unsafe_allow_html=True,
        )
        st.stop()

    if after_df.empty:
        st.markdown(
            f"<div class='alert-warn'>⚠️ No KPI data found in the After window "
            f"<b>{after_start}</b> → <b>{after_end}</b>.</div>",
            unsafe_allow_html=True,
        )
        st.stop()

    # Window summary line
    n_after = len(after_dates)
    n_before = len([d for d in before_dates if d])
    st.markdown(
        f"<div class='alert-info'>"
        f"Evaluation window: <b>{after_start}</b> → <b>{after_end}</b>  ·  "
        f"<b>{n_after}</b> After day(s) averaged against "
        f"<b>{n_before}</b> matching Before day(s)</div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════
    #  SECTION 3 — KPI TREND
    # ════════════════════════════════════════════════════════════════
    st.markdown(
        "<div class='section-header'>③ KPI Trend — Before vs After</div>",
        unsafe_allow_html=True,
    )

    # ── Controls row ──────────────────────────────────────────────────
    ctrl_a, ctrl_b, ctrl_c = st.columns([3, 2, 2])

    with ctrl_a:
        # Time-range slider — full day by default, constrained by commit caps
        # Show available window as [after_start 00:00 … after_end 23:59]
        # expressed in minutes-of-day since we only visualise a single day's
        # profile (minute_of_day 0-1439).
        time_range_vals = st.slider(
            "Time-of-day range",
            min_value=0,
            max_value=1439,
            value=(0, 1439),
            step=15,
            format="%d min",
            help=(
                "Restrict the x-axis to a sub-window of the day (0–1439 min).  "
                "Commit boundaries cap what window is available."
            ),
        )

        # Format as HH:MM for the caption
        def _fmt(m):
            return f"{m // 60:02d}:{m % 60:02d}"

        st.caption(f"Showing  {_fmt(time_range_vals[0])} → {_fmt(time_range_vals[1])}")

    # Open-ended windows (no next-hunk cap — typically the most recent
    # action) default to a simple two-line Before/After comparison
    # instead of a per-day trend, since averaging dozens/hundreds of
    # days into individual lines is unreadable and rarely useful.
    open_ended_window = next_hunk_date is None or ignore_next

    with ctrl_b:
        show_individual = st.checkbox(
            "Show days individually",
            value=(len(after_dates) > 1 and not open_ended_window),
            help=(
                "When checked, each After day is plotted separately against its "
                "matched Before day.  Days are grouped by weekday.  "
                "Uncheck to collapse back to the aggregated mean.  "
                "Defaults to OFF for open-ended windows (e.g. the most recent "
                "action with no next commit to cap it) to avoid a cluttered "
                "chart — you get a clean two-line Before/After comparison instead."
            ),
        )
        show_ma = False
        if not show_individual:
            show_ma = st.checkbox(
                "Also show moving-average trend line",
                value=not open_ended_window,
                help="Uncheck for a clean two-line Before/After comparison only.",
            )

    with ctrl_c:
        show_commits = st.checkbox(
            "Annotate commits on chart",
            value=True,
            help="Draw vertical markers, at their actual time of day, for every commit in the selected hunk.",
        )

    # ── Collect commits to annotate (all commits in selected hunk) ────
    commits_to_annotate = selected_hunk["commits"] if show_commits else None

    time_range = time_range_vals  # always pass the tuple

    # ── Render ────────────────────────────────────────────────────────
    if selected_kpi not in before_df.columns or selected_kpi not in after_df.columns:
        st.warning(f"KPI `{selected_kpi}` not available in the fetched data window.")

    elif show_individual and len(after_dates) > 1:
        # ── Individual-day mode ────────────────────────────────────────
        weekday_data = collect_individual_days(kpi_df, after_start, after_end)

        if not weekday_data:
            st.warning("No individual day data could be built for this window.")
        else:
            weekday_order = [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]
            present_weekdays = [w for w in weekday_order if w in weekday_data]
            # Also include any weekday not in the canonical list
            present_weekdays += [w for w in weekday_data if w not in weekday_order]

            fig_dict = plot_kpi_trend_individual(
                weekday_data,
                kpi=selected_kpi,
                time_range=time_range,
                commits_in_window=commits_to_annotate,
            )

            # Aggregate-per-weekday toggle
            agg_weekdays = st.checkbox(
                "Also show per-weekday aggregate overlay",
                value=False,
                help=(
                    "Adds a thick mean line on top of the individual day traces, "
                    "one per weekday group."
                ),
            )

            tabs = st.tabs(present_weekdays) if len(present_weekdays) > 1 else [None]

            for tab, weekday in zip(tabs, present_weekdays):
                ctx = tab if tab else st
                with ctx:
                    fig = fig_dict.get(weekday)
                    if fig:
                        if agg_weekdays:
                            # Add aggregate mean traces on top
                            day_data = weekday_data[weekday]
                            all_after = list(day_data["after_days"].values())
                            all_before = list(day_data["before_days"].values())

                            def _mean_frames(frames, col):
                                frames = [
                                    f
                                    for f in frames
                                    if not f.empty and col in f.columns
                                ]
                                if not frames:
                                    return pd.Series(dtype=float)
                                aligned = pd.concat(frames, axis=1).mean(axis=1)
                                return aligned

                            mean_after = _mean_frames(all_after, selected_kpi)
                            mean_before = _mean_frames(all_before, selected_kpi)

                            if not mean_after.empty:
                                if time_range:
                                    s, e = time_range
                                    mean_after = mean_after.loc[
                                        (mean_after.index >= s)
                                        & (mean_after.index <= e)
                                    ]
                                    mean_before = (
                                        mean_before.loc[
                                            (mean_before.index >= s)
                                            & (mean_before.index <= e)
                                        ]
                                        if not mean_before.empty
                                        else mean_before
                                    )

                                xt = [_fmt(m) for m in mean_after.index]
                                fig.add_trace(
                                    go.Scatter(
                                        x=xt,
                                        y=mean_after.round(4),
                                        mode="lines",
                                        name=f"Mean After ({weekday})",
                                        line=dict(color="#ffffff", width=3),
                                        opacity=0.85,
                                    )
                                )
                                if not mean_before.empty:
                                    xb = [_fmt(m) for m in mean_before.index]
                                    fig.add_trace(
                                        go.Scatter(
                                            x=xb,
                                            y=mean_before.round(4),
                                            mode="lines",
                                            name=f"Mean Before ({weekday})",
                                            line=dict(
                                                color="#ffb347", width=2, dash="dot"
                                            ),
                                            opacity=0.85,
                                        )
                                    )

                        st.plotly_chart(fig, width="stretch")
                    else:
                        st.info(f"No data for {weekday}.")

    else:
        # ── Aggregated mode (original behaviour) ───────────────────────
        fig_trend = plot_kpi_trend(
            before_df,
            after_df,
            selected_kpi,
            after_dates,
            before_dates,
            commits_in_window=commits_to_annotate,
            time_range=time_range,
            show_ma=show_ma,
        )
        st.plotly_chart(fig_trend, width="stretch")
        if open_ended_window and not show_individual:
            st.caption(
                "Open-ended evaluation window (no next action to cap it) — "
                "showing a simple two-line Before/After comparison rather than "
                f"averaging all {n_after} day(s) into a cluttered trend."
            )

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════
    #  SECTION 4 — DELTA BAR CHART
    # ════════════════════════════════════════════════════════════════
    st.markdown(
        "<div class='section-header'>④ Interval Delta — After minus Before</div>",
        unsafe_allow_html=True,
    )

    if selected_kpi in before_df.columns and selected_kpi in after_df.columns:
        fig_delta = plot_delta_bars(
            before_df,
            after_df,
            selected_kpi,
            polarity=polarity_map[selected_kpi],
        )
        st.plotly_chart(fig_delta, width="stretch")

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════
    #  SECTION 5 — SUMMARY TABLE
    # ════════════════════════════════════════════════════════════════
    st.markdown(
        "<div class='section-header'>⑤ KPI Impact Summary — All Metrics</div>",
        unsafe_allow_html=True,
    )

    summary_df = build_summary_table(before_df, after_df, kpi_columns, polarity_map)

    if summary_df.empty:
        st.info("No KPI summary could be computed for the selected window.")
    else:

        def color_status(val):
            if val == "🟢 Improved":
                return "color:#00e599;font-weight:bold"
            if val == "🔴 Degraded":
                return "color:#ff4d6d;font-weight:bold"
            return ""

        styled = summary_df.style.map(color_status, subset=["Status"]).format(
            {
                "Before Avg": "{:.4f}",
                "After Avg": "{:.4f}",
                "Abs Change": "{:+.4f}",
                "% Change": "{:+.2f}%",
            }
        )
        st.dataframe(styled, width="stretch", height=400)

        n_improved = (summary_df["Status"] == "🟢 Improved").sum()
        n_degraded = (summary_df["Status"] == "🔴 Degraded").sum()
        n_neutral = len(summary_df) - n_improved - n_degraded

        ci, cd, cn = st.columns(3)
        for col, label, val, color in [
            (ci, "Improved KPIs", n_improved, "#00e599"),
            (cd, "Degraded KPIs", n_degraded, "#ff4d6d"),
            (cn, "No Change", n_neutral, "#6b8cae"),
        ]:
            with col:
                st.markdown(
                    f"<div class='metric-tile'><div class='label'>{label}</div>"
                    f"<div class='value' style='color:{color}'>{val}</div></div>",
                    unsafe_allow_html=True,
                )

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════
    #  SECTION 6 — CROSS-ACTION / CROSS-CELL COMPARISON
    # ════════════════════════════════════════════════════════════════
    st.markdown(
        "<div class='section-header'>⑥ Comparison — Actions vs Actions, Cells vs Cells</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Compare several optimization actions on the same cell, or the same/"
        "similar action across different cells, for their effect on one KPI."
    )

    per_cell_hunks = build_action_hunks_by_cell(log_df)
    if not per_cell_hunks:
        st.info("No per-cell actions available to compare under the current filters.")
    else:
        cmp_c1, cmp_c2 = st.columns([3, 1])
        with cmp_c1:
            cmp_labels = [h["label"] for h in per_cell_hunks]
            chosen_labels = st.multiselect(
                "Actions to compare (2+)",
                options=cmp_labels,
                default=cmp_labels[-min(3, len(cmp_labels)):],
            )
        with cmp_c2:
            cmp_kpi = st.selectbox("KPI", options=kpi_columns, key="cmp_kpi")
            cmp_days = st.number_input("After-window length (days)", min_value=1, max_value=14, value=1)

        chosen_actions = [h for h in per_cell_hunks if h["label"] in chosen_labels]
        if len(chosen_actions) >= 2:
            cmp_dates = [a["date"] for a in chosen_actions]
            cmp_fetch_start = (
                datetime.strptime(min(cmp_dates), "%Y-%m-%d") - timedelta(days=7)
            ).strftime("%Y-%m-%d")
            cmp_fetch_end = (
                datetime.strptime(max(cmp_dates), "%Y-%m-%d") + timedelta(days=int(cmp_days))
            ).strftime("%Y-%m-%d")
            full_kpi_df = _get_kpi_data(conn, start=cmp_fetch_start, end=cmp_fetch_end)
            comparison_df = compare_actions(full_kpi_df, chosen_actions, cmp_kpi, eval_days=int(cmp_days))
            if comparison_df.empty:
                st.warning("Not enough data to compare the selected actions.")
            else:
                fig_cmp = plot_action_comparison(comparison_df, cmp_kpi, polarity_map.get(cmp_kpi, "higher"))
                st.plotly_chart(fig_cmp, width="stretch")
                st.dataframe(comparison_df, width="stretch")
        else:
            st.info("Select at least two actions to compare.")

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════
    #  SECTION 7 — ACTION COMMIT & ROLLBACK
    # ════════════════════════════════════════════════════════════════
    st.markdown(
        "<div class='section-header'>⑦ Action Commit &amp; Rollback</div>",
        unsafe_allow_html=True,
    )

    commit_c1, commit_c2 = st.columns([1, 1])
    with commit_c1:
        with st.form("commit_action_form"):
            st.markdown("**Commit a new action**")
            ca_cell = st.selectbox("Cell", options=all_cell_ids, key="ca_cell")
            ca_param = st.selectbox("Parameter", options=param_names, key="ca_param")
            ca_current = get_current_param_value(conn, ca_cell, ca_param)
            st.caption(f"Current value: `{ca_current}`")
            ca_value = st.text_input("New value", value=str(ca_current) if ca_current is not None else "")
            ca_msg = st.text_input("Commit message", value=f"Adjust {ca_param} on {ca_cell}")
            ca_submit = st.form_submit_button("✅ Commit Action", type="primary")
            if ca_submit:
                commit_action(conn, ca_cell, ca_param, ca_value, ca_msg, committer="you")
                _get_log.clear()
                _get_kpi_data.clear()
                st.success(f"Committed {ca_param} = {ca_value} on {ca_cell}.")
                st.rerun()

    with commit_c2:
        st.markdown("**Rollback a recent commit**")
        recent = log_df.sort_values("date", ascending=False).head(15)
        for _, r in recent.iterrows():
            rc1, rc2 = st.columns([4, 1])
            with rc1:
                st.markdown(
                    f"`{str(r['commit_hash'])[:8]}` · {r['date']} · "
                    f"**{r.get('cell_id','—')}** · {r.get('parameter','—')}: "
                    f"{r.get('from_val','—')} → {r.get('to_val','—')}  \n"
                    f"<span style='color:#6b8cae'>{r['message']}</span>",
                    unsafe_allow_html=True,
                )
            with rc2:
                if st.button("↩ Rollback", key=f"rb_{r['commit_hash']}"):
                    rollback_action(conn, r["commit_hash"], committer="you")
                    _get_log.clear()
                    _get_kpi_data.clear()
                    st.success(f"Rolled back {str(r['commit_hash'])[:8]}.")
                    st.rerun()

    st.markdown("---")

    # ════════════════════════════════════════════════════════════════
    #  SECTION 8 — GRADUAL PARAMETER SWEEP
    # ════════════════════════════════════════════════════════════════
    st.markdown(
        "<div class='section-header'>⑧ Parameter Sweep — Automated Step Optimization</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Incrementally step a parameter in fixed increments over a defined "
        "period. Each due step is auto-committed on load; once complete, the "
        "best-scoring value can be auto-committed as the permanent setting."
    )

    sweep_c1, sweep_c2 = st.columns([1, 1])
    with sweep_c1:
        with st.form("create_sweep_form"):
            st.markdown("**Configure a new sweep**")
            sw_cell = st.selectbox("Cell", options=all_cell_ids, key="sw_cell")
            sw_param = st.selectbox("Parameter", options=param_names, key="sw_param")
            sw_current = get_current_param_value(conn, sw_cell, sw_param)
            try:
                sw_default_start = float(sw_current)
            except (TypeError, ValueError):
                sw_default_start = 0.0
            sw_start = st.number_input("Start value", value=sw_default_start)
            sw_step = st.number_input("Step size", value=float(param_catalog.get(sw_param, {}).get("step") or 0.5))
            sw_n = st.number_input("Number of steps", min_value=2, max_value=20, value=5)
            sw_interval = st.number_input("Days between steps", min_value=1, max_value=30, value=3)
            sw_submit = st.form_submit_button("🚀 Start Sweep", type="primary")
            if sw_submit:
                create_parameter_sweep(
                    conn, sw_cell, sw_param, sw_start, sw_step, int(sw_n), int(sw_interval), committer="you"
                )
                st.success(f"Sweep started for {sw_param} on {sw_cell}.")
                st.rerun()

    with sweep_c2:
        st.markdown("**Active & completed sweeps**")
        sweeps = get_sweeps(conn)
        if not sweeps:
            st.info("No sweeps configured yet.")
        for sw in sweeps:
            done = sum(1 for s in sw["steps"] if s["executed"])
            st.markdown(
                f"`{sw['id']}` · **{sw['cell_id']} · {sw['parameter']}** · "
                f"status: **{sw['status']}** · {done}/{sw['n_steps']} steps executed"
            )
            step_rows = pd.DataFrame(sw["steps"])
            st.dataframe(step_rows, width="stretch", height=160)
            if sw["status"] == "completed":
                st.markdown(
                    f"🎯 Best value found: **{sw['best_value']}** "
                    f"(step {sw['best_step_index'] + 1}/{sw['n_steps']})"
                )
                if st.button("✅ Finalize — auto-commit best value", key=f"fin_{sw['id']}"):
                    finalize_sweep(conn, sw["id"])
                    _get_log.clear()
                    _get_kpi_data.clear()
                    st.success("Best value committed.")
                    st.rerun()
            st.markdown("---")

    # ── Footer ────────────────────────────────────────────────────────
    st.markdown(
        "<div style='text-align:center;padding:32px 0 8px;font-size:.8rem;"
        "letter-spacing:.12em;color:#ffffff;text-transform:uppercase'>"
        "NetOps Impact Analyzer v2  ·  Dolt Version-Controlled Database</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
