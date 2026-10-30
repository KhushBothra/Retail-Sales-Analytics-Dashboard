# Automated Test Suite

This folder contains automated checks for the dashboard's business logic,
filter validation, forecasting, and MySQL repository behavior. The database
repository tests use a mock connection, so the suite does not need a running
MySQL server and does not read or change the project database.

## Requirements

- Python 3.10 or later
- Project dependencies installed from the project root

If the project environment is not set up yet, open PowerShell in the project
root and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run the full suite

From the project root (the folder containing `app.py`), run:

```powershell
python -m unittest discover -s tests -v
```

The verbose output lists each test and ends with the number of tests that
passed or failed. A nonzero exit code means at least one test failed.

## Run one test module

```powershell
python -m unittest discover -s tests -p "test_sales_analysis.py" -v
```

Change the pattern to `test_forecasting.py`, `test_domain_and_config.py`, or
`test_mysql_repository.py` to run another module.

## Coverage and limits

The suite checks period completion, shared filters, aggregate values, KPI
calculations, forecast output shape, invalid filter combinations, environment
configuration, and the repository's read-only transaction behavior. It does
not test the visual layout in a browser or verify a live MySQL server/schema.
