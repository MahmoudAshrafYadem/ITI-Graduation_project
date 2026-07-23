# ============================================================
# LTE KPI Degradation Analyzer - Initialization
# ============================================================
# This file contains the main GUI application class and initialization.
# ============================================================

import os
import threading
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

import numpy as np
import pandas as pd

from KPI_Configuration import (
    DATE_COL,
    SITE_COL,
    CELL_COL,
    BASELINE_MODE_LAST_WEEK,
    BASELINE_MODE_4WEEK_AVG,
    BASELINE_MODE_CUSTOM,
    KPI_CONFIGS,
)
from clean_excel_and_helpers import find_matching_column
from main_function_for_selected_kpi import analyze_selected_kpi
from combined_degraded_kpi import analyze_all_kpis
from Visualization_Functions import show_dashboard, show_trend_dashboard
from Generate_Word_Report import generate_word_report, DOCX_AVAILABLE
from Save_Results import save_csv_results, save_excel_results
from Loading_file_inputs_outputs import browse_excel_file, get_save_path, get_save_directory
from anomaly_detection import detect_kpi_anomalies_last_day

class LTEKPIAnalyzerApp:
    """
    Main GUI Application for LTE KPI Degradation Analyzer.
    
    Features:
    - Single KPI and Multi-KPI analysis
    - Configurable baseline windows
    - Statistical significance testing
    - Dashboard visualization
    - Word report generation
    - CSV export
    """
    
    def __init__(self, root):
        """Initialize the application with default settings."""
        self.root = root
        self.root.title("LTE KPI Degradation Analyzer v2.0 - Developed by Musketeers_Team (ITI Graduation Project 2026)")
        self.root.geometry("1350x800")
        self.root.minsize(1150, 750)
        
        # File and sheet
        self.file_path = tk.StringVar()
        self.excel_sheets = []
        self.selected_sheet = tk.StringVar()
        
        # Analysis settings
        self.selected_kpi = tk.StringVar(value="DL Traffic")
        self.num_days = tk.IntVar(value=4)
        self.threshold = tk.DoubleVar(value=KPI_CONFIGS["DL Traffic"]["default_threshold"])
        self.require_complete_days = tk.BooleanVar(value=True)
        
        # Baseline mode settings
        self.baseline_mode = tk.StringVar(value=BASELINE_MODE_LAST_WEEK)
        self.custom_baseline_start = tk.StringVar()
        self.custom_baseline_end = tk.StringVar()
        
        # Statistical significance test
        self.enable_significance_test = tk.BooleanVar(value=True)
        
        # Output storage
        self.output_df = None
        self.original_df = None
        self.clean_cells_df = None
        self.degraded_cell_ids = set()
        self.all_outputs = {}
        self.summary_df = None
        self.quarantine_df = None
        self.incomplete_df = None
        self.anomalies_df = None
        self.analysis_mode = "single"
        
        # Running state
        self.is_running = False
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_percent_var = tk.StringVar(value="0%")
        self.status_var = tk.StringVar(value="Ready")
        
        self.build_ui()
    
    def build_ui(self):
        """Build the user interface components."""
        # Main frames
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill="x")
        
        settings_frame = ttk.LabelFrame(self.root, text="Analysis Settings", padding=10)
        settings_frame.pack(fill="x", padx=10, pady=5)
        
        result_frame = ttk.LabelFrame(self.root, text="Results Preview", padding=10)
        result_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=10)
        log_frame.pack(fill="x", padx=10, pady=5)
        
        # File selection with sheet selector
        ttk.Label(top_frame, text="Excel File:").pack(side="left")
        ttk.Entry(top_frame, textvariable=self.file_path, width=70).pack(side="left", padx=5)
        ttk.Button(top_frame, text="Browse", command=self.browse_file).pack(side="left", padx=5)
        
        # Sheet selector
        ttk.Label(top_frame, text="Sheet:").pack(side="left", padx=(20, 5))
        self.sheet_combo = ttk.Combobox(top_frame, textvariable=self.selected_sheet, 
                                         values=[], state="readonly", width=25)
        self.sheet_combo.pack(side="left", padx=5)
        
        # Row 0: KPI and Days
        ttk.Label(settings_frame, text="KPI:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.kpi_combo = ttk.Combobox(
            settings_frame, textvariable=self.selected_kpi,
            values=list(KPI_CONFIGS.keys()), state="readonly", width=25,
        )
        self.kpi_combo.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        self.kpi_combo.bind("<<ComboboxSelected>>", self.on_kpi_change)
        
        ttk.Label(settings_frame, text="Comparison Days:").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        ttk.Spinbox(settings_frame, from_=1, to=14, textvariable=self.num_days, width=8).grid(
            row=0, column=3, sticky="w", padx=5, pady=5
        )
        
        ttk.Label(settings_frame, text="Threshold (%):").grid(row=0, column=4, sticky="w", padx=5, pady=5)
        ttk.Entry(settings_frame, textvariable=self.threshold, width=10).grid(
            row=0, column=5, sticky="w", padx=5, pady=5
        )
        
        # Row 1: Baseline Mode
        ttk.Label(settings_frame, text="Baseline Mode:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        baseline_frame = ttk.Frame(settings_frame)
        baseline_frame.grid(row=1, column=1, columnspan=3, sticky="w", padx=5, pady=5)
        
        ttk.Radiobutton(baseline_frame, text="Same weekdays last week only", variable=self.baseline_mode, 
                        value=BASELINE_MODE_LAST_WEEK).pack(side="left", padx=5)
        ttk.Radiobutton(baseline_frame, text="Same weekdays last 4 weeks", variable=self.baseline_mode,
                        value=BASELINE_MODE_4WEEK_AVG).pack(side="left", padx=5)
        ttk.Radiobutton(baseline_frame, text="Custom Range", variable=self.baseline_mode,
                        value=BASELINE_MODE_CUSTOM).pack(side="left", padx=5)
        
        # Custom date range
        ttk.Label(settings_frame, text="Custom Baseline:").grid(row=1, column=4, sticky="w", padx=5, pady=5)
        custom_frame = ttk.Frame(settings_frame)
        custom_frame.grid(row=1, column=5, columnspan=2, sticky="w", padx=5, pady=5)
        ttk.Label(custom_frame, text="Start:").pack(side="left")
        ttk.Entry(custom_frame, textvariable=self.custom_baseline_start, width=12).pack(side="left", padx=2)
        ttk.Label(custom_frame, text="End:").pack(side="left", padx=(5, 0))
        ttk.Entry(custom_frame, textvariable=self.custom_baseline_end, width=12).pack(side="left", padx=2)
        
        # Row 2: Checkboxes and buttons
        ttk.Checkbutton(
            settings_frame, text="Require complete days",
            variable=self.require_complete_days,
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=5, pady=5)
        
        ttk.Checkbutton(
            settings_frame, text="Enable t-test significance filter",
            variable=self.enable_significance_test,
        ).grid(row=2, column=2, columnspan=2, sticky="w", padx=5, pady=5)
        
        # Buttons
        self.run_button = ttk.Button(settings_frame, text="Run Selected KPI", command=self.run_analysis_thread)
        self.run_button.grid(row=0, column=6, padx=10, pady=5)
        
        self.run_all_button = ttk.Button(settings_frame, text="Analyze All KPIs", command=self.run_all_analysis_thread)
        self.run_all_button.grid(row=0, column=7, padx=10, pady=5)
        
        self.report_button = ttk.Button(settings_frame, text="Generate Report", command=self.generate_report)
        self.report_button.grid(row=0, column=8, padx=10, pady=5)
        
        self.save_button = ttk.Button(settings_frame, text="Save CSV", command=self.save_csv)
        self.save_button.grid(row=2, column=6, padx=10, pady=5)
        
        self.excel_button = ttk.Button(settings_frame, text="Export Excel", command=self.export_excel)
        self.excel_button.grid(row=2, column=7, padx=10, pady=5)
        
        self.dashboard_button = ttk.Button(settings_frame, text="Show Dashboard", command=self.show_dashboard)
        self.dashboard_button.grid(row=3, column=6, padx=10, pady=5)
        
        self.trend_button = ttk.Button(settings_frame, text="Trend Dashboard", command=self.show_trend)
        self.trend_button.grid(row=3, column=7, padx=10, pady=5)
        
        # Info label
        self.info_label = ttk.Label(settings_frame, text="")
        self.info_label.grid(row=3, column=0, columnspan=5, sticky="w", padx=5, pady=5)
        self.update_info_label()
        
        # Progress bar
        ttk.Label(settings_frame, text="Progress:").grid(row=4, column=0, sticky="w", padx=5, pady=5)
        self.progress_bar = ttk.Progressbar(
            settings_frame, variable=self.progress_var,
            maximum=100, length=500, mode="determinate",
        )
        self.progress_bar.grid(row=4, column=1, columnspan=4, sticky="we", padx=5, pady=5)
        
        self.progress_percent_label = ttk.Label(
            settings_frame, textvariable=self.progress_percent_var, width=7,
        )
        self.progress_percent_label.grid(row=4, column=5, sticky="w", padx=5, pady=5)
        
        self.status_label = ttk.Label(settings_frame, textvariable=self.status_var)
        self.status_label.grid(row=4, column=6, columnspan=3, sticky="w", padx=5, pady=5)
        
        # Results treeview
        self.tree = ttk.Treeview(result_frame, show="headings")
        tree_y = ttk.Scrollbar(result_frame, orient="vertical", command=self.tree.yview)
        tree_x = ttk.Scrollbar(result_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_y.set, xscrollcommand=tree_x.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_y.grid(row=0, column=1, sticky="ns")
        tree_x.grid(row=1, column=0, sticky="ew")
        
        result_frame.rowconfigure(0, weight=1)
        result_frame.columnconfigure(0, weight=1)
        
        # Log box
        self.log_text = tk.Text(log_frame, height=6)
        self.log_text.pack(fill="x")
    
    # ============================================================
    # Helper Methods
    # ============================================================
    
    def log(self, msg):
        """Thread-safe logging."""
        self.root.after(0, lambda: self._log_safe(msg))
    
    def _log_safe(self, msg):
        """Actual log implementation (must run in main thread)."""
        self.log_text.insert("end", str(msg) + "\n")
        self.log_text.see("end")
    
    def update_progress(self, value, status):
        """Thread-safe progress update."""
        self.root.after(0, lambda: self._update_progress_safe(value, status))
    
    def _update_progress_safe(self, value, status):
        """Actual progress update (must run in main thread)."""
        value = max(0, min(100, float(value)))
        self.progress_var.set(value)
        self.progress_percent_var.set(f"{int(value)}%")
        self.status_var.set(status)
        self._log_safe(f"[{int(value)}%] {status}")
    
    def browse_file(self):
        """Open file dialog to select Excel file."""
        browse_excel_file(self.file_path, self.sheet_combo, self.log)
    
    def on_kpi_change(self, event=None):
        """Handle KPI selection change."""
        config = KPI_CONFIGS[self.selected_kpi.get()]
        self.threshold.set(config["default_threshold"])
        self.update_info_label()
    
    def update_info_label(self):
        """Update the info label with current KPI settings."""
        config = KPI_CONFIGS[self.selected_kpi.get()]
        min_baseline = config.get("min_baseline_value", 0)
        self.info_label.config(
            text=f"Target: {config['target_kpi']} | Bad direction: {config['bad_direction']} | Min baseline: {min_baseline}"
        )
    
    def set_running_state(self, running):
        """Set the running state and disable/enable buttons."""
        self.root.after(0, lambda: self._set_running_state_safe(running))
    
    def _set_running_state_safe(self, running):
        """Actual running state update (must run in main thread)."""
        self.is_running = running
        state = "disabled" if running else "normal"
        for btn in [self.run_button, self.run_all_button, self.save_button, self.excel_button,
                    self.dashboard_button, self.trend_button, self.report_button]:
            btn.config(state=state)
    
    def update_table(self, df):
        """Update the results table with new data."""
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = []
        
        if df is None or df.empty:
            return
        
        preview = df.head(200).copy()
        cols = list(preview.columns)
        self.tree["columns"] = cols
        
        for col in cols:
            self.tree.heading(col, text=col[:30])
            self.tree.column(col, width=140, anchor="w")
        
        for _, row in preview.iterrows():
            vals = ["" if pd.isna(row[c]) else str(row[c])[:80] for c in cols]
            self.tree.insert("", "end", values=vals)
    
    # ============================================================
    # Analysis Methods
    # ============================================================
    
    def run_analysis_thread(self):
        """Start analysis in a separate thread."""
        if self.is_running:
            messagebox.showinfo("Running", "Analysis is already running.")
            return
        self.progress_var.set(0)
        self.progress_percent_var.set("0%")
        self.status_var.set("Starting...")
        thread = threading.Thread(target=self.run_analysis, daemon=True)
        thread.start()
    
    def run_all_analysis_thread(self):
        """Start analysis of all KPIs in a separate thread."""
        if self.is_running:
            messagebox.showinfo("Running", "Analysis is already running.")
            return
        self.progress_var.set(0)
        self.progress_percent_var.set("0%")
        self.status_var.set("Starting Analyze All KPIs...")
        thread = threading.Thread(target=self.run_all_analysis, daemon=True)
        thread.start()
    
    def run_analysis(self):
        """Run analysis for selected KPI."""
        try:
            self.set_running_state(True)
            self.update_progress(2, "Checking selected file...")
            
            path = self.file_path.get().strip()
            if not path:
                self.root.after(0, lambda: messagebox.showwarning("Missing file", "Please select an Excel file."))
                return
            
            if not os.path.exists(path):
                self.root.after(0, lambda: messagebox.showerror("File error", "File does not exist."))
                return
            
            sheet_name = self.selected_sheet.get() if self.selected_sheet.get() else 0
            self.update_progress(10, f"Loading Excel sheet: {sheet_name}...")
            df = pd.read_excel(path, sheet_name=sheet_name)
            
            self.update_progress(20, "Cleaning column names...")
            self.original_df = df.copy()
            
            selected_kpi = self.selected_kpi.get()
            num_days = int(self.num_days.get())
            threshold = float(self.threshold.get())
            complete_days = bool(self.require_complete_days.get())
            baseline_mode = self.baseline_mode.get()
            enable_sig = bool(self.enable_significance_test.get())
            
            self.log(f"Loaded: {df.shape[0]} rows, {df.shape[1]} columns")
            self.log(f"Baseline mode: {baseline_mode}")
            self.log(f"Significance test: {'Enabled' if enable_sig else 'Disabled'}")
            
            self.update_progress(35, f"Analyzing KPI: {selected_kpi}...")
            
            output_df, metadata = analyze_selected_kpi(
                df=df,
                selected_kpi_name=selected_kpi,
                num_days=num_days,
                degradation_threshold=threshold,
                require_complete_days=complete_days,
                baseline_mode=baseline_mode,
                custom_baseline_start=self.custom_baseline_start.get() if baseline_mode == BASELINE_MODE_CUSTOM else None,
                custom_baseline_end=self.custom_baseline_end.get() if baseline_mode == BASELINE_MODE_CUSTOM else None,
                enable_significance_test=enable_sig,
                log_callback=self.log,
            )
            
            self.output_df = output_df
            self.all_outputs = {}
            self.summary_df = None
            self.quarantine_df = metadata.get("quarantine_df")
            self.incomplete_df = metadata.get("incomplete_df")
            self.analysis_mode = "single"
            
            # Detect anomalies
            self.log("Running anomaly detection...")
            self.anomalies_df = detect_kpi_anomalies_last_day(
                df=df,
                output_path=None,
                lookback_weeks=4,
                log_callback=self.log,
            )
            self.log(f"Anomalies found: {len(self.anomalies_df)}")
            
            # Store degraded cell IDs
            self.degraded_cell_ids = set()
            if not output_df.empty and SITE_COL in output_df.columns and CELL_COL in output_df.columns:
                for _, row in output_df.iterrows():
                    self.degraded_cell_ids.add((row.get(SITE_COL, ''), row.get(CELL_COL, '')))
            
            # Create clean cells DataFrame (original data without degraded cells)
            if self.degraded_cell_ids and SITE_COL in self.original_df.columns and CELL_COL in self.original_df.columns:
                mask = self.original_df.set_index([SITE_COL, CELL_COL]).index.isin(self.degraded_cell_ids)
                self.clean_cells_df = self.original_df[~mask].copy()
            else:
                self.clean_cells_df = self.original_df.copy() if self.original_df is not None else None
            
            self.update_progress(80, "Preparing results...")
            
            self.log(f"Recent: {metadata['recent_start'].date()} to {metadata['recent_end'].date()}")
            self.log(f"Baseline: {metadata['baseline_start'].date()} to {metadata['baseline_end'].date()}")
            debug = metadata.get("debug_info", {})
            self.log(f"Cells after merge: {debug.get('cells_after_merge')}")
            self.log(f"Degraded cells found: {output_df.shape[0]}")
            
            self.update_progress(90, "Updating table...")
            self.root.after(0, lambda: self.update_table(output_df))
            
            self.update_progress(100, "Analysis completed.")
            
            msg = f"Analysis completed. Degraded cells: {output_df.shape[0]}"
            self.root.after(0, lambda: messagebox.showinfo("Done", msg))
            
        except Exception as e:
            self.log(f"ERROR: {e}")
            self.log(traceback.format_exc()[-500:])
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.set_running_state(False)
    
    def run_all_analysis(self):
        """Run analysis for all KPIs."""
        try:
            self.set_running_state(True)
            self.update_progress(2, "Checking selected file...")
            
            path = self.file_path.get().strip()
            if not path or not os.path.exists(path):
                self.root.after(0, lambda: messagebox.showwarning("Missing file", "Please select an Excel file."))
                return
            
            sheet_name = self.selected_sheet.get() if self.selected_sheet.get() else 0
            self.update_progress(10, f"Loading Excel sheet: {sheet_name}...")
            df = pd.read_excel(path, sheet_name=sheet_name)
            self.original_df = df.copy()
            
            self.log(f"Loaded: {df.shape[0]} rows, {df.shape[1]} columns")
            
            num_days = int(self.num_days.get())
            complete_days = bool(self.require_complete_days.get())
            baseline_mode = self.baseline_mode.get()
            enable_sig = bool(self.enable_significance_test.get())
            
            combined, outputs, summary_df, quarantine_df, incomplete_df = analyze_all_kpis(
                df=df,
                num_days=num_days,
                require_complete_days=complete_days,
                baseline_mode=baseline_mode,
                enable_significance_test=enable_sig,
                log_callback=self.log,
            )
            
            self.output_df = combined
            self.all_outputs = outputs
            self.summary_df = summary_df
            self.quarantine_df = quarantine_df
            self.incomplete_df = incomplete_df
            
            # Detect anomalies
            self.log("Running anomaly detection...")
            self.anomalies_df = detect_kpi_anomalies_last_day(
                df=df,
                output_path=None,
                lookback_weeks=4,
                log_callback=self.log,
            )
            self.log(f"Anomalies found: {len(self.anomalies_df)}")

            self.analysis_mode = "all"
            
            # Store degraded cell IDs
            self.degraded_cell_ids = set()
            if not combined.empty and SITE_COL in combined.columns and CELL_COL in combined.columns:
                for _, row in combined.iterrows():
                    self.degraded_cell_ids.add((row.get(SITE_COL, ''), row.get(CELL_COL, '')))
            
            # Create clean cells DataFrame (original data without degraded cells)
            if self.degraded_cell_ids and SITE_COL in df.columns and CELL_COL in df.columns:
                mask = df.set_index([SITE_COL, CELL_COL]).index.isin(self.degraded_cell_ids)
                self.clean_cells_df = df[~mask].copy()
            else:
                self.clean_cells_df = df.copy()
            
            self.update_progress(92, "Updating table...")
            self.root.after(0, lambda: self.update_table(summary_df))
            
            total_degraded = combined.shape[0]
            self.log(f"Total degraded cells: {total_degraded}")
            
            self.update_progress(100, "Analyze All KPIs completed.")
            self.root.after(0, lambda: messagebox.showinfo("Done", f"Completed. Total degraded: {total_degraded}"))
            
        except Exception as e:
            self.log(f"ERROR: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.set_running_state(False)
    
    # ============================================================
    # Visualization Methods
    # ============================================================
    
    def show_dashboard(self):
        """Show the degradation dashboard window."""
        if self.output_df is None and self.summary_df is None:
            messagebox.showwarning("No output", "Please run analysis first.")
            return
        show_dashboard(self.root, self.output_df, self.summary_df, self.analysis_mode, self.selected_kpi.get())
    
    def show_trend(self):
        """Show the trend analysis dashboard window."""
        if self.original_df is None:
            messagebox.showwarning("No Data", "Please load an Excel file first.")
            return
        if self.output_df is None or self.output_df.empty:
            messagebox.showwarning("No Results", "No degraded cells found. Run analysis first.")
            return
        show_trend_dashboard(
            self.root,
            self.original_df,
            self.output_df,
            self.degraded_cell_ids,
            self.selected_kpi.get(),
            self.baseline_mode.get(),
            self.log,
        )
    
    # ============================================================
    # Export Methods
    # ============================================================
    
    def generate_report(self):
        """Generate a Word report with analysis results."""
        if not DOCX_AVAILABLE:
            messagebox.showerror("Missing Package", "Install python-docx: pip install python-docx")
            return
        
        if self.output_df is None or (self.output_df.empty and (self.summary_df is None or self.summary_df.empty)):
            messagebox.showwarning("No Results", "Run analysis first.")
            return
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_name = f"RF_Optimization_Report_{timestamp}.docx"
        
        save_path = get_save_path(default_name, "Word documents", ".docx")
        
        if not save_path:
            return
        
        # Pass degraded_cell_ids to the report generator
        success = generate_word_report(
            self.output_df,
            self.summary_df,
            self.analysis_mode,
            self.selected_kpi.get(),
            self.baseline_mode.get(),
            self.enable_significance_test.get(),
            save_path,
            self.original_df,
            self.degraded_cell_ids,  # NEW: Pass degraded cell IDs
            self.log,
        )
        
        if success:
            messagebox.showinfo("Report Saved", f"Report saved:\n{save_path}")
    
    def save_csv(self):
        """Save analysis results to CSV files."""
        if self.output_df is None and self.summary_df is None:
            messagebox.showwarning("No output", "Run analysis first.")
            return
        
        if self.analysis_mode == "all":
            save_dir = get_save_directory("Select folder to save CSV files")
            if not save_dir:
                return
            
            # REMOVED: self.all_outputs (no longer needed by save_csv_results)
            success = save_csv_results(
                self.output_df, self.summary_df,
                self.analysis_mode, self.selected_kpi.get(), save_dir, self.log,
                quarantine_df=self.quarantine_df, incomplete_df=self.incomplete_df,
                anomalies_df=self.anomalies_df, clean_cells_df=self.clean_cells_df,
            )
            if success:
                messagebox.showinfo("Saved", f"CSV files saved to:\n{save_dir}")
        else:
            prefix = KPI_CONFIGS[self.selected_kpi.get()]["output_prefix"]
            default_name = f"{prefix}_degraded.csv"
            save_path = get_save_path(default_name, "CSV files", ".csv")
            
            if save_path:
                # REMOVED: self.all_outputs
                success = save_csv_results(
                    self.output_df, self.summary_df,
                    self.analysis_mode, self.selected_kpi.get(), save_path, self.log,
                    quarantine_df=self.quarantine_df, incomplete_df=self.incomplete_df,
                    anomalies_df=self.anomalies_df, clean_cells_df=self.clean_cells_df,
                )
                if success:
                    messagebox.showinfo("Saved", f"CSV saved:\n{save_path}")
    
    def export_excel(self):
        """Export analysis results to Excel workbook."""
        if self.output_df is None and self.summary_df is None:
            messagebox.showwarning("No output", "Run analysis first.")
            return
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if self.analysis_mode == "all":
            default_name = f"LTE_KPI_Analysis_{timestamp}.xlsx"
        else:
            prefix = KPI_CONFIGS[self.selected_kpi.get()]["output_prefix"]
            default_name = f"{prefix}_analysis_{timestamp}.xlsx"
        
        save_path = get_save_path(default_name, "Excel files", ".xlsx")
        
        if not save_path:
            return
        
        success = save_excel_results(
            self.output_df, self.summary_df, self.analysis_mode,
            self.selected_kpi.get(), save_path, self.log,
            anomalies_df=self.anomalies_df,
            quarantine_df=self.quarantine_df,
            incomplete_df=self.incomplete_df,
            clean_cells_df=self.clean_cells_df,
        )
        
        if success:
            messagebox.showinfo("Exported", f"Excel report exported:\n{save_path}")
