from __future__ import annotations

from typing import Protocol

import pandas as pd


class SalesRepository(Protocol):
    """Read-only source of aggregated sales facts for analytics."""

    def fetch_sales_facts(self) -> pd.DataFrame:
        """Return daily facts grouped by store, product segment, and payment type."""
        ...
