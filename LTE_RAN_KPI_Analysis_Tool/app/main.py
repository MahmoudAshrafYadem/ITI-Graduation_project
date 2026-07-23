#!/usr/bin/env python3
# ============================================================
# LTE KPI Degradation Analyzer - Main Entry Point
# ============================================================
# Run this script to start the application.
# 
# Usage: python main.py
# ============================================================

import sys
import os

# Ensure the script directory is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from initialization import LTEKPIAnalyzerApp


def main():
    """Main entry point for the LTE KPI Degradation Analyzer."""
    root = tk.Tk()
    app = LTEKPIAnalyzerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
