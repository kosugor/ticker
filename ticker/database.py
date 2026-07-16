from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS exchange_rates (
    effective_date TEXT PRIMARY KEY,
    eur_unit INTEGER NOT NULL CHECK (eur_unit > 0),
    middle_rate TEXT NOT NULL,
    fetched_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS societies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    society_id TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS funds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    society_id INTEGER NOT NULL REFERENCES societies(id),
    fund_id TEXT NOT NULL,
    UNIQUE (society_id, fund_id)
);

CREATE TABLE IF NOT EXISTS fund_values (
    fund_id INTEGER NOT NULL REFERENCES funds(id),
    value_date TEXT NOT NULL,
    investment_unit_value TEXT NOT NULL,
    investment_unit_currency TEXT NOT NULL,
    fund_assets_value TEXT NOT NULL,
    fund_assets_currency TEXT NOT NULL,
    fetched_at_utc TEXT NOT NULL,
    PRIMARY KEY (value_date, fund_id)
);
CREATE INDEX IF NOT EXISTS idx_funds_fund_id ON funds(fund_id);
"""


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.executescript(SCHEMA)
        _migrate_fund_values(connection)
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _migrate_fund_values(connection: sqlite3.Connection) -> None:
    columns = {
        row[1]: row for row in connection.execute("PRAGMA table_info(fund_values)")
    }
    if (
        set(columns)
        == {
            "fund_id",
            "value_date",
            "investment_unit_value",
            "investment_unit_currency",
            "fund_assets_value",
            "fund_assets_currency",
            "fetched_at_utc",
        }
        and columns["value_date"][5] == 1
        and columns["fund_id"][5] == 2
    ):
        return

    connection.execute("ALTER TABLE fund_values RENAME TO legacy_fund_values")
    connection.execute("DROP INDEX IF EXISTS idx_fund_values_value_date")
    connection.executescript(
        """CREATE TABLE fund_values (
               fund_id INTEGER NOT NULL REFERENCES funds(id),
               value_date TEXT NOT NULL,
               investment_unit_value TEXT NOT NULL,
               investment_unit_currency TEXT NOT NULL,
               fund_assets_value TEXT NOT NULL,
               fund_assets_currency TEXT NOT NULL,
               fetched_at_utc TEXT NOT NULL,
               PRIMARY KEY (value_date, fund_id)
           );"""
    )
    if "source_url" in columns:
        connection.execute("INSERT OR IGNORE INTO societies (society_id) VALUES ('legacy')")
        connection.execute(
            """INSERT OR IGNORE INTO funds (society_id, fund_id)
               SELECT society.id, legacy.fund_id
               FROM legacy_fund_values AS legacy
               CROSS JOIN societies AS society
               WHERE society.society_id = 'legacy'"""
        )
        connection.execute(
            """INSERT OR IGNORE INTO fund_values
               (fund_id, value_date, investment_unit_value, investment_unit_currency,
                fund_assets_value, fund_assets_currency, fetched_at_utc)
               SELECT fund.id, legacy.value_date, legacy.investment_unit_value,
                      legacy.investment_unit_currency, legacy.fund_assets_value,
                      legacy.fund_assets_currency, legacy.fetched_at_utc
               FROM legacy_fund_values AS legacy
               JOIN societies AS society ON society.society_id = 'legacy'
               JOIN funds AS fund
                 ON fund.society_id = society.id AND fund.fund_id = legacy.fund_id"""
        )
    else:
        connection.execute(
            """INSERT OR IGNORE INTO fund_values
               (fund_id, value_date, investment_unit_value, investment_unit_currency,
                fund_assets_value, fund_assets_currency, fetched_at_utc)
               SELECT fund_id, value_date, investment_unit_value,
                      investment_unit_currency, fund_assets_value,
                      fund_assets_currency, fetched_at_utc
               FROM legacy_fund_values"""
        )
    connection.execute("DROP TABLE legacy_fund_values")

def exchange_rate_exists(connection: sqlite3.Connection, effective_date: date) -> bool:
    row = connection.execute(
        "SELECT 1 FROM exchange_rates WHERE effective_date = ?", (effective_date.isoformat(),)
    ).fetchone()
    return row is not None


def insert_exchange_rate(
    connection: sqlite3.Connection, effective_date: date, rate: Decimal, eur_unit: int = 1
) -> bool:
    cursor = connection.execute(
        """INSERT OR IGNORE INTO exchange_rates
           (effective_date, eur_unit, middle_rate, fetched_at_utc)
           VALUES (?, ?, ?, ?)""",
        (
            effective_date.isoformat(),
            eur_unit,
            str(rate),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    return cursor.rowcount == 1


def fund_value_exists(
    connection: sqlite3.Connection, society_id: str, fund_id: str, value_date: date
) -> bool:
    row = connection.execute(
        """SELECT 1
           FROM fund_values AS value
           JOIN funds AS fund ON fund.id = value.fund_id
           JOIN societies AS society ON society.id = fund.society_id
           WHERE society.society_id = ? AND fund.fund_id = ? AND value.value_date = ?""",
        (society_id, fund_id, value_date.isoformat()),
    ).fetchone()
    return row is not None


def insert_fund_value(connection: sqlite3.Connection, society_id: str, record: object) -> bool:
    connection.execute(
        "INSERT OR IGNORE INTO societies (society_id) VALUES (?)", (society_id,)
    )
    connection.execute(
        """INSERT OR IGNORE INTO funds (society_id, fund_id)
           SELECT id, ? FROM societies WHERE society_id = ?""",
        (record.fund_id, society_id),
    )
    cursor = connection.execute(
        """INSERT OR IGNORE INTO fund_values
           (fund_id, value_date, investment_unit_value, investment_unit_currency,
            fund_assets_value, fund_assets_currency, fetched_at_utc)
           SELECT id, ?, ?, ?, ?, ?, ?
           FROM funds
           WHERE fund_id = ?
             AND society_id = (SELECT id FROM societies WHERE society_id = ?)""",
        (
            record.value_date.isoformat(),
            str(record.investment_unit_value),
            record.investment_unit_currency,
            str(record.fund_assets_value),
            record.fund_assets_currency,
            datetime.now(timezone.utc).isoformat(),
            record.fund_id,
            society_id,
        ),
    )
    return cursor.rowcount == 1
