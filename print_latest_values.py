from __future__ import annotations

import sqlite3
from pathlib import Path

from ticker.config import Settings
from ticker.database import connect


def latest_exchange_rate(connection: sqlite3.Connection):
    return connection.execute(
        """SELECT effective_date, eur_unit, middle_rate
           FROM exchange_rates
           ORDER BY effective_date DESC
           LIMIT 1"""
    ).fetchone()


def latest_fund_values(connection: sqlite3.Connection):
    return connection.execute(
        """SELECT fund_id, value_date, investment_unit_value,
                  investment_unit_currency, fund_assets_value,
                  fund_assets_currency
           FROM fund_values
           WHERE value_date = (SELECT MAX(value_date) FROM fund_values)
           ORDER BY fund_id"""
    ).fetchall()


def print_latest_values(database_path: Path) -> None:
    with connect(database_path) as connection:
        exchange_rate = latest_exchange_rate(connection)
        fund_values = latest_fund_values(connection)

    if exchange_rate is None:
        print("Exchange rate: no data")
    else:
        effective_date, eur_unit, middle_rate = exchange_rate
        print(f"Exchange rate ({effective_date}): {eur_unit} EUR = {middle_rate} RSD")

    if not fund_values:
        print("Fund values: no data")
        return

    print(f"Fund values ({fund_values[0][1]}):")
    for (
        fund_id,
        _value_date,
        unit_value,
        unit_currency,
        assets_value,
        assets_currency,
    ) in fund_values:
        print(
            f"  {fund_id}: unit={unit_value} {unit_currency}, "
            f"assets={assets_value} {assets_currency}"
        )


def main() -> int:
    print_latest_values(Settings.from_env().database_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
