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

CREATE TABLE IF NOT EXISTS fund_values (
    fund_id TEXT NOT NULL,
    value_date TEXT NOT NULL,
    investment_unit_value TEXT NOT NULL,
    investment_unit_currency TEXT NOT NULL,
    fund_assets_value TEXT NOT NULL,
    fund_assets_currency TEXT NOT NULL,
    source_url TEXT NOT NULL,
    fetched_at_utc TEXT NOT NULL,
    PRIMARY KEY (fund_id, value_date)
);
"""


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.executescript(SCHEMA)
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


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


def fund_value_exists(connection: sqlite3.Connection, fund_id: str, value_date: date) -> bool:
    row = connection.execute(
        "SELECT 1 FROM fund_values WHERE fund_id = ? AND value_date = ?",
        (fund_id, value_date.isoformat()),
    ).fetchone()
    return row is not None


def insert_fund_value(connection: sqlite3.Connection, record: object) -> bool:
    cursor = connection.execute(
        """INSERT OR IGNORE INTO fund_values
           (fund_id, value_date, investment_unit_value, investment_unit_currency,
            fund_assets_value, fund_assets_currency, source_url, fetched_at_utc)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            record.fund_id,
            record.value_date.isoformat(),
            str(record.investment_unit_value),
            record.investment_unit_currency,
            str(record.fund_assets_value),
            record.fund_assets_currency,
            record.source_url,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    return cursor.rowcount == 1

