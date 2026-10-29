# Retail Sales Analytics Dashboard

Short-term forecasting system for retail performance.

An object-oriented application for interactive retail sales analysis and short-term forecasting. The system is intended for business analysts and reads data from a configured database; it does not perform point-of-sale, inventory-management, or transaction-entry work.

## Planned capabilities

- Explore monthly revenue and estimated gross profit.
- Compare sales across product categories, subcategories, and stores.
- Keep dashboard charts coordinated with the analyst's selected metric and filters.
- View historical results and forecasts for the next two months.

## Data and database

The prototype uses the synthetic Mancino Market grocery retail dataset, loaded into MySQL to represent an existing operational database. At runtime, the application is intended to retrieve data for analysis without modifying operational records. Dataset ingestion and database setup are separate preparation steps.

## Project structure

- `Data Prep/` — database schema, data loading, and preparation notebooks/scripts.
- `Documentation/` — local project documents; excluded from Git.
- `Mock UI/` — layout prototype; excluded from Git.

The main application is under development. Its architecture and technology choices will be documented here as they are implemented.
