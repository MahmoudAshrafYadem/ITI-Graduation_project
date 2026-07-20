#!/usr/bin/env python3
"""CLI runner for the LTE KPI forecaster pipeline.

Demonstrates that the same core functions work outside Streamlit.
Usage:
    python run_pipeline.py --cell "Cell_001" --kpi "DL_Throughput" --csv data.csv
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from config import KPI_OPTIONS, KPI_REVERSE_MAP, REQUIRED_COLS
from core.data_loading import load_data, filter_cell, validate_cell_data
from core.seasonality import compute_all_cell_seasonality
from core.models.xgboost_model import run_xgboost_forecast
from core.models.holt_winters import run_holt_winters_forecast
from core.models.baseline import run_baseline_forecast
from core.alerts import evaluate_alerts
from core.report import generate_cell_report
from core.types import ReportContext


def main():
    parser = argparse.ArgumentParser(description="LTE KPI Forecaster CLI")
    parser.add_argument("--csv", required=True, help="Path to clean_normal_cells.csv")
    parser.add_argument("--cell", required=True, help="Cell Name to analyze")
    parser.add_argument("--kpi", required=True, help="KPI internal name (e.g. DL_Throughput)")
    parser.add_argument("--test-days", type=int, default=4, help="Hold-out test days")
    parser.add_argument("--future", action="store_true", help="Generate 7-day future forecast")
    parser.add_argument("--report", action="store_true", help="Generate LLM-ready report")
    args = parser.parse_args()

    print(f"📂 Loading {args.csv}...")
    df = load_data(args.csv)
    print(f"   Loaded {len(df)} rows, {df['Cell Name'].nunique()} cells")

    cell_df = filter_cell(df, args.cell)
    print(f"   Cell '{args.cell}' has {len(cell_df)} rows")

    validation = validate_cell_data(cell_df, args.kpi, args.test_days)
    if not validation["ok"]:
        print(f"   ❌ {validation['severity'].upper()}: {validation['message']}")
        sys.exit(1)
    if validation["severity"] == "warning":
        print(f"   ⚠️  {validation['message']}")

    seasonality = compute_all_cell_seasonality(df, args.kpi, period=7).get(args.cell)
    if seasonality:
        print(f"   📊 Seasonality: {seasonality.category} (strength={seasonality.strength:.2f})")

    available_cols = [c for c in REQUIRED_COLS if c in cell_df.columns]
    cell_df = cell_df[available_cols]
    test_dates = cell_df.index[-args.test_days:]
    actual_test = cell_df[args.kpi].loc[test_dates]
    future_dates = pd.date_range(cell_df.index[-1] + pd.Timedelta(days=1), periods=7, freq="D") if args.future else None

    print(f"   🤖 Running models...")
    xgb_result = run_xgboost_forecast(
        cell_df, args.kpi, available_cols, test_dates, args.test_days,
        show_future=args.future, future_dates=future_dates,
    )
    hw_result = run_holt_winters_forecast(
        cell_df, args.kpi, test_dates, actual_test,
        show_future=args.future, future_dates=future_dates,
    )
    baseline_result = run_baseline_forecast(
        cell_df, args.kpi, test_dates, actual_test,
        show_future=args.future, future_dates=future_dates,
    )

    results = [r for r in [xgb_result, hw_result, baseline_result] if r.forecast is not None]
    best = min(results, key=lambda r: r.scores.mae)
    print(f"   ✅ Best model: {best.model_name} (MAE={best.scores.mae:.3f})")
    for r in results:
        print(f"      {r.model_name:20s} MAE={r.scores.mae:.3f} RMSE={r.scores.rmse:.3f} MAPE={r.scores.mape:.1f}%")

    alerts = evaluate_alerts(cell_df, target_col=args.kpi)
    if alerts:
        print(f"   🚨 {len(alerts)} alert(s) fired:")
        for a in alerts:
            print(f"      [{a.status.value}] {a.kpi_display}: {a.message}")
    else:
        print(f"   ✅ No alerts")

    if args.report:
        print(f"   📝 Generating report...")
        forecasts = {}
        if best.future_forecast is not None:
            forecasts[args.kpi] = best.to_report_dict(dates=future_dates)

        context = ReportContext(
            cell_name=args.cell,
            kpi_map=KPI_REVERSE_MAP,
            forecasts=forecasts,
            alerts=alerts,
            seasonality=seasonality,
        )
        report = generate_cell_report(df, args.cell, context=context)
        print("\n" + "=" * 60)
        print(report)
        print("=" * 60)

    print(f"\n✅ Pipeline complete for {args.cell} / {args.kpi}")


if __name__ == "__main__":
    main()
