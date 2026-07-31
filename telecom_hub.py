"""Unified Streamlit entry point for the "4G/5G RAN Performance Optimization TOOL".

Run from the repository root:
    streamlit run telecom_hub.py
"""
from __future__ import annotations

import runpy
import sys
from contextlib import contextmanager
from pathlib import Path

import streamlit as st

# ── Page config ──────────────────────────────────────────────
st.set_page_config(
    page_title="4G/5G RAN Performance Optimization TOOL",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).resolve().parent

TOOLS = {
    "4G(LTE)/5G(NR) KPI Degradation Analyzer": ROOT / "LTE_RAN_KPI_Analysis_Tool" / "app" / "app_streamlit.py",
    "4G(LTE)/5G(NR) KPI Forecaster":           ROOT / "forcasting_section" / "v2" / "app.py",
    "Optimization Action Analyzer":             ROOT / "ActionAnalyzer_tool" / "app.py",
    "3GPP RAG Assistant":                       ROOT / "RAG_tool" / "app" / "ui.py",
}

TOOL_META = {
    "4G(LTE)/5G(NR) KPI Degradation Analyzer": {
        "icon": "📡",
        "color": "#00C2FF",
        "desc": "Detect, classify and localize KPI degradations across your RAN network with statistical significance testing.",
        "tags": ["LTE", "NR", "Degradation", "RCA", "Anomaly"],
    },
    "4G(LTE)/5G(NR) KPI Forecaster": {
        "icon": "📈",
        "color": "#00D97E",
        "desc": "Forecast future KPI trends using time-series models trained on historical RAN performance data.",
        "tags": ["Forecasting", "Time-Series", "LTE", "XGBoost"],
    },
    "Optimization Action Analyzer": {
        "icon": "⚙️",
        "color": "#FFB400",
        "desc": "Analyze and evaluate network optimization actions with data-driven impact assessment.",
        "tags": ["Optimization", "Actions", "Impact"],
    },
    "3GPP RAG Assistant": {
        "icon": "🤖",
        "color": "#7B61FF",
        "desc": "Ask engineering questions and get cited answers sourced directly from 3GPP specifications.",
        "tags": ["3GPP", "LLM", "RAG", "NR", "LTE"],
    },
}

# ============================================================
# Global Styles  — instant dark background prevents flash
# ============================================================
st.markdown("""
<style>
/* Force dark background immediately — prevents white flash on load */
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > .main,
body { background-color: #080F1E !important; }

:root {
    --accent:  #00C2FF;
    --accent2: #7B61FF;
    --success: #00D97E;
    --warning: #FFB400;
    --border:  rgba(0,194,255,0.16);
}

/* ── Compact hub header ── */
.hub-header {
    background: linear-gradient(135deg, #050E1F 0%, #0A1628 100%);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 24px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 16px;
}
.hub-header .hub-title {
    font-size: 1.05rem;
    font-weight: 800;
    background: linear-gradient(90deg, #00C2FF 0%, #7B61FF 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.3px;
}
.hub-header .hub-sub {
    font-size: 0.75rem;
    color: rgba(255,255,255,0.65);
    margin-top: 2px;
}

/* ── Hub hero (landing) ── */
.hub-hero {
    background: linear-gradient(135deg, #050E1F 0%, #0A1628 40%, #0B1A30 100%);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 36px 40px 28px;
    margin-bottom: 28px;
    text-align: center;
    position: relative;
    overflow: hidden;
}
.hub-hero::before {
    content: "";
    position: absolute;
    inset: 0;
    background:
        radial-gradient(ellipse at 20% 50%, rgba(0,194,255,0.06) 0%, transparent 55%),
        radial-gradient(ellipse at 80% 50%, rgba(123,97,255,0.06) 0%, transparent 55%);
    pointer-events: none;
}
.hub-hero .hub-icon { font-size: 3rem; margin-bottom: 12px; display: block; }
.hub-hero h1 {
    font-size: 2.1rem;
    font-weight: 900;
    margin: 0 0 8px;
    background: linear-gradient(90deg, #00C2FF 0%, #7B61FF 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.8px;
    line-height: 1.15;
}
.hub-hero .tagline {
    font-size: 0.95rem;
    color: rgba(255,255,255,0.8);
    margin: 0 auto 18px;
    max-width: 520px;
    line-height: 1.6;
}
.hub-hero .stats-row {
    display: flex;
    justify-content: center;
    gap: 32px;
    margin-top: 20px;
    flex-wrap: wrap;
}
.hub-stat { text-align: center; }
.hub-stat .sv {
    font-size: 1.5rem;
    font-weight: 800;
    background: linear-gradient(90deg, #00C2FF, #7B61FF);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.hub-stat .sl {
    font-size: 0.72rem;
    color: rgba(255,255,255,0.75);
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-top: 2px;
}

/* ── Tool cards (landing) ── */
.tool-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 22px 20px 18px;
    cursor: pointer;
    height: 100%;
}
.tool-card.active {
    border-color: var(--accent);
    background: rgba(0,194,255,0.06);
}
.tool-card .tc-icon { font-size: 2rem; margin-bottom: 10px; display: block; }
.tool-card .tc-name { font-size: 0.93rem; font-weight: 700; color: #fff; margin-bottom: 7px; line-height: 1.3; }
.tool-card .tc-desc { font-size: 0.78rem; color: rgba(255,255,255,0.75); line-height: 1.55; margin-bottom: 12px; }
.tc-tags { display: flex; flex-wrap: wrap; gap: 5px; }
.tc-tag {
    font-size: 0.65rem; font-weight: 700; letter-spacing: 0.4px;
    border-radius: 10px; padding: 2px 8px;
    background: rgba(255,255,255,0.08);
    color: rgba(255,255,255,0.8);
    border: 1px solid rgba(255,255,255,0.12);
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #080F1E !important;
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] .stRadio > label { display: none !important; }
[data-testid="stSidebar"] .stButton > button {
    border-radius: 8px;
    font-weight: 600;
    transition: all .2s;
}
.sidebar-brand {
    padding: 8px 0 14px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    margin-bottom: 16px;
}
.sidebar-brand .sb-title {
    font-size: 1rem;
    font-weight: 800;
    background: linear-gradient(90deg, #00C2FF, #7B61FF);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.3px;
}
.sidebar-brand .sb-sub {
    font-size: 0.7rem;
    color: rgba(255,255,255,0.7);
    margin-top: 2px;
}
.sidebar-nav-label {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.1px;
    color: #ffffff;
    margin-bottom: 10px;
}
.nav-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    border-radius: 9px;
    margin-bottom: 4px;
    border: 1px solid transparent;
    font-size: 0.85rem;
    font-weight: 600;
    color: rgba(255,255,255,0.85);
}
.nav-item.active {
    background: rgba(0,194,255,0.1);
    border-color: rgba(0,194,255,0.25);
    color: #00C2FF;
}
.nav-item .ni-icon { font-size: 1rem; flex-shrink: 0; }
.nav-item .ni-label { flex: 1; line-height: 1.3; font-size: 0.82rem; }

/* ── Divider label ── */
.divider-label {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 28px 0 16px;
}
.divider-label span {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: rgba(255,255,255,0.75);
    white-space: nowrap;
}
    .divider-label hr {
        flex: 1;
        border: none;
        border-top: 1px solid rgba(255,255,255,0.10);
        margin: 0;
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
# Sidebar Navigation
# ============================================================
def _purge_local_modules(tool_dir: Path) -> None:
    for source in tool_dir.rglob("*.py"):
        sys.modules.pop(source.stem, None)
    sys.modules.pop("app", None)


@contextmanager
def _tool_environment(tool_path: Path):
    tool_dir = tool_path.parent
    added_paths = [str(tool_dir)]
    if tool_dir.name == "app" and tool_dir.parent.name == "RAG_tool":
        added_paths.append(str(tool_dir.parent))
    _purge_local_modules(tool_dir)
    for path in reversed(added_paths):
        sys.path.insert(0, path)
    try:
        yield
    finally:
        for path in added_paths:
            while path in sys.path:
                sys.path.remove(path)


st.session_state["_hub_mode"] = True

tool_names = list(TOOLS.keys())

with st.sidebar:
    st.markdown("""
    <div class="sidebar-brand">
        <div class="sb-title">📡 RANPilotAI</div>
        <div class="sb-sub">Network Optimization Toolkit</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sidebar-nav-label">Tools</div>', unsafe_allow_html=True)

    selected_tool = st.selectbox(
        "Tool",
        tool_names,
        key="hub_selected_tool",
        label_visibility="collapsed",
    )

    # Styled nav preview
    nav_html = ""
    for name in tool_names:
        meta = TOOL_META.get(name, {"icon": "🔧", "color": "#fff"})
        active_class = "active" if name == selected_tool else ""
        nav_html += f"""
        <div class="nav-item {active_class}">
            <span class="ni-icon">{meta['icon']}</span>
            <span class="ni-label">{name}</span>
        </div>
        """
    st.markdown(nav_html, unsafe_allow_html=True)

    st.divider()
    st.caption("Select a tool above to load its interface.")
    st.caption("Musketeers Team · ITI Graduation 2026")


# ============================================================
# If no tool has been run yet — show the landing hero
# ============================================================
_loaded_tools: set = st.session_state.get("_loaded_tools", set())

if not _loaded_tools:
    # Hero — shown only on very first visit before any tool runs
    st.markdown("""
    <div class="hub-hero">
        <span class="hub-icon">📡</span>
        <h1>5G/4G RAN Performance Optmization Assistant Tool</h1>
        <p class="tagline">
            An integrated suite of AI-powered tools for 4G/5G RAN performance
            monitoring, KPI forecasting, optimization analysis, and specification retrieval.
        </p>
        <div class="stats-row">
            <div class="hub-stat"><div class="sv">4</div><div class="sl">Tools</div></div>
            <div class="hub-stat"><div class="sv">LTE · NR</div><div class="sl">Technologies</div></div>
            <div class="hub-stat"><div class="sv">3GPP</div><div class="sl">Spec Engine</div></div>
            <div class="hub-stat"><div class="sv">AI</div><div class="sl">Powered</div></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="divider-label"><hr><span>Available Tools</span><hr></div>
    """, unsafe_allow_html=True)

    card_cols = st.columns(4)
    for col, (name, meta) in zip(card_cols, TOOL_META.items()):
        active = "active" if name == selected_tool else ""
        tags_html = "".join(f'<span class="tc-tag">{t}</span>' for t in meta["tags"])
        col.markdown(f"""
        <div class="tool-card {active}">
            <span class="tc-icon">{meta['icon']}</span>
            <div class="tc-name">{name}</div>
            <div class="tc-desc">{meta['desc']}</div>
            <div class="tc-tags">{tags_html}</div>
        </div>
        """, unsafe_allow_html=True)
else:
    # Compact header — shown once a tool is active
    meta = TOOL_META.get(selected_tool, {"icon": "🔧", "color": "#fff"})
    st.markdown(f"""
    <div class="hub-header">
        <span style="font-size:1.6rem">{meta['icon']}</span>
        <div>
            <div class="hub-title">{selected_tool}</div>
            <div class="hub-sub">{meta.get('desc', '')}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# Load & Run Selected Tool
# ============================================================
tool_path = TOOLS[selected_tool]
_prev_tool = st.session_state.get("_active_tool")

try:
    if _prev_tool != selected_tool:
        with _tool_environment(tool_path):
            runpy.run_path(str(tool_path), run_name="__main__")
        st.session_state["_active_tool"] = selected_tool
    else:
        runpy.run_path(str(tool_path), run_name="__main__")
    loaded = st.session_state.get("_loaded_tools", set())
    loaded.add(selected_tool)
    st.session_state["_loaded_tools"] = loaded
except Exception as exc:
    st.error(f"Could not load **{selected_tool}**: {exc}")
    st.exception(exc)
