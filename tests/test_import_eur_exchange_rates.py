import sqlite3
from datetime import date
from decimal import Decimal

from import_eur_exchange_rates import import_directory
from ticker.database import connect, insert_exchange_rate


def test_imports_second_and_last_columns_and_is_idempotent(tmp_path) -> None:
    input_directory = tmp_path / "eur"
    input_directory.mkdir()
    (input_directory / "one.csv").write_text(
        "Датум формирања,Датум примене,Валута,Назив земље,Ознака,Важи за,Средњи курс\n"
        "31.12.2007,01.01.2008,978,EMU,EUR,1,79.2362\n"
        "03.01.2008,03.01.2008,978,EMU,EUR,1,79.7577\n",
        encoding="utf-8",
    )
    database = tmp_path / "ticker.sqlite3"

    assert import_directory(input_directory, database) == (2, 2)
    assert import_directory(input_directory, database) == (2, 0)

    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT effective_date, middle_rate FROM eur_exchange_rates "
            "ORDER BY effective_date"
        ).fetchall() == [
            ("2008-01-01", "79.2362"),
            ("2008-01-03", "79.7577"),
        ]


def test_migrates_legacy_exchange_rates_table(tmp_path) -> None:
    database = tmp_path / "ticker.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TABLE exchange_rates (
                effective_date TEXT PRIMARY KEY,
                eur_unit INTEGER NOT NULL,
                middle_rate TEXT NOT NULL,
                fetched_at_utc TEXT NOT NULL
            )"""
        )
        connection.execute(
            "INSERT INTO exchange_rates VALUES (?, ?, ?, ?)",
            ("2026-07-15", 1, "117.20", "2026-07-15T10:00:00+00:00"),
        )

    with connect(database) as connection:
        assert connection.execute(
            "SELECT effective_date, middle_rate FROM eur_exchange_rates"
        ).fetchall() == [("2026-07-15", "117.20")]
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'exchange_rates'"
        ).fetchone() is None
        assert [row[1] for row in connection.execute("PRAGMA table_info(eur_exchange_rates)")] == [
            "effective_date", "middle_rate"
        ]
        assert insert_exchange_rate(connection, date(2026, 7, 16), Decimal("117.30"))
