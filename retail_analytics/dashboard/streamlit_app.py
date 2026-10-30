from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st
from mysql.connector import Error as MySQLError

from retail_analytics.config import DatabaseSettings
from retail_analytics.dashboard.charts import make_donut_chart, make_trend_chart
from retail_analytics.dashboard.formatting import display_store_name
from retail_analytics.domain.models import (
    AnalysisMode,
    ComparisonDimension,
    FilterCriteria,
    SalesMetric,
    TimeInterval,
)
from retail_analytics.repositories.mysql_sales_repository import MySQLSalesRepository
from retail_analytics.services.dashboard_controller import DashboardController
from retail_analytics.services.forecasting_service import (
    ForecastingService,
    HoltDampedTrendForecastStrategy,
)
from retail_analytics.services.sales_analysis_service import SalesAnalysisService


def _reset_all() -> None:
    st.session_state.update(
        metric=SalesMetric.REVENUE.label,
        analysis_mode=AnalysisMode.HISTORICAL.value,
        comparison=ComparisonDimension.OVERALL.value,
        category_selection=[],
        subcategory_selection=[],
        store_selection=[],
        interval=TimeInterval.MONTHLY.value,
        category_chart_revision=st.session_state.get("category_chart_revision", 0) + 1,
        store_chart_revision=st.session_state.get("store_chart_revision", 0) + 1,
    )


def _reset_categories() -> None:
    st.session_state["category_selection"] = []
    st.session_state["subcategory_selection"] = []
    st.session_state["category_chart_revision"] = st.session_state.get("category_chart_revision", 0) + 1


def _reset_stores() -> None:
    st.session_state["store_selection"] = []
    st.session_state["store_chart_revision"] = st.session_state.get("store_chart_revision", 0) + 1


def _comparison_changed() -> None:
    comparison = st.session_state.get("comparison", ComparisonDimension.OVERALL.value)
    if comparison != ComparisonDimension.CATEGORIES.value:
        st.session_state["category_selection"] = []
        st.session_state["subcategory_selection"] = []
    if comparison != ComparisonDimension.STORES.value:
        st.session_state["store_selection"] = []
    st.session_state["category_chart_revision"] = st.session_state.get("category_chart_revision", 0) + 1
    st.session_state["store_chart_revision"] = st.session_state.get("store_chart_revision", 0) + 1


def _category_changed() -> None:
    st.session_state["subcategory_selection"] = []
    st.session_state["category_chart_revision"] = st.session_state.get("category_chart_revision", 0) + 1


def _selection_labels(chart_key: str) -> list[str]:
    state = st.session_state.get(chart_key)
    selection = state.get("selection", {}) if state is not None else {}
    labels: list[str] = []
    for point in selection.get("points", []):
        custom = point.get("customdata")
        if isinstance(custom, (list, tuple)) and custom:
            label = custom[0]
        elif isinstance(custom, str):
            label = custom
        else:
            label = point.get("label")
        if label is not None and str(label) not in labels:
            labels.append(str(label))
    return labels


def _category_chart_selected() -> None:
    chart_key = st.session_state.get("active_category_chart_key", "")
    labels = _selection_labels(chart_key)
    if not labels:
        return
    was_subcategory_view = st.session_state.get("active_category_chart_is_subcategory", False)
    if was_subcategory_view:
        st.session_state["subcategory_selection"] = labels
    else:
        st.session_state["comparison"] = ComparisonDimension.CATEGORIES.value
        st.session_state["category_selection"] = labels
        st.session_state["subcategory_selection"] = []
        st.session_state["store_selection"] = []
    is_subcategory_view = was_subcategory_view or len(labels) == 1
    if was_subcategory_view != is_subcategory_view:
        st.session_state["category_chart_revision"] = st.session_state.get("category_chart_revision", 0) + 1


def _store_chart_selected() -> None:
    chart_key = st.session_state.get("active_store_chart_key", "")
    labels = _selection_labels(chart_key)
    if not labels:
        return
    st.session_state["comparison"] = ComparisonDimension.STORES.value
    st.session_state["store_selection"] = labels
    st.session_state["category_selection"] = []
    st.session_state["subcategory_selection"] = []


@st.cache_data(ttl=300, show_spinner="Reading sales data from MySQL…")
def _load_facts(settings: DatabaseSettings) -> pd.DataFrame:
    return MySQLSalesRepository(settings).fetch_sales_facts()


def _build_controller(settings: DatabaseSettings) -> DashboardController:
    repository = _CachedRepository(_load_facts, settings)
    analysis_service = SalesAnalysisService(repository)
    return DashboardController(
        analysis_service,
        ForecastingService(HoltDampedTrendForecastStrategy()),
    )


class _CachedRepository:
    """Adapter that lets the repository use Streamlit's short-lived cache."""

    def __init__(self, loader, settings: DatabaseSettings) -> None:
        self._loader = loader
        self._settings = settings

    def fetch_sales_facts(self) -> pd.DataFrame:
        return self._loader(self._settings)


def _render_metric_cards(snapshot, metric: SalesMetric) -> None:
    kpis = snapshot.analysis.kpis
    latest_change = None
    if kpis.prior_month_value not in (None, 0):
        latest_change = (kpis.latest_month_value / kpis.prior_month_value - 1) * 100

    store_label = display_store_name(kpis.leading_store) if kpis.leading_store else "—"
    change_markup = ""
    if latest_change is not None:
        arrow = "↑" if latest_change >= 0 else "↓"
        tone = "positive" if latest_change >= 0 else "negative"
        change_markup = (
            f'<div class="kpi-delta {tone}">{arrow} {latest_change:+.1f}% vs prior month</div>'
        )
    cost_note = (
        f'<div class="kpi-note">{kpis.missing_unit_cost_lines:,} line items lack unit cost</div>'
        if kpis.missing_unit_cost_lines
        else ""
    )
    cards = [
        ("Estimated gross profit", _money(kpis.total_estimated_gross_profit), cost_note),
        (f"Latest full month · {metric.label}", _money(kpis.latest_month_value), change_markup),
        ("Leading category", kpis.leading_category or "—", ""),
        ("Leading store", store_label, ""),
    ]
    card_markup = "".join(
        '<div class="kpi-card">'
        f'<div class="kpi-label">{escape(label)}</div>'
        f'<div class="kpi-value">{escape(value)}</div>'
        f"{detail}</div>"
        for label, value, detail in cards
    )
    st.markdown(f'<div class="kpi-grid">{card_markup}</div>', unsafe_allow_html=True)


def _money(value: float) -> str:
    return f"${value:,.0f}"


def _render_dashboard(
    controller: DashboardController,
    categories: list[str],
    stores: list[str],
    subcategories_by_category: dict[str, list[str]],
) -> None:
    options_col, main_col = st.columns([1, 4.15], gap="small")
    with options_col:
        with st.container(border=True):
            metric_label = st.radio(
                "Performance measure",
                [SalesMetric.REVENUE.label, SalesMetric.ESTIMATED_GROSS_PROFIT.label],
                key="metric",
            )
        with st.container(border=True):
            mode_label = st.radio(
                "Analysis view",
                [AnalysisMode.HISTORICAL.value, AnalysisMode.PREDICTIVE.value],
                key="analysis_mode",
            )
            if mode_label == AnalysisMode.PREDICTIVE.value:
                st.caption("Holt damped-trend forecast")
        selected_categories: list[str] = []
        selected_subcategories: list[str] = []
        selected_stores: list[str] = []
        with st.container(border=True):
            comparison_label = st.radio(
                "Compare across",
                [item.value for item in ComparisonDimension],
                key="comparison",
                on_change=_comparison_changed,
            )
            if comparison_label == ComparisonDimension.CATEGORIES.value:
                selected_categories = st.multiselect(
                    "Categories",
                    categories,
                    key="category_selection",
                    placeholder="Select categories",
                    on_change=_category_changed,
                )
                if len(selected_categories) == 1:
                    all_subcategories = subcategories_by_category.get(selected_categories[0], [])
                    selected_subcategories = st.multiselect(
                        f"{selected_categories[0]} subcategories",
                        all_subcategories,
                        key="subcategory_selection",
                        placeholder="All subcategories",
                    )
            elif comparison_label == ComparisonDimension.STORES.value:
                selected_stores = st.multiselect(
                    "Stores",
                    stores,
                    key="store_selection",
                    placeholder="Select stores",
                    format_func=display_store_name,
                )
        with st.container(border=True):
            interval_label = st.selectbox(
                "Time interval", [item.value for item in TimeInterval], index=0, key="interval"
            )
        with st.container(border=True):
            st.markdown("**Reset selections**")
            button_left, button_right = st.columns(2)
            button_left.button(
                "Reset category",
                use_container_width=True,
                on_click=_reset_categories,
                disabled=not selected_categories,
            )
            button_right.button(
                "Reset store",
                use_container_width=True,
                on_click=_reset_stores,
                disabled=not selected_stores,
            )
            st.button("Reset all", use_container_width=True, on_click=_reset_all)

    try:
        criteria = FilterCriteria(
            metric=(
                SalesMetric.REVENUE
                if metric_label == SalesMetric.REVENUE.label
                else SalesMetric.ESTIMATED_GROSS_PROFIT
            ),
            mode=AnalysisMode(mode_label),
            comparison=ComparisonDimension(comparison_label),
            categories=tuple(selected_categories),
            subcategories=tuple(selected_subcategories),
            stores=tuple(selected_stores),
        )
        snapshot = controller.refresh(criteria, TimeInterval(interval_label))
    except (MySQLError, OSError, ValueError) as exc:
        with main_col:
            st.error("Could not load sales data from MySQL.")
            st.caption(str(exc))
            st.info(
                "Set MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE, MYSQL_USER, and MYSQL_PASSWORD. "
                "Use a MySQL account that has SELECT permission only on the analytics schema."
            )
        return

    analysis = snapshot.analysis
    with main_col:
        trend_col, payment_col, glance_col = st.columns([2.3, 1, 1.2], gap="small")
        with trend_col, st.container(border=True):
            st.markdown(f"**{TimeInterval(interval_label).value} {criteria.metric.label.lower()}**")
            trend_figure = make_trend_chart(
                analysis.trend,
                analysis.value_column,
                snapshot.forecast,
            )
            if trend_figure is None:
                st.info("No sales records match the current selections.")
            else:
                st.plotly_chart(trend_figure, use_container_width=True, theme="streamlit")
        with payment_col, st.container(border=True):
            st.markdown("**By payment type**")
            payment_figure = make_donut_chart(
                analysis.by_payment_type,
                "payment_type",
                analysis.value_column,
                show_legend=False,
                show_labels=True,
                height=285,
            )
            if payment_figure is None:
                st.info("No payment data available.")
            else:
                st.plotly_chart(payment_figure, use_container_width=True, theme="streamlit")
        with glance_col:
            _render_metric_cards(snapshot, criteria.metric)

        store_col, category_col = st.columns(2, gap="small")
        with store_col, st.container(border=True):
            st.markdown("**By store**")
            store_frame = analysis.by_store.copy()
            if not store_frame.empty:
                store_frame["store_display"] = store_frame["store"].map(display_store_name)
            store_figure = make_donut_chart(
                store_frame,
                "store_display",
                analysis.value_column,
                show_legend=True,
                show_labels=False,
                height=350,
            )
            if store_figure is None:
                st.info("No store data available.")
            else:
                store_chart_key = f"store_chart_{st.session_state.get('store_chart_revision', 0)}"
                st.session_state["active_store_chart_key"] = store_chart_key
                store_figure.update_traces(customdata=store_frame[["store"]].to_numpy())
                store_figure.update_layout(clickmode="event+select")
                st.plotly_chart(
                    store_figure,
                    key=store_chart_key,
                    on_select=_store_chart_selected,
                    selection_mode="points",
                    use_container_width=True,
                    theme="streamlit",
                )
        with category_col, st.container(border=True):
            if len(selected_categories) == 1:
                st.markdown(f"**{selected_categories[0]} subcategories**")
                category_frame = analysis.by_subcategory
                category_label = "subcategory"
            else:
                category_chart_key = f"category_chart_{st.session_state.get('category_chart_revision', 0)}"
                st.session_state["active_category_chart_key"] = category_chart_key
                st.session_state["active_category_chart_is_subcategory"] = False
                st.markdown("**By category**")
                category_frame = analysis.by_category
                category_label = "category"
            if len(selected_categories) == 1:
                category_chart_key = f"category_chart_{st.session_state.get('category_chart_revision', 0)}"
                st.session_state["active_category_chart_key"] = category_chart_key
                st.session_state["active_category_chart_is_subcategory"] = True
            category_figure = make_donut_chart(
                category_frame,
                category_label,
                analysis.value_column,
                show_legend=True,
                show_labels=False,
                height=350,
            )
            if category_figure is None:
                st.info("No category data available.")
            else:
                category_figure.update_traces(customdata=category_frame[[category_label]].to_numpy())
                category_figure.update_layout(clickmode="event+select")
                st.plotly_chart(
                    category_figure,
                    key=category_chart_key,
                    on_select=_category_chart_selected,
                    selection_mode="points",
                    use_container_width=True,
                    theme="streamlit",
                )


def render() -> None:
    st.set_page_config(
        page_title="Retail Sales Analytics Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(
        """
        <style>
        .block-container { max-width: 100%; padding: 3.65rem .8rem .35rem; }
        header[data-testid="stHeader"]::before { content: "Retail Sales Dashboard"; position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); font-size: 1.35rem; font-weight: 800; letter-spacing: -.01em; color: var(--text-color); pointer-events: none; white-space: nowrap; }
        div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px; }
        .dashboard-title { font-size: 1.2rem; font-weight: 750; line-height: 1.25; }
        .kpi-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .5rem; }
        .kpi-card { box-sizing: border-box; border: 1px solid rgba(128,128,128,.28); border-radius: 12px; padding: .85rem .9rem; min-height: 168px; display: flex; flex-direction: column; justify-content: center; overflow-wrap: anywhere; }
        .kpi-label { opacity: .84; font-size: .94rem; line-height: 1.3; margin-bottom: .4rem; }
        .kpi-value { font-size: 1.42rem; font-weight: 650; line-height: 1.22; }
        .kpi-delta { font-size: .9rem; font-weight: 600; margin-top: .35rem; }
        .kpi-delta.positive { color: #1f9d63; }
        .kpi-delta.negative { color: #e24949; }
        .kpi-note { font-size: .78rem; opacity: .78; margin-top: .25rem; }
        .eyebrow { color: #438277; text-transform: uppercase; font-weight: 700; font-size: .68rem; letter-spacing: .13em; }
        .brand-title { font-weight: 800; font-size: 1.7rem; line-height: 1.05; letter-spacing: -.04em; margin: .4rem 0; }
        .brand-subtitle { opacity: .75; font-size: .84rem; line-height: 1.3; }
        [data-testid="stMetric"] { padding: .35rem .55rem; }
        [data-testid="stMetricLabel"] p { font-size: .86rem; }
        [data-testid="stMetricValue"] div { font-size: 1.4rem; }
        [data-testid="stMetricDelta"] { font-size: .8rem; }
        [data-testid="stWidgetLabel"] p { font-size: 1rem; margin-bottom: .12rem; }
        [data-testid="stRadio"] label p { font-size: 1rem; }
        [data-testid="stVerticalBlock"] { gap: .42rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    try:
        settings = DatabaseSettings.from_environment()
        facts = _load_facts(settings)
    except (MySQLError, ValueError, OSError) as exc:
        st.title("Retail Sales Analytics Dashboard")
        st.error("The database connection is not ready.")
        st.caption(str(exc))
        st.info(
            "Configure MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE, MYSQL_USER, and MYSQL_PASSWORD. "
            "The application expects a read-only MySQL user."
        )
        return

    if facts.empty:
        st.title("Retail Sales Analytics Dashboard")
        st.warning("The analytics database is connected, but it contains no sales records yet.")
        return

    categories = sorted(facts["category"].dropna().unique().tolist())
    stores = sorted(facts["store"].dropna().unique().tolist())
    subcategories_by_category = {
        category: sorted(group["subcategory"].dropna().unique().tolist())
        for category, group in facts.groupby("category")
    }
    _render_dashboard(_build_controller(settings), categories, stores, subcategories_by_category)

