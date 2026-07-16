#!/usr/bin/env python3
"""Import every downloaded provider history CSV into one SQLite database."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


IMPORTS = (
    ("Eclectica Capital", "import_eclecticacapital_csv_to_sqlite.py", "eclecticacapital_history.csv"),
    ("Intesa Invest", "import_intesainvest_csv_to_sqlite.py", "intesainvest_history.csv"),
    ("NLB Fondovi", "import_nlbfondovi_csv_to_sqlite.py", "nlbfondovi_history.csv"),
    ("Raiffeisen Invest", "import_raiffeiseninvest_csv_to_sqlite.py", "raiffeiseninvest_history.csv"),
    ("UniCredit Invest", "import_unicreditinvest_csv_to_sqlite.py", "unicreditinvest_history.csv"),
    ("Vista Rica", "import_vistarica_csv_to_sqlite.py", "vistarica_history.csv"),
    ("WVP Fondovi", "import_wvpfondovi_csv_to_sqlite.py", "wvpfondovi_history.csv"),
)
DEFAULT_DATABASE = Path("data/ticker.sqlite3")


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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    script_dir = Path(__file__).resolve().parent
    input_dir = args.input_dir.resolve()
    database = args.database.resolve()
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
