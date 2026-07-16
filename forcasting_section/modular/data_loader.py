"""CSV loading, column renaming, and numeric coercion."""
import pandas as pd
import streamlit as st

from config import COLUMN_RENAME_MAP, NUMERIC_COERCE_COLS


@st.cache_data
def load_data(file):
    """Load the uploaded CSV, parse dates, rename KPI columns to short internal
    names, and coerce percentage/rate columns to numeric."""
    df = pd.read_csv(file)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.rename(columns=COLUMN_RENAME_MAP)

    for col in NUMERIC_COERCE_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace("%", "", regex=False).str.strip(),
                errors="coerce",
            )

    return df
