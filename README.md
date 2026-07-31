# RANPilotAi: AI-Powered RAN Performance Optimization Assistant for Modern 4G and 5G Mobile Networks

### Graduation Project — ITI 2026 | RF Optimization & LTE/NR Network Intelligence Suite

---

## 👥 Team Members

| # | Name |
|---|------|
| 1 | Mahmoud Ashraf |
| 2 | Ibrahim Samy |
| 3 | Khaled Mogahed |
| 4 | Tasneem Amein |
| 5 | Mohab Tarek |

---

## 📖 Project Overview

**RANPilotAi** is an integrated, AI-powered toolkit for 4G/5G Radio Access Network (RAN) engineers. It brings together statistical KPI degradation detection, time-series forecasting, configuration change impact analysis, and 3GPP specification Q&A — all accessible from a single unified web interface called the **Telecom Hub**.

---

## 🖥️ RAN Performance Optimization Assistant Tool — The Main Interface

The entire suite is launched through a single entry point: **`telecom_hub.py`**.

The **RAN Performance Optimization Assistant Tool** is a dark-themed Streamlit web application that acts as a unified launcher and navigation shell for all four tools. You never need to run each tool separately — it loads and runs whichever tool you select directly within the same interface.

### ⚙️ Installation

A single `requirements.txt` at the project root covers all four tools. Install everything with one command:

```bash
pip install -r requirements.txt
```

### How to Launch

```bash
streamlit run telecom_hub.py
```

Then open the URL shown in the terminal (usually `http://localhost:8501`) in your browser.

### How to Navigate

1. **Landing Page** — On first load, you'll see the Hub hero screen with cards for all four tools.
2. **Sidebar** — Use the dropdown on the left sidebar to select any of the four tools.
3. **Tool Loads In-Place** — The selected tool's full UI renders immediately inside the Hub — no new tabs or separate servers.
4. **Switch Anytime** — Use the sidebar dropdown to switch between tools at any time.

```
┌─────────────────────────────────────────────────────────────────┐
│  📡 Telecom Hub  (telecom_hub.py)                               │
│ ┌──────────────┐  ┌───────────────────────────────────────────┐ │
│ │   SIDEBAR    │  │            MAIN CONTENT AREA              │ │
│ │              │  │                                           │ │
│ │ ▸ Tool 1     │  │  (Selected tool's full UI renders here)   │ │
│ │   Tool 2     │  │                                           │ │
│ │   Tool 3     │  │                                           │ │
│ │   Tool 4     │  │                                           │ │
│ └──────────────┘  └───────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ The Four Tools

The Hub is divided into four specialized tools:

---

### 1. 📡 4G(LTE)/5G(NR) KPI Degradation Analyzer
**Location:** `LTE_RAN_KPI_Analysis_Tool/`

Automatically detects performance degradation in LTE/NR cells by comparing recent KPI windows against historical baselines using statistical methods.

**Key Features:**
- Detects degradation across 13+ KPI categories (Throughput, Drop Rate, HO Success Rate, Availability, VoLTE, CSFB, RRC Re-establishment, and more)
- Two baseline strategies: **Last Week** and **4-Week Rolling Median**
- **Welch's t-test** for statistical confidence scoring
- RF-aware cause scoring to rank and pinpoint root causes
- Handles ratio KPIs (percentage-point difference) vs. counter KPIs (relative % change) correctly
- Outputs: interactive dashboard, CSV export, and Word report

**KPIs Covered:**

| # | KPI Category | Bad Direction |
|---|-------------|--------------|
| 1 | DL Traffic Volume | Low |
| 2 | UL Traffic Volume | Low |
| 3 | DL Throughput | Low |
| 4 | UL Throughput | Low |
| 5 | RRC Setup Success Rate | Low |
| 6 | E-RAB Setup Success Rate | Low |
| 7 | Drop Rate | High |
| 8 | Handover Success Rate | Low |
| 9 | Cell Availability | Low |
| 10 | RACH Success Rate | Low |
| 11 | CSFB KPI | Low |
| 12 | VoLTE KPIs | Varies |
| 13 | RRC Re-establishment | High |

---

### 2. 📈 4G(LTE)/5G(NR) KPI Forecaster
**Location:** `forcasting_section/v2/`

Forecasts future KPI trends using time-series models trained on historical RAN performance data, helping engineers anticipate degradation before it occurs.

**Key Features:**
- XGBoost-based forecasting with feature engineering
- Holt-Winters exponential smoothing as an alternative model
- Interactive Plotly charts showing forecast vs. actual
- Configurable forecast horizon and confidence intervals

---

### 3. ⚙️ Optimization Action Analyzer
**Location:** `ActionAnalyzer_tool/`

Correlates RF optimization actions (tilt/power changes, parameter updates) with KPI impact using **Dolt** — a version-controlled SQL database that tracks exactly when configurations changed.

**Key Features:**
- Links Dolt commit history to KPI time windows automatically
- **Weekday-aligned baseline** — compares post-action KPIs to the same weekday before the action
- **Same-day action grouping** — multiple commits on the same date are treated as one "Action Hunk"
- **Dynamic KPI polarity** — mark each KPI as "Higher is Better" or "Lower is Better"
- Interactive timeline, before/after line chart overlay, delta bar chart, and summary impact table

> **Note:** Requires [Dolt](https://docs.dolthub.com/introduction/installation) installed and a running Dolt SQL server with `network_kpis` and `network_configs` tables.

---

### 4. 🤖 3GPP RAG Assistant
**Location:** `RAG_tool/`

An AI chatbot that answers complex RF optimization and 5G/LTE engineering questions directly from 3GPP specification PDFs — with strict citations to TS number, release, and section.

**Key Features:**
- **Section-aware chunking** — respects 3GPP document structure (e.g., `5.5.4.4 Event A3`)
- **Table extraction** — converts PDF tables to Markdown for the LLM to read accurately
- **Cross-encoder re-ranking** using `bge-reranker-base` for precision retrieval
- **Anti-hallucination prompt** — forces the model to say *"I cannot find this in the supplied specifications"* instead of guessing
- **Local Qdrant vector database** — embeddings run fully offline; only the LLM call goes to the cloud
- **Metadata filtering** — restrict answers to a specific TS number or 3GPP release

**Setup (first time only):**
```bash
# Copy and fill in your OpenRouter API key
cp RAG_tool/.env.example RAG_tool/.env

# Place 3GPP PDFs in RAG_tool/data/ using this filename format:
#   TS_<NUMBER>_Rel_<RELEASE>.pdf
# Example: TS_36.331_Rel_17.pdf

# Index the PDFs into the local vector database
python RAG_tool/app/ingest.py
```

> **Required:** OpenRouter API key in `RAG_tool/.env` and 3GPP PDF files in `RAG_tool/data/`.

---

## 🗂️ Project Structure

```
.
├── telecom_hub.py                     # ← Main entry point (launch this)
│
├── LTE_RAN_KPI_Analysis_Tool/         # Tool 1: KPI degradation detection
│   ├── app/                           # Streamlit UI + analysis modules
│   ├── DATA/                          # Input KPI data files
│   └── requirements.txt
│
├── forcasting_section/                # Tool 2: KPI forecasting
│   ├── v2/app.py                      # Main forecasting Streamlit app
│   ├── holt_forecasting.ipynb
│   ├── xg_forecast_app.py
│   └── modular/
│
├── ActionAnalyzer_tool/               # Tool 3: Config-change impact analysis
│   ├── app.py                         # Main Streamlit app
│   ├── db.py                          # Dolt/MySQL data access layer
│   ├── data.py                        # Data processing logic
│   ├── viz.py                         # Plotly visualizations
│   └── requirements.txt
│
├── RAG_tool/                          # Tool 4: 3GPP spec Q&A chatbot
│   ├── app/                           # RAG pipeline + Streamlit UI
│   ├── vector_db/                     # Local Qdrant database (auto-created)
│   ├── .env.example                   # Environment variable template
│   └── requirements.txt
│
├── OUTPUT/                            # Sample analysis output files
├── Project materials/                 # Reference docs and project poster
└── data_forcasting_trials.ipynb       # Standalone forecasting notebook
```

---

## ⚙️ Technology Stack

| Category | Technologies |
|----------|-------------|
| **Hub & UI** | Streamlit, Plotly |
| **Data Processing** | Pandas, NumPy, SciPy |
| **Machine Learning** | XGBoost, scikit-learn, statsmodels |
| **NLP / AI** | Sentence Transformers (BGE-large), Cross-Encoder (BGE-reranker) |
| **Vector Database** | Qdrant (local embedded mode) |
| **LLM Backend** | OpenRouter API |
| **PDF Processing** | PyMuPDF |
| **Database** | Dolt (version-controlled SQL) + PyMySQL |
| **Report Generation** | python-docx, openpyxl |
| **Language** | Python 3.11+ |

---

## 📄 License

This project was developed as a graduation project for academic purposes — ITI 2026.
