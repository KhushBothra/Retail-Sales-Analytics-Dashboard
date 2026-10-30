from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from retail_analytics.config import DatabaseSettings
from retail_analytics.repositories.mysql_sales_repository import FACT_QUERY, MySQLSalesRepository


class MySQLSalesRepositoryTests(unittest.TestCase):
    def test_fetch_uses_read_only_transaction_and_closes_resources(self) -> None:
        settings = DatabaseSettings("localhost", 3306, "analytics", "reader", "secret")
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.description = [("sale_date",), ("revenue",), ("estimated_gross_profit",), ("missing_unit_cost_lines",)]
        cursor.fetchall.return_value = [("2025-01-01", "120.5", "40.5", "0")]

        with patch("retail_analytics.repositories.mysql_sales_repository.mysql.connector.connect", return_value=connection) as connect:
            frame = MySQLSalesRepository(settings).fetch_sales_facts()

        connect.assert_called_once_with(
            host="localhost",
            port=3306,
            database="analytics",
            user="reader",
            password="secret",
            connection_timeout=10,
            autocommit=False,
            use_pure=True,
        )
        connection.start_transaction.assert_called_once_with(readonly=True)
        cursor.execute.assert_called_once_with(FACT_QUERY)
        cursor.close.assert_called_once_with()
        connection.rollback.assert_called_once_with()
        connection.close.assert_called_once_with()
        self.assertEqual(float(frame.loc[0, "revenue"]), 120.5)
        self.assertEqual(float(frame.loc[0, "estimated_gross_profit"]), 40.5)


if __name__ == "__main__":
    unittest.main()
