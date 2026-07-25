"""Streamlit Chat UI for Telecom RAG Assistant"""
import streamlit as st
import os
from app.rag import TelecomRAG
from app import profiler
from app.config import DEBUG_MODE, DATA_DIR

# --- Page Config ---
st.set_page_config(
    page_title="Telecom RAG Assistant",
    page_icon="📡",
    layout="wide"
)

# --- Helper function to get PDF files ---
@st.cache_data
def get_pdf_list():
    """Get a list of PDF files from the data directory."""
    if not os.path.exists(DATA_DIR):
        return ["All"]
    try:
        files = [f for f in os.listdir(DATA_DIR) if f.endswith(".pdf")]
        return ["All"] + files
    except Exception as e:
        st.error(f"Error reading data directory: {e}")
        return ["All"]

# --- Cache RAG Pipeline Initialization ---
@st.cache_resource
def get_rag_pipeline():
    print("Loading RAG Pipeline...")
    return TelecomRAG()

# --- Initialize Session State for Chat History ---
if "messages" not in st.session_state:
    st.session_state.messages = []

if "pipeline_metrics" not in st.session_state:
    st.session_state.pipeline_metrics = []

# --- Sidebar for Filters ---
with st.sidebar:
    st.header("🔎 Search Filters")
    st.write("Limit the search to a specific specification.")

    pdf_options = get_pdf_list()
    selected_pdf = st.selectbox("Filter by PDF", pdf_options)

    ts_filter = None
    release_filter = None

    if selected_pdf != "All":
        try:
            parts = selected_pdf.replace('.pdf', '').split('_')
            if len(parts) >= 3:
                ts_filter = parts[1]
                release_filter = parts[3]
        except Exception:
            st.warning(f"Could not parse TS and Release from '{selected_pdf}'.")

    st.divider()
    st.write("⚠️ **Note:** First question takes a few seconds as the AI models load.")

    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.session_state.pipeline_metrics = []
        st.rerun()

    if DEBUG_MODE:
        st.divider()
        st.subheader("🛠 Debug Panel")
        show_metrics = st.checkbox("Show Performance Metrics", value=False)
        if show_metrics and st.session_state.pipeline_metrics:
            for i, metric in enumerate(st.session_state.pipeline_metrics):
                with st.expander(f"Query {i + 1} — {metric.get('question', '?')[:50]}...", expanded=False):
                    st.json(metric)

# --- Main UI ---
st.title("📡 Telecom RAG Assistant")
st.caption("Ask engineering questions directly from 3GPP Specifications.")

# Initialize pipeline
try:
    rag = get_rag_pipeline()
except Exception as e:
    st.error(f"Failed to initialize AI models. Error: {e}")
    st.stop()

# Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        if message.get("references"):
            with st.expander(f"📖 View Citations ({len(message['references'])})"):
                for ref in message["references"]:
                    st.write(f"- **TS {ref['ts']}** | Release {ref['release']} | Section {ref['section']} | Page {ref['page']} _(Score: {ref['score']:.4f})_")

# Handle User Input
if prompt := st.chat_input("e.g., Explain Event A3 in LTE"):
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    stages = [
        "Embedding query...",
        "Searching vector database...",
        "Reranking retrieved chunks...",
        "Building prompt...",
        "Sending request to OpenRouter...",
        "Generating answer...",
        "Rendering response...",
    ]

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_answer = ""

        try:
            for stage_text in stages:
                placeholder.status(stage_text)

            response = rag.ask(
                question=prompt,
                ts_filter=ts_filter,
                release_filter=release_filter,
                history=st.session_state.messages[:-1]  # Pass all but the current user message
            )

            answer = response["answer"]
            refs = response["references"]
            metrics = response.get("metrics", {})

            full_answer = answer
            placeholder.success(full_answer)

            if refs:
                with st.expander(f"📖 View Citations ({len(refs)})"):
                    for ref in refs:
                        st.write(f"- **TS {ref['ts']}** | Release {ref['release']} | Section {ref['section']} | Page {ref['page']} _(Score: {ref['score']:.4f})_")

            st.session_state.messages.append({
                "role": "assistant",
                "content": full_answer,
                "references": refs
            })

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

                # Performance dashboard
                st.divider()
                with st.expander("📊 Performance Dashboard", expanded=False):
                    cols = st.columns(3)
                    for idx, (name, t_ms) in enumerate(stages_data.items()):
                        col = cols[idx % 3]
                        col.metric(
                            label=name,
                            value=f"{t_ms * 1000:.1f} ms",
                        )

                    if total_ms > 0:
                        slowest = max(stages_data, key=stages_data.get)
                        st.info(
                            f"Slowest stage: **{slowest}** "
                            f"({stages_data[slowest] * 1000:.1f} ms)"
                        )

                    if metrics:
                        st.divider()
                        st.subheader("Pipeline Efficiency")
                        eff_cols = st.columns(2)
                        eff_cols[0].metric("Retrieved", metrics.get("total_retrieved", "N/A"))
                        eff_cols[1].metric("After Dedup", metrics.get("after_dedup", "N/A"))
                        eff_cols[0].metric("After Filter", metrics.get("after_filter", "N/A"))
                        eff_cols[1].metric("After Rerank", metrics.get("after_rerank", "N/A"))

                        prompt_stats = {
                            k: v for k, v in metrics.items()
                            if k in ("chunks", "chars", "estimated_tokens", "avg_chunk_chars", "max_chunk_chars", "min_chunk_chars", "total_prompt_tokens")
                        }
                        if prompt_stats:
                            st.divider()
                            st.subheader("Prompt Statistics")
                            for k, v in prompt_stats.items():
                                st.write(f"- **{k}**: {v:,}" if isinstance(v, int) else f"- **{k}**: {v}")

        except Exception as e:
            placeholder.error(f"An error occurred: {e}")
