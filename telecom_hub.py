"""Unified Streamlit entry point for the telecom optimization tools.

Run from the repository root:
    streamlit run telecom_hub.py
"""
from __future__ import annotations

import runpy
import sys
from contextlib import contextmanager
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).resolve().parent
TOOLS = {
    "LTE KPI Degradation Analyzer": ROOT / "LTE_RAN_KPI_Analysis_Tool" / "app" / "app_streamlit.py",
    "LTE KPI Forecaster": ROOT / "forcasting_section" / "v2" / "app.py",
    "Optimization Action Analyzer": ROOT / "ActionAnalyzer_tool" / "app.py",
    "3GPP RAG Assistant": ROOT / "RAG_tool" / "app" / "ui.py",
}


def _purge_local_modules(tool_dir: Path) -> None:
    """Prevent bare imports such as ``config`` leaking between selected tools."""
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

with st.sidebar:
    st.title("Telecom Tools")
    selected_tool = st.selectbox("Choose a tool", list(TOOLS), key="hub_selected_tool")
    st.caption("Select a tool to load its interface below.")
    st.divider()

tool_path = TOOLS[selected_tool]
try:
    with _tool_environment(tool_path):
        runpy.run_path(str(tool_path), run_name="__main__")
except Exception as exc:
    st.error(f"Could not load {selected_tool}: {exc}")
    st.exception(exc)
