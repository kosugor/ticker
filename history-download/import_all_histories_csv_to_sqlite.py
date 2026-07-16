#!/usr/bin/env python3
"""Import every downloaded provider history CSV into one SQLite database."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

from ticker.database import connect


IMPORTS = (
    ("Eclectica Capital", "import_eclecticacapital_csv_to_sqlite.py", "eclecticacapital_history.csv"),
    ("Intesa Invest", "import_intesainvest_csv_to_sqlite.py", "intesainvest_history.csv"),
    ("NLB Fondovi", "import_nlbfondovi_csv_to_sqlite.py", "nlbfondovi_history.csv"),
    ("Raiffeisen Invest", "import_raiffeiseninvest_csv_to_sqlite.py", "raiffeiseninvest_history.csv"),
    ("UniCredit Invest", "import_unicreditinvest_csv_to_sqlite.py", "unicreditinvest_history.csv"),
    ("Vista Rica", "import_vistarica_csv_to_sqlite.py", "vistarica_history.csv"),
    ("WVP Fondovi", "import_wvpfondovi_csv_to_sqlite.py", "wvpfondovi_history.csv"),
)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE = PROJECT_ROOT / "data/ticker.sqlite3"
DEFAULT_SOCIETIES_CSV = PROJECT_ROOT / "data/societies.csv"
DEFAULT_FUNDS_CSV = PROJECT_ROOT / "data/funds.csv"


def _read_seed_csv(path: Path, columns: tuple[str, ...]) -> list[dict[str, str]]:
    """Read and validate one seed CSV file."""
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames != list(columns):
            raise ValueError(
                f"unexpected columns in {path}: {reader.fieldnames!r}; "
                f"expected {list(columns)!r}"
            )
        rows = []
        for row_number, row in enumerate(reader, start=2):
            if None in row or any(not row[column].strip() for column in columns):
                raise ValueError(f"{path} row {row_number}: all columns are required")
            rows.append({column: row[column].strip() for column in columns})
    return rows


def initialize_database(
    database: Path, societies_csv: Path, funds_csv: Path
) -> tuple[int, int]:
    """Create the application schema and seed societies and funds idempotently."""
    societies = _read_seed_csv(societies_csv, ("society_id", "society_key"))
    funds = _read_seed_csv(funds_csv, ("fund_id", "society_id", "fund_key"))
    society_ids = [row["society_id"] for row in societies]
    if len(society_ids) != len(set(society_ids)):
        raise ValueError(f"duplicate society_id in {societies_csv}")
    fund_keys = [(row["society_id"], row["fund_id"]) for row in funds]
    if len(fund_keys) != len(set(fund_keys)):
        raise ValueError(f"duplicate society_id/fund_id pair in {funds_csv}")
    missing_societies = sorted({society_id for society_id, _ in fund_keys} - set(society_ids))
    if missing_societies:
        raise ValueError(
            f"{funds_csv} references societies missing from {societies_csv}: "
            + ", ".join(missing_societies)
        )

    with connect(database) as connection:
        connection.executemany(
            "INSERT OR IGNORE INTO societies (id, society_id) VALUES (?, ?)",
            ((int(row["society_id"]), row["society_key"]) for row in societies),
        )
        connection.executemany(
            "INSERT OR IGNORE INTO funds (id, society_id, fund_id) VALUES (?, ?, ?)",
            ((int(row["fund_id"]), int(row["society_id"]), row["fund_key"]) for row in funds),
        )
    return len(societies), len(funds)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import all provider history CSV files into one SQLite database."
    )
    parser.add_argument(
        "--input-dir", type=Path, default=Path(__file__).resolve().parent,
        help="directory containing history CSV files (default: history-download)",
    )
    parser.add_argument(
        "-d", "--database", type=Path, default=DEFAULT_DATABASE,
        help=f"output SQLite database (default: {DEFAULT_DATABASE})",
    )
    parser.add_argument(
        "--societies-csv", type=Path, default=DEFAULT_SOCIETIES_CSV,
        help=f"society seed CSV (default: {DEFAULT_SOCIETIES_CSV})",
    )
    parser.add_argument(
        "--funds-csv", type=Path, default=DEFAULT_FUNDS_CSV,
        help=f"fund seed CSV (default: {DEFAULT_FUNDS_CSV})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    script_dir = Path(__file__).resolve().parent
    input_dir = args.input_dir.resolve()
    database = args.database.resolve()
    try:
        society_count, fund_count = initialize_database(
            database, args.societies_csv.resolve(), args.funds_csv.resolve()
        )
    except (OSError, UnicodeError, ValueError, csv.Error) as error:
        print(f"error: could not initialize database from seed CSVs: {error}", file=sys.stderr)
        return 1
    print(
        f"Initialized {database} from seed CSVs: "
        f"societies={society_count}, funds={fund_count}",
        flush=True,
    )
    for provider, script_name, csv_name in IMPORTS:
        command = [
            sys.executable, str(script_dir / script_name),
            "--input", str(input_dir / csv_name),
            "--database", str(database),
        ]
        print(f"Importing {provider} history...", flush=True)
        result = subprocess.run(command, cwd=script_dir, check=False)
        if result.returncode != 0:
            print(f"error: {script_name} failed with exit status {result.returncode}", file=sys.stderr)
            return result.returncode
    print(f"Imported all histories into {database}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
