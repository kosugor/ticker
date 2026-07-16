"""Shared importer for normalized provider histories."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

from ticker.database import connect


CSV_COLUMNS = (
    "society_id", "fund_id", "fund_name", "source_url", "date", "unit_value",
    "unit_currency", "fund_assets_value", "fund_assets_currency",
)
DEFAULT_DATABASE = "data/ticker.sqlite3"


def normalize_date(date_text: str, row_number: int) -> str:
    """Convert the supported provider date formats to ISO format."""
    for format_string in ("%Y-%m-%d", "%d.%m.%Y", "%d. %m. %Y"):
        try:
            return datetime.strptime(date_text, format_string).date().isoformat()
        except ValueError:
            pass
    raise ValueError(
        f"CSV row {row_number}: invalid date {date_text!r}; "
        "expected yyyy-mm-dd or dd.mm.yyyy"
    )


def import_csv(input_path: Path, database_path: Path) -> int:
    """Import normalized history rows into fund_values using integer fund IDs."""
    with input_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames != list(CSV_COLUMNS):
            raise ValueError(
                f"unexpected CSV columns: {reader.fieldnames!r}; "
                f"expected {list(CSV_COLUMNS)!r}"
            )
        with connect(database_path) as connection:
            insert_sql = """
                INSERT OR IGNORE INTO fund_values (
                    fund_id, value_date, investment_unit_value,
                    investment_unit_currency, fund_assets_value,
                    fund_assets_currency, fetched_at_utc
                )
                SELECT fund.id, ?, ?, ?, ?, ?, ?
                FROM funds AS fund
                JOIN societies AS society ON society.id = fund.society_id
                WHERE society.id = ? AND fund.id = ?
            """
            fetched_at_utc = datetime.now(timezone.utc).isoformat()
            row_count = 0
            for row_number, row in enumerate(reader, start=2):
                if None in row or any(row[column] is None for column in CSV_COLUMNS):
                    raise ValueError(f"CSV row {row_number}: unexpected number of fields")
                date_iso = normalize_date(row["date"], row_number)
                cursor = connection.execute(
                    insert_sql,
                    (
                        date_iso, row["unit_value"], row["unit_currency"],
                        row["fund_assets_value"], row["fund_assets_currency"],
                        fetched_at_utc, int(row["society_id"]), int(row["fund_id"]),
                    ),
                )
                if cursor.rowcount == 0:
                    exists = connection.execute(
                        """SELECT 1 FROM funds AS fund
                           JOIN societies AS society ON society.id = fund.society_id
                           WHERE society.id = ? AND fund.id = ?""",
                        (int(row["society_id"]), int(row["fund_id"])),
                    ).fetchone()
                    if exists is None:
                        raise ValueError(
                            f"CSV row {row_number}: fund {row['fund_id']!r} "
                            f"is not seeded for society {row['society_id']!r}"
                        )
                row_count += 1
    return row_count


def main(
    provider_name: str,
    default_input: str,
    default_database: str = DEFAULT_DATABASE,
    argv: list[str] | None = None,
) -> int:
    """Run a provider-specific normalized-history importer CLI."""
    parser = argparse.ArgumentParser(
        description=f"Import {provider_name} history into fund_values."
    )
    parser.add_argument("-i", "--input", type=Path, default=Path(default_input))
    parser.add_argument("-d", "--database", type=Path, default=Path(default_database))
    args = parser.parse_args(argv)
    try:
        row_count = import_csv(args.input, args.database)
    except (OSError, UnicodeError, ValueError, csv.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Imported {row_count} CSV rows into fund_values in {args.database}")
    return 0
