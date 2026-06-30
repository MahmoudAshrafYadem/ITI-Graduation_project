import streamlit as st
import pandas as pd
import numpy as np
import xgboost as xgb
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.metrics import mean_absolute_error, mean_squared_error
from statsmodels.stats.stattools import durbin_watson
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.holtwinters import ExponentialSmoothing

st.set_page_config(page_title="LTE KPI Forecaster", layout="wide")

st.title("📡 LTE Cell KPI Forecaster")
st.markdown("Upload your cleaned LTE data, select a cell and KPI, choose a forecast model, and get a forecast.")

# ── 1. File upload ──────────────────────────────────────────────────────────
uploaded = st.file_uploader("Upload `clean_normal_cells.csv`", type=["csv"])

if not uploaded:
    st.info("👆 Upload your CSV file to get started.")
    st.stop()

@st.cache_data
def load_data(file):
    df = pd.read_csv(file)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.rename(columns={
        "(HU) Cell DL Average Throughput (Mbps)": "DL_Throughput",
        "(HU) DL Traffic Volume (GBytes)":        "DL_Traffic",
        "(HU) Average UE Number":                 "Avg_UE_Number",
        "L.Traffic.ActiveUser.Avg":               "Active_Users",
    })
    return df

df = load_data(uploaded)

KPI_OPTIONS = {
    "DL Traffic Volume (GBytes)":       "DL_Traffic",
    "DL Average Throughput (Mbps)":     "DL_Throughput",
    "Average UE Number":                "Avg_UE_Number",
    "Active Users":                     "Active_Users",
}

# ── 2. Sidebar controls ──────────────────────────────────────────────────────
st.sidebar.header("⚙️ Settings")

st.sidebar.subheader("Forecast Model")
forecast_method = st.sidebar.radio(
    "Choose forecasting method",
    options=["XGBoost", "Holt-Winters", "Compare Both"],
    index=0,
)
st.sidebar.markdown("---")

cell_names = sorted(df["Cell Name"].unique())
selected_cell = st.sidebar.selectbox("Select Cell", cell_names)

selected_kpi_label = st.sidebar.selectbox("Select KPI to Forecast", list(KPI_OPTIONS.keys()))
target_col = KPI_OPTIONS[selected_kpi_label]

test_days = st.sidebar.slider(
    "Hold-out test days", min_value=2, max_value=10, value=4,
    help="Number of most-recent days used as the test set."
)

run_xgb = forecast_method in ("XGBoost", "Compare Both")
run_hw  = forecast_method in ("Holt-Winters", "Compare Both")

if run_xgb:
    st.sidebar.markdown("---")
    st.sidebar.subheader("XGBoost hyperparameters")
    n_estimators  = st.sidebar.slider("n_estimators",  50, 300, 100, 50)
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

required_cols = ["DL_Throughput", "DL_Traffic", "Avg_UE_Number", "Active_Users"]
available_cols = [c for c in required_cols if c in cell_df.columns]
cell_df = cell_df[available_cols]

if target_col not in cell_df.columns:
    st.error(f"Column **{target_col}** not found in data. Please pick another KPI.")
    st.stop()

if len(cell_df) < 15:
    st.warning(f"Only {len(cell_df)} rows for this cell — results may be unreliable.")

if len(cell_df) <= test_days:
    st.error(f"Not enough data ({len(cell_df)} rows) for {test_days} test days. Reduce the hold-out slider.")
    st.stop()

# Common test window (last `test_days` dates) used by every model for a fair comparison
test_dates = cell_df.index[-test_days:]
actual_test = cell_df[target_col].loc[test_dates]

# ── 4. XGBoost feature engineering ───────────────────────────────────────────
def build_features(cell_df, target_col):
    features = pd.DataFrame(index=cell_df.index)
    features["y"] = cell_df[target_col]

    # --- Telecom KPIs (shifted to avoid leakage) ---
    for col in available_cols:
        if col != target_col:
            features[col] = cell_df[col].shift(1)

    # --- Lag features ---
    for k in [1, 2, 3, 5, 6, 7]:
        features[f"lag_{k}"] = features["y"].shift(k)

    # --- Rolling stats (shift 1 to avoid leakage) ---
    _y_shifted = features["y"].shift(1)
    _week_mean = _y_shifted.rolling(7).mean()

    features["week_std"]       = _y_shifted.rolling(7).std()
    features["week_min"]       = _y_shifted.rolling(7).min()
    features["rolling_mean_3"] = _y_shifted.rolling(3).mean()
    features["ewm_3"]          = _y_shifted.ewm(span=3).mean()
    features["rolling_cv"]     = features["week_std"] / _week_mean

    # --- Normalized lags ---
    features["lag5_norm"]    = features["lag_5"] / _week_mean
    features["lag7_norm"]    = features["lag_7"] / _week_mean

    # --- Shape descriptors ---
    features["lag7_position"]  = features["lag_7"] - _week_mean
    features["weekly_slope"]   = features["lag_1"] - features["lag_7"]

    # --- Momentum ---
    features["momentum_1"]   = features["lag_1"] - features["lag_2"]
    features["momentum_2"]   = features["lag_2"] - features["lag_3"]

    # --- Lag ratio ---
    features["lag1_lag7_ratio"] = features["lag_1"] / (features["lag_7"] + 1e-9)

    # --- Week-over-week diff ---
    features["lag_8"]        = features["y"].shift(8)
    features["wow_diff"]     = features["lag_1"] - features["lag_8"]

    features["lag1_x_lag7"] = features["lag_1"] * features["lag_7"]
    return features.dropna()


xgb_forecast = None
hw_forecast = None

if run_xgb:
    features = build_features(cell_df, target_col)
    if len(features) <= test_days:
        st.error(
            f"Not enough data after feature engineering ({len(features)} rows) "
            f"for {test_days} test days. Reduce the hold-out slider."
        )
        st.stop()

    # ── Train / test split ───────────────────────────────────────────────────
    split   = len(features) - test_days
    train   = features.iloc[:split]
    test    = features.iloc[split:]

    X_train = train.drop(columns="y")
    y_train = train["y"]
    X_test  = test.drop(columns="y")
    y_test  = test["y"]

    # ── Model training ───────────────────────────────────────────────────────
    @st.cache_resource(show_spinner="Training XGBoost model…")
    def train_model(X_tr, y_tr, n_est, lr, depth, subs):
        model = xgb.XGBRegressor(
            n_estimators=n_est,
            learning_rate=lr,
            max_depth=depth,
            subsample=subs,
            colsample_bytree=0.8,
            min_child_weight=3,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=42,
            verbosity=0,
        )
        model.fit(X_tr, y_tr)
        return model

    model = train_model(
        X_train, y_train,
        n_estimators, learning_rate, max_depth, subsample
    )

    xgb_forecast = pd.Series(model.predict(X_test), index=y_test.index)

    # Residuals
    train_preds     = model.predict(X_train)
    train_residuals = y_train.values - train_preds
    test_residuals  = y_test.values - xgb_forecast.values

    xgb_mae  = mean_absolute_error(y_test, xgb_forecast)
    xgb_rmse = np.sqrt(mean_squared_error(y_test, xgb_forecast))
    xgb_mape = np.mean(np.abs((y_test.values - xgb_forecast.values) / y_test.values.clip(1e-6))) * 100

# ── 5. Holt-Winters forecasting ──────────────────────────────────────────────
if run_hw:
    hw_train_series = cell_df[target_col].loc[: test_dates[0]].iloc[:-1]

    min_required = (hw_seasonal_periods * 2) if hw_seasonal else 2
    if hw_seasonal and len(hw_train_series) < min_required:
        st.warning(
            f"⚠️ Holt-Winters needs at least {min_required} training points for "
            f"{hw_seasonal_periods}-day seasonality, but only {len(hw_train_series)} are available. "
            "Seasonal component may be unreliable or fail to fit."
        )

    try:
        hw_model = ExponentialSmoothing(
            hw_train_series,
            trend=hw_trend if hw_trend != "None" else None,
            seasonal=hw_seasonal if hw_seasonal != "None" else None,
            seasonal_periods=hw_seasonal_periods if hw_seasonal else None,
            initialization_method="estimated",
        )
        hw_fitted = hw_model.fit(optimized=True)
        hw_forecast = pd.Series(hw_fitted.forecast(test_days).values, index=test_dates)

        hw_mae  = mean_absolute_error(actual_test, hw_forecast)
        hw_rmse = np.sqrt(mean_squared_error(actual_test, hw_forecast))
        hw_mape = np.mean(np.abs((actual_test.values - hw_forecast.values) / actual_test.values.clip(1e-6))) * 100
    except Exception as e:
        st.error(f"Holt-Winters fitting failed: {e}")
        hw_forecast = None

# ── 6. Layout: header + metrics ──────────────────────────────────────────────
st.markdown(f"### Cell: `{selected_cell}`  |  KPI: **{selected_kpi_label}**  |  Model: **{forecast_method}**")

if forecast_method == "Compare Both":
    metric_cols = st.columns(2)
    with metric_cols[0]:
        st.markdown("**XGBoost**")
        c1, c2, c3 = st.columns(3)
        c1.metric("MAE",  f"{xgb_mae:.3f}")
        c2.metric("RMSE", f"{xgb_rmse:.3f}")
        c3.metric("MAPE", f"{xgb_mape:.1f}%")
    with metric_cols[1]:
        st.markdown("**Holt-Winters**")
        if hw_forecast is not None:
            c1, c2, c3 = st.columns(3)
            c1.metric("MAE",  f"{hw_mae:.3f}")
            c2.metric("RMSE", f"{hw_rmse:.3f}")
            c3.metric("MAPE", f"{hw_mape:.1f}%")
        else:
            st.info("No Holt-Winters results.")
elif forecast_method == "XGBoost":
    c1, c2, c3 = st.columns(3)
    c1.metric("MAE",  f"{xgb_mae:.3f}")
    c2.metric("RMSE", f"{xgb_rmse:.3f}")
    c3.metric("MAPE", f"{xgb_mape:.1f}%")
elif forecast_method == "Holt-Winters" and hw_forecast is not None:
    c1, c2, c3 = st.columns(3)
    c1.metric("MAE",  f"{hw_mae:.3f}")
    c2.metric("RMSE", f"{hw_rmse:.3f}")
    c3.metric("MAPE", f"{hw_mape:.1f}%")

## ── 7. Forecast plot ──────────────────────────────────────────────────────────
#fig = go.Figure()
#
#if run_xgb:
#    fig.add_trace(go.Scatter(
#        x=y_train.index, y=y_train,
#        mode="lines+markers", name="Train (actual)",
#        line=dict(color="#4C9BE8"),
#    ))
#
#fig.add_trace(go.Scatter(
#    x=test_dates, y=actual_test,
#    mode="lines+markers", name="Actual",
#    line=dict(color="#2ECC71"),
#))
#
#if xgb_forecast is not None:
#    fig.add_trace(go.Scatter(
#        x=xgb_forecast.index, y=xgb_forecast,
#        mode="lines+markers", name="XGBoost Forecast",
#        line=dict(color="#E74C3C", dash="dash"),
#    ))
#
#if hw_forecast is not None:
#    fig.add_trace(go.Scatter(
#        x=hw_forecast.index, y=hw_forecast,
#        mode="lines+markers", name="Holt-Winters Forecast",
#        line=dict(color="#9B59B6", dash="dot"),
#    ))
#
#fig.update_layout(
#    title=f"Forecast — {selected_kpi_label}",
#    xaxis_title="Date",
#    yaxis_title=selected_kpi_label,
#    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
#    hovermode="x unified",
#    height=450,
#)
#
#st.plotly_chart(fig, use_container_width=True)
#

# ── 7. Forecast plot ──────────────────────────────────────────────────────────
fig = go.Figure()

# Plot the complete actual series (train + test) as one continuous line
fig.add_trace(go.Scatter(
    x=cell_df.index,
    y=cell_df[target_col],
    mode="lines+markers",
    name="Actual",
    line=dict(color="#2ECC71", width=2),
))

# XGBoost forecast
if xgb_forecast is not None:
    fig.add_trace(go.Scatter(
        x=xgb_forecast.index,
        y=xgb_forecast,
        mode="lines+markers",
        name="XGBoost Forecast",
        line=dict(color="#E74C3C", dash="dash", width=2),
    ))

# Holt-Winters forecast
if hw_forecast is not None:
    fig.add_trace(go.Scatter(
        x=hw_forecast.index,
        y=hw_forecast,
        mode="lines+markers",
        name="Holt-Winters Forecast",
        line=dict(color="#9B59B6", dash="dot", width=2),
    ))

# Mark where the test period starts
fig.add_vline(
    x=test_dates[0],
    line_dash="dash",
    line_color="gray",
    annotation_text="Test Start",
    annotation_position="top right",
)

fig.update_layout(
    title=f"Forecast — {selected_kpi_label}",
    xaxis_title="Date",
    yaxis_title=selected_kpi_label,
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
    ),
    hovermode="x unified",
    height=450,
)

st.plotly_chart(fig, use_container_width=True)






# ── 8. Predictions section ───────────────────────────────────────────────────
st.subheader("Predictions")

pred_df = pd.DataFrame({
    "Date":   test_dates.strftime("%Y-%m-%d"),
    "Actual Values": actual_test.values.round(3),
})

if xgb_forecast is not None:
    pred_df["XGBoost Forecast"] = xgb_forecast.values.round(3)

if hw_forecast is not None:
    pred_df["Holt-Winters Forecast"] = hw_forecast.values.round(3)

st.dataframe(pred_df, use_container_width=True, hide_index=True)

# ── 9. Feature importance (XGBoost only) ──────────────────────────────────────
if run_xgb:
    with st.expander("📊 Feature Importance (XGBoost)"):
        imp_df = (
            pd.DataFrame({
                "Feature":    X_train.columns,
                "Importance": model.feature_importances_,
            })
            .sort_values("Importance", ascending=True)
            .tail(15)
        )

        fig_imp = go.Figure(go.Bar(
            x=imp_df["Importance"],
            y=imp_df["Feature"],
            orientation="h",
            marker_color="#4C9BE8",
        ))
        fig_imp.update_layout(
            title="Top 15 Feature Importances (gain)",
            xaxis_title="Importance",
            height=420,
        )
        st.plotly_chart(fig_imp, use_container_width=True)

# ── 10. Residual Analysis (XGBoost only) ──────────────────────────────────────
if run_xgb:
    with st.expander("🔬 Residual Analysis — XGBoost (in-sample train residuals)", expanded=True):

        st.markdown(
            "Diagnostics run on **training residuals** (in-sample). "
            "Ideally residuals should be random, zero-mean, and uncorrelated."
        )

        # ── Summary stats + DW test ─────────────────────────────────────────
        dw_stat   = durbin_watson(train_residuals)
        res_mean  = train_residuals.mean()
        res_std   = train_residuals.std()

        max_lags  = max(2, min(10, len(train_residuals) // 2))
        lb_result = acorr_ljungbox(train_residuals, lags=[max_lags], return_df=True)
        lb_pval   = float(lb_result["lb_pvalue"].iloc[0])

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Mean residual",  f"{res_mean:.4f}", help="Should be near 0")
        s2.metric("Std of residuals", f"{res_std:.4f}")
        s3.metric("Durbin-Watson",  f"{dw_stat:.3f}",
                  help="~2 = no autocorr · <1 = positive autocorr · >3 = negative autocorr")
        s4.metric(f"Ljung-Box p (lag {max_lags})", f"{lb_pval:.3f}",
                  help="p > 0.05 → residuals are uncorrelated (good)")

        if abs(res_mean) > 0.05 * res_std:
            st.warning("⚠️ Residual mean is notably non-zero — model may have a systematic bias.")

        if dw_stat < 1.5:
            st.warning("⚠️ Durbin-Watson < 1.5 — positive autocorrelation detected. "
                       "Consider adding more lag features or a seasonal component.")
        elif dw_stat > 2.5:
            st.warning("⚠️ Durbin-Watson > 2.5 — negative autocorrelation detected.")
        else:
            st.success("✅ Durbin-Watson in acceptable range (1.5 – 2.5).")

        if lb_pval < 0.05:
            st.warning(f"⚠️ Ljung-Box p = {lb_pval:.3f} — significant autocorrelation remains in residuals.")
        else:
            st.success(f"✅ Ljung-Box p = {lb_pval:.3f} — no significant autocorrelation detected.")

        st.markdown("---")

        # ── Four-panel residual plot ─────────────────────────────────────────
        fig_res = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                "Residuals over Time",
                "Residual Distribution",
                "ACF of Residuals",
                "Residuals vs Fitted",
            ),
            vertical_spacing=0.18,
            horizontal_spacing=0.12,
        )

        dates = y_train.index

        fig_res.add_trace(
            go.Scatter(x=dates, y=train_residuals, mode="lines+markers",
                       line=dict(color="#E74C3C"), name="Residual"),
            row=1, col=1
        )
        fig_res.add_hline(y=0, line_dash="dash", line_color="gray", row=1, col=1)

        fig_res.add_trace(
            go.Histogram(x=train_residuals, nbinsx=12,
                         marker_color="#4C9BE8", opacity=0.75, name="Freq"),
            row=1, col=2
        )

        n        = len(train_residuals)
        max_acf  = min(15, n - 2)
        acf_vals = [
            np.corrcoef(train_residuals[:-lag], train_residuals[lag:])[0, 1]
            if lag > 0 else 1.0
            for lag in range(max_acf + 1)
        ]
        conf_bound = 1.96 / np.sqrt(n)

        lags_x = list(range(max_acf + 1))
        bar_colors = [
            "#E74C3C" if abs(v) > conf_bound and i > 0 else "#4C9BE8"
            for i, v in enumerate(acf_vals)
        ]

        fig_res.add_trace(
            go.Bar(x=lags_x, y=acf_vals, marker_color=bar_colors,
                   name="ACF", showlegend=False),
            row=2, col=1
        )
        fig_res.add_hline(y= conf_bound, line_dash="dot", line_color="orange", row=2, col=1)
        fig_res.add_hline(y=-conf_bound, line_dash="dot", line_color="orange", row=2, col=1)
        fig_res.add_hline(y=0,           line_dash="dash", line_color="gray",  row=2, col=1)

        fig_res.add_trace(
            go.Scatter(x=train_preds, y=train_residuals,
                       mode="markers", marker=dict(color="#9B59B6", size=7, opacity=0.7),
                       name="Res vs Fitted"),
            row=2, col=2
        )
        fig_res.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=2)

        fig_res.update_layout(
            height=620,
            showlegend=False,
            title_text="Residual Diagnostics (training set)",
        )
        fig_res.update_xaxes(title_text="Date",   row=1, col=1)
        fig_res.update_xaxes(title_text="Residual", row=1, col=2)
        fig_res.update_xaxes(title_text="Lag",    row=2, col=1)
        fig_res.update_xaxes(title_text="Fitted value", row=2, col=2)
        fig_res.update_yaxes(title_text="Residual", row=1, col=1)
        fig_res.update_yaxes(title_text="Count",    row=1, col=2)
        fig_res.update_yaxes(title_text="ACF",      row=2, col=1)
        fig_res.update_yaxes(title_text="Residual", row=2, col=2)

        st.plotly_chart(fig_res, use_container_width=True)

        significant_lags = [
            i for i, v in enumerate(acf_vals)
            if i > 0 and abs(v) > conf_bound
        ]
        if significant_lags:
            st.info(
                f"📌 Significant autocorrelation at lag(s): **{significant_lags}**. "
                "Red bars exceed the 95 % confidence band (orange dashed lines). "
                "Consider adding these as explicit lag features."
            )
        else:
            st.success("✅ No significant autocorrelation found in residuals — ACF looks clean.")
