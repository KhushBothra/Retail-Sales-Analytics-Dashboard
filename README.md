# Retail Sales Analytics Dashboard

An object-oriented application for interactive retail sales analysis and short-term forecasting. It is intended for business analysts and reads data from a configured database; it does not perform point-of-sale, inventory-management, or transaction-entry work.

## Capabilities in progress

- Explore revenue and estimated gross profit using weekly or monthly trends.
- Exclude incomplete periods at both ends of the available date range. Weeks run Sunday through Saturday; a week appears only when the source covers the whole week.
- Compare performance across product categories, subcategories, stores, and payment types.
- Keep dashboard aggregations coordinated with one shared metric and filter state.
- Provide a historical view and a two-month Holt damped-trend forecast. Smoothing parameters are selected with rolling one-step validation; this is an initial temporal baseline, not a final model selection.

## Data and database

The prototype uses the synthetic Mancino Market grocery retail dataset, loaded into MySQL to represent an existing operational database. At runtime, the application retrieves data through a read-only transaction and is intended to use a MySQL account granted `SELECT` access only. Dataset ingestion and database setup are separate preparation steps.

Revenue is currently derived from `transaction_line_items.line_total`. Estimated gross profit uses the working formula `line_total - (qty * products.unit_cost)`; confirm the source fields' business semantics before treating it as a finalized accounting definition.

## Run locally

Install the Python requirements, then configure these environment variables for the application:

- `MYSQL_HOST` (default: `localhost`)
- `MYSQL_PORT` (default: `3306`)
- `MYSQL_DATABASE` (default: `mancino_analytics`)
- `MYSQL_USER` (default: `analytics_reader`)
- `MYSQL_PASSWORD` (required)

Use a database account with read-only access for the application. The data-preparation loader uses a separate account because it creates and populates the prototype schema.

```powershell
python -m pip install -r requirements.txt
$env:MYSQL_USER = "analytics_reader"
$env:MYSQL_PASSWORD = "your-read-only-account-password"
python -m streamlit run app.py
```

## Project structure

- `app.py` — Streamlit entry point.
- `retail_analytics/domain/` — shared filter, metric, and analysis types.
- `retail_analytics/repositories/` — read-only MySQL access.
- `retail_analytics/services/` — analysis, dashboard coordination, and forecasting boundary.
- `retail_analytics/dashboard/` — Streamlit presentation and charts.
- `Data Prep/` — database schema, data loading, and preparation notebooks/scripts.
- `Data/` — only the four CSVs currently used by the preparation and ingestion workflow are tracked.
- `Documentation/` — local project documents; excluded from Git.
- `Mock UI/` — layout prototype; excluded from Git.

Filter controls and category/store pie selections share one dashboard filter state. Selecting one category changes its pie to a subcategory breakdown. Store names are shortened for display by removing the common `Mancino Market -` prefix, while the original names remain the store filter keys. The forecasting service accepts a replaceable model strategy so the initial temporal baseline can later be replaced by an evaluated model.
