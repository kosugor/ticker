import sqlite3

from import_usd_exchange_rates import import_directory


def test_imports_second_and_last_columns_and_is_idempotent(tmp_path) -> None:
    input_directory = tmp_path / "usd"
    input_directory.mkdir()
    (input_directory / "one.csv").write_text(
        "Датум формирања,Датум примене,Валута,Назив земље,Ознака,Важи за,Средњи курс\n"
        "31.12.2007,01.01.2008,840,United States,USD,1,53.7267\n"
        "03.01.2008,03.01.2008,840,United States,USD,1,54.2016\n",
        encoding="utf-8",
    )
    database = tmp_path / "ticker.sqlite3"

    assert import_directory(input_directory, database) == (2, 2)
    assert import_directory(input_directory, database) == (2, 0)

    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT effective_date, middle_rate FROM usd_exchange_rates "
            "ORDER BY effective_date"
        ).fetchall() == [
            ("2008-01-01", "53.7267"),
            ("2008-01-03", "54.2016"),
        ]

        assert [row[1] for row in connection.execute(
            "PRAGMA table_info(usd_exchange_rates)"
        )] == ["effective_date", "middle_rate"]
