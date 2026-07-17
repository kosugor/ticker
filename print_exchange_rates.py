from __future__ import annotations

import sqlite3
from pathlib import Path

from ticker.config import Settings
from ticker.database import connect


def exchange_rates(connection: sqlite3.Connection):
    return connection.execute(
        """SELECT effective_date, middle_rate
           FROM eur_exchange_rates
           ORDER BY effective_date ASC"""
    ).fetchall()


def print_exchange_rates(database_path: Path) -> None:
    with connect(database_path) as connection:
        rows = exchange_rates(connection)

    if not rows:
        print("Exchange rates: no data")
        return

    for effective_date, middle_rate in rows:
        print(f"Exchange rate ({effective_date}): 1 EUR = {middle_rate} RSD")


def main() -> int:
    print_exchange_rates(Settings.from_env().database_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
