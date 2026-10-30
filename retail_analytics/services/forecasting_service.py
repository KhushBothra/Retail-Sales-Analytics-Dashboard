from __future__ import annotations

from typing import Protocol

import numpy as np
import pandas as pd

from retail_analytics.domain.models import TimeInterval


class ForecastingStrategy(Protocol):
    """Interface implemented by a forecasting algorithm."""

    def forecast(
        self,
        history: pd.DataFrame,
        value_column: str,
        interval: TimeInterval,
    ) -> pd.DataFrame:
        """Return forecast rows with ``period``, ``series``, and ``value`` columns."""
        ...


class ForecastingNotConfiguredError(RuntimeError):
    pass


class ForecastingService:
    """Coordinates forecasts while keeping the chosen model replaceable."""

    def __init__(self, strategy: ForecastingStrategy | None = None) -> None:
        self._strategy = strategy

    @property
    def is_configured(self) -> bool:
        return self._strategy is not None

    def forecast(
        self,
        history: pd.DataFrame,
        value_column: str,
        interval: TimeInterval,
    ) -> pd.DataFrame:
        if self._strategy is None:
            raise ForecastingNotConfiguredError(
                "No forecasting model has been selected and evaluated yet."
            )
        return self._strategy.forecast(history, value_column, interval)


class HoltDampedTrendForecastStrategy:
    """Holt damped-trend forecast with parameters selected by rolling validation."""

    _ALPHAS = (0.2, 0.4, 0.6, 0.8)
    _BETAS = (0.1, 0.3, 0.5)
    _PHIS = (0.8, 0.9, 0.98)

    @classmethod
    def _holt_fit(cls, values: np.ndarray) -> tuple[float, float, float]:
        """Return final level, trend, and damping factor for a univariate series."""
        if len(values) == 1:
            return float(values[0]), 0.0, 0.9
        if len(values) < 4:
            slope = float(np.polyfit(np.arange(len(values)), values, 1)[0])
            return float(values[-1]), slope, 0.9

        best: tuple[float, float, float, float] | None = None
        validation_start = max(3, len(values) // 2)
        for alpha in cls._ALPHAS:
            for beta in cls._BETAS:
                for phi in cls._PHIS:
                    level = float(values[0])
                    trend = float(values[1] - values[0])
                    errors: list[float] = []
                    for index in range(1, len(values)):
                        prediction = level + phi * trend
                        if index >= validation_start:
                            errors.append((float(values[index]) - prediction) ** 2)
                        previous_level = level
                        level = alpha * float(values[index]) + (1 - alpha) * prediction
                        trend = beta * (level - previous_level) + (1 - beta) * phi * trend
                    score = float(np.mean(errors)) if errors else float("inf")
                    candidate = (score, alpha, beta, phi)
                    if best is None or candidate < best:
                        best = candidate

        assert best is not None
        _, alpha, beta, phi = best
        level = float(values[0])
        trend = float(values[1] - values[0])
        for observed in values[1:]:
            previous_level = level
            prediction = level + phi * trend
            level = alpha * float(observed) + (1 - alpha) * prediction
            trend = beta * (level - previous_level) + (1 - beta) * phi * trend
        return level, trend, phi

    def forecast(
        self,
        history: pd.DataFrame,
        value_column: str,
        interval: TimeInterval,
    ) -> pd.DataFrame:
        columns = ["period", "series", "value"]
        if history.empty:
            return pd.DataFrame(columns=columns)

        last_period = pd.Timestamp(history["period"].max())
        if interval == TimeInterval.MONTHLY:
            future_periods = pd.date_range(
                last_period + pd.offsets.MonthBegin(1), periods=2, freq="MS"
            )
        else:
            horizon_end = last_period + pd.DateOffset(months=2)
            future_periods = pd.date_range(
                last_period + pd.Timedelta(days=7), horizon_end, freq="7D"
            )

        rows: list[dict[str, object]] = []
        for series_name, group in history.groupby("series", sort=False):
            ordered = group.sort_values("period")
            values = (
                pd.to_numeric(ordered[value_column], errors="coerce")
                .dropna()
                .to_numpy(dtype=float)
            )
            if not len(values):
                continue
            level, trend, phi = self._holt_fit(values)
            for step_index, period in enumerate(future_periods, start=1):
                prediction = level + trend * sum(
                    phi**step for step in range(1, step_index + 1)
                )
                if value_column == "revenue":
                    prediction = max(0.0, prediction)
                rows.append(
                    {
                        "period": period,
                        "series": series_name,
                        "value": prediction,
                    }
                )
        return pd.DataFrame(rows, columns=columns)
