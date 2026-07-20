"""Residual diagnostics for the XGBoost model (Durbin-Watson, Ljung-Box, ACF)."""
import numpy as np
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from statsmodels.stats.stattools import durbin_watson
from statsmodels.stats.diagnostic import acorr_ljungbox


def render_residual_analysis(y_train, train_preds, train_residuals):
    """Renders the full residual-diagnostics expander: summary stats,
    Durbin-Watson / Ljung-Box tests, and the four-panel residual plot."""
    with st.expander("🔬 Residual Analysis — XGBoost (in-sample train residuals)", expanded=True):

        st.markdown(
            "Diagnostics run on **training residuals** (in-sample). "
            "Ideally residuals should be random, zero-mean, and uncorrelated."
        )

        dw_stat  = durbin_watson(train_residuals)
        res_mean = train_residuals.mean()
        res_std  = train_residuals.std()

        max_lags  = max(2, min(10, len(train_residuals) // 2))
        lb_result = acorr_ljungbox(train_residuals, lags=[max_lags], return_df=True)
        lb_pval   = float(lb_result["lb_pvalue"].iloc[0])

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Mean residual", f"{res_mean:.4f}", help="Should be near 0")
        s2.metric("Std of residuals", f"{res_std:.4f}")
        s3.metric("Durbin-Watson", f"{dw_stat:.3f}",
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

        fig_res = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                "Residuals over Time", "Residual Distribution",
                "ACF of Residuals", "Residuals vs Fitted",
            ),
            vertical_spacing=0.18, horizontal_spacing=0.12,
        )

        dates = y_train.index

        fig_res.add_trace(
            go.Scatter(x=dates, y=train_residuals, mode="lines+markers",
                       line=dict(color="#E74C3C"), name="Residual"),
            row=1, col=1,
        )
        fig_res.add_hline(y=0, line_dash="dash", line_color="gray", row=1, col=1)

        fig_res.add_trace(
            go.Histogram(x=train_residuals, nbinsx=12,
                         marker_color="#4C9BE8", opacity=0.75, name="Freq"),
            row=1, col=2,
        )

        n = len(train_residuals)
        max_acf = min(15, n - 2)
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
            go.Bar(x=lags_x, y=acf_vals, marker_color=bar_colors, name="ACF", showlegend=False),
            row=2, col=1,
        )
        fig_res.add_hline(y=conf_bound, line_dash="dot", line_color="orange", row=2, col=1)
        fig_res.add_hline(y=-conf_bound, line_dash="dot", line_color="orange", row=2, col=1)
        fig_res.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)

        fig_res.add_trace(
            go.Scatter(x=train_preds, y=train_residuals, mode="markers",
                       marker=dict(color="#9B59B6", size=7, opacity=0.7), name="Res vs Fitted"),
            row=2, col=2,
        )
        fig_res.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=2)

        fig_res.update_layout(height=620, showlegend=False, title_text="Residual Diagnostics (training set)")
        fig_res.update_xaxes(title_text="Date", row=1, col=1)
        fig_res.update_xaxes(title_text="Residual", row=1, col=2)
        fig_res.update_xaxes(title_text="Lag", row=2, col=1)
        fig_res.update_xaxes(title_text="Fitted value", row=2, col=2)
        fig_res.update_yaxes(title_text="Residual", row=1, col=1)
        fig_res.update_yaxes(title_text="Count", row=1, col=2)
        fig_res.update_yaxes(title_text="ACF", row=2, col=1)
        fig_res.update_yaxes(title_text="Residual", row=2, col=2)

        st.plotly_chart(fig_res, use_container_width=True)

        significant_lags = [i for i, v in enumerate(acf_vals) if i > 0 and abs(v) > conf_bound]
        if significant_lags:
            st.info(
                f"📌 Significant autocorrelation at lag(s): **{significant_lags}**. "
                "Red bars exceed the 95 % confidence band (orange dashed lines). "
                "Consider adding these as explicit lag features."
            )
        else:
            st.success("✅ No significant autocorrelation found in residuals — ACF looks clean.")
