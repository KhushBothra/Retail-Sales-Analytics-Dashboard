from __future__ import annotations

import unittest

import pandas as pd

from retail_analytics.domain.models import TimeInterval
from retail_analytics.services.forecasting_service import (
    ForecastingNotConfiguredError,
    ForecastingService,
    HoltDampedTrendForecastStrategy,
)


class ForecastingTests(unittest.TestCase):
    def test_unconfigured_service_explains_forecast_is_unavailable(self) -> None:
        service = ForecastingService()
        self.assertFalse(service.is_configured)
        with self.assertRaises(ForecastingNotConfiguredError):
            service.forecast(pd.DataFrame(), "revenue", TimeInterval.MONTHLY)

    def test_monthly_strategy_returns_two_future_periods(self) -> None:
        history = pd.DataFrame(
            {
                "period": pd.date_range("2025-01-01", periods=8, freq="MS"),
                "series": ["Overall"] * 8,
                "revenue": [100, 112, 108, 125, 131, 128, 142, 150],
            }
        )
        forecast = HoltDampedTrendForecastStrategy().forecast(
            history, "revenue", TimeInterval.MONTHLY
        )
        self.assertEqual(list(forecast.columns), ["period", "series", "value"])
        self.assertEqual(len(forecast), 2)
        self.assertEqual(forecast["period"].tolist(), [pd.Timestamp("2025-09-01"), pd.Timestamp("2025-10-01")])
        self.assertTrue((forecast["value"] >= 0).all())
        self.assertNotEqual(forecast["value"].iloc[0], history["revenue"].iloc[-1])

    def test_empty_history_returns_empty_result_with_expected_columns(self) -> None:
        forecast = HoltDampedTrendForecastStrategy().forecast(
            pd.DataFrame(columns=["period", "series", "revenue"]),
            "revenue",
            TimeInterval.MONTHLY,
        )
        self.assertTrue(forecast.empty)
        self.assertEqual(list(forecast.columns), ["period", "series", "value"])


if __name__ == "__main__":
    unittest.main()
