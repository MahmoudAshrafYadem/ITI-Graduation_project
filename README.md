# Data-Driven & Automation-Based RF Optimization for Modern 4G/5G Mobile Networks

> **LTE KPI Degradation Analyzer v2.0**  
> **Graduation Project — Information Technology Institute (ITI) 2026**  
> **Team: Musketeers_Team**

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Core Concepts & Methodology](#3-core-concepts--methodology)
4. [Project Structure](#4-project-structure)
5. [Installation & Dependencies](#5-installation--dependencies)
6. [Configuration Guide](#6-configuration-guide)
7. [Usage Guide](#7-usage-guide)
8. [Data Quality Framework](#8-data-quality-framework)
9. [KPI Configuration Reference](#9-kpi-configuration-reference)
10. [Root Cause Analysis Engine](#10-root-cause-analysis-engine)
11. [Visualization & Reporting](#11-visualization--reporting)
12. [Recent Changes](#12-recent-changes)
13. [Extending the System](#13-extending-the-system)
13. [Troubleshooting](#14-troubleshooting)
15. [License & Attribution](#15-license--attribution)

---

## 1. Project Overview

### 1.1 Mission Statement

This project addresses the critical challenge of **Radio Frequency (RF) optimization** in modern 4G LTE and 5G NR mobile networks through an **automated, data-driven analytical framework**. Traditional RF optimization relies heavily on manual counter inspection, engineer expertise, and reactive troubleshooting. Our system transforms this paradigm by:

- **Automating** the detection of KPI degradation across the entire network
- **Intelligently correlating** degraded KPIs with related network counters
- **Pinpointing root causes** with severity-weighted scoring
- **Generating actionable recommendations** for RF engineers
- **Providing statistical confidence** via Welch's t-test significance testing

### 1.2 Problem Domain

Modern cellular networks generate massive volumes of performance data:
- **Traffic volumes** (DL/UL GBytes)
- **Throughput metrics** (Mbps per cell/user)
- **Accessibility KPIs** (RRC/ERAB Setup Success Rates)
- **Retainability KPIs** (Drop Rates, Abnormal Releases)
- **Mobility KPIs** (Handover Success Rates)
- **Quality metrics** (CQI, BLER, MCS, Interference)
- **Coverage indicators** (TA Distribution, CEU metrics)
- **Carrier Aggregation** (CA activation, SCell metrics)

**The Challenge:** When a KPI degrades, engineers must manually inspect dozens of related counters, compare against baselines, and determine the root cause — a process that is time-consuming, error-prone, and unscalable for large networks.

### 1.3 Solution Approach

Our analyzer implements a **three-layer analytical pipeline**:

```
+-------------------------------------------------------------+
|  LAYER 1: DATA INGESTION & QUALITY ASSURANCE                |
|  +-- Excel/CSV import with smart column matching            |
|  +-- Unit-aware validation (negative counters, % bounds)    |
|  +-- Sentinel value detection (vendor null markers)         |
|  +-- Baseline gap imputation (same-weekday median)          |
+-------------------------------------------------------------+
|  LAYER 2: DEGRADATION DETECTION & STATISTICAL VALIDATION    |
|  +-- Configurable baseline windows (last week / 4-week avg) |
|  +-- Degradation ratio calculation with direction awareness |
|  +-- Welch's t-test for statistical significance            |
|  +-- Minimum baseline value filtering                       |
+-------------------------------------------------------------+
|  LAYER 3: ROOT CAUSE ANALYSIS & RECOMMENDATION ENGINE       |
|  +-- Severity-weighted cause scoring (1-5 scale)            |
|  +-- Multi-cause detection with ranking                     |
|  +-- Category-based classification (Radio, Capacity, etc.)  |
|  +-- Actionable RF optimization recommendations             |
+-------------------------------------------------------------+
```

### 1.4 Key Features (v2.0 Enhanced)

| Feature | Description |
|---------|-------------|
| **13 KPI Categories** | Traffic, Integrity, Accessibility, Retainability, Mobility, Availability, CSFB, VoLTE, RRC Re-establishment |
| **142 Detection Rules** | Correlated counter analysis with configurable thresholds |
| **3 Baseline Modes** | Last-week parallel, 4-week rolling average, custom date range |
| **Statistical Significance** | Welch's t-test with p-value reporting |
| **Data Quality Engine** | Unit validation, sentinel detection, baseline imputation |
| **Coverage Analysis** | TA Distribution bins (0-156m to 6.6-14km) |
| **Cell Edge Analysis** | CEU throughput and border UE metrics |
| **Carrier Aggregation** | SCell activation, 3CC CA, FDD-TDD CA tracking |
| **MIMO/Rank Analysis** | Rank 2 reporting, CQI codeword tracking |
| **Interactive Dashboard** | Tkinter GUI with real-time charts |
| **Streamlit Web Interface** | Browser-based dashboard with tabbed results and interactive charts |
| **Word Report Generation** | Automated DOCX export with formatted tables |
| **Batch CSV Export** | Per-KPI and combined output files |

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
                     +---------------------+
                     |   User Interface    |
                     | (Tkinter / Streamlit)|
                     +----------+----------+
                                |
                     +----------v----------+
                     |  Analysis Engine    |
                     |  (Core Pipeline)    |
                     +----------+----------+
                                |
         +----------------------+----------------------+
         |                      |                      |
 +-------v--------+    +--------v---------+    +------v-------+
 |  Data Quality  |    |  Degradation     |    |   Cause      |
 |  Validator     |    |  & Baseline Eng. |    |  Detection   |
 +-------+--------+    +--------+---------+    +------+-------+
         |                      |                    |
         +----------------------+----------------------+
                                |
                     +----------v----------+
                     |  Output Generators  |
                     | (CSV / Word / Viz)  |
                     +---------------------+
```

### 2.2 Module Interaction Diagram

```
main.py
  |
  +---> initialization.py  ---> LTEKPIAnalyzerApp (Tkinter GUI Controller)
  |       |
  |       +---> main_function_for_selected_kpi.py
  |       |       +---> KPI_Configuration.py      (Rules & Thresholds)
  |       |       +---> clean_excel_and_helpers.py (Data Cleaning)
  |       |       +---> data_quality.py            (Validation & Imputation)
  |       |       +---> cause_detect_functions.py    (Root Cause Engine)
  |       |
  |       +---> combined_degraded_kpi.py           (Multi-KPI Orchestrator)
  |       +---> Visualization_Functions.py         (Charts & Dashboards)
  |       +---> Generate_Word_Report.py            (DOCX Export)
  |       +---> Save_Results.py                    (CSV Export)
  |       +---> Loading_file_inputs_outputs.py     (File I/O)
  |
  +---> app_streamlit.py  ---> Streamlit Web UI
  +---> test_data_quality.py    (Integration Tests)
  +---> test_negative_filter.py  (Unit Tests)
```

### 2.3 Data Flow

```
Raw Excel Data
      |
      v
+-----------------+
| Column Cleaning |  <- clean_excel_columns()
| (spaces, breaks)|
+--------+--------+
         |
         v
+-----------------+
| Smart Matching  |  <- find_matching_column()
| (fuzzy names)   |
+--------+--------+
         |
         v
+-----------------+
| Data Quality    |  <- validate_columns()
| Validation      |     compute_baseline_imputed()
+--------+--------+
         |
         v
+-----------------+
| Period Splitting|  <- get_periods_enhanced()
| (Recent vs Baseline)
+--------+--------+
         |
         v
+-----------------+
| Aggregation     |  <- groupby().agg()
| (mean/max/sum)  |
+--------+--------+
         |
         v
+-----------------+
| Degradation     |  <- calculate_degradation()
| Calculation     |
+--------+--------+
         |
         v
+-----------------+
| Significance    |  <- perform_ttest()
| Testing         |
+--------+--------+
         |
         v
+-----------------+
| Cause Detection |  <- find_degradation_causes_vectorized()
| & Scoring       |
+--------+--------+
         |
         v
+-----------------+
| Output Gen.     |  <- CSV / Word / Dashboard
+-----------------+
```

---

## 3. Core Concepts & Methodology

### 3.1 Degradation Detection Formula

For a given KPI with **bad direction** defined:

**If bad_direction = "low"** (degradation when value decreases):
```
Degradation % = ((baseline_value - recent_value) / baseline_value) x 100
```

**If bad_direction = "high"** (degradation when value increases):
```
Degradation % = ((recent_value - baseline_value) / baseline_value) x 100
```

**Ratio KPI Special Case:**
For percentage-based KPIs (RRC SR, Drop Rate, HO SR, Availability, etc.), the degradation is calculated as a **signed difference in percentage points** rather than relative percentage change:

```
Degradation % = recent_value - baseline_value   (for bad_direction = "high")
Degradation % = baseline_value - recent_value   (for bad_direction = "low")
```

This avoids division-by-zero when baseline is 0 and correctly reflects that a drop from 99% to 95% is a 4-percentage-point degradation regardless of the baseline value. The sign preserves directional information even though threshold gating uses `>=`.

A cell is flagged as **degraded** when:
```
Degradation % >= Threshold AND (statistical_significance = True OR disabled)
```

### 3.2 Baseline Window Strategies

| Mode | Description | Use Case |
|------|-------------|----------|
| **Last Week** | Same N days from previous week | Detecting sudden incidents |
| **4-Week Rolling** | Median of same weekdays over 4 weeks | Smoothing weekly patterns |
| **Custom Range** | User-defined start/end dates | Special event analysis |

### 3.3 Statistical Significance Testing

**Welch's t-test** (unequal variance) is performed between recent and baseline value distributions:

```python
t_stat, p_value = scipy.stats.ttest_ind(
    recent_values, baseline_values, equal_var=False
)
```

- **Significant** if `p_value < 0.05`
- Prevents false positives from high-variability cells
- Can be disabled for faster processing

### 3.4 Severity-Weighted Cause Scoring

Each detected cause receives a **score** for ranking:

```
Score = ChangeValue x Severity_Level
```

**Note:** The unit of `ChangeValue` depends on the feature type:
- For **dB/dBm** features (RSRP, RIN, interference): absolute difference in **dB**
- For **ratio/percentage** features (RRC SR%, Drop Rate%, PRB%): absolute difference in **percentage points**
- For **counters/volumes** (attempts, GBytes, Mbps): relative **percentage change** `((baseline - recent) / baseline) × 100`

| Severity | Level | Examples |
|----------|-------|----------|
| 1 | Low | Traffic demand variations |
| 2 | Medium | Capacity indicators, CA issues |
| 3 | High | Throughput degradation, interference |
| 4 | Critical | Radio failures, MME issues |
| 5 | Emergency | Availability loss, abnormal releases |

The cause with the **highest score** is reported as the main root cause.

### 3.5 Data Quality Framework

#### 3.5.1 Unit-Aware Validation

Columns are classified by physical unit:

| Unit Type | Valid Range | Example Columns | Notes |
|-----------|-------------|-----------------|-------|
| `nonneg` | >= 0 | Traffic volumes, counters, throughput | Zero is valid (not missing) |
| `pct` | [0, 100] | Success rates, utilization percentages | Zero baseline handled specially for ratio KPIs |
| `dbm` | <= 0 | RSRP, interference (received power) | Negative values are physically valid |
| `db` | Any | SINR, RSRQ (can be positive or negative) | Negative values are physically valid |

#### 3.5.2 Sentinel Value Detection

Vendor-specific "no data" markers are identified and nullified:
- `4294967295` (0xFFFFFFFF — unsigned int max)
- `4294967294` (0xFFFFFFFE)

#### 3.5.3 Baseline Imputation

For missing baseline days, the system imputes using:
```
imputed_value = median(same_weekday_values_over_last_N_weeks)
```

**Constraints:**
- Minimum 2 historical samples required
- Recent window is NEVER imputed (preserves real outage detection)
- Imputation is applied internally during baseline aggregation; cells with imputed values are listed in the incomplete-cells output

#### 3.5.4 Baseline Fallback (Ratio vs Non-Ratio Handling)

The fallback logic now distinguishes between **ratio KPIs** (percentages like RRC SR, Drop Rate, HO SR) and **non-ratio KPIs** (volumes like Traffic, Throughput):

**For ratio KPIs:**
- **NaN baseline** (missing data): attempt historical fallback → then `min_baseline_value`
- **Zero baseline** (actual 0%): pass through as `0` — the signed-difference formula has no denominator, so zero is safe and correctly represents outage recovery (if recent > 0, it's improvement; if recent = 0, degradation is 0)

**For non-ratio KPIs:**
- **NaN baseline** (missing data): attempt historical fallback → then `min_baseline_value`
- **Zero baseline** (actual 0 GB/Mbps): attempt historical fallback first → then marked as `NaN` with source `no_usable_baseline` and **excluded** from analysis (the old `0.001` placeholder was removed because it manufactured false signals, e.g., dead cells scoring +100%)

This ensures ratio KPIs with a legitimate 0% baseline are evaluated correctly without artificial floor values.

---

## 4. Project Structure

```
LTE_RAN_KPI_Analysis_Tool/
|
+-- main.py                              # Application entry point
+-- initialization.py                    # Tkinter GUI & app controller
+-- app_streamlit.py                     # Streamlit web interface
|
+-- KPI_Configuration.py                 # KPI definitions, rules, thresholds
|   +-- 13 KPI configurations
|   +-- 142+ related detection rules
|   +-- Unit classification & validation
|   +-- is_ratio flags for percentage-aware handling
|
+-- main_function_for_selected_kpi.py    # Core analysis pipeline
|   +-- Data loading & cleaning
|   +-- Period splitting & aggregation
|   +-- Degradation calculation (ratio-aware)
|   +-- Significance testing
|   +-- Cause detection integration
|
+-- combined_degraded_kpi.py             # Multi-KPI batch analysis
|
+-- cause_detect_functions.py            # Root cause analysis engine
|   +-- Vectorized cause detection (ratio-aware)
|   +-- Row-by-row fallback
|
+-- data_quality.py                      # Data validation & imputation
|   +-- validate_columns()
|   +-- compute_baseline_imputed()
|   +-- compute_baseline_fallback_from_history()
|   +-- apply_baseline_fallback() (ratio-aware)
|
+-- clean_excel_and_helpers.py           # Data cleaning utilities
|   +-- Column name normalization
|   +-- Smart column matching
|   +-- Numeric cleaning
|   +-- Degradation calculation (ratio-aware)
|
+-- anomaly_detection.py                 # Last-day anomaly detection
|   +-- Zero anomaly detection
|   +-- Spike anomaly detection (24-day z-score baseline)
|
+-- Visualization_Functions.py           # Charts & dashboards
|   +-- show_dashboard()
|   +-- show_trend_dashboard()
|
+-- Generate_Word_Report.py              # DOCX report generation
|
+-- Save_Results.py                      # CSV/Excel export
|
+-- Loading_file_inputs_outputs.py       # File I/O dialogs
|
+-- kpi_test_utils.py                    # Test utilities
+-- requirements.txt                     # Python dependencies
+-- KPI_and_its_related_counters.md      # Complete KPI reference
```

---

## 5. Installation & Dependencies

### 5.1 System Requirements

- **Python:** 3.8 or higher
- **OS:** Windows 10/11, Linux, macOS
- **RAM:** 4GB minimum (8GB recommended for large datasets)
- **Display:** 1366x768 minimum resolution for GUI

### 5.2 Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-org/lte-kpi-analyzer.git
cd lte-kpi-analyzer

# 2. Create virtual environment (recommended)
python -m venv venv

# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify installation
python test_data_quality.py
python test_negative_filter.py
```

### 5.3 Dependency Reference

| Package | Version | Purpose |
|---------|---------|---------|
| `numpy` | >=1.20.0 | Numerical operations, array handling |
| `pandas` | >=1.3.0 | DataFrame manipulation, Excel I/O |
| `scipy` | >=1.7.0 | Statistical testing (Welch's t-test) |
| `matplotlib` | >=3.4.0 | Chart visualization |
| `python-docx` | >=0.8.11 | Word document generation (optional) |
| `openpyxl` | >=3.0.0 | Excel .xlsx file reading |
| `xlrd` | >=2.0.0 | Excel .xls file reading |

---

## 6. Configuration Guide

### 6.1 KPI Configuration (KPI_Configuration.py)

Each KPI follows this structure:

```python
"KPI Name": {
    "target_kpi": "(HU) DL Traffic Volume (GBytes)",  # Exact or fuzzy column name
    "bad_direction": "low",                           # "low" or "high"
    "default_threshold": 30.0,                        # Degradation trigger %
    "category": "Traffic",                            # Classification
    "output_prefix": "dl_traffic",                    # File naming
    "min_baseline_value": 1.0,                        # Minimum baseline filter
    "is_ratio": False,                                # True for percentage KPIs
    "related_rules": [
        {
            "feature": "(HU) Cell DL Average Throughput (Mbps)",
            "bad_direction": "low",
            "threshold": 20,                          # Rule-specific threshold
            "severity": 3,                            # 1-5 severity scale
            "category": "DL Throughput Degradation",
            "reason": "Cell DL throughput decreased.",
            "recommended_action": "Check DL scheduler, bandwidth..."
        },
        # ... more rules
    ]
}
```

**Ratio KPIs** (`is_ratio: True`) use absolute difference in percentage points for degradation calculation and special zero-baseline handling. Non-ratio KPIs (`is_ratio: False`) use relative percentage change.

### 6.2 Adding a New KPI

```python
# 1. Add to KPI_CONFIGS dictionary
"My New KPI": {
    "target_kpi": "My Counter Name",
    "bad_direction": "low",
    "default_threshold": 10.0,
    "category": "Custom",
    "output_prefix": "my_kpi",
    "min_baseline_value": 0.0,
    "related_rules": [
        {
            "feature": "Related Counter 1",
            "bad_direction": "high",
            "threshold": 20,
            "severity": 3,
            "category": "Custom Category",
            "reason": "Description of why this indicates degradation",
            "recommended_action": "What the engineer should check"
        }
    ]
}

# 2. Run validation (automatic on import)
# validate_kpi_configs() is called at module load

# 3. Restart the application
```

### 6.3 Imputation Configuration

```python
# In KPI_Configuration.py
IMPUTATION_CONFIG = {
    "enable_imputation": True,      # Master switch
    "lookback_weeks": 4,            # Historical weeks for median
    "min_impute_samples": 2,        # Minimum samples to impute
}
```

### 6.4 Sentinel Values

```python
# In KPI_Configuration.py
SENTINEL_VALUES = (4294967295, 4294967294)  # Add vendor-specific markers
```

---

## 7. Usage Guide

### 7.1 Starting the Application

```bash
# Desktop GUI (Tkinter)
python main.py

# Web Interface (Streamlit)
streamlit run LTE_RAN_KPI_Analysis_Tool/app_streamlit.py
```

### 7.2 GUI Overview

```
+-----------------------------------------------------------------------------+
| LTE KPI Degradation Analyzer v2.0 -- Developed by Musketeers_Team          |
+-----------------------------------------------------------------------------+
| [Browse] C:\data\kpi_export.xlsx  [Sheet: v Sheet1]                        |
+-----------------------------------------------------------------------------+
| KPI: [v DL Traffic        ]  Days: [4 ^]  Threshold: [30.0  ]            |
| Baseline Mode: (*) Last Week  ( ) 4-Week Avg  ( ) Custom Range             |
| [x] Require complete days    [x] Enable t-test significance filter         |
|                                                                              |
| [Run Selected KPI] [Analyze All KPIs] [Generate Report] [Save CSV]         |
| [Show Dashboard] [Trend Dashboard]                                         |
+-----------------------------------------------------------------------------+
| Results Preview                                                              |
| +-----------------+-----------------+----------------------+----------------+|
| | eNodeB Name     | Cell Name       | kpi_degradation_%    | main_cause... ||
| +-----------------+-----------------+----------------------+----------------+|
| | eNB001          | Cell-A          | 45.23                | Radio Quality  ||
| | eNB001          | Cell-B          | 38.91                | Capacity Issue ||
| +-----------------+-----------------+----------------------+----------------+|
+-----------------------------------------------------------------------------+
| Log                                                                          |
| [10%] Loading Excel sheet: Sheet1...                                         |
| [35%] Analyzing KPI: DL Traffic...                                           |
| [100%] Analysis completed.                                                   |
+-----------------------------------------------------------------------------+
```

### 7.2 Streamlit Web Interface

The Streamlit UI provides the same analysis capabilities in a browser-based interface:

**Sidebar Inputs:**
- File upload (.xlsx/.xls) with automatic sheet detection
- KPI selector, comparison days, threshold
- Baseline mode (last week / 4-week rolling average)
- Completeness and t-test toggles

**Main Area Tabs:**
1. **Degraded Cells** - Filterable table with site/cell search and degradation range slider
2. **Charts** - Bar charts for degraded cells per KPI and root cause distribution
3. **Trends** - Before/after line chart showing enhancement potential after removing degraded cells
4. **Exports** - CSV and Excel download buttons

### 7.3 Analysis Workflow

1. **Select File:** Click "Browse" and choose your Excel file
2. **Select Sheet:** Choose the appropriate sheet from the dropdown
3. **Configure Analysis:**
   - Select KPI from dropdown
   - Set comparison days (1-14)
   - Adjust threshold if needed
   - Choose baseline mode
4. **Run Analysis:** Click "Run Selected KPI" or "Analyze All KPIs"
5. **Review Results:** Examine degraded cells in the preview table
6. **Visualize:** Click "Show Dashboard" for charts
7. **Export:** Save as CSV or generate Word report

### 7.4 Output Columns Reference

| Column | Description |
|--------|-------------|
| `eNodeB Name` / `Cell Name` / `LocalCell Id` | Cell identifiers |
| `selected_kpi_name` | Name of analyzed KPI |
| `target_kpi_column` | Actual matched column name |
| `kpi_category` | KPI classification |
| `kpi_bad_direction` | "low" or "high" |
| `selected_threshold_%` | Applied degradation threshold |
| `recent_period` / `baseline_period` | Analysis date ranges |
| `recent_avg_kpi` / `baseline_avg_kpi` | Aggregated values |
| `recent_days_count` / `baseline_days_count` | Data completeness |
| `kpi_degradation_ratio_%` | Calculated degradation |
| `kpi_status` | "Degraded" or "Normal" |
| `stat_significant` | True if p < 0.05 |
| `p_value` / `t_statistic` | Test statistics |
| `main_cause_counter_or_kpi` | Top-ranked root cause |
| `main_root_cause_category` | Cause classification |
| `main_degradation_reason` | Human-readable explanation |
| `main_recommended_action` | Engineering action item |
| `number_of_detected_causes` | Total causes found |
| `multi_cause_flag` | "Yes" if multiple causes |
| `all_detected_causes` | Top 5 causes with values |
| `all_cause_categories` | Categories of top 5 causes |
| `all_recommended_actions` | Actions for top 5 causes |

---

## 8. Data Quality Framework

### 8.1 Validation Pipeline

```
Input Data
    |
    +---> Column Name Matching (fuzzy)
    |
    +---> Unit Classification
    |       +-- nonneg -> check < 0
    |       +-- pct -> check < 0 or > 100
    |       +-- dbm -> check > 0
    |       +-- db -> sentinel only
    |
    +---> Sentinel Detection (4294967295, 4294967294)
    |
    +---> Invalid Value Nullification
    |
    +---> Quarantine Recording
```

### 8.2 Quarantine Output

Invalid values are saved to a quarantine CSV file:

- **Single-KPI mode:** `{prefix}_counter_quarantine.csv`
- **All-KPIs mode:** `data_quality_quarantine.csv`

| Column | Description |
|--------|-------------|
| `eNodeB Name` / `Cell Name` / `LocalCell Id` | Cell identifiers |
| `Date` | Timestamp of invalid value |
| `kpi` | KPI being analyzed |
| `counter` | Column with invalid value |
| `bad_value` | The invalid raw value |
| `reason` | Why it was quarantined |

### 8.3 Incomplete Cell Tracking

Cells with insufficient data are saved to `data_quality_incomplete_cells.csv`:

| Column | Description |
|--------|-------------|
| `recent_days_count` / `baseline_days_count` | Actual available days |
| `expected_recent_days` / `expected_baseline_days` | Required days |
| `reason` | Why excluded (no baseline, no recent, incomplete, zero baseline) |

---

## 9. KPI Configuration Reference

### 9.1 Complete KPI Listing

| # | KPI Name | Target Column | Direction | Threshold | Category | Rules | Ratio |
|---|----------|---------------|-----------|-----------|----------|-------|-------|
| 1 | DL Traffic | `(HU) DL Traffic Volume (GBytes)` | low | 30% | Traffic | 24 | No |
| 2 | UL Traffic | `(HU) UL Traffic Volume (GBytes)` | low | 30% | Traffic | 13 | No |
| 3 | DL Throughput | `(HU) User DL Average Throughput (Mbps)` | low | 20% | Integrity | 14 | No |
| 4 | UL Throughput | `(HU) User UL Average Throughput (Mbps)` | low | 20% | Integrity | 8 | No |
| 5 | RRC Setup SR | `(TE) RRC Setup SR%` | low | 5% | Accessibility | 8 | Yes |
| 6 | ERAB Setup SR | `ERAB Setup Success Rate` | low | 5% | Accessibility | 6 | Yes |
| 7 | E-RAB Drop Rate | `E-RAB Drop Rate (E-NodeB + MME) %` | high | 0.5% | Retainability | 15 | Yes |
| 8 | HO Success Rate | `HO SR% Overall` | low | 5% | Mobility | 14 | Yes |
| 9 | Availability | `Availability` | low | 1% | Availability | 4 | Yes |
| 10 | RACH Success Rate | `(HU) RACH Success Rate(%)` | low | 5% | Accessibility | 5 | Yes |
| 11 | CSFB KPI | `CSFB SR%` | low | 5% | CSFB / Voice | 9 | Yes |
| 12 | VoLTE KPIs | `BA_Voice E2E VQI` | low | 2% | VoLTE | 14 | Yes |
| 13 | RRC Re-establishment | `RRC Reestablish Setup Success Rate(%)` | low | 10% | Mobility | 8 | Yes |

### 9.2 Feature Categories

| Category | Description | Example Features |
|----------|-------------|------------------|
| Radio Quality | Signal quality issues | CQI, IBLER, RBLER |
| Throughput | Cell/user throughput | DL/UL throughput metrics |
| Capacity | Resource utilization | PRB utilization, CCE failures |
| Interference | Uplink/downlink noise | UL interference, UpPTS |
| Availability | Cell/site outages | Unavailable time, S1 failures |
| Carrier Aggregation | CA performance | SCell activation, CA traffic |
| Coverage | Distance/cell edge | TA distribution, CEU metrics |
| MIMO | Spatial multiplexing | Rank 2, CQI codewords |
| Accessibility | Access failures | RRC/ERAB setup failures |
| Retainability | Drop issues | Abnormal releases |
| Mobility | Handover problems | HO preparation/execution |
| RACH | Random access | Contention failures |
| CSFB | Circuit switch fallback | Redirection, flash CSFB |
| VoLTE | Voice over LTE | VoIP ERAB, QCI-1/7 |
| SRVCC | Voice continuity | SRVCC HO success |
| Transport | Backhaul issues | TNL failures |
| Core | MME problems | MME overload, failures |

---

## 10. Root Cause Analysis Engine

### 10.1 Vectorized Detection Algorithm

```python
def find_degradation_causes_vectorized(df, rules):
    # 1. Reset index for alignment
    df_work = df.reset_index(drop=True).copy()

    # 2. For each rule, vectorized numpy operations
    for rule in rules:
        feature = rule["feature"]
        unit = classify_unit(feature)       # 'dbm' | 'db' | 'pct' | 'nonneg'
        is_ratio = _is_ratio_feature(feature)

        # Routing: dB/dBm and ratio features use signed difference (no denominator);
        # everything else uses relative percentage change.
        if unit in ('dbm', 'db') or is_ratio:
            if rule["bad_direction"] == "low":
                change_pct = baseline_values - recent_values   # positive = degraded
            else:  # high
                change_pct = recent_values - baseline_values   # positive = degraded
        else:
            # Non-ratio, non-dB: relative % change
            change_pct = ((recent - baseline) / baseline) * 100

        # Vectorized threshold mask
        mask = change_pct >= rule["threshold"]

        # Severity-weighted scoring
        score = change_pct * rule["severity"]

    # 3. Aggregate per cell, sort by score
    # 4. Return top cause + top 5 all causes
```

### 10.2 Cause Ranking Example

For a cell with DL Traffic degradation:

| Rank | Feature | Change % | Severity | Score | Category |
|------|---------|----------|----------|-------|----------|
| 1 | `Availability` | -2.5% | 5 | **12.5** | Availability Issue |
| 2 | `DL RBLER` | +35% | 4 | **140.0** | DL Radio Failure |
| 3 | `DL Average CQI` | -18% | 3 | **54.0** | Radio Quality Issue |

**Main Cause:** `Availability` (highest severity-weighted score despite smaller percentage change)

**Rationale:** A 2.5% availability drop (severity 5) is more critical than a 35% RBLER increase (severity 4) because availability impacts all users and indicates a site-level problem.

### 10.3 Multi-Cause Detection

When multiple causes are detected (`multi_cause_flag = "Yes"`), the system reports:
- **Main cause:** Highest scored single issue
- **All causes:** Top 5 causes with recent/baseline values and change percentages
- **All categories:** Classification of each cause
- **All actions:** Recommended actions for each cause

---

## 11. Visualization & Reporting

### 11.1 Dashboard Features

**Degradation Dashboard:**
- Summary metrics (total KPIs, degraded cells)
- Bar chart: Degraded cells per KPI
- Horizontal bar chart: Root cause distribution
- Interactive Tkinter window

**Trend Dashboard:**
- Before/after degraded cell removal comparison
- Time-series line chart
- Fill-between highlighting degraded impact
- KPI selector dropdown

### 11.2 Word Report Structure

```
RF Optimization Analysis Report
+-- Analysis Summary
|   +-- Mode (Single/All KPIs)
|   +-- Baseline configuration
|   +-- Significance test status
|   +-- Degraded cell counts
+-- Degraded Cells Details (top 30)
|   +-- eNodeB Name, Cell Name
|   +-- Degradation ratio
|   +-- Root cause category
|   +-- Recommended action
|   +-- Statistical significance
+-- KPI Summary Table (All KPIs mode)
    +-- KPI name
    +-- Degraded cells count
    +-- Max/mean degradation
    +-- Status
```

### 11.3 CSV Export Structure

**Single KPI mode:**
- `{prefix}_degraded.csv` -- Main output
- `{prefix}_counter_quarantine.csv` -- Invalid values
- `{prefix}_incomplete_cells.csv` -- Excluded cells

**All KPIs mode:**
- `{prefix}_degraded.csv` -- Per-KPI output (13 files)
- `all_kpis_combined.csv` -- Unified degraded cells
- `summary_report.csv` -- KPI statistics
- `data_quality_quarantine.csv` -- All invalid values
- `data_quality_incomplete_cells.csv` -- All incomplete cells

---


## 12. Recent Changes

### 12.1 Unit-Aware Change Calculation & Baseline Handling

Major refactor to correctly handle different metric units in root cause detection and baseline fallback:

- **Unit-aware routing** in `cause_detect_functions.py`: `classify_unit()` routes each related counter to the correct calculation:
  - **dB/dBm** features (RSRP, RSRQ, SINR, interference): signed absolute difference in dB — avoids sign flip from negative baselines
  - **Ratio/percentage** features (RRC SR%, Drop Rate%, PRB%): signed absolute difference in percentage points
  - **Counters/volumes** (attempts, GBytes, Mbps): relative percentage change `((baseline - recent) / baseline) × 100`
- **Baseline fallback simplified for ratio KPIs**: zero baseline now passes through as `0` directly — signed difference has no denominator, so `0` is safe and correctly represents outage recovery. Removed vestigial `0.001` substitution for ratio KPIs.
- **Post-fallback exclusion fixed**: cells with `recent_avg_kpi = 0` or `baseline_avg_kpi = 0` are no longer conflated with missing data (`.isna()` check only). Genuine outages (e.g., SR = 0%, Traffic = 0 GB) now pass through to degradation calculation instead of being silently dropped.
- **Root cause detection** updated in both vectorized and row-fallback paths to use the new routing logic.

### 12.2 Anomaly Detection Baseline Fix

- `anomaly_detection.py` now **always uses the last 24 days (all weekdays)** as the historical baseline for z-score spike detection
- Compares last-day value against the full 24-day distribution of that specific cell
- Provides more robust detection than same-weekday matching by using all available recent history
- Z-score thresholding remains the primary spike detection method

### 12.3 Streamlit Web Dashboard

New `app_streamlit.py` provides a browser-based interface:
- File upload with automatic sheet detection
- Single KPI and All-KPIs analysis modes
- Interactive filters (site, cell, degradation range)
- Tabbed results: Degraded Cells, Charts, Trends, Exports
- Trend analysis with enhancement potential calculation
- Direct CSV/Excel download buttons

### 12.4 KPI Configuration Updates

| KPI | Change | Reason |
|-----|--------|--------|
| **Drop Rate** → **E-RAB Drop Rate** | Renamed for clarity | Consistent naming |
| **E-RAB Drop Rate** threshold | 20.0% → 0.5% | Drop rate is already a percentage; 0.5% is a meaningful threshold |
| **VoLTE KPIs** threshold | 5.0% → 2.0% | VQI (1-5 scale) requires tighter threshold |

### 12.5 Bug-Fix Series — Correctness & Performance

A consolidated log of the correctness, reliability and performance fixes applied
to the analysis engine, grouped by bug ID (each maps to a stand-alone patch).
Behaviour-preserving fixes were verified to reproduce the prior results **exactly**
on the *New Cairo* dataset; the performance fixes leave outputs unchanged; the two
intentional behaviour changes (BUG-07, and the BUG-04 winsor cap) are flagged as
such below.

**Data-quality & baseline correctness**

- **BUG-04 — non-ratio zero-baseline `0.001` placeholder removed** (`data_quality.py`, patch `0001`): a genuinely-zero non-ratio baseline (no observation, no recoverable history) was substituted with `0.001` as a fake "outage recovery" reference. Because relative-% degradation divides by the baseline, this manufactured false signals — a dead cell (recent `0`) scored `+100%`, and a cell coming online produced a large negative artifact that skewed the aggregates. Such baselines are now marked `NaN` with source `no_usable_baseline` and excluded explicitly. (Completes the ratio-side removal done upstream in `ce2dc00`.)
- **BUG-02 — unit-aware outage retention in post-fallback exclusion** (`main_function_for_selected_kpi.py`, patch `0002`): a measured recent value of `0` against a healthy baseline is a genuine outage (traffic → 0, RRC/E-RAB SR → 0%) and the worst-case degradation, but it was being dropped as "no data". The exclusion now separates *no data* (recent or baseline `NaN`) from *valid zero*, dropping only `NaN` — plus, for relative-% (non-ratio) KPIs, a baseline `≤ 0` (undefined denominator). Ratio/dB KPIs compare by signed difference, so a zero baseline is valid and kept. Together with BUG-04 this removes the dead-cell false positive (`0` in both periods) while retaining true outages.
- **BUG-03 — aggregate sub-daily rows in day-by-day comparison** (`main_function_for_selected_kpi.py`, patch `0003`): `compute_day_by_day_degradation` assumed one row per `(cell, date)`. A sub-daily/hourly export normalized to date level yields duplicate `DatetimeIndex` entries, so `set_index(date)[kpi]` returned a `Series` and `pd.isna(Series)` raised *"The truth value of a Series is ambiguous"*, crashing the core analysis. Values are now aggregated per calendar day (mean, matching `compute_baseline_imputed`); a verified no-op on daily data and correct on hourly input.

**Statistical significance & anomaly detection**

- **BUG-05 — significance t-test keyed on the full cell identity** (`main_function_for_selected_kpi.py`): the Welch t-test grouped observed values by `(eNodeB Name, Cell Name)` only, dropping `LocalCell Id`. Harmless while `Cell ↔ LocalCell` is 1:1, but on any site where one `Cell Name` maps to several `LocalCell Id`s it pooled unrelated series into a single test. Now grouped once by the full `CELL_ID_COLS` identity and looked up by 3-tuple key.
- **BUG-06 — finite signed *t* for constant-but-different samples** (`clean_excel_and_helpers.py`): two constant samples with different means have zero within-sample variance, so SciPy's Welch *t* is `NaN`; the old code propagated that `NaN` and silently dropped the cell from significance gating. `perform_ttest` now returns a signed infinity (sign follows `recent − baseline`) with `p = 0.0` — a real, maximally-significant difference.
- **BUG-07 — robust (MAD-based) spike z-score** *(intentional behaviour change)* (`anomaly_detection.py`): spike detection used `(value − median) / std` over the 24-day history, but `std` is inflated by the very outliers it should catch, so a genuine spike could mask its own scale. The scale is now `1.4826 × MAD` (a consistent, outlier-resistant estimator of σ), falling back to `std` only when the history is majority-constant and `MAD = 0`. The misleading `"SAME WEEKDAY"` log line and module docstring were corrected to describe the actual all-24-day lookback. This is deliberately **more** sensitive on very stable KPIs.

**Reliability & dependencies**

- **BUG-09 — `requirements.txt` matches actual imports**: added `streamlit`, `plotly`, `scikit-learn`, `xgboost`, `statsmodels`; removed `xlrd` (`xlrd ≥ 2.0` can no longer read `.xlsx`, so listing it is misleading and risky).
- **BUG-10 — unexpected errors are surfaced, not swallowed** (`clean_excel_and_helpers.py`, `combined_degraded_kpi.py`): `perform_ttest` no longer wraps its body in a bare `except Exception: return (False, nan, nan)`. Expected degenerate-input errors are caught narrowly; anything unexpected is re-surfaced via a `RuntimeWarning` (still returning a safe result so one odd cell can't abort a batch). The per-KPI batch loop now logs the full traceback on failure.

**Performance (output-preserving)**

- **BUG-08 — vectorized the per-cell hot loops** (`main_function_for_selected_kpi.py`, `anomaly_detection.py`): both `compute_day_by_day_degradation` and the anomaly detector rebuilt a full-frame boolean mask for *every* cell (`O(cells × rows)`). They now do the same arithmetic with `groupby`/pivot passes (`O(rows)`), verified frame-for-frame against the originals. End-to-end this cut anomaly detection from **~6.4 min to ~5 s** and roughly halved per-KPI degradation runtime, with identical results.

**Residual**

- **BUG-04 (residual) — winsorize tiny-baseline degradation** *(intentional, oracle-safe)* (`clean_excel_and_helpers.py`, `main_function_for_selected_kpi.py`): a near-zero but strictly positive baseline (≈ `0.0096` GB) made the relative-% metric explode (e.g. `−8743%`), skewing the mean/max stats. The non-ratio relative change is now clipped to `± DEGRADATION_PCT_CAP` (`1000%`) — far above any real degradation (threshold is single/double digits), so no classification changes; only the artifact tails are clipped. Scalar and vectorized paths share the cap.

**Verification.** The verified baseline (current `main`) is preserved exactly after all behaviour-preserving fixes: **DL Traffic** 71 degraded / 1179 analyzed, **RRC Setup SR** 0 / 1141, **E-RAB Drop Rate** 0 / 1141 — degraded sets, counts and full result frames match to `1e-9`. A regression suite (`LTE_RAN_KPI_Analysis_Tool/test_kpi_bugs.py`, one focused test per bug) accompanies the changes: all tests pass on the fixed code and the behavioural tests fail on the pre-fix code.

---

## 13. Extending the System

### 13.1 Adding New Counter Types

To support a new vendor's counter naming convention:

```python
# In clean_excel_and_helpers.py
def normalize_column_name(col) -> str:
    col = str(col).lower()
    # Add vendor-specific normalization
    col = col.replace("vendor_prefix_", "")
    # ... existing logic
    return col
```

### 13.2 Adding New Visualization

```python
# In Visualization_Functions.py
def show_new_chart(parent_window, data, params):
    win = tk.Toplevel(parent_window)
    # chart implementation
    pass
```

### 13.3 Adding Export Format

```python
# Create new module: Generate_PDF_Report.py
def generate_pdf_report(output_df, summary_df, save_path):
    # Implementation using reportlab or fpdf2
    pass

# Register in initialization.py
from Generate_PDF_Report import generate_pdf_report
```

### 13.4 Batch/CLI Mode

For headless operation (no GUI):

```python
# batch_analysis.py
from main_function_for_selected_kpi import analyze_selected_kpi
from combined_degraded_kpi import analyze_all_kpis
import pandas as pd

df = pd.read_excel("network_data.xlsx")
output, metadata = analyze_selected_kpi(
    df=df,
    selected_kpi_name="DL Traffic",
    num_days=4,
    degradation_threshold=30.0,
    baseline_mode="last_week",
    enable_significance_test=True
)
output.to_csv("results.csv", index=False)
```

---

## 14. Troubleshooting

### 14.1 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "Target KPI column not found" | Column name mismatch | Check Excel headers, use find_matching_column() logic |
| "No degraded cells found" | Threshold too strict / no real degradation | Lower threshold, disable significance test, check date range |
| "All cells excluded" | min_baseline_value too high | Adjust min_baseline_value in KPI config |
| "python-docx not installed" | Missing optional dependency | `pip install python-docx` or disable Word export |
| "Date parsing failed" | Non-standard date format | Ensure Excel dates are proper datetime cells |
| "Memory error" | Dataset too large | Process by cluster, increase RAM, or use chunked reading |
| "Zero baseline division" | Ratio KPI with 0 baseline | System passes through 0 directly for ratio KPIs (signed difference has no denominator); non-ratio KPIs use history fallback first, then 0.001 |

### 14.2 Debug Information

The system provides debug metadata after each analysis:

```python
metadata["debug_info"] = {
    "cells_after_merge": 1523,      # Cells with both recent & baseline
    "max_degradation": 87.5,        # Worst degradation % found
    "mean_degradation": 23.4,       # Average degradation %
    "min_baseline_excluded": 45,    # Cells excluded by min baseline
    "incomplete_cells": 12,         # Cells with missing days
    "quarantined_values": 3,        # Invalid values nullified
}
```

### 14.3 Log Interpretation

```
[10%] Loading Excel sheet: Sheet1...           -> File I/O in progress
[35%] Analyzing KPI: DL Traffic...              -> Core analysis running
INFO: 45 cells excluded by min_baseline_value   -> Filter applied
DQ: 3 invalid value(s) quarantined in 'PRB'     -> Data quality action
[100%] Analysis completed.                      -> Success
```

---

## 15. License & Attribution

### 15.1 Project Information

- **Project Name:** Data-Driven & Automation-Based RF Optimization for Modern 4G/5G Mobile Networks
- **System Name:** LTE KPI Degradation Analyzer v2.0
- **Institution:** Information Technology Institute (ITI)
- **Year:** 2026
- **Team:** Musketeers_Team
- **Project Type:** Graduation Project

### 15.2 Acknowledgments

This project was developed as part of the ITI graduation requirements. The system leverages:
- **Pandas & NumPy** for data manipulation
- **SciPy** for statistical testing
- **Matplotlib** for visualization
- **python-docx** for report generation
- **Tkinter** for the desktop graphical interface
- **Streamlit** for the web-based dashboard interface

### 15.3 Citation

If using this system in academic or professional work:

```bibtex
@software{lte_kpi_analyzer_2026,
  title = {LTE KPI Degradation Analyzer v2.0},
  author = {Musketeers_Team},
  institution = {Information Technology Institute (ITI)},
  year = {2026},
  note = {Graduation Project -- Data-Driven RF Optimization}
}
```

---

## Appendix A: Complete Column Categories

### A.1 TA Distribution (Coverage)
- `0-156 m`, `156-312 m`, `312-624 m`, `624-1092 m`
- `1-2 km`, `2-3.5 km`, `3.5-6.6 km`, `6.6-14 km`
- `TA Weighted Avg (meter)`

### A.2 CEU (Cell Edge User)
- `(HU)CEU Cell Downlink/Uplink Average Throughput`
- `(HU)CEU User Downlink/Uplink Average Throughput`
- `L.Traffic.User.BorderUE.Avg`

### A.3 Carrier Aggregation
- `L.CA.UE.Avg`, `L.CA.DLSCell.Act.Att`, `L.CA.DLSCell.Add.Att`
- `MAC CA Traffic Volume GB`, `MAC CA Traffic Ratio`
- `3CC DL PDCP CA Traffic Volume GB`, `DL PDCP FDDTDD CA Traffic Volume GB`

### A.4 MIMO/Rank
- `Reported rank 2 (%)`, `CQI_CW0`, `CQI_CW1`

### A.5 RRC Re-establishment
- `RRC Reestablish Setup Success Rate(%)`, `RRC Reestablish Failures(times)`
- `L.RRC.ReEstFail.NoReply`, `L.RRC.ReEstFail.Rej`, `L.RRC.ReEstFail.NoCntx`

### A.6 QCI-Specific
- `DL Traffic QCI-1/6/7/9`, `DL user Thrpt Mbps QCI 7`
- `E-RAB Drop Rate QCI 7`, `L.Traffic.ActiveUser.DL.QCI.7`

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **KPI** | Key Performance Indicator -- measurable network metric |
| **Baseline** | Reference period for comparison (historical "normal") |
| **Degradation** | Performance decline relative to baseline |
| **CEU** | Cell Edge User -- subscriber at coverage boundary |
| **CA** | Carrier Aggregation -- combining multiple carriers |
| **TA** | Timing Advance -- distance estimation from propagation delay |
| **CQI** | Channel Quality Indicator -- DL channel condition |
| **MCS** | Modulation and Coding Scheme -- spectral efficiency |
| **BLER** | Block Error Rate -- retransmission ratio |
| **PRB** | Physical Resource Block -- LTE resource unit |
| **RACH** | Random Access Channel -- initial UE access |
| **CSFB** | Circuit Switched Fallback -- voice fallback to 2G/3G |
| **VoLTE** | Voice over LTE -- packet-switched voice |
| **SRVCC** | Single Radio Voice Call Continuity -- VoLTE to 2G/3G handover |
| **Welch's t-test** | Statistical test for unequal variance means |

---

*Document Version: 2.0*  
*Last Updated: June 2026*  
*For technical support or feature requests, contact the development team.*