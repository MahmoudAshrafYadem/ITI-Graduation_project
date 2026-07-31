# ============================================================
# 4G(LTE)/5G(NR) KPI Degradation Analyzer Tool — Streamlit UI
# ============================================================
# Full-featured web dashboard for RAN KPI degradation analysis.
# Features: degradation analysis, dashboard charts, trend view,
# anomaly detection, and multi-format exports (CSV, Excel, Word).
# ============================================================

from __future__ import annotations

import io
import os
import sys
import tempfile
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import streamlit as st

warnings.filterwarnings("ignore", message=".*Matplotlib GUI.*", category=UserWarning)

# Ensure the app directory is on sys.path for sibling imports
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from KPI_Configuration import (
    KPI_CONFIGS, CELL_ID_COLS, DATE_COL, SITE_COL, CELL_COL,
    LOCAL_CELL_COL, BASELINE_MODE_LAST_WEEK, BASELINE_MODE_4WEEK_AVG,
)
from clean_excel_and_helpers import clean_numeric_series, find_matching_column
from main_function_for_selected_kpi import analyze_selected_kpi
from combined_degraded_kpi import analyze_all_kpis, get_clean_data_for_dashboard
from Visualization_Functions import KPI_SHORT_NAMES, KPI_LIST
from anomaly_detection import detect_kpi_anomalies_last_day
from Generate_Word_Report import generate_word_report, DOCX_AVAILABLE
from Save_Results import combine_not_calculated_cells, remove_anomaly_cells, date_first

# ============================================================
# Page Configuration
# ============================================================
if not st.session_state.get("_hub_mode", False):
    st.set_page_config(
        page_title="4G(LTE)/5G(NR) KPI Degradation Analyzer",
        page_icon="📡",
        layout="wide",
        initial_sidebar_state="expanded",
    )

# ============================================================
# Global Styles
# ============================================================
st.markdown("""
<style>
/* ── Core palette ── */
:root {
    --accent:      #00C2FF;
    --accent2:     #7B61FF;
    --success:     #00D97E;
    --warning:     #FFB400;
    --danger:      #FF4D4D;
    --bg-card:     rgba(255,255,255,0.04);
    --border:      rgba(0,194,255,0.18);
}

/* ── Hero banner ── */
.kpi-hero {
    background: linear-gradient(135deg, #0A1628 0%, #0E2448 50%, #0A1628 100%);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 28px 36px 22px;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
}
.kpi-hero::before {
    content: "";
    position: absolute;
    inset: 0;
    background: radial-gradient(ellipse at 70% 50%, rgba(0,194,255,0.06) 0%, transparent 70%);
    pointer-events: none;
}
.kpi-hero h1 {
    font-size: 1.85rem;
    font-weight: 800;
    margin: 0 0 4px;
    background: linear-gradient(90deg, #00C2FF, #7B61FF);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.5px;
}
.kpi-hero .subtitle {
    font-size: 0.88rem;
    color: rgba(255,255,255,0.85);
    margin: 0;
    letter-spacing: 0.3px;
}
.kpi-hero .badge-row {
    display: flex;
    gap: 8px;
    margin-top: 14px;
    flex-wrap: wrap;
}
.kpi-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(0,194,255,0.12);
    border: 1px solid rgba(0,194,255,0.3);
    color: #00C2FF;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.3px;
}
.kpi-badge.purple {
    background: rgba(123,97,255,0.12);
    border-color: rgba(123,97,255,0.3);
    color: #7B61FF;
}
.kpi-badge.green {
    background: rgba(0,217,126,0.12);
    border-color: rgba(0,217,126,0.3);
    color: #00D97E;
}

/* ── Metric cards ── */
.metric-row {
    display: grid;
    gap: 14px;
    margin: 18px 0;
}
.metric-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px 18px;
    position: relative;
    overflow: hidden;
}
.metric-card::after {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
}
.metric-card .m-label {
    font-size: 0.73rem;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: rgba(255,255,255,0.85);
    margin-bottom: 6px;
}
.metric-card .m-value {
    font-size: 1.6rem;
    font-weight: 800;
    color: #fff;
    line-height: 1;
}
.metric-card .m-value.accent { color: var(--accent); }
.metric-card .m-value.success { color: var(--success); }
.metric-card .m-value.danger  { color: var(--danger); }
.metric-card .m-value.warning { color: var(--warning); }

/* ── Section headers ── */
.section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 24px 0 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
}
.section-header .icon {
    width: 32px; height: 32px;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.95rem;
}
.section-header h3 {
    margin: 0;
    font-size: 1.05rem;
    font-weight: 700;
    color: #fff;
    letter-spacing: -0.2px;
}

/* ── Severity chips in tables ── */
.sev-critical { color: #FF4D4D; font-weight: 700; }
.sev-high     { color: #FF8C00; font-weight: 700; }
.sev-medium   { color: #FFB400; font-weight: 600; }
.sev-normal   { color: #00D97E; font-weight: 600; }

/* ── Empty state ── */
.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: rgba(255,255,255,0.8);
}
.empty-state .es-icon { font-size: 3.5rem; margin-bottom: 14px; }
.empty-state h3 {
    font-size: 1.1rem;
    color: #ffffff;
    margin-bottom: 8px;
}
.empty-state p {
    font-size: 0.85rem;
    max-width: 380px;
    margin: 0 auto;
    line-height: 1.6;
}

/* ── Sidebar polish ── */
[data-testid="stSidebar"] {
    background: #0A1628 !important;
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] .stButton > button {
    border-radius: 8px;
    font-weight: 600;
    letter-spacing: 0.2px;
    transition: all .2s;
}
[data-testid="stSidebar"] .stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 15px rgba(0,194,255,0.3);
}
.sidebar-logo {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 0 4px;
    margin-bottom: 6px;
}
.sidebar-logo .logo-icon {
    font-size: 1.5rem;
    background: linear-gradient(135deg, #00C2FF, #7B61FF);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.sidebar-logo .logo-text {
    font-size: 0.82rem;
    font-weight: 700;
    color: rgba(255,255,255,0.85);
    line-height: 1.3;
    letter-spacing: 0.2px;
}
.sidebar-section {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: #ffffff;
    padding: 16px 0 6px;
    border-bottom: 1px solid rgba(255,255,255,0.15);
    margin-bottom: 10px;
}

/* ── Tab strip ── */
[data-testid="stTabs"] [role="tablist"] {
    border-bottom: 2px solid var(--border);
    gap: 2px;
}
[data-testid="stTabs"] [role="tab"] {
    border-radius: 6px 6px 0 0;
    font-weight: 600;
    font-size: 0.82rem;
    letter-spacing: 0.2px;
    padding: 8px 16px;
}
[data-testid="stTabs"] [aria-selected="true"] {
    background: rgba(0,194,255,0.1) !important;
    color: var(--accent) !important;
    border-bottom: 2px solid var(--accent);
}

/* ── Info/success/warning callout ── */
.callout {
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 0.85rem;
    margin: 10px 0;
    display: flex;
    align-items: flex-start;
    gap: 10px;
}
.callout.success {
    background: rgba(0,217,126,0.08);
    border-left: 3px solid var(--success);
    color: rgba(255,255,255,0.8);
}
.callout.info {
    background: rgba(0,194,255,0.07);
    border-left: 3px solid var(--accent);
    color: rgba(255,255,255,0.75);
}
.callout.warning {
    background: rgba(255,180,0,0.08);
    border-left: 3px solid var(--warning);
    color: rgba(255,255,255,0.8);
}
    .callout.danger {
        background: rgba(255,77,77,0.08);
        border-left: 3px solid var(--danger);
        color: rgba(255,255,255,0.8);
    }

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
</style>
""", unsafe_allow_html=True)

# ============================================================
# Chart Helpers
# ============================================================
PALETTE = {
    "blue":    "#00C2FF",
    "purple":  "#7B61FF",
    "green":   "#00D97E",
    "orange":  "#FF8C00",
    "red":     "#FF4D4D",
    "yellow":  "#FFB400",
    "muted":   "#4A5568",
}

SEVERITY_COLORS = {
    "Critical": "#FF4D4D",
    "High":     "#FF8C00",
    "Medium":   "#FFB400",
    "Normal":   "#00D97E",
    "N/A":      "#4A5568",
}
CONFIDENCE_COLORS = {
    "High":   "#00D97E",
    "Medium": "#FFB400",
    "Low":    "#FF4D4D",
    "N/A":    "#4A5568",
}

def _apply_chart_style(fig, ax):
    """Apply consistent dark theme to a matplotlib figure."""
    fig.patch.set_facecolor("#0A1628")
    ax.set_facecolor("#0D1E35")
    # Use (r,g,b,a) tuples — matplotlib does not accept CSS rgba() strings
    ax.tick_params(colors=(1, 1, 1, 0.75), labelsize=8)
    ax.xaxis.label.set_color((1, 1, 1, 0.75))
    ax.yaxis.label.set_color((1, 1, 1, 0.75))
    ax.title.set_color("#FFFFFF")
    for spine in ax.spines.values():
        spine.set_edgecolor((1, 1, 1, 0.15))
    ax.grid(True, color=(1, 1, 1, 0.08), linewidth=0.6)

def _apply_chart_style_multi(fig, axes):
    for ax in (axes if hasattr(axes, "__iter__") else [axes]):
        _apply_chart_style(fig, ax)

# ============================================================
# Cached Data Helpers (avoid recomputation on widget reruns)
# ============================================================
@st.cache_data
def _prepare_trend_data(_original_df, _trend_kpi, _deg_ids_tuple, _date_col, _site_col, _cell_col):
    df_trend = _original_df.copy()
    df_trend[_date_col] = pd.to_datetime(df_trend[_date_col], errors="coerce")
    df_trend = df_trend.dropna(subset=[_date_col, _trend_kpi])
    df_trend[_trend_kpi] = pd.to_numeric(df_trend[_trend_kpi], errors="coerce")
    daily_before = df_trend.groupby(_date_col)[_trend_kpi].mean().reset_index()
    deg_ids = set(_deg_ids_tuple)
    if _site_col in df_trend.columns and _cell_col in df_trend.columns:
        mask_deg = df_trend.set_index([_site_col, _cell_col]).index.isin(deg_ids)
        df_clean_t = df_trend[~mask_deg]
    else:
        df_clean_t = df_trend
    daily_after = (
        df_clean_t.groupby(_date_col)[_trend_kpi].mean().reset_index()
        if len(df_clean_t) > 0 else daily_before.copy()
    )
    return daily_before, daily_after

@st.cache_data
def _prepare_cell_data(_original_df, _site, _cell, _kpi, _date_col, _site_col, _cell_col):
    cell_df = _original_df[
        (_original_df[_site_col] == _site) &
        (_original_df[_cell_col] == _cell) &
        _original_df[_kpi].notna()
    ].copy()
    cell_df[_date_col] = pd.to_datetime(cell_df[_date_col], errors="coerce")
    cell_df[_kpi] = pd.to_numeric(cell_df[_kpi], errors="coerce")
    cell_df = cell_df.dropna(subset=[_date_col, _kpi]).sort_values(_date_col)
    return cell_df

@st.cache_data
def _get_cell_list(_original_df, _site, _site_col, _cell_col):
    return sorted(
        _original_df.loc[_original_df[_site_col] == _site, _cell_col]
        .dropna().unique().tolist()
    )

# ============================================================
# Session State Initialization
# ============================================================
_STATE_KEYS = [
    "output_df", "original_df", "summary_df", "analysis_mode",
    "quarantine_df", "incomplete_df", "anomalies_df", "degraded_cell_ids",
    "all_outputs", "clean_cells_df",
]
for _k in _STATE_KEYS:
    if _k not in st.session_state:
        st.session_state[_k] = None if _k != "analysis_mode" else "single"
if st.session_state.degraded_cell_ids is None:
    st.session_state.degraded_cell_ids = set()

# ============================================================
# Sidebar
# ============================================================
with st.sidebar:
    st.markdown("""
    <div class="sidebar-logo">
        <span class="logo-icon">📡</span>
        <span class="logo-text">4G(LTE)/5G(NR)<br>KPI Analyzer</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section">📂 Data Source</div>', unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Upload Excel File",
        type=["xlsx", "xls"],
        help="Upload your RAN KPI data in Excel format (.xlsx / .xls)",
        label_visibility="collapsed",
    )

    sheet_name = None
    if uploaded_file:
        xl = pd.ExcelFile(uploaded_file)
        sheet_name = st.selectbox("Sheet", xl.sheet_names, index=0)

    st.markdown('<div class="sidebar-section">⚙️ Analysis Settings</div>', unsafe_allow_html=True)

    kpi_options = list(KPI_CONFIGS.keys()) + ["--- Analyze All KPIs ---"]
    selected_kpi = st.selectbox(
        "KPI",
        options=kpi_options,
        index=0,
        key="kpi_select",
    )
    analyze_all = selected_kpi == "--- Analyze All KPIs ---"
    if analyze_all:
        config = KPI_CONFIGS[kpi_options[0]]
    else:
        config = KPI_CONFIGS[selected_kpi]

    col_days, col_thr = st.columns(2)
    with col_days:
        num_days = st.number_input("Days", min_value=1, max_value=14, value=4, help="Number of recent comparison days")
    with col_thr:
        threshold = st.number_input("Threshold %", min_value=0.0, max_value=100.0, value=config["default_threshold"], help="Degradation threshold percentage")

    require_complete_days = st.checkbox("Require complete days only", value=True)
    enable_significance_test = st.checkbox("Enable t-test significance filter", value=True)

    st.markdown('<div class="sidebar-section">📐 Baseline Mode</div>', unsafe_allow_html=True)

    baseline_mode = st.radio(
        "Baseline",
        options=[BASELINE_MODE_LAST_WEEK, BASELINE_MODE_4WEEK_AVG],
        format_func=lambda x: (
            "Same weekdays — last week" if x == BASELINE_MODE_LAST_WEEK
            else "Historical Weekday Median"
        ),
        label_visibility="collapsed",
    )

    num_baseline_weeks = 4
    if baseline_mode == BASELINE_MODE_4WEEK_AVG:
        num_baseline_weeks = st.number_input(
            "Lookback weeks",
            min_value=1, max_value=12, value=4,
            help="How many prior weeks to include in the Historical Weekday Median baseline",
        )

    st.divider()

    if uploaded_file:
        run_analysis = st.button(
            "▶  Run Analysis",
            type="primary",
            use_container_width=True,
            help="Run selected KPI or Analyze All KPIs",
        )
        run_anomalies = st.button(
            "🔍  Detect Anomalies",
            use_container_width=True,
            help="Run statistical anomaly detection on the last day",
        )
    else:
        run_analysis = run_anomalies = False
        st.markdown(
            '<div class="callout info">⬆️ Upload an Excel file above to begin analysis.</div>',
            unsafe_allow_html=True,
        )

    st.divider()
    st.caption("Musketeers Team · ITI Graduation 2026")

# ============================================================
# Hero Banner
# ============================================================
st.markdown("""
<div class="kpi-hero">
    <h1>4G(LTE)/5G(NR) KPI Degradation Analyzer Tool</h1>
    <p class="subtitle">Advanced RAN performance monitoring — detect, classify & localize KPI degradations across your network</p>
    <div class="badge-row">
        <span class="kpi-badge">📡 Multi-KPI</span>
        <span class="kpi-badge purple">📊 Statistical t-Test</span>
        <span class="kpi-badge green">🔍 Anomaly Detection</span>
        <span class="kpi-badge purple">📄 Word &amp; Excel Export</span>
        <span class="kpi-badge">🕒 Historical Weekday Median</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# Load Data & Run Analysis
# ============================================================
df = None
progress_bar = st.progress(0, text="Ready")
progress_text = st.empty()
if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
        st.session_state.original_df = df.copy()
        progress_bar.progress(10, text="Data loaded")
        progress_text.caption("Data loaded successfully")

        # Quick data overview row
        ov1, ov2, ov3, ov4, ov5 = st.columns(5)
        ov1.metric("Rows", f"{len(df):,}")
        ov2.metric("Columns", len(df.columns))
        ov3.metric("KPI", "All KPIs" if analyze_all else selected_kpi[:20])
        ov4.metric("Threshold", f"{threshold:.1f}%")
        ov5.metric("Baseline Mode",
                   "Last Week" if baseline_mode == BASELINE_MODE_LAST_WEEK else "Hist. Median")

        # ── Run Analysis ──
        if run_analysis:
            if analyze_all:
                progress_bar.progress(20, text="Analyzing all KPIs…")
                progress_text.caption("Running multi-KPI degradation analysis...")
                with st.spinner("Analyzing all KPIs…"):
                    combined, outputs, summary_df, quarantine_df, incomplete_df = analyze_all_kpis(
                        df=df,
                        num_days=int(num_days),
                        require_complete_days=require_complete_days,
                        baseline_mode=baseline_mode,
                        num_baseline_weeks=num_baseline_weeks,
                        enable_significance_test=enable_significance_test,
                        log_callback=lambda m: None,
                    )
                    st.session_state.output_df = combined
                    st.session_state.summary_df = summary_df
                    st.session_state.all_outputs = outputs
                    st.session_state.analysis_mode = "all"
                    st.session_state.quarantine_df = quarantine_df
                    st.session_state.incomplete_df = incomplete_df
                    st.session_state.degraded_cell_ids = set()
                    if not combined.empty and SITE_COL in combined.columns and CELL_COL in combined.columns:
                        st.session_state.degraded_cell_ids = set(zip(combined[SITE_COL], combined[CELL_COL]))
                    if st.session_state.degraded_cell_ids and SITE_COL in df.columns and CELL_COL in df.columns:
                        mask = df.set_index([SITE_COL, CELL_COL]).index.isin(st.session_state.degraded_cell_ids)
                        st.session_state.clean_cells_df = df[~mask].copy()
                    else:
                        st.session_state.clean_cells_df = df.copy()
                    progress_bar.progress(70, text="Analysis complete")
                    progress_text.caption("Multi-KPI analysis completed")
                    st.markdown(
                        f'<div class="callout success">✅ Full analysis complete — '
                        f'<strong>{len(combined)}</strong> total degraded cells across '
                        f'<strong>{len(summary_df)}</strong> KPIs</div>',
                        unsafe_allow_html=True,
                    )
            else:
                progress_bar.progress(20, text=f"Analyzing {selected_kpi}…")
                progress_text.caption(f"Running degradation analysis for {selected_kpi}...")
                with st.spinner(f"Analyzing {selected_kpi}…"):
                    output_df, metadata = analyze_selected_kpi(
                        df=df,
                        selected_kpi_name=selected_kpi,
                        num_days=int(num_days),
                        degradation_threshold=float(threshold),
                        require_complete_days=require_complete_days,
                        baseline_mode=baseline_mode,
                        num_baseline_weeks=num_baseline_weeks,
                        enable_significance_test=enable_significance_test,
                        log_callback=lambda m: None,
                    )
                    st.session_state.output_df = output_df
                    st.session_state.analysis_mode = "single"
                    st.session_state.quarantine_df = metadata.get("quarantine_df")
                    st.session_state.incomplete_df = metadata.get("incomplete_df")
                    st.session_state.degraded_cell_ids = set()
                    if not output_df.empty and SITE_COL in output_df.columns and CELL_COL in output_df.columns:
                        st.session_state.degraded_cell_ids = set(zip(output_df[SITE_COL], output_df[CELL_COL]))
                    if st.session_state.degraded_cell_ids and SITE_COL in df.columns and CELL_COL in df.columns:
                        mask = df.set_index([SITE_COL, CELL_COL]).index.isin(st.session_state.degraded_cell_ids)
                        st.session_state.clean_cells_df = df[~mask].copy()
                    else:
                        st.session_state.clean_cells_df = df.copy()
                    st.session_state.summary_df = None
                    st.session_state.all_outputs = {}
                    progress_bar.progress(70, text="Analysis complete")
                    progress_text.caption("Single KPI analysis completed")
                    st.markdown(
                        f'<div class="callout success">✅ Analysis complete — '
                        f'<strong>{len(output_df)}</strong> degraded cells found &nbsp;|&nbsp; '
                        f'Recent: {metadata.get("recent_start","?")} → {metadata.get("recent_end","?")} &nbsp;|&nbsp; '
                        f'Baseline: {metadata.get("baseline_start","?")} → {metadata.get("baseline_end","?")}</div>',
                        unsafe_allow_html=True,
                    )

        # ── Detect Anomalies ──
        if run_anomalies:
            progress_bar.progress(75, text="Detecting anomalies…")
            progress_text.caption("Running anomaly detection on last day...")
            with st.spinner("Detecting anomalies…"):
                anomalies_df = detect_kpi_anomalies_last_day(
                    df=df,
                    output_path=None,
                    lookback_weeks=4,
                    log_callback=lambda m: None,
                )
                st.session_state.anomalies_df = anomalies_df
                progress_bar.progress(90, text="Anomaly detection complete")
                progress_text.caption("Anomaly detection completed")
                callout_class = "success" if len(anomalies_df) == 0 else "warning"
                callout_msg = "✅ No anomalies detected." if len(anomalies_df) == 0 else f"⚠️ {len(anomalies_df)} anomalies detected on the last day."
                st.markdown(
                    f'<div class="callout {callout_class}">{callout_msg}</div>',
                    unsafe_allow_html=True,
                )

        if run_analysis or run_anomalies:
            progress_bar.progress(100, text="Pipeline complete")
            progress_text.caption("All pipeline stages completed successfully")
            import time
            time.sleep(0.5)
            progress_bar.empty()
            progress_text.empty()

    except Exception as e:
        progress_bar.progress(0, text="Error occurred")
        progress_text.caption(f"Error: {str(e)}")
        st.markdown(f'<div class="callout danger">❌ Error loading data: {e}</div>', unsafe_allow_html=True)
        import traceback
        with st.expander("Error details"):
            st.exception(e)

# ============================================================
# No Data — Welcome Screen
# ============================================================
if st.session_state.output_df is None or st.session_state.output_df.empty:
    if not uploaded_file:
        st.markdown("""
        <div class="empty-state">
            <div class="es-icon">📂</div>
            <h3>No data loaded yet</h3>
            <p>Upload an LTE/NR KPI Excel file using the sidebar to get started.
               The tool will automatically detect KPI columns and run the degradation pipeline.</p>
        </div>
        """, unsafe_allow_html=True)

        # Feature cards
        fc1, fc2, fc3, fc4 = st.columns(4)
        for col, icon, title, desc in [
            (fc1, "🎯", "Degradation Detection", "Threshold + t-test based cell scoring with severity tiers"),
            (fc2, "📊", "Dashboard & Charts", "KPI breakdown, root-cause distribution, confidence pie"),
            (fc3, "📈", "Trend Analysis", "Before/after enhancement potential with per-cell drill-down"),
            (fc4, "🔍", "Anomaly Detection", "Zero-value and spike anomalies over 4-week rolling baseline"),
        ]:
            col.markdown(f"""
            <div class="metric-card" style="text-align:center;padding:20px 14px">
                <div style="font-size:2rem;margin-bottom:10px">{icon}</div>
                <div style="font-weight:700;color:#fff;margin-bottom:6px;font-size:0.9rem">{title}</div>
                <div style="font-size:0.78rem;color:rgba(255,255,255,0.5);line-height:1.5">{desc}</div>
            </div>
            """, unsafe_allow_html=True)
    st.stop()

# ============================================================
# Results Tabs
# ============================================================
tabs = st.tabs([
    "📋  Summary",
    "📊  Dashboard",
    "📈  Trends",
    "🔍  Anomalies",
    "📁  Exports",
])

# ──────────────────────────────────────────────────────────────
# TAB 1 — Summary / Degraded Cells
# ──────────────────────────────────────────────────────────────
with tabs[0]:
    if st.session_state.analysis_mode == "all" and st.session_state.summary_df is not None:
        sum_df = st.session_state.summary_df
        st.markdown('<div class="section-header"><div class="icon">📋</div><h3>KPI Summary</h3></div>', unsafe_allow_html=True)
        _sum_display = [c for c in sum_df.columns if c != "error"]
        st.dataframe(sum_df[_sum_display], use_container_width=True)
    else:
        output_df = st.session_state.output_df

        st.markdown('<div class="section-header"><div class="icon">🎯</div><h3>Degraded Cell Results</h3></div>', unsafe_allow_html=True)

        # Filters row
        ff1, ff2, ff3, ff4 = st.columns([2, 2, 2, 1])
        with ff1:
            site_filter = st.text_input("🔎 Site", key="site_filter", placeholder="Filter by site name…")
        with ff2:
            cell_filter = st.text_input("🔎 Cell", key="cell_filter", placeholder="Filter by cell ID…")
        with ff3:
            sev_options = ["All"]
            if "rf_severity" in output_df.columns:
                sev_options += sorted(output_df["rf_severity"].dropna().unique().tolist())
            severity_filter = st.selectbox("Severity", sev_options, key="sev_filter")
        with ff4:
            show_deg_slider = st.checkbox("Deg. Range", value=False, key="show_deg_slider")

        deg_min, deg_max = 0.0, 100.0
        if show_deg_slider and "kpi_degradation_ratio_%" in output_df.columns:
            real_max = float(output_df["kpi_degradation_ratio_%"].max())
            deg_min, deg_max = st.slider(
                "Degradation Range (%)",
                0.0, max(100.0, real_max),
                (0.0, max(100.0, real_max)),
                key="degradation_slider",
            )

        # Apply filters
        filtered_df = output_df.copy()
        if site_filter and SITE_COL in filtered_df.columns:
            filtered_df = filtered_df[filtered_df[SITE_COL].str.contains(site_filter, case=False, na=False)]
        if cell_filter and CELL_COL in filtered_df.columns:
            filtered_df = filtered_df[filtered_df[CELL_COL].str.contains(cell_filter, case=False, na=False)]
        if severity_filter != "All" and "rf_severity" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["rf_severity"] == severity_filter]
        if show_deg_slider and "kpi_degradation_ratio_%" in filtered_df.columns:
            filtered_df = filtered_df[
                (filtered_df["kpi_degradation_ratio_%"] >= deg_min) &
                (filtered_df["kpi_degradation_ratio_%"] <= deg_max)
            ]

        # Summary metrics
        if len(filtered_df) > 0:
            sm1, sm2, sm3, sm4 = st.columns(4)
            sm1.metric("Degraded Cells", len(filtered_df))
            if "kpi_degradation_ratio_%" in filtered_df.columns:
                sm2.metric("Max Degradation", f"{filtered_df['kpi_degradation_ratio_%'].max():.2f}%")
                sm3.metric("Avg Degradation", f"{filtered_df['kpi_degradation_ratio_%'].mean():.2f}%")
            if "stat_significant" in filtered_df.columns:
                sm4.metric("Statistically Significant", int(filtered_df["stat_significant"].sum()))

        st.caption(f"Showing **{len(filtered_df)}** of **{len(output_df)}** degraded cells")

        _hide = ["day_by_day_degradations", "baseline_fallback_used",
                 "baseline_fallback_source", "baseline_fallback_value"]
        display_cols = [c for c in filtered_df.columns if c not in _hide]
        st.dataframe(
            filtered_df[display_cols],
            use_container_width=True,
            height=430,
        )

# ──────────────────────────────────────────────────────────────
# TAB 2 — Dashboard
# ──────────────────────────────────────────────────────────────
with tabs[1]:
    output_df = st.session_state.output_df

    st.markdown('<div class="section-header"><div class="icon">📊</div><h3>Analysis Dashboard</h3></div>', unsafe_allow_html=True)

    # Row 1: Degraded per KPI  +  Severity breakdown
    r1c1, r1c2 = st.columns([3, 2])

    with r1c1:
        if st.session_state.analysis_mode == "all" and st.session_state.summary_df is not None:
            plot_df = (
                st.session_state.summary_df
                .sort_values("degraded_cells_count", ascending=False)
                .head(13)
            )
            fig, ax = plt.subplots(figsize=(9, 5))
            colors = [PALETTE["blue"] if i < 3 else PALETTE["purple"] for i in range(len(plot_df))]
            bars = ax.bar(plot_df["kpi_name"], plot_df["degraded_cells_count"],
                          color=colors, edgecolor="none", width=0.65)
            ax.set_title("Degraded Cells per KPI", fontweight="bold", fontsize=12, pad=10)
            ax.set_ylabel("Cell Count", fontsize=9)
            plt.xticks(rotation=45, ha="right", fontsize=8)
            for bar in bars:
                h = bar.get_height()
                if h > 0:
                    ax.text(bar.get_x() + bar.get_width() / 2, h + 0.3,
                            f"{int(h)}", ha="center", va="bottom", fontsize=8,
                            fontweight="bold", color="#fff")
            _apply_chart_style(fig, ax)
            fig.tight_layout()
            st.pyplot(fig)
            plt.close(fig)
        else:
            if "kpi_degradation_ratio_%" in output_df.columns:
                top10 = output_df.nlargest(10, "kpi_degradation_ratio_%")
                labels = (top10[CELL_COL].astype(str) if CELL_COL in top10.columns
                          else top10.index.astype(str))
                fig, ax = plt.subplots(figsize=(9, 5))
                cmap_vals = top10["kpi_degradation_ratio_%"].values
                bar_colors = [PALETTE["red"] if v > 50 else PALETTE["orange"] if v > 25 else PALETTE["yellow"]
                              for v in cmap_vals]
                ax.barh(labels, top10["kpi_degradation_ratio_%"],
                        color=bar_colors, edgecolor="none", height=0.65)
                kpi_label = selected_kpi if not analyze_all else "All KPIs"
                ax.set_title(f"Top 10 Degraded Cells — {kpi_label}", fontweight="bold", fontsize=12, pad=10)
                ax.set_xlabel("Degradation (%)", fontsize=9)
                ax.invert_yaxis()
                _apply_chart_style(fig, ax)
                fig.tight_layout()
                st.pyplot(fig)
                plt.close(fig)

    with r1c2:
        if "rf_severity" in output_df.columns and len(output_df) > 0:
            sev_counts = output_df["rf_severity"].value_counts()
            sev_order = [s for s in ["Critical", "High", "Medium", "Normal", "N/A"] if s in sev_counts.index]
            sev_vals = [sev_counts[s] for s in sev_order]
            sev_cols = [SEVERITY_COLORS.get(s, PALETTE["muted"]) for s in sev_order]

            fig, ax = plt.subplots(figsize=(6, 5))
            bars = ax.bar(sev_order, sev_vals, color=sev_cols, edgecolor="none", width=0.55)
            ax.set_title("Severity Breakdown", fontweight="bold", fontsize=12, pad=10)
            ax.set_ylabel("Cell Count", fontsize=9)
            for bar in bars:
                h = bar.get_height()
                if h > 0:
                    ax.text(bar.get_x() + bar.get_width() / 2, h + 0.3,
                            f"{int(h)}", ha="center", va="bottom", fontsize=9,
                            fontweight="bold", color="#fff")
            _apply_chart_style(fig, ax)
            fig.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

    # Row 2: Root Cause  +  Confidence pie
    r2c1, r2c2 = st.columns([3, 2])

    with r2c1:
        if "main_root_cause_category" in output_df.columns and len(output_df) > 0:
            causes = output_df["main_root_cause_category"].value_counts().head(12).sort_values()
            fig, ax = plt.subplots(figsize=(9, 5))
            bar_colors = [PALETTE["blue"] if i % 2 == 0 else PALETTE["purple"]
                          for i in range(len(causes))]
            ax.barh(list(causes.index), causes.values,
                    color=bar_colors, edgecolor="none", height=0.65)
            ax.set_title("Root Cause Distribution", fontweight="bold", fontsize=12, pad=10)
            ax.set_xlabel("Number of Cells", fontsize=9)
            _apply_chart_style(fig, ax)
            fig.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

    with r2c2:
        if "analysis_confidence" in output_df.columns and len(output_df) > 0:
            conf_counts = output_df["analysis_confidence"].value_counts()
            c_colors = [CONFIDENCE_COLORS.get(c, PALETTE["muted"]) for c in conf_counts.index]
            fig, ax = plt.subplots(figsize=(6, 5))
            wedges, texts, autotexts = ax.pie(
                conf_counts.values,
                labels=conf_counts.index,
                autopct="%1.0f%%",
                colors=c_colors,
                startangle=90,
                pctdistance=0.78,
                wedgeprops={"edgecolor": "#0A1628", "linewidth": 2},
            )
            for t in texts:
                t.set_color((1, 1, 1, 0.9))
                t.set_fontsize(9)
            for at in autotexts:
                at.set_color("#fff")
                at.set_fontsize(9)
                at.set_fontweight("bold")
            ax.set_title("Analysis Confidence", fontweight="bold", fontsize=12, pad=10)
            fig.patch.set_facecolor("#0A1628")
            ax.set_facecolor("#0A1628")
            fig.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

    # Enhancement Potential row
    if (st.session_state.original_df is not None
            and len(st.session_state.degraded_cell_ids) > 0):
        st.markdown('<div class="section-header"><div class="icon">⚡</div><h3>Enhancement Potential (Last Day)</h3></div>', unsafe_allow_html=True)
        if st.session_state.analysis_mode == "all" and st.session_state.summary_df is not None:
            kpis_to_show = list(st.session_state.summary_df["kpi_name"].head(4))
        else:
            kpis_to_show = [selected_kpi] if not analyze_all else []
        if kpis_to_show:
            ep_cols = st.columns(min(4, len(kpis_to_show)))
            for i, kn in enumerate(kpis_to_show[:4]):
                cfg = KPI_CONFIGS.get(kn, {})
                tkpi = cfg.get("target_kpi", "")
                orig = st.session_state.original_df
                if tkpi and tkpi in orig.columns and SITE_COL in orig.columns and CELL_COL in orig.columns:
                    try:
                        df_ep = orig[[DATE_COL, SITE_COL, CELL_COL, tkpi]].copy()
                        df_ep[DATE_COL] = pd.to_datetime(df_ep[DATE_COL], errors="coerce")
                        df_ep[tkpi] = pd.to_numeric(df_ep[tkpi], errors="coerce")
                        df_ep = df_ep.dropna(subset=[DATE_COL, tkpi])
                        ld = df_ep[DATE_COL].max()
                        last_d = df_ep[df_ep[DATE_COL] == ld]
                        before = last_d[tkpi].mean()
                        mask = last_d.set_index([SITE_COL, CELL_COL]).index.isin(st.session_state.degraded_cell_ids)
                        after = last_d[~mask][tkpi].mean() if (~mask).any() else before
                        ep = ((after - before) / before * 100) if before != 0 else 0.0
                        ep_cols[i].metric(kn, f"{ep:+.1f}%",
                                          help="Projected improvement if degraded cells are resolved")
                    except Exception:
                        pass

# ──────────────────────────────────────────────────────────────
# TAB 3 — Trends
# ──────────────────────────────────────────────────────────────
with tabs[2]:
    st.markdown('<div class="section-header"><div class="icon">📈</div><h3>KPI Trend Analysis</h3></div>', unsafe_allow_html=True)

    original_df = st.session_state.original_df
    deg_ids = st.session_state.degraded_cell_ids

    if original_df is not None and len(deg_ids) > 0:
        available_kpi_cols = [
            k["target_column"]
            for k in KPI_LIST
            if k["target_column"] in original_df.columns
        ]

        if not available_kpi_cols:
            st.markdown('<div class="callout info">ℹ️ No recognized KPI columns found in uploaded data.</div>', unsafe_allow_html=True)
        else:
            trend_kpi = st.selectbox(
                "Select KPI for Trend",
                options=available_kpi_cols,
                format_func=lambda x: next(
                    (k["short_name"] for k in KPI_LIST if k["target_column"] == x), x
                ),
            )

            deg_ids_tuple = tuple(sorted(st.session_state.degraded_cell_ids))
            daily_before, daily_after = _prepare_trend_data(
                original_df, trend_kpi, deg_ids_tuple, DATE_COL, SITE_COL, CELL_COL
            )

            before_avg = daily_before[trend_kpi].mean()
            after_avg = daily_after[trend_kpi].mean()
            enhancement = ((after_avg - before_avg) / before_avg * 100) if before_avg != 0 else 0.0

            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Network Avg (All Cells)", f"{before_avg:.3f}")
            mc2.metric("Network Avg (Clean Cells)", f"{after_avg:.3f}")
            mc3.metric("Enhancement Potential", f"{enhancement:+.2f}%")

            fig, ax = plt.subplots(figsize=(13, 5))
            x = range(len(daily_before))
            labels = [str(d)[:10] for d in daily_before[DATE_COL]]
            bv = daily_before[trend_kpi].values
            av = daily_after.set_index(DATE_COL).reindex(daily_before[DATE_COL])[trend_kpi].values

            ax.plot(x, bv, color=PALETTE["blue"], marker="o",
                    label="All Cells (Before)", markersize=5, linewidth=2.2)
            ax.plot(x, av, color=PALETTE["green"], marker="s",
                    label="Clean Cells (After)", markersize=5, linewidth=2.2)
            ax.fill_between(x, bv, av, alpha=0.18, color=PALETTE["red"], label="Impact Zone")
            ax.set_xticks(list(x))
            ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
            ax.set_xlabel("Date", fontsize=9)
            ax.set_ylabel(trend_kpi, fontsize=9)
            ax.set_title(
                f"{trend_kpi} — Enhancement Potential: {enhancement:+.2f}%",
                fontweight="bold", fontsize=12, pad=10
            )
            ax.legend(fontsize=9, framealpha=0.3, facecolor="#0D1E35", edgecolor=(1, 1, 1, 0.15))
            _apply_chart_style(fig, ax)
            fig.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

        # Per-cell drill-down
        st.markdown('<div class="section-header"><div class="icon">📌</div><h3>Per-Cell Drill-Down</h3></div>', unsafe_allow_html=True)
        with st.expander("Select a specific site & cell to view its trend"):
            if SITE_COL in original_df.columns and CELL_COL in original_df.columns and available_kpi_cols:
                dc1, dc2, dc3 = st.columns(3)
                with dc1:
                    cell_kpi = st.selectbox(
                        "KPI",
                        available_kpi_cols,
                        format_func=lambda x: next((k["short_name"] for k in KPI_LIST if k["target_column"] == x), x),
                        key="per_cell_kpi",
                    )
                with dc2:
                    site_list = sorted(original_df[SITE_COL].dropna().unique().tolist())
                    sel_site = st.selectbox("Site", site_list, key="per_cell_site")
                with dc3:
                    cell_list = _get_cell_list(original_df, sel_site, SITE_COL, CELL_COL)
                    if cell_list:
                        sel_cell = st.selectbox("Cell", cell_list, key="per_cell_cell")

                if cell_list:
                    cell_df = _prepare_cell_data(
                        original_df, sel_site, sel_cell, cell_kpi, DATE_COL, SITE_COL, CELL_COL
                    )
                    if not cell_df.empty:
                        fig2, ax2 = plt.subplots(figsize=(13, 4))
                        ax2.plot(cell_df[DATE_COL], cell_df[cell_kpi],
                                 color=PALETTE["blue"], marker="o",
                                 markersize=5, linewidth=2)
                        ax2.fill_between(cell_df[DATE_COL], cell_df[cell_kpi],
                                         alpha=0.15, color=PALETTE["blue"])
                        ax2.set_title(
                            f"{sel_site} / {sel_cell} — {cell_kpi}",
                            fontweight="bold", fontsize=12, pad=10
                        )
                        ax2.set_xlabel("Date", fontsize=9)
                        ax2.set_ylabel(cell_kpi, fontsize=9)
                        plt.xticks(rotation=45, ha="right", fontsize=8)
                        _apply_chart_style(fig2, ax2)
                        fig2.tight_layout()
                        st.pyplot(fig2)
                        plt.close(fig2)
    else:
        st.markdown("""
        <div class="empty-state">
            <div class="es-icon">📈</div>
            <h3>No trend data available</h3>
            <p>Run a KPI analysis first to generate trend charts and enhancement potential estimates.</p>
        </div>
        """, unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────
# TAB 4 — Anomalies
# ──────────────────────────────────────────────────────────────
with tabs[3]:
    st.markdown('<div class="section-header"><div class="icon">🔍</div><h3>KPI Anomaly Detection</h3></div>', unsafe_allow_html=True)
    st.caption(
        "Detects zero-value and statistical spike anomalies on the last day "
        "using a robust z-score over a 4-week rolling baseline."
    )

    if st.session_state.anomalies_df is not None:
        adf = st.session_state.anomalies_df
        if adf.empty:
            st.markdown('<div class="callout success">✅ No anomalies detected on the last day — all KPIs are within normal range.</div>', unsafe_allow_html=True)
        else:
            ac1, ac2, ac3 = st.columns(3)
            ac1.metric("Total Anomalies", len(adf))
            if "anomaly_type" in adf.columns:
                ac2.metric("Zero Anomalies", int((adf["anomaly_type"] == "zero").sum()))
                ac3.metric("Spike Anomalies", int((adf["anomaly_type"] == "spike").sum()))

            if "anomaly_type" in adf.columns:
                type_filter = st.radio(
                    "Filter by type",
                    ["All", "zero", "spike"],
                    horizontal=True,
                    key="anom_type_filter",
                )
                adf_show = adf if type_filter == "All" else adf[adf["anomaly_type"] == type_filter]
            else:
                adf_show = adf

            st.dataframe(adf_show, use_container_width=True, height=380)

            if "kpi_name" in adf.columns and len(adf) > 0:
                fig, ax = plt.subplots(figsize=(10, 4))
                anom_counts = adf["kpi_name"].value_counts().head(13)
                colors = [PALETTE["orange"] if i % 2 == 0 else PALETTE["red"]
                          for i in range(len(anom_counts))]
                ax.bar(anom_counts.index, anom_counts.values,
                       color=colors, edgecolor="none", width=0.6)
                ax.set_title("Anomalies by KPI", fontweight="bold", fontsize=12, pad=10)
                ax.set_ylabel("Count", fontsize=9)
                plt.xticks(rotation=45, ha="right", fontsize=8)
                _apply_chart_style(fig, ax)
                fig.tight_layout()
                st.pyplot(fig)
                plt.close(fig)

            csv_anom = adf.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "⬇  Download Anomalies CSV",
                data=csv_anom,
                file_name="anomalies.csv",
                mime="text/csv",
                use_container_width=True,
            )

            buf_anom = io.BytesIO()
            with pd.ExcelWriter(buf_anom, engine="openpyxl") as writer:
                adf.to_excel(writer, index=False, sheet_name="All_Anomalies")
            buf_anom.seek(0)
            st.download_button(
                "⬇  Download Anomalies Excel",
                data=buf_anom.getvalue(),
                file_name="anomalies.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    else:
        st.markdown("""
        <div class="empty-state">
            <div class="es-icon">🔍</div>
            <h3>Anomaly detection not run yet</h3>
            <p>Click <strong>Detect Anomalies</strong> in the sidebar to scan the last day
               for zero-value and statistical spike anomalies.</p>
        </div>
        """, unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────
# TAB 5 — Exports
# ──────────────────────────────────────────────────────────────
with tabs[4]:
    output_df = st.session_state.output_df
    summary_df = st.session_state.summary_df

    st.markdown('<div class="section-header"><div class="icon">📁</div><h3>Export Results</h3></div>', unsafe_allow_html=True)

    st.markdown("##### 🔍 Anomalies Output")
    if st.session_state.anomalies_df is not None and not st.session_state.anomalies_df.empty:
        ac1, ac2 = st.columns(2)
        with ac1:
            csv_anom = st.session_state.anomalies_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "⬇  CSV — All Anomalies",
                data=csv_anom,
                file_name="all_anomalies.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with ac2:
            buf_anom = io.BytesIO()
            with pd.ExcelWriter(buf_anom, engine="openpyxl") as writer:
                st.session_state.anomalies_df.to_excel(writer, index=False, sheet_name="All_Anomalies")
            buf_anom.seek(0)
            st.download_button(
                "⬇  Excel — All Anomalies",
                data=buf_anom.getvalue(),
                file_name="all_anomalies.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
    else:
        st.caption("No anomalies detected. Use the sidebar button to detect anomalies.")

    st.divider()

    ec1, ec2 = st.columns(2)

    with ec1:
        st.markdown("##### 📉 All Degraded Cells")
        if output_df is not None and not output_df.empty:
            csv_deg = output_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "⬇  CSV — All Degraded Cells",
                data=csv_deg,
                file_name="all_degraded_cells.csv",
                mime="text/csv",
                use_container_width=True,
            )

            buf_deg = io.BytesIO()
            with pd.ExcelWriter(buf_deg, engine="openpyxl") as writer:
                output_df.to_excel(writer, index=False, sheet_name="All_Degraded_Cells")
            buf_deg.seek(0)
            st.download_button(
                "⬇  Excel — All Degraded Cells",
                data=buf_deg.getvalue(),
                file_name="all_degraded_cells.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        else:
            st.caption("No degraded cells to export.")

    with ec2:
        st.markdown("##### 📊 KPI Summary")
        if summary_df is not None and not summary_df.empty:
            csv_sum = summary_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "⬇  CSV — KPI Summary",
                data=csv_sum,
                file_name="kpi_summary.csv",
                mime="text/csv",
                use_container_width=True,
            )

            buf_sum = io.BytesIO()
            with pd.ExcelWriter(buf_sum, engine="openpyxl") as writer:
                summary_df.to_excel(writer, index=False, sheet_name="KPI_Summary")
            buf_sum.seek(0)
            st.download_button(
                "⬇  Excel — KPI Summary",
                data=buf_sum.getvalue(),
                file_name="kpi_summary.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        else:
            st.caption("Run Analyze All KPIs to generate summary.")

    st.divider()

    st.markdown("##### ✅ Clean Normal Cells")
    if st.session_state.clean_cells_df is not None and not st.session_state.clean_cells_df.empty:
        csv_clean = st.session_state.clean_cells_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇  CSV — Clean Normal Cells",
            data=csv_clean,
            file_name="clean_normal_cells.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.caption("Run analysis to generate clean cells export.")

    st.divider()

    excluded_out = combine_not_calculated_cells(
        st.session_state.quarantine_df, st.session_state.incomplete_df
    )
    if not excluded_out.empty:
        st.markdown("##### ⚠️ Cells Not Calculated")
        csv_excl = excluded_out.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇  CSV — Cells Not Calculated",
            data=csv_excl,
            file_name="cells_not_calculated.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.divider()

    st.markdown("##### 📊 Full Multi-Sheet Excel Report")
    st.caption("Sheets: KPI Summary, All Degraded Cells, All Anomalies, Clean Normal Cells, Cells Not Calculated")

    buf_full = io.BytesIO()
    with pd.ExcelWriter(buf_full, engine="openpyxl") as writer:
        sheet_outputs = []
        if summary_df is not None and not summary_df.empty:
            sheet_outputs.append(("KPI_Summary", summary_df))
        if output_df is not None and not output_df.empty:
            sheet_outputs.append(("All_Degraded_Cells", output_df))
        if st.session_state.anomalies_df is not None and not st.session_state.anomalies_df.empty:
            sheet_outputs.append(("All_Anomalies", st.session_state.anomalies_df))
        clean_out = remove_anomaly_cells(st.session_state.clean_cells_df, st.session_state.anomalies_df)
        if clean_out is not None and not clean_out.empty:
            sheet_outputs.append(("Clean_Normal_Cells", clean_out))
        if not excluded_out.empty:
            sheet_outputs.append(("Cells_Not_Calculated", excluded_out))

        for sheet_name, df in sheet_outputs:
            date_first(df).to_excel(writer, sheet_name=sheet_name, index=False)
    buf_full.seek(0)
    st.download_button(
        "⬇  Download Full Excel Report",
        data=buf_full.getvalue(),
        file_name=f"LTE_KPI_Analysis_{selected_kpi.replace(' ', '_') if not analyze_all else 'All_KPIs'}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    st.divider()

    st.markdown("##### 📄 Word Report (.docx)")
    if DOCX_AVAILABLE:
        if st.button("📄  Generate Word Report", use_container_width=True):
            with st.spinner("Building Word report…"):
                try:
                    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                        tmp_path = tmp.name
                    success = generate_word_report(
                        output_df if output_df is not None else pd.DataFrame(),
                        summary_df,
                        st.session_state.analysis_mode,
                        selected_kpi if not analyze_all else "All KPIs",
                        baseline_mode,
                        enable_significance_test,
                        tmp_path,
                        st.session_state.original_df,
                        st.session_state.degraded_cell_ids,
                        lambda m: None,
                    )
                    if success:
                        with open(tmp_path, "rb") as f:
                            docx_bytes = f.read()
                        os.unlink(tmp_path)
                        st.download_button(
                            "⬇  Download Word Report",
                            data=docx_bytes,
                            file_name=f"RF_Optimization_{selected_kpi.replace(' ', '_') if not analyze_all else 'All_KPIs'}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                        )
                    else:
                        st.markdown('<div class="callout danger">❌ Report generation failed.</div>', unsafe_allow_html=True)
                except Exception as e:
                    st.markdown(f'<div class="callout danger">❌ Word report error: {e}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="callout warning">⚠️ <code>python-docx</code> is not installed. Run: <code>pip install python-docx</code></div>', unsafe_allow_html=True)

# ============================================================
# Bottom expanders — always visible after analysis
# ============================================================
st.divider()

if st.session_state.summary_df is not None and not st.session_state.summary_df.empty:
    with st.expander("📊 KPI Summary Table", expanded=False):
        st.dataframe(st.session_state.summary_df, use_container_width=True)

if st.session_state.quarantine_df is not None and not st.session_state.quarantine_df.empty:
    with st.expander(f"⚠️ Quarantined Values ({len(st.session_state.quarantine_df)} records)"):
        st.dataframe(st.session_state.quarantine_df, use_container_width=True)

if st.session_state.incomplete_df is not None and not st.session_state.incomplete_df.empty:
    with st.expander(f"⏳ Incomplete Cells ({len(st.session_state.incomplete_df)} records)"):
        st.dataframe(st.session_state.incomplete_df, use_container_width=True)

if st.session_state.original_df is not None:
    with st.expander("📋 Raw Data Preview (first 50 rows)", expanded=False):
        st.dataframe(st.session_state.original_df.head(50), use_container_width=True)
