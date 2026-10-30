from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class SalesMetric(str, Enum):
    REVENUE = "revenue"
    ESTIMATED_GROSS_PROFIT = "estimated_gross_profit"

    @property
    def label(self) -> str:
        return {
            SalesMetric.REVENUE: "Revenue",
            SalesMetric.ESTIMATED_GROSS_PROFIT: "Estimated gross profit",
        }[self]


class AnalysisMode(str, Enum):
    HISTORICAL = "Historical"
    PREDICTIVE = "Predictive"


class ComparisonDimension(str, Enum):
    OVERALL = "Overall"
    CATEGORIES = "Categories"
    STORES = "Stores"


class TimeInterval(str, Enum):
    MONTHLY = "Monthly"
    WEEKLY = "Weekly"

    @property
    def period_frequency(self) -> str:
        return {
            TimeInterval.WEEKLY: "W-SAT",
            TimeInterval.MONTHLY: "M",
        }[self]


@dataclass(frozen=True)
class FilterCriteria:
    """One consistent set of analyst selections for all dashboard views."""

    metric: SalesMetric = SalesMetric.REVENUE
    mode: AnalysisMode = AnalysisMode.HISTORICAL
    comparison: ComparisonDimension = ComparisonDimension.OVERALL
    categories: tuple[str, ...] = ()
    subcategories: tuple[str, ...] = ()
    stores: tuple[str, ...] = ()
    start_date: date | None = None
    end_date: date | None = None

    def __post_init__(self) -> None:
        if self.categories and self.stores:
            raise ValueError("Select multiple categories or multiple stores, not both.")
        if self.subcategories and len(self.categories) != 1:
            raise ValueError("Subcategory filters require exactly one selected category.")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("Start date must be on or before end date.")


@dataclass(frozen=True)
class KPIValues:
    total_revenue: float
    total_estimated_gross_profit: float
    latest_month_value: float
    prior_month_value: float | None
    leading_category: str | None
    leading_store: str | None
    missing_unit_cost_lines: int
    latest_date: date | None

