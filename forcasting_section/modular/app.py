import streamlit as st
import pandas as pd

from config import KPI_OPTIONS, REQUIRED_COLS, KPI_REVERSE_MAP
from data_loader import load_data
from seasonality import compute_all_cell_seasonality
from models.xgboost_model import run_xgboost_forecast
from models.holt_winters import run_holt_winters_forecast
from models.baseline import run_baseline_forecast
from diagnostics import render_residual_analysis
from plotting import build_forecast_figure, build_feature_importance_figure
from alerts import generate_cell_alerts
from report import generate_report_for_streamlit


st.set_page_config(page_title="LTE KPI Forecaster", layout="wide")

st.title("📡 LTE Cell KPI Forecaster")
st.markdown("Upload your cleaned LTE data, select a cell and KPI, choose a forecast model, and get a forecast.")

# ── 1. File upload ──────────────────────────────────────────────────────────
uploaded = st.file_uploader("Upload `clean_normal_cells.csv`", type=["csv"])

if not uploaded:
    st.info("👆 Upload your CSV file to get started.")
    st.stop()

df = load_data(uploaded)

# ── 2. Sidebar controls ──────────────────────────────────────────────────────
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

cell_seasonality = compute_all_cell_seasonality(df, target_col, period=7)


def _cell_sort_key(cell):
    s = cell_seasonality.get(cell)
    # Known strengths first (strong → weak), cells with insufficient data pushed to the end
    return (1, 0, cell) if s is None else (0, -s, cell)


def _cell_label(cell):
    s = cell_seasonality.get(cell)
    return f"{cell}  (seasonality {s:.2f})" if s is not None else f"{cell}  (seasonality N/A)"


cell_names = sorted(df["Cell Name"].unique(), key=_cell_sort_key)
selected_cell = st.sidebar.selectbox(
    "Select Cell",
    cell_names,
    format_func=_cell_label,
    help="Sorted by weekly seasonality strength for the selected KPI (strong → weak).",
)

test_days = st.sidebar.slider(
    "Hold-out test days", min_value=2, max_value=10, value=4,
    help="Number of most-recent days used as the test set."
)

run_xgb = forecast_method in ("XGBoost", "Compare Both")
run_hw  = forecast_method in ("Holt-Winters", "Compare Both")

st.sidebar.markdown("---")
st.sidebar.subheader("Diagnostics & Fallback")
show_future = st.sidebar.checkbox(
    "Show next-7-day future forecast", value=True,
    help="Turn off to skip the recursive future forecast and speed things up."
)
show_seasonality_flag = st.sidebar.checkbox(
    "Flag seasonality strength", value=True,
    help="Runs an STL decomposition and warns when a cell has weak/unreliable weekly seasonality."
)
show_baseline = st.sidebar.checkbox(
    "Compare vs naive baseline (fallback)", value=True,
    help="Backtests a simple persistence/weekly-mean baseline and recommends it when it beats the model(s)."
)

if run_xgb:
    st.sidebar.markdown("---")
    st.sidebar.subheader("XGBoost hyperparameters")
    n_estimators  = st.sidebar.slider("n_estimators", 50, 300, 100, 50)
    learning_rate = st.sidebar.select_slider("learning_rate", [0.01, 0.03, 0.05, 0.1, 0.2], value=0.05)
    max_depth     = st.sidebar.slider("max_depth", 2, 6, 3)
    subsample     = st.sidebar.slider("subsample", 0.5, 1.0, 0.8, 0.1)

if run_hw:
    st.sidebar.markdown("---")
    st.sidebar.subheader("Holt-Winters settings")
    hw_seasonal_periods = st.sidebar.slider(
        "Seasonal periods (days)", min_value=2, max_value=7, value=7,
        help="7 = weekly seasonality on daily data."
    )
    hw_trend = st.sidebar.selectbox("Trend component", ["add", "mul", None], index=0)
    hw_seasonal = st.sidebar.selectbox("Seasonal component", ["add", "mul", None], index=0)

# ── 3. Data preparation ──────────────────────────────────────────────────────
cell_df = (
    df[df["Cell Name"] == selected_cell]
    .sort_values("Date")
    .set_index("Date")
)

available_cols = [c for c in REQUIRED_COLS if c in cell_df.columns]
cell_df = cell_df[available_cols]

if target_col not in cell_df.columns:
    st.error(f"Column **{target_col}** not found in data. Please pick another KPI.")
    st.stop()

if len(cell_df) < 15:
    st.warning(f"Only {len(cell_df)} rows for this cell — results may be unreliable.")

if len(cell_df) <= test_days:
    st.error(f"Not enough data ({len(cell_df)} rows) for {test_days} test days. Reduce the hold-out slider.")
    st.stop()

test_dates = cell_df.index[-test_days:]
actual_test = cell_df[target_col].loc[test_dates]

future_dates = None
if show_future:
    future_dates = pd.date_range(cell_df.index[-1] + pd.Timedelta(days=1), periods=7, freq="D")

seasonality_strength = cell_seasonality.get(selected_cell) if show_seasonality_flag else None

# ── 4. Run models ──────────────────────────────────────────────────────────────
xgb_result = None
if run_xgb:
    xgb_result = run_xgboost_forecast(
        cell_df, target_col, available_cols, test_dates, test_days,
        n_estimators, learning_rate, max_depth, subsample,
        show_future, future_dates,
    )

hw_result = None
if run_hw:
    hw_result = run_holt_winters_forecast(
        cell_df, target_col, test_dates, actual_test,
        hw_trend, hw_seasonal, hw_seasonal_periods,
        show_future, future_dates,
    )

baseline_result = None
if show_baseline:
    baseline_result = run_baseline_forecast(
        cell_df, target_col, test_dates, actual_test, show_future, future_dates
    )

# Unpack for convenience
xgb_forecast         = xgb_result["xgb_forecast"] if xgb_result else None
future_xgb_forecast  = xgb_result["future_xgb_forecast"] if xgb_result else None
hw_forecast          = hw_result["hw_forecast"] if hw_result else None
future_hw_forecast   = hw_result["future_hw_forecast"] if hw_result else None
baseline_forecast        = baseline_result["baseline_forecast"] if baseline_result else None
baseline_label            = baseline_result["baseline_label"] if baseline_result else None
baseline_mae              = baseline_result["baseline_mae"] if baseline_result else None
future_baseline_forecast  = baseline_result["future_baseline_forecast"] if baseline_result else None

# ── 5. Header ────────────────────────────────────────────────────────────────
st.markdown(f"### Cell: `{selected_cell}`  |  KPI: **{selected_kpi_label}**  |  Model: **{forecast_method}**")

# ── 5a. Seasonality strength badge ───────────────────────────────────────────
if show_seasonality_flag:
    if seasonality_strength is None:
        st.info("ℹ️ Not enough history to reliably assess weekly seasonality (need at least 14 rows).")
    elif seasonality_strength < 0.3:
        st.warning(
            f"⚠️ **Weak seasonality** (strength = {seasonality_strength:.2f}). "
            "This cell doesn't show a strong repeating weekly pattern — lag-7 / "
            "weekly features may be adding noise rather than signal. Forecasts "
            "for this cell should be treated with lower confidence, and the "
            "naive/weekly-mean baseline below may be more reliable."
        )
    elif seasonality_strength < 0.6:
        st.info(f"🟡 **Moderate seasonality** (strength = {seasonality_strength:.2f}).")
    else:
        st.success(f"✅ **Strong seasonality** (strength = {seasonality_strength:.2f}).")

# ── 5b. Baseline comparison + fallback recommendation ────────────────────────
if show_baseline and baseline_forecast is not None:
    model_maes = {}
    if xgb_result:
        model_maes["XGBoost"] = xgb_result["xgb_mae"]
    if hw_result and hw_result["hw_forecast"] is not None:
        model_maes["Holt-Winters"] = hw_result["hw_mae"]

    b1, b2 = st.columns([1, 2])
    b1.metric(f"Baseline MAE ({baseline_label})", f"{baseline_mae:.3f}")

    if model_maes:
        best_model_name = min(model_maes, key=model_maes.get)
        best_model_mae = model_maes[best_model_name]
        with b2:
            if baseline_mae < best_model_mae:
                st.warning(
                    f"⚠️ The **{baseline_label}** baseline (MAE {baseline_mae:.3f}) beats "
                    f"your best model, **{best_model_name}** (MAE {best_model_mae:.3f}), "
                    "on this cell's hold-out set. Consider falling back to the baseline "
                    "here rather than trusting the model output."
                )
            else:
                st.success(
                    f"✅ **{best_model_name}** (MAE {best_model_mae:.3f}) beats the "
                    f"**{baseline_label}** baseline (MAE {baseline_mae:.3f}) — model is "
                    "adding real value for this cell."
                )
    else:
        b2.caption("Run a model to compare against the baseline.")

# ── 5c. Metrics ──────────────────────────────────────────────────────────────
if forecast_method == "Compare Both":
    metric_cols = st.columns(2)
    with metric_cols[0]:
        st.markdown("**XGBoost**")
        c1, c2, c3 = st.columns(3)
        c1.metric("MAE",  f"{xgb_result['xgb_mae']:.3f}")
        c2.metric("RMSE", f"{xgb_result['xgb_rmse']:.3f}")
        c3.metric("MAPE", f"{xgb_result['xgb_mape']:.1f}%")
    with metric_cols[1]:
        st.markdown("**Holt-Winters**")
        if hw_forecast is not None:
            c1, c2, c3 = st.columns(3)
            c1.metric("MAE",  f"{hw_result['hw_mae']:.3f}")
            c2.metric("RMSE", f"{hw_result['hw_rmse']:.3f}")
            c3.metric("MAPE", f"{hw_result['hw_mape']:.1f}%")
        else:
            st.info("No Holt-Winters results.")
elif forecast_method == "XGBoost":
    c1, c2, c3 = st.columns(3)
    c1.metric("MAE",  f"{xgb_result['xgb_mae']:.3f}")
    c2.metric("RMSE", f"{xgb_result['xgb_rmse']:.3f}")
    c3.metric("MAPE", f"{xgb_result['xgb_mape']:.1f}%")
elif forecast_method == "Holt-Winters" and hw_forecast is not None:
    c1, c2, c3 = st.columns(3)
    c1.metric("MAE",  f"{hw_result['hw_mae']:.3f}")
    c2.metric("RMSE", f"{hw_result['hw_rmse']:.3f}")
    c3.metric("MAPE", f"{hw_result['hw_mape']:.1f}%")

# ── 6. Forecast plot ───────────────────────────────────────────────────────────
fig = build_forecast_figure(
    cell_df, target_col, selected_kpi_label, test_dates,
    xgb_forecast=xgb_forecast, future_xgb_forecast=future_xgb_forecast,
    hw_forecast=hw_forecast, future_hw_forecast=future_hw_forecast,
    baseline_forecast=baseline_forecast, future_baseline_forecast=future_baseline_forecast,
    baseline_label=baseline_label,
)
st.plotly_chart(fig, use_container_width=True)

# ── 7. Predictions section ─────────────────────────────────────────────────────
st.subheader("Predictions")

pred_df = pd.DataFrame({
    "Date": test_dates.strftime("%Y-%m-%d"),
    "Actual Values": actual_test.values.round(3),
})

if xgb_forecast is not None:
    pred_df["XGBoost Forecast"] = xgb_forecast.values.round(3)

if hw_forecast is not None:
    pred_df["Holt-Winters Forecast"] = hw_forecast.values.round(3)

if baseline_forecast is not None:
    pred_df[f"Baseline ({baseline_label})"] = baseline_forecast.values.round(3)

st.dataframe(pred_df, use_container_width=True, hide_index=True)

# ── 7b. Future forecast table (production forecast, no actuals available) ────
if not show_future:
    st.caption("🔕 Next-7-day future forecast is turned off (see sidebar toggle).")
elif future_xgb_forecast is not None or future_hw_forecast is not None or future_baseline_forecast is not None:
    st.subheader("Next 7 Days Forecast")

    future_df = pd.DataFrame({"Date": future_dates.strftime("%Y-%m-%d")})

    if future_xgb_forecast is not None:
        future_df["XGBoost"] = future_xgb_forecast.round(3).values

    if future_hw_forecast is not None:
        future_df["Holt-Winters"] = future_hw_forecast.round(3).values

    if future_baseline_forecast is not None:
        future_df[f"Baseline ({baseline_label})"] = future_baseline_forecast.round(3).values

    st.dataframe(future_df, hide_index=True, use_container_width=True)

# ── 8. Feature importance (XGBoost only) ──────────────────────────────────────
if xgb_result:
    with st.expander("📊 Feature Importance (XGBoost)"):
        fig_imp = build_feature_importance_figure(
            xgb_result["X_train"].columns, xgb_result["model"].feature_importances_
        )
        st.plotly_chart(fig_imp, use_container_width=True)

# ── 9. Residual analysis (XGBoost only) ───────────────────────────────────────
if xgb_result:
    render_residual_analysis(
        xgb_result["y_train"], xgb_result["train_preds"], xgb_result["train_residuals"]
    )

# ═══════════════════════════════════════════════════════════════════════════════
# 10. LLM-Ready Report — FULLY WIRED with forecasts, alerts, and metrics
# ═══════════════════════════════════════════════════════════════════════════════

# ── 10a. Build forecast_results dict for the report ──────────────────────────
forecast_results = {}

# Target KPI forecast from the active model(s)
if run_xgb and xgb_result and future_xgb_forecast is not None:
    forecast_results[target_col] = {
        "forecast": future_xgb_forecast.round(3).tolist(),
        "dates": future_xgb_forecast.index.strftime("%Y-%m-%d").tolist(),
        "mae": round(xgb_result["xgb_mae"], 3),
        "mape": round(xgb_result["xgb_mape"], 1),
    }
elif run_hw and hw_result and future_hw_forecast is not None:
    forecast_results[target_col] = {
        "forecast": future_hw_forecast.round(3).tolist(),
        "dates": future_hw_forecast.index.strftime("%Y-%m-%d").tolist(),
        "mae": round(hw_result["hw_mae"], 3),
        "mape": round(hw_result["hw_mape"], 1),
    }

# ── 10b. Build alert_results dict for the report ─────────────────────────────
alert_results = generate_cell_alerts(cell_df, target_col=target_col)

# ── 10c. Render the report UI ────────────────────────────────────────────────
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
        report_text = generate_report_for_streamlit(
            df,
            cell_name=selected_cell,
            kpi_map=KPI_REVERSE_MAP,
            forecasts=forecast_results,
            alerts=alert_results,
        )
    st.code(report_text, language=None)
    st.success("✅ Report generated! Click the copy button in the top-right of the code block above.")
