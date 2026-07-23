# Action Tracker & KPI Analyzer for Telecom Network Configurations

## 1. System Architecture & Component Overview

The tool will be structured as a modular Python application. Dolt acts as the version-controlled database, allowing us to pinpoint exactly when configuration CSVs were changed, while the Python application handles the logic of pairing those changes with network KPIs.

```
+-----------------------------------------------------------------------+
|                           Streamlit UI                                |
|  (Action Selector, KPI Dashboard, Charts, Comparison Parameters)      |
+----------------------------------+------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                       Data Processing Engine                          |
|  - Dolt/MySQL Client (PyMySQL)     - KPI Alignment Logic              |
|  - Action Timeline Parser          - Statistical Summary Generator    |
+----------------------------------+------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                             Dolt DB                                   |
|  - network_kpis (Table)          - network_configs (Versioned Table)  |
+-----------------------------------------------------------------------+

```

---

## 2. Data Strategy & Schema Design

To make this work, Dolt will track your configuration states, and a standard table will hold your time-series KPIs.

### Dolt Commit Log & Configurations (`network_configs`)

When CSVs are imported into Dolt, each action (e.g., changing a tilt or power parameter) corresponds to a Dolt commit.

- We will leverage the system table `dolt_commit_ancestors` or `dolt_log` via PyMySQL to extract the exact timestamp (`commit_date`) and metadata of the action.

### KPI Table (`network_kpis`)

- **Columns:** `timestamp` (DateTime), `cell_id` (VARCHAR), `kpi_accessibility` (FLOAT), `kpi_retainability` (FLOAT), `kpi_throughput` (FLOAT), etc.

#### 1. Dynamic KPI Extraction

- **Mechanism:** Upon initialization, the database layer executes a `DESCRIBE network_kpis` or queries `INFORMATION_SCHEMA.COLUMNS`.
- **UI Integration:** The tool excludes standard structural columns (like `timestamp`, `cell_id`, `node_id`) and populates a dropdown or sidebar config with the remaining numeric KPI columns it finds dynamically.

#### 2. Action "Hunking" Logic (Same-Day Aggregation)

- **Mechanism:** When scanning `dolt_log`, commits are sorted chronologically. Commits sharing the same calendar date (`YYYY-MM-DD`) are combined into a single **"Action Hunk."**
- **UI Behavior:** The user selects a specific _Action Hunk_ (by date) to analyze. The timeline visualizes these chunks together. If actions are separated by more than 24 hours (different calendar days), they become entirely separate hunks with their own independent baseline periods.

#### 3. KPI Optimization Polarity (Favorable vs. Unfavorable)

- **Mechanism:** For every auto-detected KPI, the UI displays a toggle or directional selector:
- 🔼 **Higher is Better** (e.g., Throughput, Call Setup Success Rate)
- 🔽 **Lower is Better** (e.g., Drop Rate, Block Rate)

- **Visual Impact:** This choice dynamically updates the bar chart and summary table color-coding logic. If "Drop Rate" drops, the delta is negative, but the tool highlights it green (🟢 Improved).

---

## 3. Step-by-Step Implementation Plan

### Phase 1: Database Integration (`db_layer.py`)

Using `PyMySQL`, we will create a data access layer to pull both the configuration diffs and the matching KPI data.

- **Extracting Actions:** Query `dolt_log` to get a list of actions, their timestamps, and commit hashes.
- **Extracting Diffs:** Use Dolt's system functions (e.g., `SELECT * FROM dolt_diff_network_configs WHERE to_commit = 'hash'`) to identify what specific parameters were changed during that action.
- **Extracting KPIs:** Query the `network_kpis` table for specific date windows.

### Phase 2: Action Alignment & Matching Logic (`analytics.py`)

This is the core logic engine handling your specific time-matching constraints.

- **Weekday Alignment Logic:** If an action occurs on **Monday, June 8th**, the tool will:

1. Define the "After" period (e.g., Monday, June 8th post-action, or the following Monday, June 15th).
2. Define the "Before" period by matching the exact same day of the week (e.g., Monday, June 1st).

- **Multi-Action Isolation:** If Action A happens at 10:00 AM and Action B happens at 2:00 PM on the same day:
- The baseline window for Action B will exclude the overlapping period, or flag to the user that Action A's tail-effect is active. The tool will slice KPI segments tightly around the commit timestamps.

### Phase 3: Visualization & UI Development (`app.py`)

We will use **Streamlit** for the web interface and **Plotly** for interactive, responsive charts.

#### 1. Action Timeline (Visual #4)

- **Component:** Plotly Timeline / Gantt chart or a scatter plot with a timeline axis.
- **Function:** Displays markers for every Dolt commit (action). Clicking a marker selects that action for analysis.

#### 2. KPI Line Chart (Visual #1)

- **Component:** Plotly Line Chart.
- **Function:** Overlays the "Before" weekday line and the "After" weekday line on a normalized 24-hour X-axis so the user can easily see deviation trends.

#### 3. Delta Bar Chart (Visual #2)

- **Component:** Plotly Bar Chart.
- **Function:** Calculates $KPI_{after} - KPI_{before}$ for each time interval.
- **Color Coding:** Use a conditional color scale (e.g., `#EF553B` [Red] for negative impact on quality/throughput, `#00CC96` [Green] for positive improvement).

#### 4. KPI Summary Table (Visual #3)

- **Component:** Streamlit `st.dataframe` with formatting.
- **Function:** Displays a structured breakdown of the overall impact.

| KPI Name       | Before Avg | After Avg | Absolute Delta | % Change | Status      |
| -------------- | ---------- | --------- | -------------- | -------- | ----------- |
| Call Drop Rate | 1.2%       | 0.8%      | -0.4%          | -33.3%   | 🟢 Improved |
| DL Throughput  | 45 Mbps    | 52 Mbps   | +7 Mbps        | +15.5%   | 🟢 Improved |

---

## 4. Proposed Project Structure

```text
telecom_analyzer/
│
├── app.py                 # Main Streamlit application (UI layout & state)
├── db_layer.py            # PyMySQL connectors and Dolt system table queries
├── analytics.py           # Weekday matching, % change calculations, data filtering
├── requirements.txt       # Streamlit, PyMySQL, Plotly, Pandas
└── README.md              # Setup instructions for Dolt and the Python environment

```

---

## 5. Potential Challenges & Mitigations

- **Data Sparsity on Matching Days:** If an action is taken on a holiday Monday, comparing it to a normal business-day Monday will yield false conclusions.
- _Mitigation:_ Add an option in the UI to change the baseline to an average of the last 3 matching weekdays instead of just one.

- **Overlapping Actions:** Two configuration changes applied within 30 minutes of each other make it impossible to isolate individual KPI impacts cleanly.
- _Mitigation:_ Introduce a "Co-dependency Warning" in the timeline view if another Dolt commit is detected within the user-defined evaluation window.
