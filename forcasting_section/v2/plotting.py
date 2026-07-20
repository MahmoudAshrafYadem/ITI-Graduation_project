"""Plotly figure builders for the forecast chart and feature importance."""
import pandas as pd
import plotly.graph_objects as go


def build_forecast_figure(
    cell_df, target_col, selected_kpi_label, test_dates,
    xgb_forecast=None, future_xgb_forecast=None,
    hw_forecast=None, future_hw_forecast=None,
    baseline_forecast=None, future_baseline_forecast=None, baseline_label=None,
):
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=cell_df.index, y=cell_df[target_col],
        mode="lines+markers", name="Actual",
        line=dict(color="#2ECC71", width=2),
    ))

    if xgb_forecast is not None:
        xgb_full = xgb_forecast.copy()
        if future_xgb_forecast is not None:
            xgb_full = pd.concat([xgb_full, future_xgb_forecast])
        fig.add_trace(go.Scatter(
            x=xgb_full.index, y=xgb_full.values,
            mode="lines+markers", name="XGBoost Forecast",
            line=dict(color="red", width=3),
        ))

    if hw_forecast is not None:
        hw_full = hw_forecast.copy()
        if future_hw_forecast is not None:
            hw_full = pd.concat([hw_full, future_hw_forecast])
        fig.add_trace(go.Scatter(
            x=hw_full.index, y=hw_full.values,
            mode="lines+markers", name="Holt-Winters Forecast",
            line=dict(color="purple", width=3),
        ))

    if baseline_forecast is not None:
        baseline_full = baseline_forecast.copy()
        if future_baseline_forecast is not None:
            baseline_full = pd.concat([baseline_full, future_baseline_forecast])
        fig.add_trace(go.Scatter(
            x=baseline_full.index, y=baseline_full.values,
            mode="lines+markers", name=f"Baseline ({baseline_label})",
            line=dict(color="gray", width=2, dash="dot"),
        ))

    fig.add_vline(
        x=test_dates[0], line_dash="dash", line_color="gray",
        annotation_text="Test Start", annotation_position="top right",
    )

    fig.update_layout(
        title=f"Forecast — {selected_kpi_label}",
        xaxis_title="Date", yaxis_title=selected_kpi_label,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified", height=450,
    )
    return fig


def build_feature_importance_figure(x_train_columns, importances):
    imp_df = (
        pd.DataFrame({"Feature": x_train_columns, "Importance": importances})
        .sort_values("Importance", ascending=True)
        .tail(15)
    )
    fig_imp = go.Figure(go.Bar(
        x=imp_df["Importance"], y=imp_df["Feature"],
        orientation="h", marker_color="#4C9BE8",
    ))
    fig_imp.update_layout(title="Top 15 Feature Importances (gain)", xaxis_title="Importance", height=420)
    return fig_imp
