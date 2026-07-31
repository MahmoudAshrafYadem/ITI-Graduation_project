"""Streamlit UI — thin wrapper around core/ functions.

NO business logic lives here. This file only: renders widgets, calls core
functions, and displays results.
"""
import streamlit as st
import pandas as pd

from config import KPI_OPTIONS, REQUIRED_COLS, KPI_REVERSE_MAP
from core.data_loading import load_data, filter_cell, validate_cell_data
from core.seasonality import compute_all_cell_seasonality
from core.models.xgboost_model import run_xgboost_forecast
from core.models.holt_winters import run_holt_winters_forecast
from core.models.baseline import run_baseline_forecast
from core.alerts import evaluate_alerts
from core.report import generate_cell_report
from core.types import ReportContext

from plotting import build_forecast_figure, build_feature_importance_figure
from diagnostics import render_residual_analysis


if not st.session_state.get("_hub_mode", False):
    st.set_page_config(page_title="LTE KPI Forecaster", layout="wide")

st.markdown("""
<style>
:root {
    --accent: #00C2FF;
    --accent2: #7B61FF;
    --success: #00D97E;
    --warning: #FFB400;
    --bg-main: #0A1628;
    --bg-panel: #0D1E35;
}
html, body, [data-testid="stAppViewContainer"] {
    background-color: var(--bg-main) !important;
}
.stMarkdown p, .stMarkdown li, .stMarkdown div {
    font-size: 0.9rem;
    line-height: 1.6;
    color: rgba(255,255,255,0.85);
}
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {
    color: #FFFFFF;
}
.stCaption {
    font-size: 0.85rem !important;
    color: rgba(255,255,255,0.65) !important;
}
.stDataFrame {
    font-size: 0.82rem !important;
}
.stSidebar .stCaption {
    font-size: 0.78rem !important;
}
[data-testid="stSidebar"] {
    background: #0A1628 !important;
}
[data-testid="stSidebar"] .stButton > button {
    border-radius: 8px;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

st.title("📡 LTE Cell KPI Forecaster")
st.markdown("Upload your cleaned LTE data, select a cell and KPI, choose a forecast model, and get a forecast.")

# ═══════════════════════════════════════════════════════════════════════════════
# 1. FILE UPLOAD (UI layer only)
# ═══════════════════════════════════════════════════════════════════════════════
uploaded = st.file_uploader("Upload `clean_normal_cells.csv`", type=["csv"])

if not uploaded:
    st.info("👆 Upload your CSV file to get started.")
    st.stop()

# Cache at UI layer only
@st.cache_data
def _load_cached(file):
    return load_data(file)

df = _load_cached(uploaded)

# ═══════════════════════════════════════════════════════════════════════════════
# 2. SIDEBAR WIDGETS (UI layer only)
# ═══════════════════════════════════════════════════════════════════════════════
st.sidebar.header("⚙️ Settings")

st.sidebar.subheader("Forecast Model")
forecast_method = st.sidebar.radio(
    "Choose forecasting method",
    options=["XGBoost", "Holt-Winters", "Compare Both"],
    index=0,
)
st.sidebar.markdown("---")

selected_kpi_label = st.sidebar.selectbox("Select KPI to Forecast", list(KPI_OPTIONS.keys()))
target_col = KPI_OPTIONS[selected_kpi_label]

# Seasonality for cell sorting — computed once per (df, target_col)
@st.cache_data
def _seasonality_cached(_df, target_col):
    return compute_all_cell_seasonality(_df, target_col, period=7)

cell_seasonality = _seasonality_cached(df, target_col)

def _cell_sort_key(cell):
    s = cell_seasonality.get(cell)
    if s is None or s.strength is None:
        return (1, 0, cell)
    return (0, -s.strength, cell)

def _cell_label(cell):
    s = cell_seasonality.get(cell)
    if s and s.strength is not None:
        return f"{cell}  (seasonality {s.strength:.2f})"
    return f"{cell}  (seasonality N/A)"

cell_names = sorted(df["Cell Name"].unique(), key=_cell_sort_key)
selected_cell = st.sidebar.selectbox(
    "Select Cell", cell_names, format_func=_cell_label,
    help="Sorted by weekly seasonality strength (strong → weak).",
)

test_days = st.sidebar.slider("Hold-out test days", min_value=2, max_value=10, value=4)

run_xgb = forecast_method in ("XGBoost", "Compare Both")
run_hw  = forecast_method in ("Holt-Winters", "Compare Both")

st.sidebar.markdown("---")
st.sidebar.subheader("Diagnostics & Fallback")
show_future = st.sidebar.checkbox("Show next-7-day future forecast", value=True)
show_seasonality_flag = st.sidebar.checkbox("Flag seasonality strength", value=True)
show_baseline = st.sidebar.checkbox("Compare vs naive baseline (fallback)", value=True)

# XGBoost hyperparameters
if run_xgb:
    st.sidebar.markdown("---")
    st.sidebar.subheader("XGBoost hyperparameters")
    n_estimators  = st.sidebar.slider("n_estimators", 50, 300, 100, 50)
    learning_rate = st.sidebar.select_slider("learning_rate", [0.01, 0.03, 0.05, 0.1, 0.2], value=0.05)
    max_depth     = st.sidebar.slider("max_depth", 2, 6, 3)
    subsample     = st.sidebar.slider("subsample", 0.5, 1.0, 0.8, 0.1)
else:
    n_estimators = 100
    learning_rate = 0.05
    max_depth = 3
    subsample = 0.8

# Holt-Winters settings
if run_hw:
    st.sidebar.markdown("---")
    st.sidebar.subheader("Holt-Winters settings")
    hw_seasonal_periods = st.sidebar.slider("Seasonal periods (days)", min_value=2, max_value=7, value=7)
    hw_trend = st.sidebar.selectbox("Trend component", ["add", "mul", None], index=0)
    hw_seasonal = st.sidebar.selectbox("Seasonal component", ["add", "mul", None], index=0)
else:
    hw_seasonal_periods = 7
    hw_trend = "add"
    hw_seasonal = "add"

# ═══════════════════════════════════════════════════════════════════════════════
# 3. DATA PREPARATION (calls pure core functions)
# ═══════════════════════════════════════════════════════════════════════════════
cell_df = filter_cell(df, selected_cell)
available_cols = [c for c in REQUIRED_COLS if c in cell_df.columns]
cell_df = cell_df[available_cols]

validation = validate_cell_data(cell_df, target_col, test_days)
if not validation["ok"] and validation["severity"] == "error":
    st.error(validation["message"])
    st.stop()
if validation["severity"] == "warning":
    st.warning(validation["message"])

test_dates = cell_df.index[-test_days:]
actual_test = cell_df[target_col].loc[test_dates]

future_dates = None
if show_future:
    future_dates = pd.date_range(cell_df.index[-1] + pd.Timedelta(days=1), periods=7, freq="D")

seasonality = cell_seasonality.get(selected_cell) if show_seasonality_flag else None

# ═══════════════════════════════════════════════════════════════════════════════
# 4. RUN MODELS (calls pure core functions)
# ═══════════════════════════════════════════════════════════════════════════════
xgb_result = None
hw_result = None
baseline_result = None

if run_xgb:
    xgb_result = run_xgboost_forecast(
        cell_df, target_col, available_cols, test_dates, test_days,
        n_estimators, learning_rate, max_depth, subsample,
        show_future, future_dates,
    )

if run_hw:
    hw_result = run_holt_winters_forecast(
        cell_df, target_col, test_dates, actual_test,
        hw_trend, hw_seasonal, hw_seasonal_periods,
        show_future, future_dates,
    )

if show_baseline:
    baseline_result = run_baseline_forecast(
        cell_df, target_col, test_dates, actual_test, show_future, future_dates
    )

# ═══════════════════════════════════════════════════════════════════════════════
# 5. HEADER & SEASONALITY BADGE
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown(f"### Cell: `{selected_cell}`  |  KPI: **{selected_kpi_label}**  |  Model: **{forecast_method}**")

if show_seasonality_flag:
    if seasonality is None or seasonality.strength is None:
        st.info("ℹ️ Not enough history to reliably assess weekly seasonality (need at least 14 rows).")
    elif seasonality.category == "weak":
        st.warning(
            f"⚠️ **Weak seasonality** (strength = {seasonality.strength:.2f}). "
            "This cell doesn't show a strong repeating weekly pattern — lag-7 / "
            "weekly features may be adding noise rather than signal. Forecasts "
            "for this cell should be treated with lower confidence, and the "
            "naive/weekly-mean baseline below may be more reliable."
        )
    elif seasonality.category == "moderate":
        st.info(f"🟡 **Moderate seasonality** (strength = {seasonality.strength:.2f}).")
    else:
        st.success(f"✅ **Strong seasonality** (strength = {seasonality.strength:.2f}).")

# ═══════════════════════════════════════════════════════════════════════════════
# 6. BASELINE COMPARISON
# ═══════════════════════════════════════════════════════════════════════════════
if show_baseline and baseline_result and baseline_result.forecast is not None:
    model_maes = {}
    if xgb_result: model_maes["XGBoost"] = xgb_result.scores.mae
    if hw_result and hw_result.forecast is not None: model_maes["Holt-Winters"] = hw_result.scores.mae

    b1, b2 = st.columns([1, 2])
    b1.metric(f"Baseline MAE ({baseline_result.model_name})", f"{baseline_result.scores.mae:.3f}")

    with b2:
        if model_maes:
            best_name = min(model_maes, key=model_maes.get)
            best_mae = model_maes[best_name]
            if baseline_result.scores.mae < best_mae:
                st.warning(
                    f"⚠️ The **{baseline_result.model_name}** baseline (MAE {baseline_result.scores.mae:.3f}) beats "
                    f"your best model, **{best_name}** (MAE {best_mae:.3f}), "
                    "on this cell's hold-out set. Consider falling back to the baseline "
                    "here rather than trusting the model output."
                )
            else:
                st.success(
                    f"✅ **{best_name}** (MAE {best_mae:.3f}) beats the "
                    f"**{baseline_result.model_name}** baseline (MAE {baseline_result.scores.mae:.3f}) — model is "
                    "adding real value for this cell."
                )
        else:
            st.caption("Run a model to compare against the baseline.")

# ═══════════════════════════════════════════════════════════════════════════════
# 7. METRICS
# ═══════════════════════════════════════════════════════════════════════════════
def _render_metrics(result, label):
    if result is None or result.forecast is None:
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("MAE",  f"{result.scores.mae:.3f}")
    c2.metric("RMSE", f"{result.scores.rmse:.3f}")
    c3.metric("MAPE", f"{result.scores.mape:.1f}%")

if forecast_method == "Compare Both":
    mc = st.columns(2)
    with mc[0]: st.markdown("**XGBoost**"); _render_metrics(xgb_result, "XGBoost")
    with mc[1]: st.markdown("**Holt-Winters**"); _render_metrics(hw_result, "HW")
elif forecast_method == "XGBoost":
    _render_metrics(xgb_result, "XGBoost")
else:
    _render_metrics(hw_result, "HW")

# ═══════════════════════════════════════════════════════════════════════════════
# 8. FORECAST PLOT
# ═══════════════════════════════════════════════════════════════════════════════
fig = build_forecast_figure(
    cell_df, target_col, selected_kpi_label, test_dates,
    xgb_forecast=xgb_result.forecast if xgb_result else None,
    future_xgb_forecast=xgb_result.future_forecast if xgb_result else None,
    hw_forecast=hw_result.forecast if hw_result else None,
    future_hw_forecast=hw_result.future_forecast if hw_result else None,
    baseline_forecast=baseline_result.forecast if baseline_result else None,
    future_baseline_forecast=baseline_result.future_forecast if baseline_result else None,
    baseline_label=baseline_result.model_name if baseline_result else None,
)
st.plotly_chart(fig, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# 9. PREDICTIONS TABLE
# ═══════════════════════════════════════════════════════════════════════════════
st.subheader("Predictions")

pred_df = pd.DataFrame({
    "Date": test_dates.strftime("%Y-%m-%d"),
    "Actual Values": actual_test.values.round(3),
})
if xgb_result and xgb_result.forecast is not None:
    pred_df["XGBoost Forecast"] = xgb_result.forecast.values.round(3)
if hw_result and hw_result.forecast is not None:
    pred_df["Holt-Winters Forecast"] = hw_result.forecast.values.round(3)
if baseline_result and baseline_result.forecast is not None:
    pred_df[f"Baseline ({baseline_result.model_name})"] = baseline_result.forecast.values.round(3)

st.dataframe(pred_df, use_container_width=True, hide_index=True)

# Future forecast table
if not show_future:
    st.caption("🔕 Next-7-day future forecast is turned off (see sidebar toggle).")
elif (xgb_result and xgb_result.future_forecast is not None) or \
     (hw_result and hw_result.future_forecast is not None) or \
     (baseline_result and baseline_result.future_forecast is not None):
    st.subheader("Next 7 Days Forecast")
    future_df = pd.DataFrame({"Date": future_dates.strftime("%Y-%m-%d")})
    if xgb_result and xgb_result.future_forecast is not None:
        future_df["XGBoost"] = xgb_result.future_forecast.round(3).values
    if hw_result and hw_result.future_forecast is not None:
        future_df["Holt-Winters"] = hw_result.future_forecast.round(3).values
    if baseline_result and baseline_result.future_forecast is not None:
        future_df[f"Baseline ({baseline_result.model_name})"] = baseline_result.future_forecast.round(3).values
    st.dataframe(future_df, hide_index=True, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# 10. FEATURE IMPORTANCE (XGBoost only)
# ═══════════════════════════════════════════════════════════════════════════════
if xgb_result and xgb_result.feature_importance is not None:
    with st.expander("📊 Feature Importance (XGBoost)"):
        fig_imp = build_feature_importance_figure(
            xgb_result.feature_importance["Feature"].values,
            xgb_result.feature_importance["Importance"].values,
        )
        st.plotly_chart(fig_imp, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# 11. RESIDUAL ANALYSIS (XGBoost only)
# ═══════════════════════════════════════════════════════════════════════════════
if xgb_result and xgb_result.y_train is not None and xgb_result.train_residuals is not None:
    render_residual_analysis(
        xgb_result.y_train,
        xgb_result.train_predictions,
        xgb_result.train_residuals,
    )

# ═══════════════════════════════════════════════════════════════════════════════
# 12. LLM-READY REPORT
# ═══════════════════════════════════════════════════════════════════════════════
st.subheader("📋 LLM-Ready Report")
report_col1, report_col2 = st.columns([1, 3])
with report_col1:
    generate_btn = st.button("📝 Generate Report for This Cell", use_container_width=True)
with report_col2:
    st.caption(
        "Produces a structured prompt summarizing all KPIs, trends, forecasts, "
        "and alerts. Copy-paste directly into Claude, ChatGPT, or any LLM."
    )

if generate_btn:
    with st.spinner("Building report…"):
        # Build forecast dict for the target KPI
        forecasts = {}
        best_for_report = None
        if run_xgb and xgb_result and xgb_result.future_forecast is not None:
            best_for_report = xgb_result
        elif run_hw and hw_result and hw_result.future_forecast is not None:
            best_for_report = hw_result

        if best_for_report and future_dates is not None:
            forecasts[target_col] = best_for_report.to_report_dict(dates=future_dates)

        # Generate alerts
        alerts = evaluate_alerts(cell_df, target_col=target_col)

        # Build report context
        context = ReportContext(
            cell_name=selected_cell,
            kpi_map=KPI_REVERSE_MAP,
            forecasts=forecasts,
            alerts=alerts,
            seasonality=seasonality,
        )
        report_text = generate_cell_report(df, selected_cell, context=context)

    st.code(report_text, language=None)
    st.success("✅ Report generated! Click the copy button in the top-right of the code block above.")
