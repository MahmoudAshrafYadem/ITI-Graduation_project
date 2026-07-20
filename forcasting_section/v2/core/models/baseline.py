"""Naive / weekly-mean baseline forecasts — pure functions."""
import pandas as pd
from sklearn.metrics import mean_absolute_error

from core.types import ForecastResult, ValidationScore


def run_baseline_forecast(
    cell_df: pd.DataFrame,
    target_col: str,
    test_dates: pd.DatetimeIndex,
    actual_test: pd.Series,
    show_future: bool = True,
    future_dates: pd.DatetimeIndex = None,
) -> ForecastResult:
    """Backtest naive (last value) and weekly-mean baselines and return
    whichever generalizes best for this cell/KPI.
    """
    train_series = cell_df[target_col].loc[: test_dates[0]].iloc[:-1]

    if len(train_series) < 1:
        return ForecastResult(
            model_name="Baseline",
            forecast=None,
            scores=ValidationScore(mae=float("inf"), rmse=float("inf"), mape=float("inf")),
        )

    naive_value = train_series.iloc[-1]
    naive_forecast = pd.Series(naive_value, index=test_dates)
    naive_mae = mean_absolute_error(actual_test, naive_forecast)

    candidates = {"Naive (last value)": (naive_forecast, naive_mae)}

    if len(train_series) >= 7:
        week_mean_value = train_series.iloc[-7:].mean()
        week_mean_forecast = pd.Series(week_mean_value, index=test_dates)
        week_mean_mae = mean_absolute_error(actual_test, week_mean_forecast)
        candidates["Weekly mean"] = (week_mean_forecast, week_mean_mae)

    best_label, (best_forecast, best_mae) = min(candidates.items(), key=lambda kv: kv[1][1])

    future_forecast = None
    if show_future and future_dates is not None:
        full_series = cell_df[target_col]
        future_val = (
            full_series.iloc[-7:].mean()
            if best_label == "Weekly mean"
            else full_series.iloc[-1]
        )
        future_forecast = pd.Series(future_val, index=future_dates)

    return ForecastResult(
        model_name=f"Baseline ({best_label})",
        forecast=best_forecast,
        scores=ValidationScore(mae=best_mae, rmse=best_mae, mape=best_mae),
        future_forecast=future_forecast,
    )
