"""Naive / weekly-mean baseline forecasts, used as a fallback sanity check."""
import pandas as pd
from sklearn.metrics import mean_absolute_error


def run_baseline_forecast(cell_df, target_col, test_dates, actual_test, show_future, future_dates):
    """Backtest naive (last value) and weekly-mean baselines and return
    whichever generalizes best for this cell/KPI, plus an optional future
    forecast. Returns None fields if there isn't enough training data."""
    train_series = cell_df[target_col].loc[: test_dates[0]].iloc[:-1]

    if len(train_series) < 1:
        return {
            "baseline_forecast": None, "baseline_label": None,
            "baseline_mae": None, "future_baseline_forecast": None,
        }

    naive_value = train_series.iloc[-1]
    naive_forecast = pd.Series(naive_value, index=test_dates)
    naive_mae = mean_absolute_error(actual_test, naive_forecast)

    candidates = {"Naive (last value)": (naive_forecast, naive_mae)}

    if len(train_series) >= 7:
        week_mean_value = train_series.iloc[-7:].mean()
        week_mean_forecast = pd.Series(week_mean_value, index=test_dates)
        week_mean_mae = mean_absolute_error(actual_test, week_mean_forecast)
        candidates["Weekly mean"] = (week_mean_forecast, week_mean_mae)

    baseline_label, (baseline_forecast, baseline_mae) = min(
        candidates.items(), key=lambda kv: kv[1][1]
    )

    future_baseline_forecast = None
    if show_future:
        full_series = cell_df[target_col]
        future_val = (
            full_series.iloc[-7:].mean()
            if baseline_label == "Weekly mean"
            else full_series.iloc[-1]
        )
        future_baseline_forecast = pd.Series(future_val, index=future_dates)

    return {
        "baseline_forecast": baseline_forecast,
        "baseline_label": baseline_label,
        "baseline_mae": baseline_mae,
        "future_baseline_forecast": future_baseline_forecast,
    }
