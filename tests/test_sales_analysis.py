from __future__ import annotations

import unittest

import pandas as pd

from retail_analytics.domain.models import (
    ComparisonDimension,
    FilterCriteria,
    SalesMetric,
    TimeInterval,
)
from retail_analytics.services.sales_analysis_service import SalesAnalysisService


class InMemorySalesRepository:
    def __init__(self, facts: pd.DataFrame) -> None:
        self.facts = facts

    def fetch_sales_facts(self) -> pd.DataFrame:
        return self.facts.copy()


def monthly_facts() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ("2025-01-01", "Chelsea", "Produce", "Fruit", "CASH", 100, 40, 0),
            ("2025-01-20", "Midtown", "Snacks", "Chips", "CREDIT", 50, 20, 1),
            ("2025-02-01", "Midtown", "Snacks", "Chips", "CREDIT", 80, 30, 0),
            ("2025-02-28", "Chelsea", "Produce", "Fruit", "CASH", 200, 80, 0),
            # March is partial and must not enter monthly results.
            ("2025-03-01", "Chelsea", "Produce", "Fruit", "CASH", 1000, 500, 0),
        ],
        columns=[
            "sale_date", "store", "category", "subcategory", "payment_type",
            "revenue", "estimated_gross_profit", "missing_unit_cost_lines",
        ],
    )


class SalesAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = SalesAnalysisService(InMemorySalesRepository(monthly_facts()))

    def test_monthly_analysis_excludes_partial_month_and_calculates_kpis(self) -> None:
        result = self.service.analyze(FilterCriteria(), TimeInterval.MONTHLY)
        self.assertEqual(result.trend["revenue"].sum(), 430)
        self.assertEqual(result.kpis.total_revenue, 430)
        self.assertEqual(result.kpis.total_estimated_gross_profit, 170)
        self.assertEqual(result.kpis.latest_month_value, 280)
        self.assertEqual(result.kpis.prior_month_value, 150)
        self.assertEqual(result.kpis.leading_category, "Produce")
        self.assertEqual(result.kpis.leading_store, "Chelsea")
        self.assertEqual(result.kpis.latest_date.isoformat(), "2025-02-28")

    def test_store_filter_is_shared_by_trend_and_distributions(self) -> None:
        criteria = FilterCriteria(
            comparison=ComparisonDimension.STORES,
            stores=("Midtown",),
        )
        result = self.service.analyze(criteria, TimeInterval.MONTHLY)
        self.assertEqual(result.trend["revenue"].sum(), 130)
        self.assertEqual(result.by_store["store"].tolist(), ["Midtown"])
        self.assertEqual(result.by_category["category"].tolist(), ["Snacks"])
        self.assertEqual(result.by_payment_type["payment_type"].tolist(), ["CREDIT"])

    def test_category_comparison_creates_one_series_per_category(self) -> None:
        criteria = FilterCriteria(comparison=ComparisonDimension.CATEGORIES)
        result = self.service.analyze(criteria, TimeInterval.MONTHLY)
        self.assertEqual(set(result.trend["series"]), {"Produce", "Snacks"})

    def test_gross_profit_metric_selects_profit_aggregations(self) -> None:
        criteria = FilterCriteria(metric=SalesMetric.ESTIMATED_GROSS_PROFIT)
        result = self.service.analyze(criteria, TimeInterval.MONTHLY)
        self.assertEqual(result.value_column, "estimated_gross_profit")
        self.assertEqual(result.trend["estimated_gross_profit"].sum(), 170)

    def test_weekly_analysis_omits_partial_edge_weeks(self) -> None:
        facts = pd.DataFrame(
            [
                ("2025-01-05", "Chelsea", "Produce", "Fruit", "CASH", 10, 4, 0),
                ("2025-01-11", "Chelsea", "Produce", "Fruit", "CASH", 20, 8, 0),
                ("2025-01-12", "Chelsea", "Produce", "Fruit", "CASH", 999, 400, 0),
                ("2025-01-15", "Chelsea", "Produce", "Fruit", "CASH", 999, 400, 0),
            ],
            columns=monthly_facts().columns,
        )
        result = SalesAnalysisService(InMemorySalesRepository(facts)).analyze(
            FilterCriteria(), TimeInterval.WEEKLY
        )
        self.assertEqual(result.trend["revenue"].sum(), 30)
        self.assertEqual(len(result.trend), 1)

    def test_empty_repository_returns_empty_aggregations(self) -> None:
        empty = InMemorySalesRepository(monthly_facts().iloc[0:0])
        result = SalesAnalysisService(empty).analyze(FilterCriteria(), TimeInterval.MONTHLY)
        self.assertTrue(result.trend.empty)
        self.assertEqual(result.kpis.total_revenue, 0)


if __name__ == "__main__":
    unittest.main()
