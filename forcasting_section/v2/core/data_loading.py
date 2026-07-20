"""Pure data loading and cell filtering.

No Streamlit imports. Caching (if desired) is the UI layer's responsibility.
"""
from typing import Union, BinaryIO
import pandas as pd

from config import COLUMN_RENAME_MAP, NUMERIC_COERCE_COLS


def load_data(source: Union[str, BinaryIO]) -> pd.DataFrame:
    """Load the uploaded CSV, parse dates, rename KPI columns to short internal
    names, and coerce percentage/rate columns to numeric.

    Parameters
    ----------
    source : str or file-like
        File path or uploaded file buffer.

    Returns
    -------
    pd.DataFrame
        Cleaned dataframe with Date as datetime and renamed columns.
    """
    df = pd.read_csv(source)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.rename(columns=COLUMN_RENAME_MAP)

    for col in NUMERIC_COERCE_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace("%", "", regex=False).str.strip(),
                errors="coerce",
            )

    return df


def filter_cell(df: pd.DataFrame, cell_name: str, date_col: str = "Date", cell_col: str = "Cell Name") -> pd.DataFrame:
    """Return a single cell's time series, sorted by date, set-indexed.

    Parameters
    ----------
    df : pd.DataFrame
        Full dataset (multi-cell).
    cell_name : str
        Cell identifier.
    date_col : str
        Name of the date column.
    cell_col : str
        Name of the cell identifier column.

    Returns
    -------
    pd.DataFrame
        Single-cell dataframe, sorted, with Date as index.
    """
    cell_df = df[df[cell_col] == cell_name].copy()
    cell_df[date_col] = pd.to_datetime(cell_df[date_col])
    return cell_df.sort_values(date_col).set_index(date_col)


def validate_cell_data(cell_df: pd.DataFrame, target_col: str, test_days: int, min_rows: int = 15) -> dict:
    """Validate that a cell has enough data for forecasting.

    Returns
    -------
    dict
        {"ok": bool, "message": str, "severity": "error"|"warning"|"info"}
    """
    n = len(cell_df)
    if target_col not in cell_df.columns:
        return {"ok": False, "message": f"Column '{target_col}' not found in data. Pick another KPI.", "severity": "error"}
    if n <= test_days:
        return {"ok": False, "message": f"Not enough data ({n} rows) for {test_days} test days. Reduce hold-out.", "severity": "error"}
    if n < min_rows:
        return {"ok": True, "message": f"Only {n} rows for this cell — results may be unreliable.", "severity": "warning"}
    return {"ok": True, "message": "", "severity": "info"}
