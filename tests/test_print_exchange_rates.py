from datetime import date
from decimal import Decimal

import print_exchange_rates as script
from ticker.config import Settings
from ticker.database import connect, insert_exchange_rate


def test_prints_all_exchange_rates_in_effective_date_order(tmp_path, capsys) -> None:
    database_path = tmp_path / "ticker.sqlite3"
    with connect(database_path) as connection:
        insert_exchange_rate(connection, date(2026, 7, 15), Decimal("117.20"))
        insert_exchange_rate(
            connection, date(2026, 7, 14), Decimal("1171.00"), eur_unit=10
        )

    script.print_exchange_rates(database_path)

    assert capsys.readouterr().out == (
        "Exchange rate (2026-07-14): 10 EUR = 1171.00 RSD\n"
        "Exchange rate (2026-07-15): 1 EUR = 117.20 RSD\n"
    )


def test_prints_no_data_for_empty_database(tmp_path, capsys) -> None:
    script.print_exchange_rates(tmp_path / "ticker.sqlite3")

    assert capsys.readouterr().out == "Exchange rates: no data\n"


def test_main_uses_database_path_from_settings(tmp_path, monkeypatch, capsys) -> None:
    database_path = tmp_path / "configured.sqlite3"
    with connect(database_path) as connection:
        insert_exchange_rate(connection, date(2026, 7, 15), Decimal("117.20"))

    settings = Settings(
        database_path=database_path,
        log_path=tmp_path / "ticker.log",
        lock_path=tmp_path / "ticker.lock",
        nbs_url="https://nbs.example/",
        http_timeout=15,
        http_retries=2,
        fund_adapter=None,
    )
    monkeypatch.setattr(script.Settings, "from_env", lambda: settings)

    assert script.main() == 0
    assert capsys.readouterr().out == (
        "Exchange rate (2026-07-15): 1 EUR = 117.20 RSD\n"
    )
