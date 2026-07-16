"""XGBoost training, evaluation, and recursive future forecasting."""
import numpy as np
import pandas as pd
import streamlit as st
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error

from features import build_features


@st.cache_resource(show_spinner="Training XGBoost model…")
def train_model(x_tr, y_tr, n_est, lr, depth, subs):
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
    model.fit(x_tr, y_tr)
    return model


def run_xgboost_forecast(
    cell_df, target_col, available_cols, test_dates, test_days,
    n_estimators, learning_rate, max_depth, subsample,
    show_future, future_dates,
):
    """Train/evaluate XGBoost on the hold-out window, and optionally run a
    recursive 7-day future forecast trained on the full series.

    Returns a dict of results. Calls st.stop() if there isn't enough data
    after feature engineering.
    """
    features = build_features(cell_df, target_col, available_cols)
    if len(features) <= test_days:
        st.error(
            f"Not enough data after feature engineering ({len(features)} rows) "
            f"for {test_days} test days. Reduce the hold-out slider."
        )
        st.stop()

    split = len(features) - test_days
    train = features.iloc[:split]
    test  = features.iloc[split:]

    x_train = train.drop(columns="y")
    y_train = train["y"]
    x_test  = test.drop(columns="y")
    y_test  = test["y"]

    model = train_model(x_train, y_train, n_estimators, learning_rate, max_depth, subsample)

    xgb_forecast = pd.Series(model.predict(x_test), index=y_test.index)

    train_preds     = model.predict(x_train)
    train_residuals = y_train.values - train_preds

    xgb_mae  = mean_absolute_error(y_test, xgb_forecast)
    xgb_rmse = np.sqrt(mean_squared_error(y_test, xgb_forecast))
    xgb_mape = np.mean(np.abs((y_test.values - xgb_forecast.values) / y_test.values.clip(1e-6))) * 100

    future_xgb_forecast = None
    if show_future:
        x_all = features.drop(columns="y")
        y_all = features["y"]

        future_model = train_model(x_all, y_all, n_estimators, learning_rate, max_depth, subsample)
        expected_cols = list(x_all.columns)
        history = cell_df.copy()
        future_predictions = []

        for _ in range(7):
            temp_features = build_features(history, target_col, available_cols)
            latest_x = temp_features.drop(columns="y").iloc[[-1]]
            latest_x = latest_x[expected_cols]  # keep column order identical to training

            pred = future_model.predict(latest_x)[0]
            next_date = history.index[-1] + pd.Timedelta(days=1)

            new_row = history.iloc[-1].copy()
            new_row[target_col] = pred
            history.loc[next_date] = new_row

            future_predictions.append(pred)

        future_xgb_forecast = pd.Series(future_predictions, index=future_dates)

    return {
        "model": model,
        "X_train": x_train,
        "y_train": y_train,
        "xgb_forecast": xgb_forecast,
        "xgb_mae": xgb_mae,
        "xgb_rmse": xgb_rmse,
        "xgb_mape": xgb_mape,
        "train_preds": train_preds,
        "train_residuals": train_residuals,
        "future_xgb_forecast": future_xgb_forecast,
    }
