"""XGBoost training, evaluation, and recursive future forecasting — pure functions."""
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error

from core.types import ForecastResult, ValidationScore
from core.features import build_features


def train_xgboost(x_tr: pd.DataFrame, y_tr: pd.Series,
                  n_est: int, lr: float, depth: int, subs: float,
                  random_state: int = 42) -> xgb.XGBRegressor:
    """Train an XGBoost regressor. No caching — the caller decides."""
    model = xgb.XGBRegressor(
        n_estimators=n_est,
        learning_rate=lr,
        max_depth=depth,
        subsample=subs,
        colsample_bytree=0.8,
        min_child_weight=3,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=random_state,
        verbosity=0,
    )
    model.fit(x_tr, y_tr)
    return model


def run_xgboost_forecast(
    cell_df: pd.DataFrame,
    target_col: str,
    available_cols: list,
    test_dates: pd.DatetimeIndex,
    test_days: int,
    n_estimators: int = 100,
    learning_rate: float = 0.05,
    max_depth: int = 3,
    subsample: float = 0.8,
    show_future: bool = True,
    future_dates: pd.DatetimeIndex = None,
) -> ForecastResult:
    """Train/evaluate XGBoost on a hold-out window, and optionally run a
    recursive 7-day future forecast trained on the full series.
    """
    features = build_features(cell_df, target_col, available_cols)
    if len(features) <= test_days:
        raise ValueError(
            f"Not enough data after feature engineering ({len(features)} rows) "
            f"for {test_days} test days. Reduce the hold-out slider."
        )

    split = len(features) - test_days
    train = features.iloc[:split]
    test  = features.iloc[split:]

    x_train = train.drop(columns="y")
    y_train = train["y"]
    x_test  = test.drop(columns="y")
    y_test  = test["y"]

    model = train_xgboost(x_train, y_train, n_estimators, learning_rate, max_depth, subsample)

    forecast = pd.Series(model.predict(x_test), index=y_test.index)
    train_preds = model.predict(x_train)
    train_residuals = y_train.values - train_preds

    scores = ValidationScore(
        mae=mean_absolute_error(y_test, forecast),
        rmse=np.sqrt(mean_squared_error(y_test, forecast)),
        mape=np.mean(np.abs((y_test.values - forecast.values) / y_test.values.clip(1e-6))) * 100,
    )

    future_forecast = None
    if show_future and future_dates is not None:
        x_all = features.drop(columns="y")
        y_all = features["y"]

        future_model = train_xgboost(x_all, y_all, n_estimators, learning_rate, max_depth, subsample)
        expected_cols = list(x_all.columns)
        history = cell_df.copy()
        future_predictions = []

        for _ in range(7):
            temp_features = build_features(history, target_col, available_cols)
            latest_x = temp_features.drop(columns="y").iloc[[-1]]
            latest_x = latest_x[expected_cols]

            pred = future_model.predict(latest_x)[0]
            next_date = history.index[-1] + pd.Timedelta(days=1)

            new_row = history.iloc[-1].copy()
            new_row[target_col] = pred
            history.loc[next_date] = new_row

            future_predictions.append(pred)

        future_forecast = pd.Series(future_predictions, index=future_dates)

    feat_imp = pd.DataFrame({
        "Feature": x_train.columns,
        "Importance": model.feature_importances_,
    }).sort_values("Importance", ascending=False)

    return ForecastResult(
        model_name="XGBoost",
        forecast=forecast,
        scores=scores,
        future_forecast=future_forecast,
        feature_importance=feat_imp,
        train_predictions=train_preds,
        train_residuals=train_residuals,
        y_train=y_train,
        model_obj=model,
    )
