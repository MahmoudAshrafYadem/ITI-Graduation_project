# ============================================================
# LTE KPI Degradation Analyzer - Loading File Inputs/Outputs
# ============================================================
# This file contains functions for loading files and handling I/O.
# ============================================================

import os
import pandas as pd
from tkinter import filedialog, messagebox


def browse_excel_file(file_path_var, sheet_combo, log_callback=None):
    """
    Open file dialog to select an Excel file.
    
    Args:
        file_path_var: Tkinter StringVar to store file path
        sheet_combo: Tkinter Combobox for sheet selection
        log_callback: Optional logging callback
        
    Returns:
        Selected file path or None
    """
    def log_msg(msg):
        if log_callback:
            log_callback(msg)
    
    path = filedialog.askopenfilename(
        title="Select KPI Excel File",
        filetypes=[("Excel files", "*.xlsx *.xls")],
    )
    
    if path:
        file_path_var.set(path)
        log_msg(f"Selected file: {path}")
        
        # Load sheet names
        try:
            xl = pd.ExcelFile(path)
            sheet_names = xl.sheet_names
            sheet_combo['values'] = sheet_names
            if sheet_names:
                sheet_combo.current(0)
                log_msg(f"Found {len(sheet_names)} sheets: {', '.join(sheet_names[:5])}{'...' if len(sheet_names) > 5 else ''}")
            return path
        except Exception as e:
            log_msg(f"Warning: Could not read sheet names: {e}")
            return path
    
    return None


def load_excel_data(file_path, sheet_name=None, log_callback=None):
    """
    Load data from an Excel file.
    
    Args:
        file_path: Path to Excel file
        sheet_name: Sheet name or index (default: first sheet)
        log_callback: Optional logging callback
        
    Returns:
        DataFrame with loaded data or None on error
    """
    def log_msg(msg):
        if log_callback:
            log_callback(msg)
    
    if not file_path or not os.path.exists(file_path):
        log_msg(f"ERROR: File not found: {file_path}")
        return None
    
    try:
        if sheet_name is None:
            sheet_name = 0
        
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        log_msg(f"Loaded: {df.shape[0]} rows, {df.shape[1]} columns")
        return df
        
    except Exception as e:
        log_msg(f"ERROR loading Excel: {e}")
        return None


def get_save_path(default_name, file_type, file_extension):
    """
    Get save path from user via file dialog.
    
    Args:
        default_name: Default file name
        file_type: File type description
        file_extension: File extension (e.g., ".csv")
        
    Returns:
        Selected save path or None
    """
    save_path = filedialog.asksaveasfilename(
        title=f"Save {file_type}",
        defaultextension=file_extension,
        initialfile=default_name,
        filetypes=[(file_type, f"*{file_extension}")]
    )
    return save_path if save_path else None


def get_save_directory(title="Select folder to save files"):
    """
    Get save directory from user via directory dialog.
    
    Args:
        title: Dialog title
        
    Returns:
        Selected directory path or None
    """
    save_dir = filedialog.askdirectory(title=title)
    return save_dir if save_dir else None
