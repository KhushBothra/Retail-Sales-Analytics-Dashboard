from __future__ import annotations

import pandas as pd
import mysql.connector

from retail_analytics.config import DatabaseSettings


FACT_QUERY = """
SELECT
    DATE(t.txn_ts) AS sale_date,
    s.store_name AS store,
    p.category AS category,
    COALESCE(p.subcategory, 'Unclassified') AS subcategory,
    COALESCE(NULLIF(TRIM(t.payment_type), ''), 'Unknown') AS payment_type,
    SUM(li.line_total) AS revenue,
    SUM(li.line_total - (li.qty * p.unit_cost)) AS estimated_gross_profit,
    SUM(CASE WHEN p.unit_cost IS NULL THEN 1 ELSE 0 END) AS missing_unit_cost_lines
FROM transactions AS t
JOIN stores AS s ON s.store_id = t.store_id
JOIN transaction_line_items AS li ON li.transaction_id = t.transaction_id
JOIN products AS p ON p.product_id = li.product_id
GROUP BY
    DATE(t.txn_ts), s.store_name, p.category,
    COALESCE(p.subcategory, 'Unclassified'),
    COALESCE(NULLIF(TRIM(t.payment_type), ''), 'Unknown')
ORDER BY sale_date, store, category, subcategory, payment_type
"""


class MySQLSalesRepository:
    """Fetch analytical facts through a MySQL read-only transaction."""

    def __init__(self, settings: DatabaseSettings) -> None:
        self._settings = settings

    def fetch_sales_facts(self) -> pd.DataFrame:
        connection = mysql.connector.connect(
            host=self._settings.host,
            port=self._settings.port,
            database=self._settings.database,
            user=self._settings.user,
            password=self._settings.password,
            connection_timeout=10,
            autocommit=False,
            use_pure=True,
        )
        try:
            connection.start_transaction(readonly=True)
            cursor = connection.cursor()
            try:
                cursor.execute(FACT_QUERY)
                rows = cursor.fetchall()
                columns = [item[0] for item in cursor.description]
                frame = pd.DataFrame.from_records(rows, columns=columns)
                for column in (
                    "revenue",
                    "estimated_gross_profit",
                    "missing_unit_cost_lines",
                ):
                    frame[column] = pd.to_numeric(frame[column], errors="coerce")
                return frame
            finally:
                cursor.close()
        finally:
            connection.rollback()
            connection.close()
