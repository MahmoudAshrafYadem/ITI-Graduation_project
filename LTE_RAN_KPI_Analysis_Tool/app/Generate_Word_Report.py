# ============================================================
# LTE KPI Degradation Analyzer - Generate Word Report
# ============================================================
# This file contains functions for generating Word reports.
# ============================================================

import numpy as np
import pandas as pd
from datetime import datetime

from KPI_Configuration import KPI_CONFIGS, DATE_COL, SITE_COL, CELL_COL

# Word document generation
try:
    from docx import Document
    from docx.shared import Inches, Pt, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


def calculate_enhancement_potential(original_df, degraded_cell_ids, selected_kpi):
    """
    Calculate the potential KPI enhancement if degraded cells are removed.
    
    Measures: "How much would the network KPI improve on the last day
    if we fix/remove the degraded cells?"
    
    Args:
        original_df: Original DataFrame with all KPI data
        degraded_cell_ids: Set of (Site, Cell) tuples for degraded cells
        selected_kpi: KPI short name (e.g., "DL Traffic")
        
    Returns:
        Enhancement potential as percentage (positive = improvement)
    """
    if original_df is None or original_df.empty:
        return 0.0

    if not degraded_cell_ids:
        return 0.0

    config = KPI_CONFIGS.get(selected_kpi, {})
    target_kpi = config.get("target_kpi")
    bad_direction = config.get("bad_direction", "low")

    if not target_kpi or target_kpi not in original_df.columns:
        return 0.0

    if DATE_COL not in original_df.columns:
        return 0.0

    df = original_df.copy()
    df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")
    df = df.dropna(subset=[DATE_COL, target_kpi])
    df[target_kpi] = pd.to_numeric(df[target_kpi], errors="coerce")

    if df.empty:
        return 0.0

    # Get last day data
    last_day = df[DATE_COL].max()
    last_day_df = df[df[DATE_COL] == last_day]

    if last_day_df.empty:
        return 0.0

    # Before: average with ALL cells on last day
    before_avg = last_day_df[target_kpi].mean()

    # After: average without degraded cells on last day
    if SITE_COL not in last_day_df.columns or CELL_COL not in last_day_df.columns:
        return 0.0

    mask = last_day_df.set_index([SITE_COL, CELL_COL]).index.isin(degraded_cell_ids)
    clean_df = last_day_df[~mask]

    if clean_df.empty:
        return 0.0

    after_avg = clean_df[target_kpi].mean()

    # Calculate enhancement based on bad direction
    if abs(before_avg) < 1e-10:
        return 0.0

    if bad_direction == "high":
        # High is bad (e.g., drop rate): improvement = decrease in value
        return ((before_avg - after_avg) / before_avg) * 100
    else:
        # Low is bad (e.g., throughput): improvement = increase in value
        return ((after_avg - before_avg) / before_avg) * 100


def get_top_cells_by_degradation(output_df, n=10):
    """
    Get top N cells with highest degradation.
    
    Args:
        output_df: DataFrame with degraded cells
        n: Number of top cells to return
        
    Returns:
        DataFrame of top cells
    """
    if output_df is None or output_df.empty:
        return pd.DataFrame()
    
    sorted_df = output_df.sort_values('kpi_degradation_ratio_%', ascending=False, key=abs)
    return sorted_df.head(n)


def generate_word_report(output_df, summary_df, analysis_mode, selected_kpi, baseline_mode, 
                          enable_significance_test, save_path, original_df=None, 
                          degraded_cell_ids=None, log_callback=None):
    """
    Generate a Word report with analysis results.
    
    Args:
        output_df: Output DataFrame with degraded cells
        summary_df: Summary DataFrame (for all KPIs mode)
        analysis_mode: "single" or "all"
        selected_kpi: Currently selected KPI name
        baseline_mode: Baseline mode setting
        enable_significance_test: Whether t-test was enabled
        save_path: Path to save the report
        original_df: Original input DataFrame
        degraded_cell_ids: Set of (Site, Cell) tuples for degraded cells
        log_callback: Optional logging callback
        
    Returns:
        True if successful, False otherwise
    """
    def log_msg(msg):
        if log_callback:
            log_callback(msg)
    
    if not DOCX_AVAILABLE:
        log_msg("ERROR: python-docx not installed. Run: pip install python-docx")
        return False
    
    if output_df is None or (output_df.empty and (summary_df is None or summary_df.empty)):
        log_msg("ERROR: No results to generate report")
        return False
    
    try:
        doc = Document()
        
        # Title
        doc.add_heading('RF Optimization Analysis Report', 0)
        doc.add_paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        doc.add_paragraph("Developed by: Musketeers_Team (ITI Graduation Project 2026)")
        doc.add_paragraph(f"Version: 2.0 Enhanced")
        
        # Analysis Summary
        doc.add_heading('Analysis Summary', level=1)
        
        if analysis_mode == "all":
            doc.add_paragraph(f"Analysis Mode: All KPIs Analysis")
            doc.add_paragraph(f"Baseline Mode: {baseline_mode}")
            doc.add_paragraph(f"Significance Test: {'Enabled' if enable_significance_test else 'Disabled'}")
            if summary_df is not None and not summary_df.empty:
                doc.add_paragraph(f"Total KPIs Analyzed: {len(summary_df)}")
                doc.add_paragraph(f"Total Degraded Cells: {int(summary_df['degraded_cells_count'].sum())}")
        else:
            doc.add_paragraph(f"Analysis Mode: Single KPI Analysis")
            doc.add_paragraph(f"Selected KPI: {selected_kpi}")
            doc.add_paragraph(f"Baseline Mode: {baseline_mode}")
            doc.add_paragraph(f"Degraded Cells: {len(output_df) if output_df is not None else 0}")
            if original_df is not None and degraded_cell_ids:
                enhancement = calculate_enhancement_potential(original_df, degraded_cell_ids, selected_kpi)
                doc.add_paragraph(f"Enhancement Potential: {enhancement:.2f}%")
        
        # ============================================================
        # MAIN KPI SUMMARY TABLE - All KPIs with key metrics
        # ============================================================
        if analysis_mode == "all" and summary_df is not None and not summary_df.empty:
            doc.add_heading('KPI Analysis Summary', level=1)
            
            # Columns from summary_df data
            data_cols = ['kpi_name', 'degraded_cells_count', 'max_degradation_%', 'threshold_%']
            available_data_cols = [c for c in data_cols if c in summary_df.columns]
            
            # Enhancement is always calculated separately (not from summary_df)
            always_include_enhancement = original_df is not None and degraded_cell_ids
            
            # Total columns = data columns + enhancement (if available)
            all_table_cols = available_data_cols + (['enhancement_potential_%'] if always_include_enhancement else [])
            
            if all_table_cols:
                # Calculate enhancement potential for each KPI
                enhancement_values = {}
                if always_include_enhancement:
                    for _, row in summary_df.iterrows():
                        kpi_name = row.get('kpi_name')
                        enhancement_values[kpi_name] = calculate_enhancement_potential(
                            original_df, degraded_cell_ids, kpi_name
                        )
                
                # Create table with header row
                table = doc.add_table(rows=1, cols=len(all_table_cols))
                table.style = 'Table Grid'
                
                # Format headers
                headers = table.rows[0].cells
                header_map = {
                    'kpi_name': 'KPI Name',
                    'degraded_cells_count': 'Degraded Cell Count',
                    'max_degradation_%': 'Max Degradation %',
                    'threshold_%': 'Threshold %',
                    'enhancement_potential_%': 'Enhancement Potential %'
                }
                for i, col in enumerate(all_table_cols):
                    headers[i].text = header_map.get(col, col.replace('_', ' ').title())
                
                # Add data rows
                for _, row in summary_df.iterrows():
                    cells = table.add_row().cells
                    for i, col in enumerate(all_table_cols):
                        if col == 'enhancement_potential_%':
                            # Use calculated enhancement potential
                            kpi_name = row.get('kpi_name')
                            if kpi_name in enhancement_values:
                                cells[i].text = f"{enhancement_values[kpi_name]:.2f}%"
                            else:
                                cells[i].text = "N/A"
                        else:
                            val = row.get(col, '')
                            if col == 'kpi_name':
                                cells[i].text = str(val)[:80]
                            elif col == 'degraded_cells_count':
                                cells[i].text = str(int(val)) if pd.notna(val) else "N/A"
                            elif col == 'threshold_%':
                                cells[i].text = f"{val:.2f}%" if pd.notna(val) else "N/A"
                            elif col.endswith('_%'):
                                cells[i].text = f"{abs(float(val)):.2f}%" if pd.notna(val) else "N/A"
                            else:
                                cells[i].text = "N/A" if pd.isna(val) else str(val)[:80]
        
        doc.save(save_path)
        log_msg(f"Report saved: {save_path}")
        return True
        
    except Exception as e:
        log_msg(f"Error generating report: {e}")
        return False