"""Shared dataclasses for the LTE forecaster pipeline.

All core functions return these types instead of bare dicts or tuples.
This makes the boundary between computation and UI rendering explicit.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
import pandas as pd
import numpy as np


class AlertTier(Enum):
    """Classification of why an alert fired."""
    THRESHOLD = "threshold"      # Hard limit breached
    TREND = "trend"              # Sustained degradation direction
    FORECAST = "forecast"        # Predicted to breach within horizon
    VOLATILITY = "volatility"    # Unstable / high coefficient of variation
    BASELINE = "baseline"        # Model underperforms naive baseline


class AlertStatus(Enum):
    """Severity classification."""
    NORMAL = "Normal"
    INFO = "Info"
    WARNING = "Warning"
    CRITICAL = "Critical"


@dataclass(frozen=True)
class Alert:
    """A single alert for one KPI."""
    kpi_internal: str           # e.g. "DL_Throughput"
    kpi_display: str            # e.g. "DL Average Throughput (Mbps)"
    tier: AlertTier
    status: AlertStatus
    message: str
    value: Optional[float] = None
    threshold: Optional[float] = None


@dataclass
class ValidationScore:
    """Back-test accuracy metrics."""
    mae: float
    rmse: float
    mape: float

    def __repr__(self) -> str:
        return f"ValidationScore(mae={self.mae:.3f}, rmse={self.rmse:.3f}, mape={self.mape:.1f}%)"


@dataclass
class ForecastResult:
    """Output of any forecaster — XGBoost, Holt-Winters, or baseline."""
    model_name: str
    forecast: pd.Series        # hold-out predictions (indexed by date)
    scores: ValidationScore
    future_forecast: Optional[pd.Series] = None   # next-7-day recursive forecast
    feature_importance: Optional[pd.DataFrame] = None   # XGBoost only
    train_predictions: Optional[np.ndarray] = None      # for residual diagnostics
    train_residuals: Optional[np.ndarray] = None
    y_train: Optional[pd.Series] = None
    model_obj: Optional[Any] = None   # raw fitted model (XGBoost regressor, etc.)

    def to_report_dict(self, dates: Optional[pd.DatetimeIndex] = None) -> Dict[str, Any]:
        """Convert to the flat dict that report.py expects."""
        return {
            "forecast": self.future_forecast.round(3).tolist() if self.future_forecast is not None else None,
            "dates": dates.strftime("%Y-%m-%d").tolist() if dates is not None else None,
            "mae": round(self.scores.mae, 3),
            "mape": round(self.scores.mape, 1),
        }


@dataclass
class SeasonalityResult:
    """STL-based seasonality diagnostics for one cell/KPI."""
    strength: Optional[float]   # 0.0–1.0, or None if insufficient data
    period: int = 7

    @property
    def category(self) -> str:
        if self.strength is None:
            return "unknown"
        if self.strength < 0.3:
            return "weak"
        if self.strength < 0.6:
            return "moderate"
        return "strong"


@dataclass
class ReportContext:
    """Everything the report generator needs in one bag."""
    cell_name: str
    kpi_map: Dict[str, str]              # internal -> display
    forecasts: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    alerts: List[Alert] = field(default_factory=list)
    seasonality: Optional[SeasonalityResult] = None
    baseline_comparison: Optional[Dict[str, Any]] = None
