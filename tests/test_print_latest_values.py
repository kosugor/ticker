from datetime import date
from decimal import Decimal

from print_latest_values import print_latest_values
from ticker.database import connect, insert_exchange_rate, insert_fund_value
from ticker.funds import FundValue


def fund_value(fund_id: str, value_date: date, value: str) -> FundValue:
    return FundValue(
        fund_id=fund_id,
        value_date=value_date,
        investment_unit_value=Decimal(value),
        investment_unit_currency="EUR",
        fund_assets_value=Decimal("1000.50"),
        fund_assets_currency="EUR",
        source_url="https://fund.example/",
    )


def test_prints_only_values_from_each_latest_date(tmp_path, capsys) -> None:
    database_path = tmp_path / "ticker.sqlite3"
    with connect(database_path) as connection:
        insert_exchange_rate(connection, date(2026, 7, 14), Decimal("117.10"))
        insert_exchange_rate(connection, date(2026, 7, 15), Decimal("117.20"))
        insert_fund_value(
            connection, "fund-example", fund_value("old-fund", date(2026, 7, 13), "9.00")
        )
        insert_fund_value(
            connection, "fund-example", fund_value("fund-b", date(2026, 7, 14), "20.00")
        )
        insert_fund_value(
            connection, "fund-example", fund_value("fund-a", date(2026, 7, 14), "10.00")
        )

    print_latest_values(database_path)

    assert capsys.readouterr().out == (
        "Exchange rate (2026-07-15): 1 EUR = 117.20 RSD\n"
        "Fund values (2026-07-14):\n"
        "  fund-a: unit=10.00 EUR, assets=1000.50 EUR\n"
        "  fund-b: unit=20.00 EUR, assets=1000.50 EUR\n"
    )


def test_prints_no_data_for_empty_database(tmp_path, capsys) -> None:
    print_latest_values(tmp_path / "ticker.sqlite3")

    assert capsys.readouterr().out == (
        "Exchange rate: no data\n"
        "Fund values: no data\n"
    )
