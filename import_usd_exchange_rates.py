"""Import historical USD exchange rates from NBS CSV files into SQLite."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ticker.config import Settings
from ticker.database import connect


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = PROJECT_ROOT / "history-download" / "usd"


def _parse_row(row: list[str], row_number: int, path: Path) -> tuple[str, str]:
    if len(row) < 2:
        raise ValueError(f"{path}, row {row_number}: expected at least two columns")

    date_text = row[1].strip()
    rate_text = row[-1].strip()
    try:
        effective_date = datetime.strptime(date_text, "%d.%m.%Y").date().isoformat()
    except ValueError as error:
        raise ValueError(
            f"{path}, row {row_number}: invalid date in second column {date_text!r}"
        ) from error

    try:
        rate = Decimal(rate_text)
    except InvalidOperation as error:
        raise ValueError(
            f"{path}, row {row_number}: invalid exchange rate in last column {rate_text!r}"
        ) from error
    if not rate.is_finite() or rate <= 0:
        raise ValueError(f"{path}, row {row_number}: exchange rate must be positive")
    return effective_date, str(rate)


def import_directory(input_directory: Path, database_path: Path) -> tuple[int, int]:
    """Import all CSV files in *input_directory*.

    Returns ``(rows_read, rows_inserted)``. Existing dates are left unchanged.
    """
    paths = sorted(input_directory.glob("*.csv"))
    if not paths:
        raise ValueError(f"no CSV files found in {input_directory}")

    rows_read = 0
    rows_inserted = 0
    with connect(database_path) as connection:
        for path in paths:
            with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
                reader = csv.reader(csv_file)
                next(reader, None)  # NBS column headings
                for row_number, row in enumerate(reader, start=2):
                    if not row or not any(cell.strip() for cell in row):
                        continue
                    effective_date, rate = _parse_row(row, row_number, path)
                    cursor = connection.execute(
                        """INSERT OR IGNORE INTO usd_exchange_rates
                           (effective_date, middle_rate) VALUES (?, ?)""",
                        (effective_date, rate),
                    )
                    rows_read += 1
                    rows_inserted += cursor.rowcount
    return rows_read, rows_inserted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-i", "--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "-d", "--database", type=Path, default=Settings.from_env().database_path
    )
    args = parser.parse_args(argv)
    try:
        rows_read, rows_inserted = import_directory(args.input, args.database)
    except (OSError, UnicodeError, ValueError, csv.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(
        f"Read {rows_read} rows; inserted {rows_inserted} exchange rates "
        f"into {args.database}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
