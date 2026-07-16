#!/usr/bin/env python3
"""Import Intesa Invest historical values from CSV into SQLite."""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_INPUT = "intesainvest_history.csv"
DEFAULT_DATABASE = "intesainvest_history.db"
DEFAULT_TABLE = "historical_values"
CSV_COLUMNS = (
    "fund_name",
    "history_url",
    "date",
    "unit_value_rsd",
    "unit_value_eur",
    "assets_rsd",
    "assets_eur",
)


def quote_identifier(identifier: str) -> str:
    """Quote a SQLite identifier supplied on the command line."""
    if not identifier or "\x00" in identifier:
        raise ValueError("table name must be nonempty and cannot contain NUL")
    return '"' + identifier.replace('"', '""') + '"'


def normalize_date(date_text: str, row_number: int) -> str:
    try:
        return datetime.strptime(date_text, "%d.%m.%Y").date().isoformat()
    except ValueError as error:
        raise ValueError(
            f"CSV row {row_number}: invalid date {date_text!r}; expected dd.mm.yyyy"
        ) from error


def import_csv(input_path: Path, database_path: Path, table: str) -> int:
    """Import CSV records in one transaction and return their count."""
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
                    fund_name TEXT NOT NULL,
                    history_url TEXT NOT NULL,
                    date_text TEXT NOT NULL,
                    date_iso TEXT NOT NULL,
                    unit_value_rsd TEXT NOT NULL,
                    unit_value_eur TEXT NOT NULL,
                    assets_rsd TEXT NOT NULL,
                    assets_eur TEXT NOT NULL,
                    UNIQUE (
                        fund_name,
                        history_url,
                        date_text,
                        date_iso,
                        unit_value_rsd,
                        unit_value_eur,
                        assets_rsd,
                        assets_eur
                    )
                )
                """
            )
            insert_sql = f"""
                INSERT OR REPLACE INTO {quoted_table} (
                    fund_name,
                    history_url,
                    date_text,
                    date_iso,
                    unit_value_rsd,
                    unit_value_eur,
                    assets_rsd,
                    assets_eur
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """

            row_count = 0
            for row_number, row in enumerate(reader, start=2):
                if None in row or any(row[column] is None for column in CSV_COLUMNS):
                    raise ValueError(f"CSV row {row_number}: unexpected number of fields")
                date_text = row["date"]
                connection.execute(
                    insert_sql,
                    (
                        row["fund_name"],
                        row["history_url"],
                        date_text,
                        normalize_date(date_text, row_number),
                        row["unit_value_rsd"],
                        row["unit_value_eur"],
                        row["assets_rsd"],
                        row["assets_eur"],
                    ),
                )
                row_count += 1

    return row_count


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import Intesa Invest historical-values CSV data into SQLite."
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=Path(DEFAULT_INPUT),
        help=f"input CSV path (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "-d",
        "--database",
        type=Path,
        default=Path(DEFAULT_DATABASE),
        help=f"output SQLite database path (default: {DEFAULT_DATABASE})",
    )
    parser.add_argument(
        "-t",
        "--table",
        default=DEFAULT_TABLE,
        help=f"destination table name (default: {DEFAULT_TABLE})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        row_count = import_csv(args.input, args.database, args.table)
    except (OSError, UnicodeError, ValueError, csv.Error, sqlite3.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(
        f"Imported {row_count} CSV rows into "
        f"{args.database} (table {args.table})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
