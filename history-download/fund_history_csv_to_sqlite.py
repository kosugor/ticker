"""Shared CSV-to-SQLite importer for normalized fund history downloads."""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


CSV_COLUMNS = (
    "fund_id", "fund_name", "source_url", "date", "unit_value", "unit_currency",
    "fund_assets_value", "fund_assets_currency",
)


def quote_identifier(identifier: str) -> str:
    """Quote a SQLite identifier supplied on the command line."""
    if not identifier or "\x00" in identifier:
        raise ValueError("table name must be nonempty and cannot contain NUL")
    return '"' + identifier.replace('"', '""') + '"'


def normalize_date(date_text: str, row_number: int) -> str:
    """Convert the supported provider date formats to ISO format."""
    for format_string in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(date_text, format_string).date().isoformat()
        except ValueError:
            pass
    raise ValueError(
        f"CSV row {row_number}: invalid date {date_text!r}; "
        "expected yyyy-mm-dd or dd.mm.yyyy"
    )


def import_csv(input_path: Path, database_path: Path, table: str) -> int:
    """Import normalized fund-history CSV records and return source row count."""
    quoted_table = quote_identifier(table)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with input_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames != list(CSV_COLUMNS):
            raise ValueError(
                f"unexpected CSV columns: {reader.fieldnames!r}; "
                f"expected {list(CSV_COLUMNS)!r}"
            )
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {quoted_table} (
                    id INTEGER PRIMARY KEY,
                    fund_id TEXT NOT NULL, fund_name TEXT NOT NULL,
                    source_url TEXT NOT NULL, date_text TEXT NOT NULL,
                    date_iso TEXT NOT NULL, unit_value TEXT NOT NULL,
                    unit_currency TEXT NOT NULL, fund_assets_value TEXT NOT NULL,
                    fund_assets_currency TEXT NOT NULL,
                    UNIQUE (fund_id, fund_name, source_url, date_text, unit_value,
                            unit_currency, fund_assets_value, fund_assets_currency)
                )
                """
            )
            insert_sql = f"""
                INSERT OR IGNORE INTO {quoted_table} (
                    fund_id, fund_name, source_url, date_text, date_iso,
                    unit_value, unit_currency, fund_assets_value,
                    fund_assets_currency
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            row_count = 0
            for row_number, row in enumerate(reader, start=2):
                if None in row or any(row[column] is None for column in CSV_COLUMNS):
                    raise ValueError(f"CSV row {row_number}: unexpected number of fields")
                connection.execute(
                    insert_sql,
                    (row["fund_id"], row["fund_name"], row["source_url"], row["date"],
                     normalize_date(row["date"], row_number), row["unit_value"],
                     row["unit_currency"], row["fund_assets_value"],
                     row["fund_assets_currency"]),
                )
                row_count += 1
    return row_count


def main(provider_name: str, default_input: str, default_database: str,
         argv: list[str] | None = None) -> int:
    """Run a provider-specific normalized-history importer CLI."""
    parser = argparse.ArgumentParser(
        description=f"Import {provider_name} historical-values CSV data into SQLite."
    )
    parser.add_argument("-i", "--input", type=Path, default=Path(default_input),
                        help=f"input CSV path (default: {default_input})")
    parser.add_argument("-d", "--database", type=Path, default=Path(default_database),
                        help=f"output SQLite database path (default: {default_database})")
    parser.add_argument("-t", "--table", default="historical_values",
                        help="destination table name (default: historical_values)")
    args = parser.parse_args(argv)
    try:
        row_count = import_csv(args.input, args.database, args.table)
    except (OSError, UnicodeError, ValueError, csv.Error, sqlite3.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Imported {row_count} CSV rows into {args.database} (table {args.table})")
    return 0
