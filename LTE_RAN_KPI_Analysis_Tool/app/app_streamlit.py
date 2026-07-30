# ============================================================
# LTE KPI Degradation Analyzer - Streamlit Dashboard
# ============================================================
# Interactive web interface with charts, filters, and detailed views
# ============================================================

import io
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

from KPI_Configuration import KPI_CONFIGS, CELL_ID_COLS, DATE_COL, SITE_COL, CELL_COL, LOCAL_CELL_COL
from clean_excel_and_helpers import clean_numeric_series, find_matching_column
from main_function_for_selected_kpi import analyze_selected_kpi
from combined_degraded_kpi import analyze_all_kpis, get_clean_data_for_dashboard
from Visualization_Functions import KPI_SHORT_NAMES, KPI_LIST
from anomaly_detection import detect_kpi_anomalies_last_day

# ============================================================
# Page Configuration
# ============================================================
st.set_page_config(
    page_title="LTE KPI Degradation Analyzer",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# Session State Initialization
# ============================================================
for key in ['output_df', 'original_df', 'summary_df', 'analysis_mode', 
            'quarantine_df', 'incomplete_df', 'anomalies_df', 'degraded_cell_ids',
            'all_outputs', 'clean_cells_df']:
    if key not in st.session_state:
        st.session_state[key] = None if key != 'analysis_mode' else "single"

# ============================================================
# Sidebar - File Upload and Settings
# ============================================================
with st.sidebar:
    st.header("Input Data")
    
    uploaded_file = st.file_uploader(
        "Upload Excel file",
        type=["xlsx", "xls"],
        help="Upload LTE KPI data Excel file"
    )
    
    sheet_name = None
    if uploaded_file:
        xl = pd.ExcelFile(uploaded_file)
        sheet_name = st.selectbox("Select Sheet", xl.sheet_names, index=0)
    
    st.header("Analysis Settings")
    
    selected_kpi = st.selectbox(
        "Select KPI",
        options=list(KPI_CONFIGS.keys()),
        index=0,
        key="kpi_select"
    )
    
    config = KPI_CONFIGS[selected_kpi]
    
    num_days = st.number_input(
        "Comparison Days",
        min_value=1,
        max_value=14,
        value=4
    )
    
    threshold = st.number_input(
        "Threshold (%)",
        min_value=0.0,
        max_value=100.0,
        value=config["default_threshold"]
    )
    
    require_complete_days = st.checkbox("Require complete days", value=True)
    
    baseline_mode = st.radio(
        "Baseline Mode",
        options=["last_week", "4week_rolling_avg"],
        format_func=lambda x: "Same weekdays last week" if x == "last_week" else "4-week rolling average",
    )
    
    enable_significance_test = st.checkbox("Enable t-test significance filter", value=True)
    
    if uploaded_file:
        col1, col2 = st.columns(2)
        with col1:
            run_single = st.button("Run Selected KPI", type="primary", use_container_width=True)
        with col2:
            run_all = st.button("Analyze All KPIs", use_container_width=True)

# ============================================================
# Main Title
# ============================================================
st.title("LTE KPI Degradation Analyzer")
st.caption("Developed by: Musketeers Team (ITI Graduation Project 2026)")

# ============================================================
# Load Data
# ============================================================
df = None
if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
        st.session_state.original_df = df.copy()
        
        # Metrics row
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Rows", len(df))
        c2.metric("Total Columns", len(df.columns))
        c3.metric("Selected KPI", selected_kpi)
        c4.metric("Threshold", f"{threshold}%")
        
        # Run Analysis
        if run_single:
            with st.spinner("Analyzing selected KPI..."):
                output_df, metadata = analyze_selected_kpi(
                    df=df,
                    selected_kpi_name=selected_kpi,
                    num_days=int(num_days),
                    degradation_threshold=float(threshold),
                    require_complete_days=require_complete_days,
                    baseline_mode=baseline_mode,
                    enable_significance_test=enable_significance_test,
                    log_callback=lambda m: None,
                )
                st.session_state.output_df = output_df
                st.session_state.analysis_mode = "single"
                st.session_state.quarantine_df = metadata.get("quarantine_df")
                st.session_state.incomplete_df = metadata.get("incomplete_df")
                st.session_state.degraded_cell_ids = set()
                if not output_df.empty and SITE_COL in output_df.columns and CELL_COL in output_df.columns:
                    st.session_state.degraded_cell_ids = set(zip(output_df[SITE_COL], output_df[CELL_COL]))
        
        if run_all:
            with st.spinner("Analyzing all KPIs..."):
                combined, outputs, summary_df, quarantine_df, incomplete_df = analyze_all_kpis(
                    df=df,
                    num_days=int(num_days),
                    require_complete_days=require_complete_days,
                    baseline_mode=baseline_mode,
                    enable_significance_test=enable_significance_test,
                    log_callback=lambda m: None,
                )
                st.session_state.output_df = combined
                st.session_state.summary_df = summary_df
                st.session_state.all_outputs = outputs
                st.session_state.analysis_mode = "all"
                st.session_state.quarantine_df = quarantine_df
                st.session_state.incomplete_df = incomplete_df
                st.session_state.degraded_cell_ids = set()
                if not combined.empty and SITE_COL in combined.columns and CELL_COL in combined.columns:
                    st.session_state.degraded_cell_ids = set(zip(combined[SITE_COL], combined[CELL_COL]))
    
    except Exception as e:
        st.error(f"Error: {str(e)}")

# ============================================================
# Results Section
# ============================================================
if st.session_state.output_df is not None and not st.session_state.output_df.empty:
    # Tabs for different views
    result_tabs = st.tabs(["📋 Degraded Cells", "📊 Charts", "📈 Trends", "📁 Exports"])
    
    # Tab 1: Degraded Cells Table with Filters
    with result_tabs[0]:
        output_df = st.session_state.output_df
        
        # Filter controls
        st.subheader("Filter Results")
        filter_cols = st.columns(4)
        
        site_filter = ""
        cell_filter = ""
        min_degradation = 0.0
        max_degradation = 100.0
        
        if SITE_COL in output_df.columns:
            site_filter = st.text_input("Site Filter", key="site_filter")
        if CELL_COL in output_df.columns:
            cell_filter = st.text_input("Cell Filter", key="cell_filter")
        if 'kpi_degradation_ratio_%' in output_df.columns:
            min_degradation, max_degradation = st.slider(
                "Degradation Range (%)",
                0.0, 100.0, (0.0, 100.0),
                key="degradation_slider"
            )
        
        # Apply filters
        filtered_df = output_df.copy()
        if site_filter and SITE_COL in filtered_df.columns:
            filtered_df = filtered_df[filtered_df[SITE_COL].str.contains(site_filter, case=False, na=False)]
        if cell_filter and CELL_COL in filtered_df.columns:
            filtered_df = filtered_df[filtered_df[CELL_COL].str.contains(cell_filter, case=False, na=False)]
        if 'kpi_degradation_ratio_%' in filtered_df.columns:
            filtered_df = filtered_df[
                (filtered_df['kpi_degradation_ratio_%'] >= min_degradation) &
                (filtered_df['kpi_degradation_ratio_%'] <= max_degradation)
            ]
        
        st.write(f"Showing {len(filtered_df)} of {len(output_df)} cells")
        
        # Format display columns
        display_cols = [c for c in filtered_df.columns if c not in ['day_by_day_degradations', 'baseline_fallback_used', 
                                                                     'baseline_fallback_source', 'baseline_fallback_value']]
        st.dataframe(filtered_df[display_cols], use_container_width=True, height=400)
        
        # Summary stats
        if len(filtered_df) > 0:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Degraded Cells", len(filtered_df))
            if 'kpi_degradation_ratio_%' in filtered_df.columns:
                col2.metric("Max Degradation", f"{filtered_df['kpi_degradation_ratio_%'].max():.2f}%")
                col3.metric("Avg Degradation", f"{filtered_df['kpi_degradation_ratio_%'].mean():.2f}%")
            if 'stat_significant' in filtered_df.columns:
                col4.metric("Statistically Significant", int(filtered_df['stat_significant'].sum()))
    
    # Tab 2: Charts
    with result_tabs[1]:
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            if st.session_state.analysis_mode == "all" and st.session_state.summary_df is not None:
                plot_df = st.session_state.summary_df.sort_values("degraded_cells_count", ascending=False).head(12)
                fig, ax = plt.subplots(figsize=(8, 5))
                bars = ax.bar(plot_df["kpi_name"], plot_df["degraded_cells_count"], color='steelblue')
                ax.set_title("Degraded Cells per KPI")
                ax.set_ylabel("Count")
                plt.xticks(rotation=45, ha='right')
                for bar in bars:
                    ax.text(bar.get_x() + bar.get_width()/2., bar.get_height(),
                            f'{int(bar.get_height())}', ha='center', va='bottom', fontweight='bold')
                st.pyplot(fig)
        
        with chart_col2:
            output_df = st.session_state.output_df
            if "main_root_cause_category" in output_df.columns and len(output_df) > 0:
                causes = output_df["main_root_cause_category"].value_counts().head(10)
                fig, ax = plt.subplots(figsize=(8, 5))
                causes_sorted = causes.sort_values()
                bars = ax.barh(list(causes_sorted.index), causes_sorted.values, color='coral')
                ax.set_title("Root Causes Distribution")
                ax.set_xlabel("Count")
                st.pyplot(fig)
    
    # Tab 3: Trend Analysis
    with result_tabs[2]:
        if st.session_state.original_df is not None and len(st.session_state.degraded_cell_ids) > 0:
            # KPI selector for trend
            trend_kpi = st.selectbox(
                "Select KPI for Trend",
                options=[k["target_column"] for k in KPI_LIST if k["target_column"] in st.session_state.original_df.columns],
                format_func=lambda x: next((k["short_name"] for k in KPI_LIST if k["target_column"] == x), x)
            )
            
            if trend_kpi:
                df_trend = st.session_state.original_df.copy()
                df_trend[DATE_COL] = pd.to_datetime(df_trend[DATE_COL], errors='coerce')
                df_trend = df_trend.dropna(subset=[DATE_COL, trend_kpi])
                df_trend[trend_kpi] = pd.to_numeric(df_trend[trend_kpi], errors='coerce')
                
                # Before: all cells
                daily_before = df_trend.groupby(DATE_COL)[trend_kpi].mean().reset_index()
                
                # After: without degraded cells
                mask = df_trend.set_index([SITE_COL, CELL_COL]).index.isin(st.session_state.degraded_cell_ids)
                df_clean = df_trend[~mask]
                daily_after = df_clean.groupby(DATE_COL)[trend_kpi].mean().reset_index() if len(df_clean) > 0 else daily_before.copy()
                
                # Calculate enhancement
                before_avg = daily_before[trend_kpi].mean()
                after_avg = daily_after[trend_kpi].mean()
                if before_avg != 0:
                    enhancement = ((after_avg - before_avg) / before_avg) * 100
                else:
                    enhancement = 0
                
                fig, ax = plt.subplots(figsize=(12, 5))
                dates = daily_before[DATE_COL].tolist()
                x = range(len(dates))
                labels = [str(d)[:10] for d in dates]
                
                ax.plot(x, daily_before[trend_kpi].values, 'b-o', label='Before (All Cells)', markersize=4)
                ax.plot(x, daily_after[trend_kpi].values, 'g-s', label='After (Clean Cells)', markersize=4)
                ax.fill_between(x, daily_before[trend_kpi].values, daily_after[trend_kpi].values,
                               alpha=0.3, color='red', label='Impact Zone')
                
                ax.set_xticks(x)
                ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
                ax.set_xlabel('Date')
                ax.set_ylabel(trend_kpi)
                ax.set_title(f'{trend_kpi} - Enhancement Potential: {enhancement:.2f}%')
                ax.legend()
                ax.grid(True, alpha=0.3)
                st.pyplot(fig)
    
    # Tab 4: Exports
    with result_tabs[3]:
        output_df = st.session_state.output_df
        
        # CSV Download
        csv = output_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="Download Degraded Cells (CSV)",
            data=csv,
            file_name=f"{selected_kpi}_degraded.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        # Excel Download
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            output_df.to_excel(writer, index=False, sheet_name='Degraded_Cells')
        buffer.seek(0)
        st.download_button(
            label="Download Excel Report",
            data=buffer.getvalue(),
            file_name=f"{selected_kpi}_analysis.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# ============================================================
# Additional Info Sections
# ============================================================
if st.session_state.summary_df is not None and not st.session_state.summary_df.empty:
    st.subheader("KPI Summary")
    st.dataframe(st.session_state.summary_df, use_container_width=True)

if st.session_state.quarantine_df is not None and not st.session_state.quarantine_df.empty:
    with st.expander(f"Quarantined Values ({len(st.session_state.quarantine_df)} records)"):
        st.dataframe(st.session_state.quarantine_df, use_container_width=True)

if st.session_state.incomplete_df is not None and not st.session_state.incomplete_df.empty:
    with st.expander(f"Incomplete Cells ({len(st.session_state.incomplete_df)} records)"):
        st.dataframe(st.session_state.incomplete_df, use_container_width=True)

# ============================================================
# Raw Data Preview
# ============================================================
if st.session_state.original_df is not None:
    with st.expander("Raw Data Preview"):
        st.dataframe(st.session_state.original_df.head(50), use_container_width=True)
