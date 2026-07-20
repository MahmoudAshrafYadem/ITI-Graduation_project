"""
Chat-based forecast assistant for lte_forecaster.
User types natural language like "show me the forecast for cell_001" and
the LLM decides to call get_cell_forecast(), then writes up the answer.

Wired to the actual core/ forecasting pipeline (not a stub).

Run with: streamlit run chat_forecast.py
Requires: ollama Python library (pip install ollama)
"""
import json
import streamlit as st
import pandas as pd

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
MODEL = "gemma4:latest"  # or "gemma4:latest" — change to your pulled model

# ---------------------------------------------------------------------------
# DATA LOADING (cached — load once per session)
# ---------------------------------------------------------------------------
@st.cache_data
def _load_data(path: str):
    from core.data_loading import load_data
    return load_data(path)

# ---------------------------------------------------------------------------
# 1. REAL DATA FUNCTION — wired to core/ pipeline
# ---------------------------------------------------------------------------
def get_cell_forecast(cell_id: str, kpi: str = "DL_Throughput", horizon_days: int = 7):
    """Run the actual forecasting pipeline for a cell and return structured results."""
    from config import KPI_OPTIONS, KPI_REVERSE_MAP, REQUIRED_COLS
    from core.data_loading import filter_cell, validate_cell_data
    from core.seasonality import compute_all_cell_seasonality
    from core.models.xgboost_model import run_xgboost_forecast
    from core.models.holt_winters import run_holt_winters_forecast
    from core.models.baseline import run_baseline_forecast
    from core.alerts import evaluate_alerts

    # Check if data is loaded
    if "df" not in st.session_state:
        return {"error": "No CSV uploaded yet. Please upload data in the main app first, or ensure a default CSV is configured."}

    df = st.session_state.df

    # Validate cell exists
    if cell_id not in df["Cell Name"].unique():
        available = ", ".join(df["Cell Name"].unique()[:10])
        return {"error": f"Cell '{cell_id}' not found. Available cells include: {available}..."}

    # Map friendly KPI name to internal
    kpi_internal = kpi
    if kpi not in REQUIRED_COLS:
        # Try reverse lookup from display name
        for display, internal in KPI_OPTIONS.items():
            if kpi.lower() in display.lower() or internal.lower() == kpi.lower():
                kpi_internal = internal
                break

    if kpi_internal not in REQUIRED_COLS:
        return {"error": f"KPI '{kpi}' not recognized. Try one of: {list(KPI_OPTIONS.keys())}"}

    # Prepare data
    cell_df = filter_cell(df, cell_id)
    available_cols = [c for c in REQUIRED_COLS if c in cell_df.columns]
    cell_df = cell_df[available_cols]

    test_days = 4
    validation = validate_cell_data(cell_df, kpi_internal, test_days)
    if not validation["ok"]:
        return {"error": validation["message"]}

    test_dates = cell_df.index[-test_days:]
    actual_test = cell_df[kpi_internal].loc[test_dates]
    future_dates = pd.date_range(cell_df.index[-1] + pd.Timedelta(days=1), periods=horizon_days, freq="D")

    # Run all models
    try:
        xgb_result = run_xgboost_forecast(
            cell_df, kpi_internal, available_cols, test_dates, test_days,
            show_future=True, future_dates=future_dates,
        )
        hw_result = run_holt_winters_forecast(
            cell_df, kpi_internal, test_dates, actual_test,
            show_future=True, future_dates=future_dates,
        )
        baseline_result = run_baseline_forecast(
            cell_df, kpi_internal, test_dates, actual_test,
            show_future=True, future_dates=future_dates,
        )
    except Exception as e:
        return {"error": f"Forecast failed: {str(e)}"}

    # Pick best
    results = [r for r in [xgb_result, hw_result, baseline_result] if r.forecast is not None]
    if not results:
        return {"error": "All models failed to produce a forecast."}
    best = min(results, key=lambda r: r.scores.mae)

    # Get alerts
    alerts = evaluate_alerts(cell_df, target_col=kpi_internal)
    alert_summary = [
        {"kpi": a.kpi_display, "status": a.status.value, "message": a.message}
        for a in alerts if a.status.value not in ("Normal", "Info")
    ]

    # Seasonality
    seasonality = compute_all_cell_seasonality(df, kpi_internal, period=7).get(cell_id)

    return {
        "cell_id": cell_id,
        "kpi": kpi_internal,
        "kpi_display": KPI_REVERSE_MAP.get(kpi_internal, kpi_internal),
        "model_used": best.model_name,
        "mae": round(best.scores.mae, 3),
        "rmse": round(best.scores.rmse, 3),
        "mape": round(best.scores.mape, 1),
        "forecast": [round(v, 2) for v in best.future_forecast.values] if best.future_forecast is not None else [],
        "dates": [d.strftime("%Y-%m-%d") for d in future_dates],
        "horizon_days": horizon_days,
        "alerts": alert_summary,
        "seasonality": seasonality.category if seasonality else "unknown",
        "seasonality_strength": round(seasonality.strength, 2) if seasonality and seasonality.strength else None,
    }


# ---------------------------------------------------------------------------
# 2. TOOL SCHEMA — tells the LLM what functions are available
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_cell_forecast",
            "description": (
                "Get the KPI forecast for a specific LTE cell. Use this whenever "
                "the user asks about a forecast, prediction, expected trend, "
                "or future values for a named cell."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cell_id": {
                        "type": "string",
                        "description": "The cell identifier, e.g. 'LCAIN10118-1' or 'Cell_001'",
                    },
                    "kpi": {
                        "type": "string",
                        "description": (
                            "Which KPI to forecast. Examples: 'DL_Throughput', "
                            "'DL_Traffic', 'RRC_Setup_SR', 'ERAB_Drop_Rate', "
                            "'DL_CQI', 'DL_IBLER'. Defaults to DL_Throughput."
                        ),
                    },
                    "horizon_days": {
                        "type": "integer",
                        "description": "How many days ahead to forecast. Default is 7.",
                    },
                },
                "required": ["cell_id"],
            },
        },
    }
]

AVAILABLE_FUNCTIONS = {
    "get_cell_forecast": get_cell_forecast,
}


# ---------------------------------------------------------------------------
# 3. TOOL-CALLING LOOP
# ---------------------------------------------------------------------------
def run_chat_turn(messages):
    """Send messages to LLM. If it wants to call a tool, execute it and
    call the model again for the final natural-language answer."""
    try:
        from ollama import chat
    except ImportError:
        return "❌ Error: ollama Python library not installed. Run: pip install ollama"

    try:
        response = chat(model=MODEL, messages=messages, tools=TOOLS)
    except Exception as e:
        return f"❌ Error connecting to Ollama: {str(e)}\n   Is Ollama running? Start with: ollama serve"

    msg = response["message"]
    tool_calls = msg.get("tool_calls")

    if not tool_calls:
        return msg["content"]

    # Model wants to call tool(s)
    messages.append(msg)

    for call in tool_calls:
        fn_name = call["function"]["name"]
        fn_args = call["function"]["arguments"]
        if isinstance(fn_args, str):
            fn_args = json.loads(fn_args)

        fn = AVAILABLE_FUNCTIONS.get(fn_name)
        if fn is None:
            result = {"error": f"Unknown tool: {fn_name}"}
        else:
            try:
                result = fn(**fn_args)
            except Exception as e:
                result = {"error": str(e)}

        # Convert numpy types to native Python types for JSON serialization
        def _convert(obj):
            if hasattr(obj, 'item'):  # numpy scalar
                return obj.item()
            if isinstance(obj, dict):
                return {k: _convert(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_convert(v) for v in obj]
            return obj
        messages.append({"role": "tool", "content": json.dumps(_convert(result))})

    # Call model again with tool results
    try:
        followup = chat(model=MODEL, messages=messages, tools=TOOLS)
        return followup["message"]["content"]
    except Exception as e:
        return f"❌ Error in follow-up: {str(e)}"


# ---------------------------------------------------------------------------
# 4. STREAMLIT CHAT UI
# ---------------------------------------------------------------------------
st.set_page_config(page_title="LTE Forecast Assistant", page_icon="📡", layout="wide")
st.title("📡 LTE Forecast Chat Assistant")
st.markdown("Ask about any cell's forecast in natural language. The AI will run the forecasting pipeline and explain the results.")

# ── Sidebar: data upload ──
st.sidebar.header("📂 Data Source")
csv_path = st.sidebar.text_input(
    "CSV file path",
    value="clean_data_28.csv",
    help="Path to your clean_normal_cells.csv file",
)

if st.sidebar.button("Load Data", use_container_width=True):
    try:
        st.session_state.df = _load_data(csv_path)
        st.sidebar.success(f"✅ Loaded {len(st.session_state.df)} rows, {st.session_state.df['Cell Name'].nunique()} cells")
    except Exception as e:
        st.sidebar.error(f"❌ Failed to load: {e}")

if "df" in st.session_state:
    st.sidebar.caption(f"📊 {st.session_state.df['Cell Name'].nunique()} cells available")

# ── Model selector ──
st.sidebar.header("🤖 Model")
model_choice = st.sidebar.selectbox(
    "Ollama model",
    ["gemma4:latest", "hermes3:latest", "llama3.1:latest", "mistral:latest"],
    index=0,
)
MODEL = model_choice

st.sidebar.markdown("---")
st.sidebar.caption("Make sure Ollama is running: `ollama serve`")

st.sidebar.markdown("---")
st.sidebar.info(
    "💡 **Gemma 4 Tip:** If the model answers without calling the tool, "
    "try rephrasing your question to explicitly ask for a forecast or prediction."
)

# ── Chat history ──
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "system",
            "content": (
                "You are an expert RF / telecom network optimization engineer. "
                "You have access to a forecasting tool called get_cell_forecast. "
                "When the user asks about ANY forecast, prediction, trend, or "
                "future value for a cell, you MUST call the get_cell_forecast tool. "
                "Do NOT guess or use your training data — always use the tool. "
                "After receiving tool results, summarize clearly for a telecom engineer."
            ),
        }
    ]

# Render chat history
for m in st.session_state.messages:
    if m["role"] in ("user", "assistant") and m.get("content"):
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

# ── Chat input ──
if prompt := st.chat_input("Ask about a cell's forecast, e.g. 'show me the forecast for LCAIN10118-1'"):
    if "df" not in st.session_state:
        st.error("❌ Please load a CSV file first using the sidebar.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner(f"Running forecast pipeline via {MODEL}..."):
            answer = run_chat_turn(st.session_state.messages)
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
