"""Holt-Winters exponential smoothing forecast."""
import numpy as np
import pandas as pd
import streamlit as st
from sklearn.metrics import mean_absolute_error, mean_squared_error
from statsmodels.tsa.holtwinters import ExponentialSmoothing


def run_holt_winters_forecast(
    cell_df, target_col, test_dates, actual_test,
    hw_trend, hw_seasonal, hw_seasonal_periods,
    show_future, future_dates,
):
    """Fit Holt-Winters on the hold-out window and, optionally, on the full
    series for a 7-day future forecast. Returns a dict of results (forecast
    fields are None if fitting failed)."""
    hw_train_series = cell_df[target_col].loc[: test_dates[0]].iloc[:-1]

    min_required = (hw_seasonal_periods * 2) if hw_seasonal else 2
    if hw_seasonal and len(hw_train_series) < min_required:
        st.warning(
            f"⚠️ Holt-Winters needs at least {min_required} training points for "
            f"{hw_seasonal_periods}-day seasonality, but only {len(hw_train_series)} are available. "
            "Seasonal component may be unreliable or fail to fit."
        )

    hw_forecast = None
    hw_mae = hw_rmse = hw_mape = None

    try:
        hw_model = ExponentialSmoothing(
            hw_train_series,
            trend=hw_trend if hw_trend != "None" else None,
            seasonal=hw_seasonal if hw_seasonal != "None" else None,
            seasonal_periods=hw_seasonal_periods if hw_seasonal else None,
            initialization_method="estimated",
        )
        hw_fitted = hw_model.fit(optimized=True)
        hw_forecast = pd.Series(hw_fitted.forecast(len(test_dates)).values, index=test_dates)

        hw_mae  = mean_absolute_error(actual_test, hw_forecast)
        hw_rmse = np.sqrt(mean_squared_error(actual_test, hw_forecast))
        hw_mape = np.mean(np.abs((actual_test.values - hw_forecast.values) / actual_test.values.clip(1e-6))) * 100
    except Exception as e:
        st.error(f"Holt-Winters fitting failed: {e}")
        hw_forecast = None

    future_hw_forecast = None
    if show_future:
        try:
            hw_full = ExponentialSmoothing(
                cell_df[target_col],
                trend=hw_trend if hw_trend != "None" else None,
                seasonal=hw_seasonal if hw_seasonal != "None" else None,
                seasonal_periods=hw_seasonal_periods if hw_seasonal else None,
                initialization_method="estimated",
            ).fit(optimized=True)

            future_hw_forecast = pd.Series(hw_full.forecast(7).values, index=future_dates)
        except Exception:
            future_hw_forecast = None

    return {
        "hw_forecast": hw_forecast,
        "hw_mae": hw_mae,
        "hw_rmse": hw_rmse,
        "hw_mape": hw_mape,
        "future_hw_forecast": future_hw_forecast,
    }
