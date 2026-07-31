"""Streamlit Chat UI — 3GPP RAG Assistant (Professional Rebuild)"""

from __future__ import annotations

import streamlit as st
import os
from app.rag import TelecomRAG
from app import profiler
from app.config import DEBUG_MODE, DATA_DIR

# ── Page config ──────────────────────────────────────────────
if not st.session_state.get("_hub_mode", False):
    st.set_page_config(
        page_title="3GPP RAG Assistant",
        page_icon="🤖",
        layout="wide",
    )

# ============================================================
# Global Styles
# ============================================================
st.markdown(
    """
<style>
/* ── Core palette ── */
:root {
    --accent:   #00C2FF;
    --accent2:  #7B61FF;
    --success:  #00D97E;
    --warning:  #FFB400;
    --danger:   #FF4D4D;
    --bg-card:  rgba(255,255,255,0.04);
    --border:   rgba(0,194,255,0.18);
    --bg-main:  #0A1628;
    --bg-panel: #0D1E35;
}

/* ── Hero banner ── */
.rag-hero {
    background: linear-gradient(135deg, #0A1628 0%, #0E2448 55%, #0A1628 100%);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 24px 32px 20px;
    margin-bottom: 20px;
    position: relative;
    overflow: hidden;
}
.rag-hero::before {
    content: "";
    position: absolute;
    inset: 0;
    background: radial-gradient(ellipse at 30% 50%, rgba(123,97,255,0.07) 0%, transparent 60%);
    pointer-events: none;
}
.rag-hero h1 {
    font-size: 1.7rem;
    font-weight: 800;
    margin: 0 0 4px;
    background: linear-gradient(90deg, #00C2FF, #7B61FF);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.4px;
}
.rag-hero .subtitle {
    font-size: 0.87rem;
    color: rgba(255,255,255,0.5);
    margin: 0 0 14px;
}
.rag-hero .badge-row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}
.rag-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(0,194,255,0.1);
    border: 1px solid rgba(0,194,255,0.28);
    color: #00C2FF;
    border-radius: 20px;
    padding: 3px 11px;
    font-size: 0.73rem;
    font-weight: 600;
    letter-spacing: 0.3px;
}
.rag-badge.purple {
    background: rgba(123,97,255,0.1);
    border-color: rgba(123,97,255,0.28);
    color: #7B61FF;
}
.rag-badge.green {
    background: rgba(0,217,126,0.1);
    border-color: rgba(0,217,126,0.28);
    color: #00D97E;
}

/* ── Chat messages ── */
.chat-wrapper {
    display: flex;
    flex-direction: column;
    gap: 14px;
    margin-bottom: 8px;
}
.msg-bubble {
    border-radius: 12px;
    padding: 14px 18px;
    line-height: 1.65;
    font-size: 0.9rem;
    max-width: 92%;
    position: relative;
}
.msg-user {
    background: linear-gradient(135deg, rgba(0,194,255,0.12), rgba(123,97,255,0.12));
    border: 1px solid rgba(0,194,255,0.22);
    align-self: flex-end;
    border-bottom-right-radius: 4px;
    color: rgba(255,255,255,0.92);
}
.msg-assistant {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.09);
    align-self: flex-start;
    border-bottom-left-radius: 4px;
    color: rgba(255,255,255,0.88);
}
.msg-role-label {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 7px;
    opacity: 0.55;
}
.msg-role-label.user  { color: #00C2FF; }
.msg-role-label.asst  { color: #7B61FF; }

/* ── Citation card ── */
.citation-card {
    background: rgba(0,194,255,0.06);
    border: 1px solid rgba(0,194,255,0.2);
    border-radius: 8px;
    padding: 10px 14px;
    margin: 6px 0;
    font-size: 0.8rem;
    color: rgba(255,255,255,0.75);
    display: flex;
    align-items: center;
    gap: 10px;
}
.citation-rank {
    background: linear-gradient(135deg, #00C2FF, #7B61FF);
    color: #fff;
    border-radius: 50%;
    width: 22px;
    height: 22px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 0.7rem;
    font-weight: 800;
    flex-shrink: 0;
}
.citation-meta { flex: 1; }
.citation-meta strong { color: #fff; font-size: 0.82rem; }
.citation-score {
    font-size: 0.7rem;
    color: #00D97E;
    font-weight: 700;
    background: rgba(0,217,126,0.1);
    border-radius: 10px;
    padding: 2px 8px;
    white-space: nowrap;
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
    box-shadow: 0 4px 14px rgba(123,97,255,0.3);
}
.sidebar-logo {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 0 4px;
    margin-bottom: 6px;
}
.sidebar-logo .logo-icon {
    font-size: 1.5rem;
}
.sidebar-logo .logo-text {
    font-size: 0.82rem;
    font-weight: 700;
    color: #ffffff;
    line-height: 1.3;
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

/* ── Empty state ── */
.empty-state {
    text-align: center;
    padding: 56px 20px;
    color: rgba(255,255,255,0.4);
}
.empty-state .es-icon { font-size: 3rem; margin-bottom: 12px; }
.empty-state h3 { font-size: 1.05rem; color: rgba(255,255,255,0.6); margin-bottom: 6px; }
.empty-state p  { font-size: 0.83rem; max-width: 360px; margin: 0 auto; line-height: 1.6; }

/* ── Callout ── */
.callout {
    border-radius: 8px;
    padding: 11px 15px;
    font-size: 0.84rem;
    margin: 10px 0;
    display: flex;
    align-items: flex-start;
    gap: 10px;
}
.callout.info {
    background: rgba(0,194,255,0.07);
    border-left: 3px solid var(--accent);
    color: rgba(255,255,255,0.75);
}
.callout.warning {
    background: rgba(255,180,0,0.07);
    border-left: 3px solid var(--warning);
    color: rgba(255,255,255,0.75);
}

/* ── Suggestion chips ── */
.chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 16px 0 20px;
}
.chip {
    background: rgba(123,97,255,0.1);
    border: 1px solid rgba(123,97,255,0.3);
    color: rgba(255,255,255,0.75);
    border-radius: 20px;
    padding: 5px 14px;
    font-size: 0.78rem;
    cursor: pointer;
    transition: all .2s;
}
.chip:hover {
    background: rgba(123,97,255,0.2);
    color: #fff;
}

/* ── Stage progress ── */
.stage-bar {
    background: rgba(255,255,255,0.05);
    border-radius: 6px;
    padding: 8px 14px;
    margin: 4px 0;
    font-size: 0.8rem;
    color: rgba(255,255,255,0.6);
    display: flex;
    align-items: center;
    gap: 8px;
}
.stage-bar .dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--accent);
    flex-shrink: 0;
}
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# Helpers
# ============================================================
@st.cache_data
def get_pdf_list():
    if not os.path.exists(DATA_DIR):
        return ["All"]
    try:
        files = [f for f in os.listdir(DATA_DIR) if f.endswith(".pdf")]
        return ["All"] + sorted(files)
    except Exception as e:
        return ["All"]


@st.cache_resource
def get_rag_pipeline():
    return TelecomRAG()


def _render_citations(refs: list):
    """Render a list of citation references as styled cards."""
    if not refs:
        return
    html = ""
    for i, ref in enumerate(refs, 1):
        score_pct = f"{ref['score'] * 100:.1f}%"
        html += f"""
        <div class="citation-card">
            <span class="citation-rank">{i}</span>
            <span class="citation-meta">
                <strong>TS {ref["ts"]}</strong> &nbsp;·&nbsp;
                Release {ref["release"]} &nbsp;·&nbsp;
                §{ref["section"]} &nbsp;·&nbsp;
                Page {ref["page"]}
            </span>
            <span class="citation-score">Score {score_pct}</span>
        </div>
        """
    st.markdown(html, unsafe_allow_html=True)


# ============================================================
# Session State
# ============================================================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pipeline_metrics" not in st.session_state:
    st.session_state.pipeline_metrics = []

# ============================================================
# Sidebar
# ============================================================
with st.sidebar:
    st.markdown(
        """
    <div class="sidebar-logo">
        <span class="logo-icon">🤖</span>
        <span class="logo-text">3GPP RAG<br>Assistant</span>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="sidebar-section">📂 Specification Filter</div>',
        unsafe_allow_html=True,
    )
    st.caption("Narrow the search to a specific 3GPP document.")

    pdf_options = get_pdf_list()
    selected_pdf = st.selectbox(
        "Filter by PDF",
        pdf_options,
        label_visibility="collapsed",
    )

    ts_filter: str | None = None
    release_filter: str | None = None

    if selected_pdf != "All":
        try:
            parts = selected_pdf.replace(".pdf", "").split("_")
            if len(parts) >= 3:
                ts_filter = parts[1]
                release_filter = parts[3]
        except Exception:
            st.markdown(
                f'<div class="callout warning">⚠️ Could not parse TS/Release from "{selected_pdf}".</div>',
                unsafe_allow_html=True,
            )

    if selected_pdf != "All" and ts_filter:
        st.markdown(
            f'<div class="callout info">🎯 Searching within <strong>TS {ts_filter}</strong> · Rel. {release_filter}</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="sidebar-section">💬 Session</div>', unsafe_allow_html=True)

    msg_count = len([m for m in st.session_state.messages if m["role"] == "user"])
    st.metric("Questions Asked", msg_count)

    if st.button("🗑️  Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pipeline_metrics = []
        st.rerun()

    st.divider()
    st.markdown('<div class="sidebar-section">ℹ️ About</div>', unsafe_allow_html=True)
    st.caption(
        "Retrieves answers directly from 3GPP specifications "
        "using semantic search + cross-encoder reranking + LLM generation."
    )
    st.caption("⏱️ First question takes a few extra seconds while AI models warm up.")

    # Debug panel
    if DEBUG_MODE:
        st.divider()
        st.markdown(
            '<div class="sidebar-section">🛠️ Debug</div>', unsafe_allow_html=True
        )
        show_metrics = st.checkbox("Show Pipeline Metrics", value=False)
        if show_metrics and st.session_state.pipeline_metrics:
            for i, metric in enumerate(st.session_state.pipeline_metrics):
                with st.expander(
                    f"Q{i + 1} — {metric.get('question', '?')[:45]}…", expanded=False
                ):
                    st.json(metric)

# ============================================================
# Initialize RAG pipeline
# ============================================================
try:
    rag = get_rag_pipeline()
except Exception as e:
    st.error(f"Failed to initialize AI models: {e}")
    st.stop()

# ============================================================
# Hero Banner
# ============================================================
st.markdown(
    """
<div class="rag-hero">
    <h1>🤖 3GPP RAG Assistant</h1>
    <p class="subtitle">Ask engineering questions — answers grounded directly in 3GPP specifications</p>
    <div class="badge-row">
        <span class="rag-badge">📡 3GPP Specs</span>
        <span class="rag-badge purple">🔍 Semantic Search</span>
        <span class="rag-badge green">⚡ Cross-Encoder Reranking</span>
        <span class="rag-badge">🧠 LLM Generation</span>
        <span class="rag-badge purple">📖 Cited Answers</span>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# ============================================================
# Chat History
# ============================================================
if not st.session_state.messages:
    # Welcome / suggestion state
    st.markdown(
        """
    <div class="empty-state">
        <div class="es-icon">💬</div>
        <h3>Start a conversation</h3>
        <p>Ask any question about LTE/NR procedures, measurements, events, or 3GPP protocols.
           Answers are cited directly from the loaded specifications.</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown("**Try asking:**")
    suggestions = [
        "Explain Event A3 in LTE",
        "What is the RRC connection re-establishment procedure?",
        "How does PDCP integrity protection work in 5G NR?",
        "What triggers a handover failure in LTE?",
        "Explain the difference between SRB1 and SRB2",
        "What is Time-To-Trigger (TTT) in measurement events?",
    ]
    cols = st.columns(3)
    for i, sug in enumerate(suggestions):
        if cols[i % 3].button(sug, use_container_width=True, key=f"sug_{i}"):
            # Push as if the user typed it
            st.session_state._prefill_prompt = sug
            st.rerun()
else:
    # Render full history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("references"):
                with st.expander(
                    f"📖 {len(message['references'])} Citation(s)", expanded=False
                ):
                    _render_citations(message["references"])

# ============================================================
# Chat Input
# ============================================================
prefill = st.session_state.pop("_prefill_prompt", None)
prompt = (
    st.chat_input(
        "e.g., Explain Event A3 in LTE, or ask any 3GPP question…",
    )
    or prefill
)

if prompt:
    # Show user message
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Build response
    with st.chat_message("assistant"):
        STAGES = [
            ("🔢", "Embedding query"),
            ("🔍", "Searching vector database"),
            ("⚖️", "Reranking retrieved chunks"),
            ("📝", "Building prompt context"),
            ("🤖", "Generating answer via LLM"),
        ]

        # Animated stage display
        stage_container = st.empty()
        stage_html = '<div style="padding:4px 0">'
        for icon, label in STAGES:
            stage_html += (
                f'<div class="stage-bar"><span class="dot"></span>{icon} {label}…</div>'
            )
        stage_html += "</div>"
        stage_container.markdown(stage_html, unsafe_allow_html=True)

        answer_placeholder = st.empty()
        refs: list = []

        try:
            response = rag.ask(
                question=prompt,
                ts_filter=ts_filter,
                release_filter=release_filter,
                history=st.session_state.messages[:-1],
            )

            answer = response["answer"]
            refs = response["references"]
            metrics = response.get("metrics", {})

            # Clear stage display; show answer
            stage_container.empty()
            answer_placeholder.markdown(answer)

            # Citations
            if refs:
                with st.expander(
                    f"📖 {len(refs)} Citation(s) — click to expand", expanded=False
                ):
                    _render_citations(refs)

            # Save to history
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                    "references": refs,
                }
            )

            # Debug: Performance Dashboard
            if DEBUG_MODE:
                stages_data = profiler.get_all_stages()
                total_ms = sum(v * 1000 for v in stages_data.values())
                metric_entry = {
                    "question": prompt,
                    "stages_ms": {k: v * 1000 for k, v in stages_data.items()},
                    "total_ms": total_ms,
                    "pipeline_efficiency": metrics,
                    "details": profiler.get_stage_details(),
                }
                st.session_state.pipeline_metrics.append(metric_entry)

                with st.expander("📊 Pipeline Performance", expanded=False):
                    perf_cols = st.columns(3)
                    for idx, (name, t_ms) in enumerate(stages_data.items()):
                        perf_cols[idx % 3].metric(name, f"{t_ms * 1000:.1f} ms")

                    if total_ms > 0:
                        slowest = max(stages_data, key=stages_data.get)
                        st.info(
                            f"Slowest stage: **{slowest}** "
                            f"({stages_data[slowest] * 1000:.1f} ms) &nbsp;·&nbsp; "
                            f"Total: **{total_ms:.0f} ms**"
                        )

                    if metrics:
                        st.divider()
                        eff1, eff2 = st.columns(2)
                        eff1.metric("Retrieved", metrics.get("total_retrieved", "N/A"))
                        eff2.metric("After Dedup", metrics.get("after_dedup", "N/A"))
                        eff1.metric("After Filter", metrics.get("after_filter", "N/A"))
                        eff2.metric("After Rerank", metrics.get("after_rerank", "N/A"))

        except Exception as e:
            stage_container.empty()
            answer_placeholder.markdown(
                f'<div class="callout warning">⚠️ An error occurred while generating the answer: <code>{e}</code></div>',
                unsafe_allow_html=True,
            )
