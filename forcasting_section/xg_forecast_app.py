import streamlit as st
import pandas as pd
import numpy as np
import xgboost as xgb
import plotly.graph_objects as go
from sklearn.metrics import mean_absolute_error, mean_squared_error

st.set_page_config(page_title="LTE KPI Forecaster", layout="wide")

st.title("📡 LTE Cell KPI Forecaster — XGBoost")
st.markdown("Upload your cleaned LTE data, select a cell and KPI, and get a forecast.")

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

cell_names = sorted(df["Cell Name"].unique())
selected_cell = st.sidebar.selectbox("Select Cell", cell_names)

selected_kpi_label = st.sidebar.selectbox("Select KPI to Forecast", list(KPI_OPTIONS.keys()))
target_col = KPI_OPTIONS[selected_kpi_label]

test_days = st.sidebar.slider(
    "Hold-out test days", min_value=2, max_value=10, value=4,
    help="Number of most-recent days used as the test set."
)

st.sidebar.markdown("---")
st.sidebar.subheader("XGBoost hyperparameters")
n_estimators  = st.sidebar.slider("n_estimators",  50, 300, 100, 50)
learning_rate = st.sidebar.select_slider("learning_rate", [0.01, 0.03, 0.05, 0.1, 0.2], value=0.05)
max_depth     = st.sidebar.slider("max_depth", 2, 6, 3)
subsample     = st.sidebar.slider("subsample", 0.5, 1.0, 0.8, 0.1)

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

# ── 4. Feature engineering ───────────────────────────────────────────────────
def build_features(cell_df, target_col):
    features = pd.DataFrame(index=cell_df.index)
    features["y"] = cell_df[target_col]

    # --- Telecom KPIs (shifted to avoid leakage, DL_Traffic excluded — covered by lag_1) ---
    for col in available_cols:
        if col != target_col:
            features[col] = cell_df[col].shift(1)

    # --- Lag features (lag_4 dropped — zero importance) ---
    for k in [1, 2, 3, 5, 6, 7]:
        features[f"lag_{k}"] = features["y"].shift(k)

    # --- Rolling stats (shift 1 to avoid leakage) ---
    _week_mean = features["y"].shift(1).rolling(7).mean()  # local, not a feature
    features["week_std"] = features["y"].shift(1).rolling(7).std()
    features["week_min"] = features["y"].shift(1).rolling(7).min()
    # Dropped: rolling_mean_3, rolling_mean_7, week_mean, week_max (zero/near-zero importance)

    # --- Normalized lags (only lag5 and lag7 had meaningful importance) ---
    features["lag5_norm"] = features["lag_5"] / _week_mean
    features["lag7_norm"] = features["lag_7"] / _week_mean
    # Dropped: lag1_norm, lag2_norm, lag3_norm, lag4_norm, lag6_norm (zero importance)

    # --- Shape descriptors ---
    features["lag7_position"] = features["lag_7"] - _week_mean
    features["weekly_slope"]  = features["lag_1"] - features["lag_7"]
    # Dropped: week_range, lag1_to_lag7_ratio (zero importance)
    # Dropped: day_of_week (zero importance given ~30 day window)

    return features.dropna()


features = build_features(cell_df, target_col)
if len(features) <= test_days:
    st.error(
        f"Not enough data after feature engineering ({len(features)} rows) "
        f"for {test_days} test days. Reduce the hold-out slider."
    )
    st.stop()
# ── 5. Train / test split ────────────────────────────────────────────────────
split   = len(features) - test_days
train   = features.iloc[:split]
test    = features.iloc[split:]

X_train = train.drop(columns="y")
y_train = train["y"]
X_test  = test.drop(columns="y")
y_test  = test["y"]

# ── 6. Model training ────────────────────────────────────────────────────────
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

forecast = model.predict(X_test)

mae  = mean_absolute_error(y_test, forecast)
rmse = np.sqrt(mean_squared_error(y_test, forecast))
mape = np.mean(np.abs((y_test.values - forecast) / y_test.values.clip(1e-6))) * 100

# ── 7. Layout ─────────────────────────────────────────────────────────────────
st.markdown(f"### Cell: `{selected_cell}`  |  KPI: **{selected_kpi_label}**")

col1, col2, col3 = st.columns(3)
col1.metric("MAE",  f"{mae:.3f}")
col2.metric("RMSE", f"{rmse:.3f}")
col3.metric("MAPE", f"{mape:.1f}%")

# ── 8. Forecast plot ──────────────────────────────────────────────────────────
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=y_train.index, y=y_train,
    mode="lines+markers",
    name="Train (actual)",
    line=dict(color="#4C9BE8"),
))

fig.add_trace(go.Scatter(
    x=y_test.index, y=y_test,
    mode="lines+markers",
    name="Test (actual)",
    line=dict(color="#2ECC71"),
))

fig.add_trace(go.Scatter(
    x=y_test.index, y=forecast,
    mode="lines+markers",
    name="XGBoost forecast",
    line=dict(color="#E74C3C", dash="dash"),
))

fig.update_layout(
    title=f"XGBoost Forecast — {selected_kpi_label}",
    xaxis_title="Date",
    yaxis_title=selected_kpi_label,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    hovermode="x unified",
    height=450,
)

st.plotly_chart(fig, use_container_width=True)

# ── 9. Forecast vs Actual table ───────────────────────────────────────────────
with st.expander("📋 Forecast vs Actual (test period)"):
    result_df = pd.DataFrame({
        "Date":     y_test.index.strftime("%Y-%m-%d"),
        "Actual":   y_test.values.round(3),
        "Forecast": forecast.round(3),
        "Error":    (y_test.values - forecast).round(3),
    })
    st.dataframe(result_df, use_container_width=True, hide_index=True)

# ── 10. Feature importance ────────────────────────────────────────────────────
with st.expander("📊 Feature Importance"):
    imp_df = (
        pd.DataFrame({
            "Feature":    X_train.columns,
            "Importance": model.feature_importances_,
        })
        .sort_values("Importance", ascending=True)
        .tail(15)   # top 15
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
