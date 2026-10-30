from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from retail_analytics.domain.models import (
    ComparisonDimension,
    FilterCriteria,
    KPIValues,
    TimeInterval,
)
from retail_analytics.repositories.sales_repository import SalesRepository


@dataclass(frozen=True)
class SalesAnalysis:
    trend: pd.DataFrame
    by_category: pd.DataFrame
    by_subcategory: pd.DataFrame
    by_store: pd.DataFrame
    by_payment_type: pd.DataFrame
    kpis: KPIValues
    value_column: str


class SalesAnalysisService:
    """Applies shared filters and produces all dashboard aggregations."""

    def __init__(self, repository: SalesRepository) -> None:
        self._repository = repository

    def analyze(self, criteria: FilterCriteria, interval: TimeInterval) -> SalesAnalysis:
        facts = self._repository.fetch_sales_facts()
        if facts.empty:
            return self._empty_analysis(criteria.metric.value)

        facts = facts.copy()
        facts["sale_date"] = pd.to_datetime(facts["sale_date"])
        available_start = facts["sale_date"].min().normalize()
        available_end = facts["sale_date"].max().normalize()
        complete_start, complete_end = self._complete_period_bounds(
            available_start, available_end, interval
        )
        if complete_start is None or complete_end is None or complete_start > complete_end:
            return self._empty_analysis(criteria.metric.value)
        facts = facts[
            (facts["sale_date"] >= complete_start)
            & (facts["sale_date"] <= complete_end)
        ]
        filtered = facts
        if criteria.start_date is not None:
            filtered = filtered[filtered["sale_date"].dt.date >= criteria.start_date]
        if criteria.end_date is not None:
            filtered = filtered[filtered["sale_date"].dt.date <= criteria.end_date]
        if criteria.categories:
            filtered = filtered[filtered["category"].isin(criteria.categories)]
        if criteria.subcategories:
            filtered = filtered[filtered["subcategory"].isin(criteria.subcategories)]
        if criteria.stores:
            filtered = filtered[filtered["store"].isin(criteria.stores)]
        if filtered.empty:
            return self._empty_analysis(criteria.metric.value)

        value_column = criteria.metric.value
        filtered = filtered.copy()
        filtered["period"] = (
            filtered["sale_date"].dt.to_period(interval.period_frequency).dt.start_time
        )
        trend = self._make_trend(filtered, criteria, value_column)
        by_category = self._sum_by(filtered, "category", value_column)
        by_subcategory = self._sum_by(filtered, "subcategory", value_column)
        by_store = self._sum_by(filtered, "store", value_column)
        by_payment = self._sum_by(filtered, "payment_type", value_column)
        latest_full_month_end = self._latest_complete_month_end(available_end)
        kpis = self._make_kpis(filtered, value_column, latest_full_month_end)
        return SalesAnalysis(
            trend=trend,
            by_category=by_category,
            by_subcategory=by_subcategory,
            by_store=by_store,
            by_payment_type=by_payment,
            kpis=kpis,
            value_column=value_column,
        )

    @staticmethod
    def _sum_by(frame: pd.DataFrame, dimension: str, value: str) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=[dimension, value])
        return (
            frame.groupby(dimension, as_index=False, dropna=False)[value]
            .sum(min_count=1)
            .sort_values(value, ascending=False)
        )

    @staticmethod
    def _make_trend(
        frame: pd.DataFrame, criteria: FilterCriteria, value: str
    ) -> pd.DataFrame:
        if criteria.comparison == ComparisonDimension.CATEGORIES and criteria.categories:
            result = frame.groupby(["period", "category"], as_index=False)[value].sum()
            return result.rename(columns={"category": "series"})
        if criteria.comparison == ComparisonDimension.STORES and criteria.stores:
            result = frame.groupby(["period", "store"], as_index=False)[value].sum()
            return result.rename(columns={"store": "series"})
        result = frame.groupby("period", as_index=False)[value].sum()
        result["series"] = "Overall"
        return result

    @staticmethod
    def _complete_period_bounds(
        first_date: pd.Timestamp,
        last_date: pd.Timestamp,
        interval: TimeInterval,
    ) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
        """Keep only periods fully covered by the available source date range."""
        frequency = interval.period_frequency
        first_period = first_date.to_period(frequency)
        last_period = last_date.to_period(frequency)
        first_boundary = first_period.start_time.normalize()
        last_boundary = last_period.end_time.normalize()

        start = first_boundary if first_date.date() == first_boundary.date() else (first_period + 1).start_time.normalize()
        end = last_boundary if last_date.date() == last_boundary.date() else (last_period - 1).end_time.normalize()
        return start, end

    @staticmethod
    def _latest_complete_month_end(last_date: pd.Timestamp) -> pd.Timestamp:
        month = last_date.to_period("M")
        if last_date.date() != month.end_time.date():
            month -= 1
        return month.end_time.normalize()

    @staticmethod
    def _make_kpis(
        frame: pd.DataFrame, metric: str, latest_full_month_end: pd.Timestamp
    ) -> KPIValues:
        if frame.empty:
            return KPIValues(0, 0, 0, None, None, None, 0, None)

        complete_months = frame[frame["sale_date"] <= latest_full_month_end].copy()
        monthly = complete_months.assign(month=complete_months["sale_date"].dt.to_period("M"))
        if monthly.empty:
            latest_value = 0.0
            previous_value = None
        else:
            latest_month = monthly["month"].max()
            latest_value_raw = monthly.loc[monthly["month"] == latest_month, metric].sum(min_count=1)
            latest_value = 0.0 if pd.isna(latest_value_raw) else float(latest_value_raw)
            prior_month = latest_month - 1
            previous_value_raw = monthly.loc[monthly["month"] == prior_month, metric].sum(min_count=1)
            previous_value = None if pd.isna(previous_value_raw) else float(previous_value_raw)
        category_totals = frame.groupby("category")[metric].sum(min_count=1).dropna()
        store_totals = frame.groupby("store")[metric].sum(min_count=1).dropna()
        revenue_total = frame["revenue"].sum(min_count=1)
        profit_total = frame["estimated_gross_profit"].sum(min_count=1)
        return KPIValues(
            total_revenue=0.0 if pd.isna(revenue_total) else float(revenue_total),
            total_estimated_gross_profit=0.0 if pd.isna(profit_total) else float(profit_total),
            latest_month_value=latest_value,
            prior_month_value=previous_value,
            leading_category=None if category_totals.empty else str(category_totals.idxmax()),
            leading_store=None if store_totals.empty else str(store_totals.idxmax()),
            missing_unit_cost_lines=int(frame["missing_unit_cost_lines"].sum()),
            latest_date=frame["sale_date"].max().date(),
        )

    @staticmethod
    def _empty_analysis(value_column: str) -> SalesAnalysis:
        return SalesAnalysis(
            trend=pd.DataFrame(columns=["period", "series", value_column]),
            by_category=pd.DataFrame(columns=["category", value_column]),
            by_subcategory=pd.DataFrame(columns=["subcategory", value_column]),
            by_store=pd.DataFrame(columns=["store", value_column]),
            by_payment_type=pd.DataFrame(columns=["payment_type", value_column]),
            kpis=KPIValues(0, 0, 0, None, None, None, 0, None),
            value_column=value_column,
        )
