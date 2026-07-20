"""Holt-Winters exponential smoothing — pure functions."""
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from core.types import ForecastResult, ValidationScore


def run_holt_winters_forecast(
    cell_df: pd.DataFrame,
    target_col: str,
    test_dates: pd.DatetimeIndex,
    actual_test: pd.Series,
    hw_trend: str = "add",
    hw_seasonal: str = "add",
    hw_seasonal_periods: int = 7,
    show_future: bool = True,
    future_dates: pd.DatetimeIndex = None,
) -> ForecastResult:
    """Fit Holt-Winters on the hold-out window and, optionally, on the full
    series for a 7-day future forecast.
    """
    hw_train_series = cell_df[target_col].loc[: test_dates[0]].iloc[:-1]

    min_required = (hw_seasonal_periods * 2) if hw_seasonal else 2
    if hw_seasonal and len(hw_train_series) < min_required:
        return ForecastResult(
            model_name="Holt-Winters",
            forecast=None,
            scores=ValidationScore(mae=np.nan, rmse=np.nan, mape=np.nan),
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
        forecast = pd.Series(hw_fitted.forecast(len(test_dates)).values, index=test_dates)

        scores = ValidationScore(
            mae=mean_absolute_error(actual_test, forecast),
            rmse=np.sqrt(mean_squared_error(actual_test, forecast)),
            mape=np.mean(np.abs((actual_test.values - forecast.values) / actual_test.values.clip(1e-6))) * 100,
        )
    except Exception:
        return ForecastResult(
            model_name="Holt-Winters",
            forecast=None,
            scores=ValidationScore(mae=np.nan, rmse=np.nan, mape=np.nan),
        )

    future_forecast = None
    if show_future and future_dates is not None:
        try:
            hw_full = ExponentialSmoothing(
                cell_df[target_col],
                trend=hw_trend if hw_trend != "None" else None,
                seasonal=hw_seasonal if hw_seasonal != "None" else None,
                seasonal_periods=hw_seasonal_periods if hw_seasonal else None,
                initialization_method="estimated",
            ).fit(optimized=True)
            future_forecast = pd.Series(hw_full.forecast(7).values, index=future_dates)
        except Exception:
            future_forecast = None

    return ForecastResult(
        model_name="Holt-Winters",
        forecast=forecast,
        scores=scores,
        future_forecast=future_forecast,
    )
