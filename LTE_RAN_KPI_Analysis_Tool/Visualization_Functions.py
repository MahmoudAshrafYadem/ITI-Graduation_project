# ============================================================
# LTE KPI Degradation Analyzer - Visualization Functions
# ============================================================
# This file contains functions for dashboard and chart visualization.
# Includes KPI lists for slicers and trend visualization helpers.
# ============================================================

import tkinter as tk
from tkinter import ttk
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from KPI_Configuration import (
    DATE_COL,
    SITE_COL,
    CELL_COL,
    LOCAL_CELL_COL,
    CELL_ID_COLS,
    KPI_CONFIGS,
)
from clean_excel_and_helpers import clean_numeric_series, find_matching_column


# ============================================================
# KPI LISTS FOR DASHBOARD SLICER (13 Analyzed KPIs)
# ============================================================

# Short names for dashboard display (user-friendly)
KPI_SHORT_NAMES = [
    "DL Traffic",
    "UL Traffic",
    "DL Throughput",
    "UL Throughput",
    "RRC Setup SR",
    "ERAB Setup SR",
    "Drop Rate",
    "HO Success Rate",
    "Availability",
    "RACH Success Rate",
    "CSFB KPI",
    "VoLTE KPIs",
    "RRC Re-establishment",
]

# Full list with details
KPI_LIST = [
    {
        "short_name": "DL Traffic",
        "target_column": "(HU) DL Traffic Volume (GBytes)",
        "category": "Traffic",
        "threshold_%": 30.0,
        "bad_direction": "low",
    },
    {
        "short_name": "UL Traffic",
        "target_column": "(HU) UL Traffic Volume (GBytes)",
        "category": "Traffic",
        "threshold_%": 30.0,
        "bad_direction": "low",
    },
    {
        "short_name": "DL Throughput",
        "target_column": "(HU) User DL Average Throughput (Mbps)",
        "category": "Integrity",
        "threshold_%": 20.0,
        "bad_direction": "low",
    },
    {
        "short_name": "UL Throughput",
        "target_column": "(HU) User UL Average Throughput (Mbps)",
        "category": "Integrity",
        "threshold_%": 20.0,
        "bad_direction": "low",
    },
    {
        "short_name": "RRC Setup SR",
        "target_column": "(TE) RRC Setup SR%",
        "category": "Accessibility",
        "threshold_%": 5.0,
        "bad_direction": "low",
    },
    {
        "short_name": "ERAB Setup SR",
        "target_column": "ERAB Setup Success Rate",
        "category": "Accessibility",
        "threshold_%": 5.0,
        "bad_direction": "low",
    },
    {
        "short_name": "Drop Rate",
        "target_column": "E-RAB Drop Rate (E-NodeB + MME) %",
        "category": "Retainability",
        "threshold_%": 20.0,
        "bad_direction": "high",
    },
    {
        "short_name": "HO Success Rate",
        "target_column": "HO SR% Overall",
        "category": "Mobility",
        "threshold_%": 5.0,
        "bad_direction": "low",
    },
    {
        "short_name": "Availability",
        "target_column": "Availability",
        "category": "Availability",
        "threshold_%": 1.0,
        "bad_direction": "low",
    },
    {
        "short_name": "RACH Success Rate",
        "target_column": "(HU) RACH Success Rate(%)",
        "category": "Accessibility",
        "threshold_%": 5.0,
        "bad_direction": "low",
    },
    {
        "short_name": "CSFB KPI",
        "target_column": "CSFB SR%",
        "category": "CSFB / Voice Accessibility",
        "threshold_%": 5.0,
        "bad_direction": "low",
    },
    {
        "short_name": "VoLTE KPIs",
        "target_column": "BA_Voice E2E VQI",
        "category": "VoLTE",
        "threshold_%": 5.0,
        "bad_direction": "low",
    },
    {
        "short_name": "RRC Re-establishment",
        "target_column": "RRC Reestablish Setup Success Rate(%)",
        "category": "Mobility",
        "threshold_%": 10.0,
        "bad_direction": "low",
    },
]

# Categories for grouping in dashboard
KPI_CATEGORIES = {
    "Traffic": ["DL Traffic", "UL Traffic"],
    "Integrity": ["DL Throughput", "UL Throughput"],
    "Accessibility": ["RRC Setup SR", "ERAB Setup SR", "RACH Success Rate"],
    "Retainability": ["Drop Rate"],
    "Mobility": ["HO Success Rate", "RRC Re-establishment"],
    "Availability": ["Availability"],
    "CSFB / Voice Accessibility": ["CSFB KPI"],
    "VoLTE": ["VoLTE KPIs"],
}

# Target columns to filter in raw data
KPI_TARGET_COLUMNS = [kpi["target_column"] for kpi in KPI_LIST]


# ============================================================
# HELPER FUNCTIONS FOR DASHBOARD
# ============================================================

def get_kpi_dataframe():
    """
    Get a DataFrame with all KPI information for dashboard slicer.
    
    Returns:
        DataFrame with columns: short_name, target_column, category, threshold_%, bad_direction
    """
    return pd.DataFrame(KPI_LIST)


def get_kpi_target_column(kpi_short_name):
    """
    Get the target column name for a KPI short name.
    
    Args:
        kpi_short_name: Short name of the KPI (e.g., "RACH Success Rate")
        
    Returns:
        Target column name or None if not found
    """
    for kpi in KPI_LIST:
        if kpi["short_name"] == kpi_short_name:
            return kpi["target_column"]
    return None


def get_kpi_bad_direction(target_column, selected_kpi=None):
    """
    Get the degradation direction for a KPI target column.
    """
    for kpi in KPI_LIST:
        if kpi["target_column"] == target_column:
            return kpi["bad_direction"]

    config = KPI_CONFIGS.get(selected_kpi, {}) if selected_kpi else {}
    return config.get("bad_direction", "low")


def get_kpi_threshold(kpi_short_name):
    """
    Get the threshold for a KPI short name.
    
    Args:
        kpi_short_name: Short name of the KPI
        
    Returns:
        Threshold % or None if not found
    """
    for kpi in KPI_LIST:
        if kpi["short_name"] == kpi_short_name:
            return kpi["threshold_%"]
    return None


def get_kpi_category(kpi_short_name):
    """
    Get the category for a KPI short name.
    
    Args:
        kpi_short_name: Short name of the KPI
        
    Returns:
        Category name or None if not found
    """
    for kpi in KPI_LIST:
        if kpi["short_name"] == kpi_short_name:
            return kpi["category"]
    return None


def filter_columns_for_kpis(df, include_cell_cols=True, include_date_col=True):
    """
    Filter DataFrame to show only the 13 KPI columns (plus cell/date identifiers).
    
    Args:
        df: Original DataFrame with all columns
        include_cell_cols: Include cell identifier columns
        include_date_col: Include date column
        
    Returns:
        DataFrame with only KPI columns (and optional identifiers)
    """
    cols_to_keep = []
    
    if include_cell_cols:
        cols_to_keep.extend(CELL_ID_COLS)
    
    if include_date_col:
        cols_to_keep.append(DATE_COL)
    
    # Add KPI target columns that exist in df
    for kpi in KPI_LIST:
        target_col = kpi["target_column"]
        if target_col in df.columns:
            cols_to_keep.append(target_col)
    
    # Remove duplicates while preserving order
    cols_to_keep = list(dict.fromkeys(cols_to_keep))
    
    # Filter to columns that exist
    existing_cols = [c for c in cols_to_keep if c in df.columns]
    
    return df[existing_cols].copy()


def melt_kpis_for_trend(df, value_name="KPI_Value"):
    """
    Melt DataFrame from wide to long format for trend visualization.
    
    Args:
        df: DataFrame in wide format (one column per KPI)
        value_name: Name for the value column in melted output
        
    Returns:
        DataFrame in long format
    """
    df_filtered = filter_columns_for_kpis(df, include_cell_cols=True, include_date_col=True)
    
    col_to_kpi = {kpi["target_column"]: kpi["short_name"] for kpi in KPI_LIST}
    col_to_category = {kpi["target_column"]: kpi["category"] for kpi in KPI_LIST}
    
    id_vars = list(CELL_ID_COLS) + [DATE_COL]
    value_vars = [col for col in df_filtered.columns if col not in id_vars]
    
    melted = df_filtered.melt(
        id_vars=id_vars,
        value_vars=value_vars,
        var_name="KPI_Column",
        value_name=value_name
    )
    
    melted["KPI"] = melted["KPI_Column"].map(col_to_kpi)
    melted["Category"] = melted["KPI_Column"].map(col_to_category)
    melted = melted.drop(columns=["KPI_Column"])
    
    col_order = list(CELL_ID_COLS) + [DATE_COL, "KPI", "Category", value_name]
    melted = melted[[c for c in col_order if c in melted.columns]]
    
    return melted


def calculate_enhancement_potential(original_df, degraded_cell_ids, selected_kpi_col, bad_direction):
    """
    Calculate the potential KPI enhancement if degraded cells are removed.
    
    Args:
        original_df: Original DataFrame with all KPI data
        degraded_cell_ids: Set of (Site, Cell) tuples for degraded cells
        selected_kpi_col: Target KPI column name
        bad_direction: "high" or "low"
        
    Returns:
        Enhancement potential as percentage (positive = improvement)
    """
    if original_df is None or original_df.empty or not degraded_cell_ids:
        return 0.0

    if DATE_COL not in original_df.columns or selected_kpi_col not in original_df.columns:
        return 0.0

    if SITE_COL not in original_df.columns or CELL_COL not in original_df.columns:
        return 0.0

    df = original_df.copy()
    df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")
    df = df.dropna(subset=[DATE_COL, selected_kpi_col])
    df[selected_kpi_col] = pd.to_numeric(df[selected_kpi_col], errors="coerce")

    if df.empty:
        return 0.0

    # Get last day data
    last_day = df[DATE_COL].max()
    last_day_df = df[df[DATE_COL] == last_day]

    if last_day_df.empty:
        return 0.0

    # Before: average with ALL cells on last day
    before_avg = last_day_df[selected_kpi_col].mean()

    # After: average without degraded cells on last day
    mask = last_day_df.set_index([SITE_COL, CELL_COL]).index.isin(degraded_cell_ids)
    clean_df = last_day_df[~mask]

    if clean_df.empty:
        return 0.0

    after_avg = clean_df[selected_kpi_col].mean()

    # Calculate enhancement based on bad direction
    if abs(before_avg) < 1e-10:
        return 0.0

    if bad_direction == "high":
        # High is bad (e.g., drop rate): improvement = decrease in value
        return ((before_avg - after_avg) / before_avg) * 100
    else:
        # Low is bad (e.g., throughput): improvement = increase in value
        return ((after_avg - before_avg) / before_avg) * 100


# ============================================================
# DASHBOARD FUNCTIONS
# ============================================================

def show_dashboard(parent_window, output_df, summary_df, analysis_mode, selected_kpi):
    """
    Show the degradation dashboard window.
    
    Args:
        parent_window: Parent Tkinter window
        output_df: Output DataFrame with degraded cells
        summary_df: Summary DataFrame (for all KPIs mode)
        analysis_mode: "single" or "all"
        selected_kpi: Currently selected KPI name
    """
    if output_df is None and summary_df is None:
        return
    
    dash = tk.Toplevel(parent_window)
    dash.title("LTE KPI Degradation Dashboard")
    dash.geometry("1200x760")
    
    main_frame = ttk.Frame(dash, padding=10)
    main_frame.pack(fill="both", expand=True)
    
    ttk.Label(main_frame, text="LTE KPI Degradation Dashboard", font=("Arial", 16, "bold")).pack(anchor="w", pady=(0, 10))
    
    metrics_frame = ttk.LabelFrame(main_frame, text="Summary Metrics", padding=10)
    metrics_frame.pack(fill="x", pady=(0, 10))
    
    charts_frame = ttk.Frame(main_frame)
    charts_frame.pack(fill="both", expand=True)
    
    left_chart = ttk.LabelFrame(charts_frame, text="Degraded Cells per KPI", padding=10)
    left_chart.pack(side="left", fill="both", expand=True, padx=(0, 5))
    
    right_chart = ttk.LabelFrame(charts_frame, text="Root Cause Distribution", padding=10)
    right_chart.pack(side="right", fill="both", expand=True, padx=(5, 0))
    
    # Metrics
    if analysis_mode == "all" and summary_df is not None:
        total_kpis = summary_df.shape[0]
        total_degraded = int(summary_df["degraded_cells_count"].sum()) if "degraded_cells_count" in summary_df.columns else 0
        metrics = [("Mode", "All KPIs"), ("KPIs", total_kpis), ("Total Degraded", total_degraded)]
    else:
        total_degraded = output_df.shape[0] if output_df is not None else 0
        metrics = [("Mode", "Single KPI"), ("KPI", selected_kpi), ("Degraded", total_degraded)]
    
    for i, (name, val) in enumerate(metrics):
        box = ttk.LabelFrame(metrics_frame, text=name, padding=5)
        box.grid(row=0, column=i, sticky="nsew", padx=5)
        ttk.Label(box, text=str(val), font=("Arial", 11, "bold")).pack()
        metrics_frame.columnconfigure(i, weight=1)
    
    # Charts
    fig1 = Figure(figsize=(8, 6), dpi=100)
    ax1 = fig1.add_subplot(111)
    
    if analysis_mode == "all" and summary_df is not None and "degraded_cells_count" in summary_df.columns:
        plot_df = summary_df.sort_values("degraded_cells_count", ascending=False).head(12)
        bars = ax1.bar(plot_df["kpi_name"], plot_df["degraded_cells_count"], color='steelblue')
        ax1.set_title("Degraded Cells per KPI")
        ax1.tick_params(axis="x", rotation=70)
        
        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{int(height)}',
                    ha='center', va='bottom', fontsize=9, fontweight='bold')
    else:
        ax1.text(0.5, 0.5, "No data", ha="center")
    
    fig1.tight_layout()
    canvas1 = FigureCanvasTkAgg(fig1, master=left_chart)
    canvas1.draw()
    canvas1.get_tk_widget().pack(fill="both", expand=True)
    
    fig2 = Figure(figsize=(8, 6), dpi=100)
    ax2 = fig2.add_subplot(111)
    
    if output_df is not None and not output_df.empty:
        if "main_root_cause_category" in output_df.columns:
            causes = output_df["main_root_cause_category"].value_counts().head(10)
            if not causes.empty:
                causes = causes.sort_values()
                bars = ax2.barh(causes.index, causes.values, color='coral')
                ax2.set_title("Root Causes Distribution")
                ax2.set_xlabel("Count")
                
                for bar in bars:
                    width = bar.get_width()
                    ax2.text(width, bar.get_y() + bar.get_height()/2.,
                            f' {int(width)}',
                            ha='left', va='center', fontsize=9, fontweight='bold')
            else:
                ax2.text(0.5, 0.5, "No root cause data", ha="center", va="center")
        else:
            ax2.text(0.5, 0.5, "No root cause column", ha="center", va="center")
    else:
        ax2.text(0.5, 0.5, "No data", ha="center", va="center")
    
    fig2.tight_layout()
    canvas2 = FigureCanvasTkAgg(fig2, master=right_chart)
    canvas2.draw()
    canvas2.get_tk_widget().pack(fill="both", expand=True)


def show_trend_dashboard(parent_window, original_df, output_df, degraded_cell_ids, selected_kpi, baseline_mode="last_week", log_callback=None):
    """
    Show the trend analysis dashboard window.
    
    Args:
        parent_window: Parent Tkinter window
        original_df: Original input DataFrame
        output_df: Output DataFrame with degraded cells
        degraded_cell_ids: Set of degraded cell IDs
        selected_kpi: Currently selected KPI name
        baseline_mode: Baseline mode used (kept for compatibility, not used in enhancement calc)
        log_callback: Optional logging callback
    """
    if original_df is None:
        if log_callback:
            log_callback("No data loaded")
        return
    
    if output_df is None or output_df.empty:
        if log_callback:
            log_callback("No degraded cells found")
        return
    
    trend_win = tk.Toplevel(parent_window)
    trend_win.title("KPI Trend - Before vs After Degradation Removal")
    trend_win.geometry("1300x800")
    
    main_frame = ttk.Frame(trend_win, padding=10)
    main_frame.pack(fill="both", expand=True)
    
    ttk.Label(main_frame, text="KPI Trend Analysis - Before vs After Degraded Cell Removal",
              font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 10))
    
    # Controls
    controls = ttk.Frame(main_frame)
    controls.pack(fill="x", pady=(0, 10))
    
    ttk.Label(controls, text="Select KPI:").pack(side="left", padx=5)
    
    # Use only the 13 KPIs for the slicer
    kpi_target_cols = []
    for kpi in KPI_LIST:
        target_col = kpi["target_column"]
        if target_col in original_df.columns:
            kpi_target_cols.append(target_col)
    
    if not kpi_target_cols:
        numeric_cols = original_df.select_dtypes(include=[np.number]).columns.tolist()
        numeric_cols = [c for c in numeric_cols if c not in [SITE_COL, CELL_COL, LOCAL_CELL_COL]]
        kpi_target_cols = numeric_cols[:30]
    
    config = KPI_CONFIGS.get(selected_kpi, {})
    target_kpi = config.get("target_kpi", "")
    kpi_col = find_matching_column(original_df, target_kpi)

    trend_kpi = tk.StringVar(value=kpi_col if kpi_col else (kpi_target_cols[0] if kpi_target_cols else ""))
    
    kpi_combo = ttk.Combobox(controls, textvariable=trend_kpi, values=kpi_target_cols, state="readonly", width=50)
    kpi_combo.pack(side="left", padx=5)
    
    chart_frame = ttk.LabelFrame(main_frame, text="Trend Chart", padding=10)
    chart_frame.pack(fill="both", expand=True, pady=5)
    
    def draw_chart():
        for w in chart_frame.winfo_children():
            w.destroy()
        
        col = trend_kpi.get()
        if not col or col not in original_df.columns:
            ttk.Label(chart_frame, text="Invalid KPI column").pack()
            return
        
        df = original_df.copy()
        
        if DATE_COL not in df.columns:
            ttk.Label(chart_frame, text="Date column not found").pack()
            return
        
        df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors='coerce')
        df = df.dropna(subset=[DATE_COL])
        df[col] = clean_numeric_series(df[col])
        
        # Before: all cells daily average
        daily_before = df.groupby(DATE_COL)[col].mean().reset_index()
        daily_before.columns = ['Date', 'Average']
        
        # After: remove degraded cells daily average
        if degraded_cell_ids and SITE_COL in df.columns and CELL_COL in df.columns:
            mask = df.set_index([SITE_COL, CELL_COL]).index.isin(degraded_cell_ids)
            df_clean = df[~mask]
            daily_after = df_clean.groupby(DATE_COL)[col].mean().reset_index() if len(df_clean) > 0 else daily_before.copy()
            daily_after.columns = ['Date', 'Average']
        else:
            daily_after = daily_before.copy()
        
        if daily_before.empty:
            ttk.Label(chart_frame, text="No data to plot").pack()
            return
        
        # Calculate enhancement potential using the centralized function
        bad_direction = get_kpi_bad_direction(col, selected_kpi)
        enhancement_potential = calculate_enhancement_potential(
            original_df, degraded_cell_ids, col, bad_direction
        )
        
        fig = Figure(figsize=(12, 5), dpi=100)
        ax = fig.add_subplot(111)
        
        dates = daily_before['Date'].tolist()
        x = range(len(dates))
        labels = [d.strftime('%m/%d') if hasattr(d, 'strftime') else str(d)[:10] for d in dates]
        
        ax.plot(x, daily_before['Average'].values, 'b-o', linewidth=2, markersize=6, label='Before (All Cells)')
        ax.plot(x, daily_after['Average'].values, 'g-s', linewidth=2, markersize=6, label='After (Clean Cells)')
        
        if degraded_cell_ids:
            diff = daily_before['Average'].values - daily_after['Average'].values
            ax.fill_between(x, daily_before['Average'].values, daily_after['Average'].values,
                           where=diff != 0, alpha=0.3, color='red', label='Degraded Impact')
        
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
        ax.set_xlabel('Date')
        ax.set_ylabel(col[:40])
        ax.set_title(
            f'{col[:40]} - Daily Trend (Enhancement Potential: {enhancement_potential:.2f}%)'
        )
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
    
    ttk.Button(controls, text="Update Chart", command=draw_chart).pack(side="left", padx=10)
    
    # Legend
    legend_frame = ttk.Frame(main_frame)
    legend_frame.pack(fill="x", pady=5)
    ttk.Label(legend_frame, text="■", foreground='blue', font=('Arial', 12)).pack(side="left", padx=2)
    ttk.Label(legend_frame, text="Before Removal (All Cells)").pack(side="left", padx=(0, 20))
    ttk.Label(legend_frame, text="■", foreground='green', font=('Arial', 12)).pack(side="left", padx=2)
    ttk.Label(legend_frame, text="After Removal (Clean Cells)").pack(side="left", padx=(0, 20))
    ttk.Label(legend_frame, text="■", foreground='red', font=('Arial', 12)).pack(side="left", padx=2)
    ttk.Label(legend_frame, text="Degraded Impact").pack(side="left")
    
    draw_chart()


def show_kpi_slicer_window(parent_window, original_df, degraded_df=None, log_callback=None):
    """
    Show a KPI slicer window with the 13 analyzed KPIs.
    
    Args:
        parent_window: Parent Tkinter window
        original_df: Original input DataFrame
        degraded_df: Optional DataFrame with degraded cells
        log_callback: Optional logging callback
    """
    if original_df is None:
        if log_callback:
            log_callback("No data loaded")
        return
    
    slicer_win = tk.Toplevel(parent_window)
    slicer_win.title("KPI Slicer - 13 Analyzed KPIs")
    slicer_win.geometry("1000x700")
    
    main_frame = ttk.Frame(slicer_win, padding=10)
    main_frame.pack(fill="both", expand=True)
    
    ttk.Label(main_frame, text="KPI Slicer - Select from 13 Analyzed KPIs",
              font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 10))
    
    # KPI Selection
    select_frame = ttk.LabelFrame(main_frame, text="KPI Selection", padding=10)
    select_frame.pack(fill="x", pady=(0, 10))
    
    ttk.Label(select_frame, text="Select KPI:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
    
    kpi_var = tk.StringVar(value=KPI_SHORT_NAMES[0])
    kpi_combo = ttk.Combobox(select_frame, textvariable=kpi_var, values=KPI_SHORT_NAMES, state="readonly", width=30)
    kpi_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")
    
    # KPI Info
    info_frame = ttk.LabelFrame(main_frame, text="KPI Information", padding=10)
    info_frame.pack(fill="x", pady=(0, 10))
    
    info_labels = {}
    info_fields = [
        ("Target Column:", "target_column"),
        ("Category:", "category"),
        ("Threshold %:", "threshold_%"),
        ("Bad Direction:", "bad_direction"),
    ]
    
    for i, (label_text, field_key) in enumerate(info_fields):
        ttk.Label(info_frame, text=label_text).grid(row=i, column=0, padx=5, pady=2, sticky="w")
        info_labels[field_key] = ttk.Label(info_frame, text="", width=50, anchor="w")
        info_labels[field_key].grid(row=i, column=1, padx=5, pady=2, sticky="w")
    
    def update_info(event=None):
        selected = kpi_var.get()
        for kpi in KPI_LIST:
            if kpi["short_name"] == selected:
                info_labels["target_column"].config(text=kpi["target_column"])
                info_labels["category"].config(text=kpi["category"])
                info_labels["threshold_%"].config(text=str(kpi["threshold_%"]))
                info_labels["bad_direction"].config(text=kpi["bad_direction"])
                break
    
    kpi_combo.bind("<<ComboboxSelected>>", update_info)
    update_info()
    
    # Chart Frame
    chart_frame = ttk.LabelFrame(main_frame, text="KPI Trend", padding=10)
    chart_frame.pack(fill="both", expand=True)
    
    def draw_kpi_chart():
        for w in chart_frame.winfo_children():
            w.destroy()
        
        selected_kpi = kpi_var.get()
        target_col = get_kpi_target_column(selected_kpi)
        
        if not target_col or target_col not in original_df.columns:
            ttk.Label(chart_frame, text=f"Column '{target_col}' not found in data").pack()
            return
        
        df = original_df.copy()
        
        if DATE_COL not in df.columns:
            ttk.Label(chart_frame, text="Date column not found").pack()
            return
        
        df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors='coerce')
        df = df.dropna(subset=[DATE_COL])
        
        daily_avg = df.groupby(DATE_COL)[target_col].mean().reset_index()
        daily_avg.columns = ['Date', 'Average']
        
        if daily_avg.empty:
            ttk.Label(chart_frame, text="No data to plot").pack()
            return
        
        fig = Figure(figsize=(10, 4), dpi=100)
        ax = fig.add_subplot(111)
        
        dates = daily_avg['Date'].tolist()
        x = range(len(dates))
        labels = [d.strftime('%m/%d') if hasattr(d, 'strftime') else str(d)[:10] for d in dates]
        
        ax.plot(x, daily_avg['Average'].values, 'b-o', linewidth=2, markersize=4)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
        ax.set_xlabel('Date')
        ax.set_ylabel(selected_kpi)
        ax.set_title(f'{selected_kpi} - Daily Trend')
        ax.grid(True, alpha=0.3)
        
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
    
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill="x", pady=5)
    ttk.Button(btn_frame, text="Show Trend", command=draw_kpi_chart).pack(side="left", padx=5)
    
    draw_kpi_chart()


# ============================================================
# CONVENIENCE: Print KPI list
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("KPI LIST FOR DASHBOARD SLICER (13 KPIs)")
    print("=" * 60)
    print()
    for i, kpi in enumerate(KPI_LIST, 1):
        print(f"{i:2d}. {kpi['short_name']}")
        print(f"    Target: {kpi['target_column']}")
        print(f"    Category: {kpi['category']}")
        print(f"    Threshold: {kpi['threshold_%']}%")
        print()