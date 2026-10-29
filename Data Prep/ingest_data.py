from __future__ import annotations

import argparse
import getpass
import os
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import mysql.connector
import pandas as pd
from mysql.connector import Error


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
DATA_DIR = PROJECT_ROOT / "Data" / "v1_2025-11-01"
SCHEMA_FILE = HERE / "schema.sql"
DATABASE = "mancino_analytics"
BATCH_SIZE = 5_000
MONEY = Decimal("0.01")
QUANTITY = Decimal("0.001")
COORDINATE = Decimal("0.000001")

TABLE_COLUMNS = {
    "stores": [
        "store_id", "store_name", "neighborhood", "address", "city", "state",
        "zip", "latitude", "longitude",
    ],
    "products": [
        "product_id", "product_name", "brand", "category", "subcategory",
        "unit_size", "price", "unit_cost",
    ],
    "transactions": [
        "transaction_id", "customer_id", "store_id", "txn_ts", "subtotal", "tax",
        "total", "num_items", "payment_type", "day_name",
    ],
    "transaction_line_items": [
        "transaction_id", "line_no", "product_id", "qty", "unit_price",
        "line_subtotal", "line_discount", "line_total",
    ],
}

CSV_FILES = {
    "stores": "stores.csv",
    "products": "products.csv",
    "transactions": "transactions.csv",
    "transaction_line_items": "transaction_line_items.csv",
}

ID_DTYPES = {
    "stores": {},
    "products": {"product_id": "string"},
    "transactions": {"transaction_id": "string", "customer_id": "string"},
    "transaction_line_items": {"transaction_id": "string", "product_id": "string"},
}

REQUIRED_COLUMNS = {
    "stores": ["store_id", "store_name"],
    "products": ["product_id", "product_name", "category"],
    "transactions": ["transaction_id", "store_id", "txn_ts"],
    "transaction_line_items": [
        "transaction_id", "line_no", "product_id", "qty", "unit_price",
        "line_subtotal", "line_discount", "line_total",
    ],
}

PRIMARY_KEYS = {
    "stores": ["store_id"],
    "products": ["product_id"],
    "transactions": ["transaction_id"],
    "transaction_line_items": ["transaction_id", "line_no"],
}

MONEY_COLUMNS = {
    "stores": [],
    "products": ["price", "unit_cost"],
    "transactions": ["subtotal", "tax", "total"],
    "transaction_line_items": ["unit_price", "line_subtotal", "line_discount", "line_total"],
}

QUANTITY_COLUMNS = {"transaction_line_items": ["qty"]}
COORDINATE_COLUMNS = {"stores": ["latitude", "longitude"]}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost", help="MySQL host (default: localhost)")
    parser.add_argument("--port", type=int, default=3306, help="MySQL port (default: 3306)")
    parser.add_argument("--user", default="root", help="MySQL user (default: root)")
    parser.add_argument("--replace", action="store_true", help="Clear the four target tables before loading")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR, help="Directory containing the four CSV files")
    return parser.parse_args()


def require_columns(frame: pd.DataFrame, expected: list[str], label: str) -> None:
    missing = [column for column in expected if column not in frame.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def read_source_files(data_dir: Path) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for table, filename in CSV_FILES.items():
        path = data_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required source file not found: {path}")
        frame = pd.read_csv(path, dtype=ID_DTYPES[table])
        require_columns(frame, TABLE_COLUMNS[table], filename)
        frames[table] = frame[TABLE_COLUMNS[table]].copy()
    return frames


def validate_frames(frames: dict[str, pd.DataFrame]) -> None:
    for table, frame in frames.items():
        missing_required = frame[REQUIRED_COLUMNS[table]].isna().any(axis=1)
        if missing_required.any():
            raise ValueError(f"{table}: {int(missing_required.sum())} rows have missing required values")
        duplicate_keys = frame.duplicated(PRIMARY_KEYS[table])
        if duplicate_keys.any():
            raise ValueError(f"{table}: {int(duplicate_keys.sum())} rows have duplicate primary keys")

    stores = set(frames["stores"]["store_id"].astype("string"))
    products = set(frames["products"]["product_id"].dropna())
    transactions = set(frames["transactions"]["transaction_id"].dropna())
    tx_store_ids = frames["transactions"]["store_id"].astype("string")
    line_items = frames["transaction_line_items"]

    unknown_stores = ~tx_store_ids.isin(stores)
    unknown_transactions = ~line_items["transaction_id"].isin(transactions)
    unknown_products = ~line_items["product_id"].isin(products)
    for description, invalid in (
        ("transactions referencing unknown stores", unknown_stores),
        ("line items referencing unknown transactions", unknown_transactions),
        ("line items referencing unknown products", unknown_products),
    ):
        if invalid.any():
            raise ValueError(f"Found {int(invalid.sum())} {description}")

    timestamps = pd.to_datetime(frames["transactions"]["txn_ts"], errors="coerce")
    if timestamps.isna().any():
        raise ValueError(f"transactions: {int(timestamps.isna().sum())} timestamps cannot be parsed")
    frames["transactions"]["txn_ts"] = timestamps

    numeric = frames["transaction_line_items"]
    for column in ("line_no", "qty", "unit_price", "line_subtotal", "line_discount", "line_total"):
        numeric[column] = pd.to_numeric(numeric[column], errors="coerce")
        if numeric[column].isna().any():
            raise ValueError(f"transaction_line_items: {column} contains non-numeric or missing values")
    if (numeric["qty"] <= 0).any():
        raise ValueError("transaction_line_items contains non-positive quantities")
    if (numeric[["unit_price", "line_subtotal", "line_discount", "line_total"]] < 0).any().any():
        raise ValueError("transaction_line_items contains negative monetary values")

    tolerance = 0.02
    subtotal_mismatch = (numeric["qty"] * numeric["unit_price"] - numeric["line_subtotal"]).abs() > tolerance
    total_mismatch = (numeric["line_subtotal"] - numeric["line_discount"] - numeric["line_total"]).abs() > tolerance
    if subtotal_mismatch.any() or total_mismatch.any():
        raise ValueError(
            "Line-item arithmetic check failed: "
            f"{int(subtotal_mismatch.sum())} subtotal mismatches, "
            f"{int(total_mismatch.sum())} net-total mismatches (tolerance {tolerance:.2f})"
        )


def decimal_value(value: Any, quantizer: Decimal) -> Decimal | None:
    if pd.isna(value):
        return None
    try:
        return Decimal(str(value)).quantize(quantizer, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Cannot convert {value!r} to a decimal") from exc


def mysql_value(table: str, column: str, value: Any) -> Any:
    if pd.isna(value):
        return None
    if column == "txn_ts":
        return pd.Timestamp(value).to_pydatetime()
    if column in MONEY_COLUMNS.get(table, []):
        return decimal_value(value, MONEY)
    if column in QUANTITY_COLUMNS.get(table, []):
        return decimal_value(value, QUANTITY)
    if column in COORDINATE_COLUMNS.get(table, []):
        return decimal_value(value, COORDINATE)
    if hasattr(value, "item"):
        return value.item()
    return value


def apply_schema(cursor: Any) -> None:
    statements = [statement.strip() for statement in SCHEMA_FILE.read_text(encoding="utf-8").split(";")]
    for statement in statements:
        if statement:
            cursor.execute(statement)


def count_rows(cursor: Any, table: str) -> int:
    cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
    return int(cursor.fetchone()[0])


def insert_frame(cursor: Any, table: str, frame: pd.DataFrame) -> None:
    columns = TABLE_COLUMNS[table]
    column_sql = ", ".join(f"`{column}`" for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    query = f"INSERT INTO `{table}` ({column_sql}) VALUES ({placeholders})"
    values = (
        tuple(mysql_value(table, column, value) for column, value in zip(columns, row))
        for row in frame[columns].itertuples(index=False, name=None)
    )
    while batch := list(_take(values, BATCH_SIZE)):
        cursor.executemany(query, batch)


def _take(iterator: Any, size: int):
    for _ in range(size):
        try:
            yield next(iterator)
        except StopIteration:
            return


def main() -> int:
    args = parse_args()
    frames = read_source_files(args.data_dir.resolve())
    validate_frames(frames)
    print("Source validation passed:")
    for table, frame in frames.items():
        print(f"  {table}: {len(frame):,} rows")

    password = os.environ.get("MYSQL_PASSWORD")
    if password is None:
        password = getpass.getpass(f"MySQL password for {args.user}@{args.host}: ")

    connection = None
    try:
        connection = mysql.connector.connect(
            host=args.host,
            port=args.port,
            user=args.user,
            password=password,
            connection_timeout=10,
        )
        connection.autocommit = False
        cursor = connection.cursor()
        apply_schema(cursor)

        existing = {table: count_rows(cursor, table) for table in TABLE_COLUMNS}
        populated = {table: count for table, count in existing.items() if count > 0}
        if populated and not args.replace:
            raise RuntimeError(
                "Target tables already contain data: "
                f"{populated}. Re-run with --replace only if you intend to replace these table contents."
            )

        if args.replace:
            for table in ("transaction_line_items", "transactions", "products", "stores"):
                cursor.execute(f"DELETE FROM `{table}`")

        for table, frame in frames.items():
            insert_frame(cursor, table, frame)
            print(f"Loaded {len(frame):,} rows into {table}")

        connection.commit()
        print(f"\nIngestion complete. Database: {DATABASE}")
        return 0
    except (Error, OSError, ValueError, RuntimeError) as exc:
        if connection is not None:
            connection.rollback()
        print(f"Ingestion failed: {exc}")
        return 1
    finally:
        if connection is not None and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
