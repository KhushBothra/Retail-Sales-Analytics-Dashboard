from __future__ import annotations

import os
import unittest
from datetime import date
from unittest.mock import patch

from retail_analytics.config import DatabaseSettings
from retail_analytics.dashboard.formatting import display_store_name
from retail_analytics.domain.models import (
    ComparisonDimension,
    FilterCriteria,
    SalesMetric,
    TimeInterval,
)


class FilterCriteriaTests(unittest.TestCase):
    def test_rejects_category_and_store_filters_together(self) -> None:
        with self.assertRaisesRegex(ValueError, "categories or multiple stores"):
            FilterCriteria(categories=("Produce",), stores=("Chelsea",))

    def test_subcategories_require_exactly_one_category(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly one selected category"):
            FilterCriteria(subcategories=("Apples",))

    def test_rejects_start_date_after_end_date(self) -> None:
        with self.assertRaisesRegex(ValueError, "on or before"):
            FilterCriteria(start_date=date(2025, 2, 1), end_date=date(2025, 1, 1))

    def test_accepts_one_category_with_subcategory(self) -> None:
        criteria = FilterCriteria(
            metric=SalesMetric.ESTIMATED_GROSS_PROFIT,
            comparison=ComparisonDimension.CATEGORIES,
            categories=("Produce",),
            subcategories=("Apples",),
        )
        self.assertEqual(criteria.metric, SalesMetric.ESTIMATED_GROSS_PROFIT)


class ConfigurationAndFormattingTests(unittest.TestCase):
    def test_database_settings_use_documented_defaults(self) -> None:
        with patch.dict(os.environ, {"MYSQL_PASSWORD": "secret"}, clear=True):
            settings = DatabaseSettings.from_environment()
        self.assertEqual(settings.host, "localhost")
        self.assertEqual(settings.port, 3306)
        self.assertEqual(settings.database, "mancino_analytics")
        self.assertEqual(settings.user, "analytics_reader")
        self.assertEqual(settings.password, "secret")

    def test_database_settings_require_password(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "MYSQL_PASSWORD"):
                DatabaseSettings.from_environment()

    def test_store_display_name_removes_market_prefix_case_insensitively(self) -> None:
        self.assertEqual(display_store_name("Mancino Market - Chelsea"), "Chelsea")
        self.assertEqual(display_store_name("mancino market – NoHo"), "NoHo")
        self.assertEqual(display_store_name("Independent Shop"), "Independent Shop")

    def test_weekly_interval_starts_sunday_and_monthly_is_supported(self) -> None:
        self.assertEqual(TimeInterval.WEEKLY.period_frequency, "W-SAT")
        self.assertEqual(TimeInterval.MONTHLY.period_frequency, "M")


if __name__ == "__main__":
    unittest.main()
