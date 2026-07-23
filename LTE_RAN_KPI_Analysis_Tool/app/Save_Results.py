# ============================================================
# LTE KPI Degradation Analyzer - Save Results
# ============================================================
# This file contains functions for saving results to CSV and Excel files.
# ============================================================

import os
import pandas as pd

from KPI_Configuration import CELL_ID_COLS, DATE_COL


def date_first(df):
    """Return a view/copy with Date as the first column when present."""
    if df is None or DATE_COL not in df.columns:
        return df
    return df[[DATE_COL] + [col for col in df.columns if col != DATE_COL]]


def combine_not_calculated_cells(quarantine_df=None, incomplete_df=None):
    """Combine rows excluded from calculation into one output table."""
    excluded = []

    if quarantine_df is not None and not quarantine_df.empty:
        q_df = quarantine_df.copy()
        q_df.insert(0, "Exclusion_Type", "Invalid counter value")
        excluded.append(q_df)

    if incomplete_df is not None and not incomplete_df.empty:
        i_df = incomplete_df.copy()
        i_df.insert(0, "Exclusion_Type", "Missing or insufficient data")
        excluded.append(i_df)

    if not excluded:
        return pd.DataFrame(columns=["Exclusion_Type"])

    return pd.concat(excluded, ignore_index=True, sort=False)


def remove_anomaly_cells(clean_cells_df=None, anomalies_df=None):
    """Remove cells with anomalies from the clean normal-cell output."""
    if clean_cells_df is None or clean_cells_df.empty:
        return pd.DataFrame() if clean_cells_df is None else clean_cells_df
    if anomalies_df is None or anomalies_df.empty:
        return clean_cells_df

    id_cols = [
        col for col in CELL_ID_COLS
        if col in clean_cells_df.columns and col in anomalies_df.columns
    ]
    if not id_cols:
        return clean_cells_df

    anomaly_ids = anomalies_df[id_cols].drop_duplicates()
    clean_index = pd.MultiIndex.from_frame(clean_cells_df[id_cols])
    anomaly_index = pd.MultiIndex.from_frame(anomaly_ids)
    return clean_cells_df[~clean_index.isin(anomaly_index)].copy()


def save_csv_results(
    output_df,
    summary_df,
    analysis_mode,
    selected_kpi,
    save_path_or_dir,
    log_callback=None,
    quarantine_df=None,
    incomplete_df=None,
    anomalies_df=None,
    clean_cells_df=None,
):
    """
    Save analysis results to CSV files.
    
    Args:
        output_df: Output DataFrame with degraded cells
        summary_df: Summary DataFrame
        analysis_mode: "single" or "all"
        selected_kpi: Currently selected KPI name
        save_path_or_dir: File path (single mode) or directory path (all mode)
        log_callback: Optional logging callback
        quarantine_df: Quarantined invalid values
        incomplete_df: Cells with insufficient data
        anomalies_df: Detected anomalies
        clean_cells_df: Original data without degraded or anomaly cells
        
    Returns:
        True if successful, False otherwise
    """
    def log_msg(msg):
        if log_callback:
            log_callback(msg)
    
    if output_df is None and summary_df is None:
        log_msg("ERROR: No output to save")
        return False
    
    try:
        if analysis_mode == "all":
            save_dir = save_path_or_dir
            if not save_dir:
                return False
            
            degraded_out = output_df if output_df is not None else pd.DataFrame()
            anomalies_out = anomalies_df if anomalies_df is not None else pd.DataFrame()
            clean_out = remove_anomaly_cells(clean_cells_df, anomalies_df)
            excluded_out = combine_not_calculated_cells(quarantine_df, incomplete_df)

            # Only save files that actually contain data
            outputs = [
                ("all_degraded_cells.csv", degraded_out),
                ("kpi_summary.csv", summary_df if summary_df is not None else pd.DataFrame()),
            ]
            
            if not anomalies_out.empty:
                outputs.append(("all_anomalies.csv", anomalies_out))
            if not clean_out.empty:
                outputs.append(("clean_normal_cells.csv", clean_out))
            if not excluded_out.empty:
                outputs.append(("cells_not_calculated.csv", excluded_out))

            for filename, df in outputs:
                date_first(df).to_csv(
                    os.path.join(save_dir, filename),
                    index=False,
                    encoding="utf-8-sig"
                )

            log_msg(f"Saved {len(outputs)} files to: {save_dir}")
            return True
        
        # Single KPI mode
        if output_df is None or output_df.empty:
            log_msg("ERROR: No degraded cells to save")
            return False
        
        date_first(output_df).to_csv(save_path_or_dir, index=False, encoding="utf-8-sig")
        log_msg(f"CSV saved: {save_path_or_dir}")
        return True
        
    except PermissionError:
        log_msg("ERROR: Permission denied. Check if file is open in another program or folder is read-only.")
        return False
    except OSError as e:
        log_msg(f"ERROR: Cannot save file - {e}")
        return False
    except Exception as e:
        log_msg(f"ERROR saving CSV: {str(e)}")
        return False


def save_excel_results(
    output_df,
    summary_df,
    analysis_mode,
    selected_kpi,
    excel_file_path,
    log_callback=None,
    anomalies_df=None,
    quarantine_df=None,
    incomplete_df=None,
    clean_cells_df=None,
):
    """
    Save analysis results to an Excel workbook.
    
    Sheets created (only if data exists):
    1. KPI Summary - Overview of degradation per KPI (All mode)
    2. All Degraded Cells - Degraded cells with root causes
    3. All Anomalies - Detected anomaly types
    4. Clean Normal Cells - Normal cells excluding degraded/anomaly cells
    5. Cells Not Calculated - Quarantine and incomplete rows
    
    Args:
        output_df: Output DataFrame with degraded cells
        summary_df: Summary DataFrame
        analysis_mode: "single" or "all"
        selected_kpi: Currently selected KPI name
        excel_file_path: Path to save the Excel file
        log_callback: Optional logging callback
        anomalies_df: Anomalies DataFrame
        quarantine_df: Quarantine DataFrame
        incomplete_df: Incomplete cells DataFrame
        clean_cells_df: Original data without degraded cells
        
    Returns:
        True if successful, False otherwise
    """
    def log_msg(msg):
        if log_callback:
            log_callback(msg)
    
    if output_df is None and summary_df is None:
        log_msg("ERROR: No output to save")
        return False
    
    try:
        with pd.ExcelWriter(excel_file_path, engine='openpyxl') as writer:
            degraded_out = output_df if output_df is not None else pd.DataFrame()
            anomalies_out = anomalies_df if anomalies_df is not None else pd.DataFrame()
            clean_out = remove_anomaly_cells(clean_cells_df, anomalies_df)
            excluded_out = combine_not_calculated_cells(quarantine_df, incomplete_df)

            # Build sheet list - ONLY include sheets with actual data
            sheet_outputs = []
            
            # Summary first (most important for management reporting)
            if summary_df is not None and not summary_df.empty:
                sheet_outputs.append(("KPI Summary", summary_df))
            
            # Degraded cells
            if not degraded_out.empty:
                sheet_outputs.append(("All Degraded Cells", degraded_out))
            
            # Anomalies - skip if empty
            if not anomalies_out.empty:
                sheet_outputs.append(("All Anomalies", anomalies_out))
            
            # Clean cells - skip if empty
            if not clean_out.empty:
                sheet_outputs.append(("Clean Normal Cells", clean_out))
            
            # Excluded cells - skip if empty
            if not excluded_out.empty:
                sheet_outputs.append(("Cells Not Calculated", excluded_out))

            # Write sheets
            for sheet_name, df in sheet_outputs:
                date_first(df).to_excel(writer, sheet_name=sheet_name, index=False)
                log_msg(f"  Sheet '{sheet_name}': {df.shape[0]} records")
        
        log_msg(f"Excel saved: {excel_file_path} ({len(sheet_outputs)} sheets)")
        return True
        
    except PermissionError:
        log_msg("ERROR: Permission denied. Close the Excel file if it's open and try again.")
        return False
    except OSError as e:
        log_msg(f"ERROR: Cannot save Excel - {e}")
        return False
    except Exception as e:
        log_msg(f"ERROR saving Excel: {str(e)}")
        return False