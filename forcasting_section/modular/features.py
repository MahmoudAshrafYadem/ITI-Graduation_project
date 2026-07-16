"""Feature engineering for the XGBoost forecaster."""
import pandas as pd


def build_features(cell_df, target_col, available_cols):
    """Build the lag/rolling/cross-KPI feature matrix for one cell/KPI.

    `available_cols` is the set of KPI columns present for this cell (from
    config.REQUIRED_COLS, filtered to what's actually in the data). Every
    column other than `target_col` is added as a lag-1 feature — leakage-safe
    since only past values of other KPIs are used.
    """
    features = pd.DataFrame(index=cell_df.index)
    features["y"] = cell_df[target_col]

    # --- Cross-KPI features (shifted to avoid leakage) ---
    for col in available_cols:
        if col != target_col:
            features[col] = cell_df[col].shift(1)

    # --- Lag features ---
    for k in [1, 2, 3, 5, 6, 7]:
        features[f"lag_{k}"] = features["y"].shift(k)

    # --- Longer-horizon lags (bi-weekly / tri-weekly structure) ---
    # Left as raw point lags — only ~9-22 rows will ever have these populated
    # on a 30-day dataset. That's fine: XGBoost handles NaN natively (see
    # dropna below), it just means these features get fewer split
    # opportunities than lag_1..lag_7, so don't read low gain-based
    # importance as "not useful".
    features["lag_14"] = features["y"].shift(14)
    features["lag_21"] = features["y"].shift(21)

    # --- Rolling stats (shift 1 to avoid leakage) ---
    _y_shifted = features["y"].shift(1)
    _week_mean = _y_shifted.rolling(7).mean()

    features["week_std"]       = _y_shifted.rolling(7).std()
    features["week_min"]       = _y_shifted.rolling(7).min()
    features["rolling_mean_3"] = _y_shifted.rolling(3).mean()
    features["ewm_3"]          = _y_shifted.ewm(span=3).mean()
    features["rolling_cv"]     = features["week_std"] / _week_mean

    # --- Coverage-friendly longer rolling means ---
    # min_periods lets these start producing values well before the full
    # window is available, so they don't inherit the same low-coverage
    # importance bias as lag_14 / lag_21 above — a fairer, smoother
    # alternative for the model to lean on when raw point lags are still
    # mostly NaN.
    features["rolling_mean_14"] = _y_shifted.rolling(14, min_periods=7).mean()
    features["rolling_mean_21"] = _y_shifted.rolling(21, min_periods=10).mean()

    # --- Normalized lags ---
    features["lag5_norm"] = features["lag_5"] / _week_mean
    features["lag7_norm"] = features["lag_7"] / _week_mean

    # --- Shape descriptors ---
    features["lag7_position"] = features["lag_7"] - _week_mean
    features["weekly_slope"]  = features["lag_1"] - features["lag_7"]

    # --- Momentum ---
    features["momentum_1"] = features["lag_1"] - features["lag_2"]
    features["momentum_2"] = features["lag_2"] - features["lag_3"]

    # --- Lag ratio ---
    features["lag1_lag7_ratio"] = features["lag_1"] / (features["lag_7"] + 1e-9)

    # --- Week-over-week diff ---
    features["lag_8"]    = features["y"].shift(8)
    features["wow_diff"] = features["lag_1"] - features["lag_8"]

    features["lag1_x_lag7"] = features["lag_1"] * features["lag_7"]

    # Only require the TARGET to be non-missing. Feature-column NaNs (e.g.
    # early rows before lag_14/lag_21 have enough history) are left in —
    # XGBoost splits natively on missing values, so these rows are still
    # usable training examples instead of being discarded entirely.
    return features.dropna(subset=["y"])
