# LTE Cell KPI Forecaster

A Streamlit web application for cell-level LTE KPI forecasting, built by **Musketeers_Team** for the ITI graduation project on LTE network KPI forecasting and proactive maintenance.

Upload a cleaned KPI export, select a cell and KPI, and the app will backtest the selected model(s) on a hold-out window, display accuracy metrics, produce a recursive 7-day future forecast, run residual diagnostics, flag cells with weak weekly seasonality, generate an LLM-ready analysis report, and compare against naive baselines.

---

## Features

- **Multiple forecasting models**: XGBoost, Holt-Winters exponential smoothing, and naive/weekly-mean baseline
- **Model comparison**: side-by-side evaluation with MAE / RMSE / MAPE metrics
- **Automatic baseline fallback**: recommends the naive baseline when it outperforms the model
- **Seasonality detection**: STL-based weekly seasonality strength flagging (strong / moderate / weak)
- **Cross-KPI feature engineering**: leakage-safe lag and rolling features leveraging other KPIs
- **Residual diagnostics**: Durbin-Watson, Ljung-Box, ACF analysis, and four-panel residual plots for XGBoost
- **Feature importance**: top-15 gain-based XGBoost feature importance horizontal bar chart
- **Recursive 7-day future forecast**: extended predictions trained on the full series
- **LLM-ready report generation**: produces a copy-pasteable prompt summarizing KPI state, trends, forecasts, and alerts for RF / network optimization reasoning
- **Interactive sidebar controls**: adjustable hyperparameters, hold-out window, and diagnostic toggles
- **Streaming UI**: wide-layout dashboard with Plotly charts, metric cards, and data tables

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend / UI | Streamlit |
| Plotting | Plotly |
| Gradient boosting | XGBoost |
| Classical forecasting | statsmodels (ExponentialSmoothing) |
| Time-series diagnostics | statsmodels (STL, Durbin-Watson, Ljung-Box) |
| Data processing | pandas, numpy |
| Machine learning utilities | scikit-learn |

---

## Project Structure

```
lte_forecaster/
├── app.py                  # Streamlit entry point — sidebar controls, orchestration, rendering
├── config.py                # KPI dropdown options, column rename map, feature source columns
├── data_loader.py           # CSV loading, column renaming, numeric coercion
├── seasonality.py           # STL-based weekly seasonality strength per cell
├── features.py              # Lag, rolling, cross-KPI, and momentum feature engineering
├── plotting.py              # Plotly figure builders (forecast chart, feature importance)
├── diagnostics.py           # Residual analysis (Durbin-Watson, Ljung-Box, ACF plot)
├── report.py                # LLM-ready text report generator (prompt-style output)
└── models/
    ├── __init__.py
    ├── xgboost_model.py     # XGBoost training, evaluation, recursive future forecast
    ├── holt_winters.py      # Holt-Winters exponential smoothing forecast
    └── baseline.py          # Naive / weekly-mean fallback baseline
```

`app.py` stays thin — it only reads sidebar inputs, calls the model functions, coordinates the workflow, and renders the results. All forecasting logic lives in `features.py` and `models/`.

---

## Setup

Requires **Python 3.10+**.

```bash
python -m venv venv

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install streamlit pandas numpy xgboost scikit-learn statsmodels plotly
```

---

## Running the App

```bash
cd lte_forecaster
streamlit run app.py
```

Then upload a cleaned KPI CSV (e.g. `clean_normal_cells.csv`) when prompted in the browser UI.

---

## Expected Input Format

A CSV with:
- A `Date` column (parseable by `pandas.to_datetime`, e.g., `YYYY-MM-DD`)
- A `Cell Name` column identifying each cell
- One column per KPI, matching the raw counter names defined in `config.COLUMN_RENAME_MAP`

Raw column names are mapped to internal short names automatically via `COLUMN_RENAME_MAP`. If your source export uses different raw column names, update that dictionary — everything downstream (dropdown labels, feature engineering, cross-KPI features) is driven off the renamed short names, so no other file needs to change.

### Example CSV structure

| Date | Cell Name | (HU) Cell DL Average Throughput (Mbps) | (TE) RRC Setup SR% | ... |
|------|-----------|----------------------------------------|--------------------|-----|
| 2024-01-01 | Cell_001 | 45.2 | 98.5% | ... |
| 2024-01-02 | Cell_001 | 47.1 | 98.7% | ... |

---

## Supported KPIs

| Category | KPI Display Name | Internal Name |
|----------|------------------|---------------|
| Traffic | DL Traffic Volume (GBytes) | `DL_Traffic` |
| Traffic | DL Average Throughput (Mbps) | `DL_Throughput` |
| Traffic | Average UE Number | `Avg_UE_Number` |
| Traffic | Active Users | `Active_Users` |
| Accessibility | RRC Setup Success Rate (%) | `RRC_Setup_SR` |
| Retainability | E-RAB Drop Rate (%) | `ERAB_Drop_Rate` |
| Mobility | Intra-Freq HO Success Rate (%) | `Intra_HO_SR` |
| Mobility | Inter-Freq HO Success Rate (%) | `Inter_HO_SR` |
| Integrity | DL Average CQI | `DL_CQI` |
| Integrity | DL IBLER (%) | `DL_IBLER` |
| Utilization | DL PRB Utilization (%) | `DL_PRB_Util` |
| Experience | User DL Avg Throughput (Mbps) | `User_DL_Throughput` |

These cover the five standard KPI pillars: **accessibility, retainability, mobility, integrity/quality, and availability/utilization**.

---

## How Forecasting Works

### 1. Data Loading (`data_loader.py`)
The uploaded CSV is parsed with `pandas`, the `Date` column is converted to datetime, raw KPI column names are renamed to internal short names, and percentage/rate columns are coerced from strings (e.g. `"98.5%"`) to floats.

### 2. Seasonality Analysis (`seasonality.py`)
STL decomposition (`statsmodels`) computes a **weekly seasonality strength** score for each cell/KPI combination using the Hyndman-Athanasopoulos definition:

```
F_seasonal = max(0, 1 - Var(residual) / Var(seasonal + residual))
```

This score is used to sort the cell dropdown (strong seasonality first) and to display status badges in the UI. Cells with weak seasonality are flagged so that lag-7 and weekly features are interpreted with reduced confidence.

### 3. Feature Engineering (`features.py`)
For each cell/KPI, a leakage-safe feature matrix is built:

- **Cross-KPI features**: every other KPI shifted by 1 day (lag-1), ensuring only past values influence the forecast
- **Lag features**: days 1-7, 14, and 21
- **Rolling statistics**: 7-day and 3-day rolling mean, 7-day rolling std, rolling coefficient of variation, 14- and 21-day minimum-period rolling means
- **Normalized lags**: lag-5 and lag-7 divided by the 7-day rolling mean
- **Shape descriptors**: weekly slope (lag-1 minus lag-7), lag-1 minus weekly-mean deviation
- **Momentum**: day-over-day momentum (lag-1 minus lag-2, lag-2 minus lag-3)
- **Week-over-week difference**: lag-1 minus lag-8
- **Lag interactions**: lag-1 multiplied by lag-7

NaNs from early lags are intentionally preserved — XGBoost handles missing values natively via its split-based decision logic.

### 4. XGBoost Model (`models/xgboost_model.py`)
- A hold-out window (default 4 days) is carved from the tail of the series for backtesting
- Model hyperparameters are configurable via the sidebar: `n_estimators`, `learning_rate`, `max_depth`, `subsample`
- Fixed regularization: `colsample_bytree=0.8`, `min_child_weight=3`, `reg_alpha=0.1`, `reg_lambda=1.0`
- Cached resource Streamlit decorator ensures the model trains only once per session
- **Recursive future forecast**: retrained on the full series, then iteratively predicts 7 days ahead by appending each prediction to the history and rebuilding features for the next step

### 5. Holt-Winters Model (`models/holt_winters.py`)
- Exponential smoothing with configurable trend (`add`, `mul`, or `None`) and seasonal components
- Configurable seasonal periods (2-7 days, default 7 for weekly seasonality)
- Fit with optimization via `statsmodels.tsa.holtwinters.ExponentialSmoothing`
- Produces both backtest and future 7-day forecasts

### 6. Baseline Model (`models/baseline.py`)
- Two naive strategies are backtested:
  - **Naive (last value)**: carries the final training value forward
  - **Weekly mean**: carries the 7-day average forward (when enough history exists)
- The best-performing baseline by MAE is selected automatically
- This baseline is compared against the model(s) to flag cells where the model is not adding real value

### 7. Residual Diagnostics (`diagnostics.py`)
For XGBoost only, an expandable four-panel chart provides:

- Residuals over time (with zero-line reference)
- Residual distribution histogram
- ACF of residuals with 95% confidence band
- Residuals vs fitted values scatter

Summary statistics include Durbin-Watson (ideal ~2), mean residual, residual standard deviation, and Ljung-Box p-value (p > 0.05 indicates uncorrelated residuals).

### 8. LLM-Ready Report (`report.py`)
Generates a structured prompt designed for pasting directly into an LLM (e.g., Claude, ChatGPT). The report includes:
- Cell identifier and data window
- Active alert summary
- Per-KPI blocks with latest value, 30-day range, trend direction, forecast, and backtest accuracy
- Explicit task instructions for the LLM: identify correlated degradation, propose root causes, flag threshold crossings, and recommend optimization steps

---

## Sidebar Controls

The sidebar provides the following interactive controls:

### Forecast Configuration
- **Choose Forecasting Method**: XGBoost, Holt-Winters, or Compare Both (side-by-side)
- **Select KPI to Forecast**: dropdown of all 12 supported KPIs
- **Select Cell**: sorted by weekly seasonality strength (strongest first)

### Hold-out Settings
- **Hold-out Test Days**: 2-10 most recent days used as the test set (default 4)

### Diagnostics & Fallback
- **Show Next-7-Day Future Forecast**: toggles recursive future forecasting
- **Flag Seasonality Strength**: displays STL-based seasonality badges and warnings
- **Compare vs Naive Baseline (Fallback)**: backtests naive and weekly-mean baselines, recommends when they outperform the model

### XGBoost Hyperparameters (when selected)
- **n_estimators**: 50-300 (default 100)
- **learning_rate**: 0.01, 0.03, 0.05, 0.1, 0.2 (default 0.05)
- **max_depth**: 2-6 (default 3)
- **subsample**: 0.5-1.0 (default 0.8)

### Holt-Winters Settings (when selected)
- **Seasonal Periods (Days)**: 2-7 (default 7 for weekly seasonality)
- **Trend Component**: `add`, `mul`, or `None`
- **Seasonal Component**: `add`, `mul`, or `None`

---

## Outputs

### Forecast Chart
A Plotly line chart showing actual values, model forecast(s), baseline forecast, and future 7-day projections. A vertical dashed line separates training and test periods.

### Metrics
Per-model metric cards displaying:
- **MAE** (Mean Absolute Error)
- **RMSE** (Root Mean Squared Error)
- **MAPE** (Mean Absolute Percentage Error)

### Baseline Comparison
A comparison panel showing baseline MAE and a status badge indicating whether the best model outperforms (or underperforms) the naive baseline.

### Predictions Table
A dataframe of actual vs. forecast values on the hold-out test dates for every active model.

### Next 7 Days Forecast Table
A forward-looking dataframe of predicted values for the next 7 days when future forecasting is enabled.

### Feature Importance Expandable
A horizontal bar chart of the top-15 XGBoost features by gain-based importance.

### Residual Analysis Expandable
A four-panel diagnostic chart with statistical tests (Durbin-Watson, Ljung-Box) and actionable warnings.

### LLM-Ready Report Expandable
A copy-pasteable text block covering all KPIs, trends, forecasts, and alerts, ready to be pasted into an LLM for network optimization analysis.

---

## Known Constraints

- **Short data window (~30 days)**: limits how much history-dependent features like `lag_21` or `rolling_mean_21` can populate. These features are intentionally left as native-NaN rather than dropped, since XGBoost can split on missing values natively.
- **High feature-to-row ratio**: with all cross-KPI lag features included, the feature matrix can be wide relative to the number of rows. If feature importance looks flat or residuals are unstable, consider pruning `available_cols` in `app.py` to a domain-relevant subset per target KPI.
- **Post-refactor startup time**: initial page load can feel slower than a single-file version due to import overhead across multiple files (`xgboost`, `statsmodels`, `plotly` are the heaviest). This is a one-time cost per process start, not a per-interaction slowdown.

---

## Troubleshooting Slow Startup

If the app is slow to **load** (not slow to forecast):

- Confirm you're running `streamlit run app.py` from inside the `lte_forecaster/` folder.
- If the project folder is inside OneDrive / Google Drive sync, move it to a local-only folder — cloud sync + antivirus scanning on every `.py` import can add several seconds to startup.
- Add a Windows Defender exclusion for the project folder if running on Windows.
- The first run after a fresh clone/unzip is expected to be slower (Python compiles each module to bytecode); subsequent runs should be faster once `__pycache__` exists.

---

## Extending the App

### Adding a New KPI

1. Add the raw CSV column name and internal short name to `COLUMN_RENAME_MAP` in `config.py`
2. Add the internal short name to `NUMERIC_COERCE_COLS` if it contains percentage signs
3. Add the internal short name to `REQUIRED_COLS` (so it can be used as a cross-KPI feature)
4. Add a human-readable label to `KPI_OPTIONS` in `config.py`

### Changing Feature Engineering

All feature logic lives in `features.py`. Edit `build_features()` there. No changes are needed in `app.py` or the model files.

### Adding a New Model

Create a new file under `models/` (e.g., `models/prophet_model.py`) with a `run_<model>_forecast()` function that accepts the same arguments and returns a compatible dict. Import and wire it into `app.py`.

---

## License

This project was built as part of the Musketeers_Team graduation project at ITI (Information Technology Institute).
