from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from retail_analytics.domain.models import FilterCriteria, TimeInterval
from retail_analytics.services.forecasting_service import (
    ForecastingNotConfiguredError,
    ForecastingService,
)
from retail_analytics.services.sales_analysis_service import SalesAnalysis, SalesAnalysisService


@dataclass(frozen=True)
class DashboardSnapshot:
    analysis: SalesAnalysis
    forecast: pd.DataFrame | None
    forecast_message: str | None


class DashboardController:
    """Coordinates one dashboard refresh using a single filter state."""

    def __init__(
        self,
        sales_analysis: SalesAnalysisService,
        forecasting: ForecastingService,
    ) -> None:
        self._sales_analysis = sales_analysis
        self._forecasting = forecasting

    def refresh(self, criteria: FilterCriteria, interval: TimeInterval) -> DashboardSnapshot:
        analysis = self._sales_analysis.analyze(criteria, interval)
        if criteria.mode.value != "Predictive":
            return DashboardSnapshot(analysis, None, None)
        try:
            forecast = self._forecasting.forecast(
                analysis.trend,
                analysis.value_column,
                interval,
            )
            return DashboardSnapshot(analysis, forecast, None)
        except ForecastingNotConfiguredError as exc:
            return DashboardSnapshot(analysis, None, str(exc))
