# Retail Sales Analytics Dashboard

An object-oriented retail analytics application built with Python,
Streamlit, Plotly, and MySQL. The dashboard helps users explore
historical sales performance, compare business dimensions, and view
short-term forecasts.

The application is an analytics layer over an existing database. It is
**not** a point-of-sale, transaction-entry, inventory-management, or
procurement system.

## Table of contents

-   [Features](#features)
-   [Data source](#data-source)
-   [Data preparation and database](#data-preparation-and-database)
-   [Analytics and business metrics](#analytics-and-business-metrics)
-   [Forecasting](#forecasting)
-   [Application architecture](#application-architecture)
-   [Requirements](#requirements)
-   [Setup and execution](#setup-and-execution)
-   [Configuration](#configuration)
-   [Project structure](#project-structure)
-   [Design notes and limitations](#design-notes-and-limitations)

## Features

### Historical analysis

-   Explore **revenue** and **estimated gross profit**.
-   Switch between weekly and monthly time intervals.
-   View overall performance or compare selected stores, product
    categories, or subcategories.
-   Examine category, store, and payment-type distributions.
-   Select a category to inspect its subcategory breakdown.
-   Use the dashboard filter controls to coordinate the displayed charts
    and KPIs.
-   Reset individual filter groups or restore the dashboard to its
    default state.
-   View headline KPIs, including revenue, estimated gross profit,
    transaction count, and leading category/store information.

### Predictive analysis

-   Switch from historical analysis to a predictive view.
-   Generate short-term forecasts from the historical time series.
-   Forecasting is implemented as a separate service behind a
    replaceable strategy interface.

## Data source

The project uses the **Mancino Market synthetic retail dataset**.

**Original dataset repository:**\
<https://github.com/jrmst102/mancino/tree/main>

The repository contains multiple related data files. This application
uses four core tables:

  -----------------------------------------------------------------------
  Table                               Purpose
  ----------------------------------- -----------------------------------
  `stores`                            Store details and identifiers

  `products`                          Product details, categories,
                                      subcategories, selling prices, and
                                      unit costs

  `transactions`                      Transaction headers, timestamps,
                                      store references, and payment types

  `transaction_line_items`            Product-level quantities, prices,
                                      discounts, and line totals
  -----------------------------------------------------------------------

### Dataset versions used in this project

Two versions are retained in the repository:

-   **`v1_2025-11-01`** --- the original downloaded Mancino dataset
    files.
-   **`v2_illustrative_variation`** --- a derived version used by the
    current MySQL application database.

The original dataset has relatively uniform category and payment-type
distributions across stores. This makes comparisons between stores less
visually differentiated. The project therefore includes a
data-preparation notebook that creates an illustrative variation with
more differentiated store-level category preferences and payment-type
mixes.

The v2 variation changes transaction store assignments and payment types
for analytical demonstration. It retains the transaction identifiers and
underlying monetary and line-item information. It is intended to make
dashboard comparisons more informative; **the modified distributions are
illustrative and should not be interpreted as empirical evidence of real
customer behaviour**.

The current application database is populated with
**`v2_illustrative_variation`**.

## Data preparation and database

The application reads analytical data from MySQL. Data preparation and
ingestion are kept separate from the dashboard's runtime read path.

### Database schema

The normalized schema consists of four tables:

-   `stores`
-   `products`
-   `transactions`
-   `transaction_line_items`

The schema and foreign-key relationships are defined in
[`Data Prep/schema.sql`](Data%20Prep/schema.sql).

### Preparing and loading the data

The repository includes notebooks and a reusable loader:

-   [`Data Prep/data_cleaning.ipynb`](Data%20Prep/data_cleaning.ipynb)
    --- data inspection and cleaning workflow.
-   [`Data Prep/database_checks.ipynb`](Data%20Prep/database_checks.ipynb)
    --- database/data-integrity checks.
-   [`Data Prep/synthetic_data_variation.ipynb`](Data%20Prep/synthetic_data_variation.ipynb)
    --- creates `v2_illustrative_variation` from the original data and
    includes the ingestion workflow used to populate the current MySQL
    database.
-   [`Data Prep/ingest_data.py`](Data%20Prep/ingest_data.py) --- an
    alternative reusable command-line ingestion utility. Its default
    data directory points to the original v1 dataset; use `--data-dir`
    when loading another version.

The notebook is the documented workflow for generating and loading the
current illustrative v2 data. The standalone loader is provided as a
reusable alternative; it is not a description of how the current
database was populated.

### Runtime database access

At runtime, the dashboard retrieves data from MySQL through the
repository layer. The application should use a database account with
**read-only (`SELECT`) privileges**. Schema creation and data ingestion
require separate privileges and should be performed outside the running
dashboard.

The dashboard caches retrieved analytical facts for **five minutes**.
This is intentional for the intended operational-database use case: the
source database may be updated by an external management system, and the
cache balances data freshness with query overhead. As a result, the
dashboard may display data that is up to five minutes old.

## Analytics and business metrics

### Revenue

Revenue is calculated from transaction line items:

`Revenue = SUM(transaction_line_items.line_total)`

`line_total` represents the net line amount after the line discount.

### Estimated gross profit

The dashboard calculates estimated gross profit using product unit cost:

`Estimated Gross Profit = SUM(line_total - (qty * unit_cost))`

This is an analytical estimate based on the unit-cost field in the
dataset. It should not be treated as a finalized accounting measure.

### Time aggregation

-   Monthly and weekly aggregations are supported.
-   Weeks run from **Sunday through Saturday**.
-   Incomplete periods at the beginning or end of the available data
    range are excluded so that partial periods do not distort
    comparisons.

## Forecasting

The current forecasting implementation uses **Holt's damped-trend
method**.

-   The forecasting implementation is contained in
    `retail_analytics/services/forecasting_service.py`.
-   The algorithm is accessed through a `ForecastingStrategy` interface,
    keeping the forecasting service independent of a specific
    forecasting algorithm.
-   Smoothing parameters are selected using rolling one-step validation.
-   The application produces a short-term forecast of approximately two
    months.
-   Forecasting operates on the aggregated historical time series
    supplied by the analysis layer; it does not issue a separate
    raw-data query to MySQL.

The current implementation is a working forecasting baseline. The
strategy boundary allows another forecasting method to be introduced
without redesigning the dashboard or analysis workflow.

## Application architecture

The application follows a modular, object-oriented structure that
separates the user interface, domain concepts, data access, business
analysis, and forecasting.

### Main layers

  ----------------------------------------------------------------------------------
  Layer                   Responsibility          Main location
  ----------------------- ----------------------- ----------------------------------
  Presentation            Streamlit interface,    `retail_analytics/dashboard/`
                          user interactions, and  
                          Plotly charts           

  Domain                  Shared analysis types,  `retail_analytics/domain/`
                          metrics, and filter     
                          criteria                

  Repository              Data-access abstraction `retail_analytics/repositories/`
                          and MySQL               
                          implementation          

  Services                Sales analysis,         `retail_analytics/services/`
                          dashboard coordination, 
                          and forecasting         

  Configuration           Database connection     `retail_analytics/config.py`
                          settings from           
                          environment variables   
  ----------------------------------------------------------------------------------

### Important components

-   **`SalesRepository`** --- repository interface that defines the
    data-access boundary.
-   **`MySQLSalesRepository`** --- retrieves the required sales facts
    from the normalized MySQL tables.
-   **`SalesAnalysisService`** --- applies filters, performs time
    aggregation, prepares distributions, and calculates KPIs.
-   **`DashboardController`** --- coordinates analysis and forecasting
    and provides the dashboard with a consolidated snapshot.
-   **`ForecastingService`** --- delegates forecasting to the configured
    strategy.
-   **`HoltDampedTrendForecastStrategy`** --- current implementation of
    the forecasting strategy.
-   **`FilterCriteria`** --- shared domain representation of dashboard
    filters, with validation for compatible selections.

This separation keeps Streamlit-specific presentation logic out of the
repository and analysis layers, and makes the forecasting algorithm
replaceable.

## Requirements

-   Python 3.10 or later
-   MySQL Server
-   A MySQL database populated with the four application tables
-   Python packages listed in [`requirements.txt`](requirements.txt)

The declared package dependencies are:

-   `mysql-connector-python`
-   `numpy`
-   `pandas`
-   `plotly`
-   `streamlit`

## Setup and execution

### 1. Obtain the project

Clone the project repository or download the project folder, then open a
terminal in the project root (the directory containing `app.py` and
`requirements.txt`).

### 2. Create a Python environment

For example, on Windows PowerShell:

``` powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

``` powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Prepare MySQL

Ensure that MySQL is running and that the `mancino_analytics` database
contains the four tables listed in the [database
section](#data-preparation-and-database).

If setting up a fresh database, use the schema in `Data Prep/schema.sql`
and load the required CSV data using the preparation workflow documented
in `Data Prep/synthetic_data_variation.ipynb` or the standalone
ingestion utility. The current project workflow uses the v2 illustrative
variation.

Create or use a dedicated MySQL account for the dashboard with read-only
access to the application tables.

### 5. Configure the database connection

Set the environment variables described in
[Configuration](#configuration). For example:

``` powershell
$env:MYSQL_HOST = "localhost"
$env:MYSQL_PORT = "3306"
$env:MYSQL_DATABASE = "mancino_analytics"
$env:MYSQL_USER = "analytics_reader"
$env:MYSQL_PASSWORD = "your-read-only-account-password"
```

### 6. Run the dashboard

From the project root:

``` powershell
python -m streamlit run app.py
```

Streamlit will start the local application and print the URL to open in
a browser.

## Configuration

The application reads its MySQL connection settings from environment
variables.

  Variable           Default               Description
  ------------------ --------------------- -------------------
  `MYSQL_HOST`       `localhost`           MySQL server host
  `MYSQL_PORT`       `3306`                MySQL server port
  `MYSQL_DATABASE`   `mancino_analytics`   Database name
  `MYSQL_USER`       `analytics_reader`    MySQL username
  `MYSQL_PASSWORD`   None (required)       MySQL password

`MYSQL_PASSWORD` must be set. The application raises a configuration
error if it is missing.

Do not commit database passwords or other credentials to version
control.

## Project structure

``` text
Project/
├── app.py
├── requirements.txt
├── README.md
│
├── retail_analytics/
│   ├── config.py
│   ├── domain/
│   │   └── models.py
│   ├── repositories/
│   │   ├── sales_repository.py
│   │   └── mysql_sales_repository.py
│   ├── services/
│   │   ├── sales_analysis_service.py
│   │   ├── dashboard_controller.py
│   │   └── forecasting_service.py
│   └── dashboard/
│       ├── streamlit_app.py
│       ├── charts.py
│       └── formatting.py
│
├── Data/
│   ├── v1_2025-11-01/
│   └── v2_illustrative_variation/
│
├── Data Prep/
│   ├── schema.sql
│   ├── ingest_data.py
│   ├── data_cleaning.ipynb
│   ├── database_checks.ipynb
│   └── synthetic_data_variation.ipynb
│
└── Data Prep/
    ├── schema.sql
    ├── ingest_data.py
    ├── data_cleaning.ipynb
    ├── database_checks.ipynb
    └── synthetic_data_variation.ipynb
```

## Design notes and limitations

-   The dashboard is an analytics and forecasting application, not an
    operational transaction-processing system.
-   The current runtime database contains the illustrative v2 dataset.
    Results and comparisons should be interpreted in that context.
-   The five-minute cache means the dashboard is not guaranteed to
    reflect every database update immediately.
-   Gross profit is estimated using the dataset's `unit_cost` values and
    is not a substitute for an organization's accounting definitions.
-   Forecast output is generated by the currently configured Holt
    damped-trend strategy; it should be interpreted as a short-term
    analytical forecast, not a guarantee of future sales.
-   The dashboard's interactive filtering is driven by its filter
    controls and shared filter state.
