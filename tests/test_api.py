from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from ticker.api import create_app
from ticker.config import Settings
from ticker.database import connect, insert_exchange_rate, insert_fund_value
from ticker.funds import FundValue


def settings(database_path) -> Settings:
    return Settings(
        database_path=database_path,
        log_path=database_path.parent / "ticker.log",
        lock_path=database_path.parent / "ticker.lock",
        nbs_url="https://nbs.example/",
        http_timeout=15,
        http_retries=2,
        fund_adapter=None,
    )


def fund_value(fund_id: str, value_date: date, value: str) -> FundValue:
    return FundValue(
        fund_id=fund_id,
        value_date=value_date,
        investment_unit_value=Decimal(value),
        investment_unit_currency="EUR",
        fund_assets_value=Decimal("1000.50"),
        fund_assets_currency="EUR",
        source_url=f"https://fund.example/{fund_id}",
    )


def populated_client(tmp_path) -> TestClient:
    database_path = tmp_path / "ticker.sqlite3"
    with connect(database_path) as connection:
        insert_exchange_rate(connection, date(2026, 7, 14), Decimal("117.10"))
        insert_exchange_rate(connection, date(2026, 7, 15), Decimal("117.20"))
        insert_fund_value(
            connection, fund_value("old-fund", date(2026, 7, 13), "9.00")
        )
        insert_fund_value(
            connection, fund_value("fund-b", date(2026, 7, 14), "20.00")
        )
        insert_fund_value(
            connection, fund_value("fund-a", date(2026, 7, 14), "10.00")
        )

    return TestClient(create_app(settings(database_path)))


def test_health(tmp_path) -> None:
    client = TestClient(create_app(settings(tmp_path / "ticker.sqlite3")))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_homepage_and_static_assets_are_served(tmp_path) -> None:
    client = TestClient(create_app(settings(tmp_path / "ticker.sqlite3")))

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Ticker Dashboard" in response.text
    assert 'id="latest"' in response.text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/styles.css").status_code == 200


def test_lists_exchange_rates_newest_first(tmp_path) -> None:
    response = populated_client(tmp_path).get("/exchange-rates")

    assert response.status_code == 200
    rows = response.json()
    assert [row["effective_date"] for row in rows] == ["2026-07-15", "2026-07-14"]
    assert rows[0]["eur_unit"] == 1
    assert rows[0]["middle_rate"] == "117.20"
    assert rows[0]["fetched_at_utc"]


def test_filters_exchange_rates_by_date_range(tmp_path) -> None:
    response = populated_client(tmp_path).get(
        "/exchange-rates",
        params={"start_date": "2026-07-15", "end_date": "2026-07-15"},
    )

    assert response.status_code == 200
    assert [row["effective_date"] for row in response.json()] == ["2026-07-15"]


def test_lists_fund_values_by_date_then_fund_id(tmp_path) -> None:
    response = populated_client(tmp_path).get("/fund-values")

    assert response.status_code == 200
    rows = response.json()
    assert [(row["value_date"], row["fund_id"]) for row in rows] == [
        ("2026-07-14", "fund-a"),
        ("2026-07-14", "fund-b"),
        ("2026-07-13", "old-fund"),
    ]
    assert rows[0]["investment_unit_value"] == "10.00"
    assert rows[0]["investment_unit_currency"] == "EUR"
    assert rows[0]["fund_assets_value"] == "1000.50"
    assert rows[0]["fund_assets_currency"] == "EUR"
    assert rows[0]["source_url"] == "https://fund.example/fund-a"
    assert rows[0]["fetched_at_utc"]


def test_filters_fund_values_by_date_range_and_fund_id(tmp_path) -> None:
    response = populated_client(tmp_path).get(
        "/fund-values",
        params={
            "start_date": "2026-07-14",
            "end_date": "2026-07-14",
            "fund_id": "fund-b",
        },
    )

    assert response.status_code == 200
    assert [(row["value_date"], row["fund_id"]) for row in response.json()] == [
        ("2026-07-14", "fund-b")
    ]


def test_latest_values_uses_each_most_recent_date(tmp_path) -> None:
    response = populated_client(tmp_path).get("/latest-values")

    assert response.status_code == 200
    payload = response.json()
    assert payload["exchange_rate"]["effective_date"] == "2026-07-15"
    assert [row["fund_id"] for row in payload["fund_values"]] == [
        "fund-a",
        "fund-b",
    ]
    assert {row["value_date"] for row in payload["fund_values"]} == {"2026-07-14"}


def test_data_endpoints_return_empty_json_for_empty_database(tmp_path) -> None:
    client = TestClient(create_app(settings(tmp_path / "ticker.sqlite3")))

    assert client.get("/exchange-rates").json() == []
    assert client.get("/fund-values").json() == []
    assert client.get("/latest-values").json() == {
        "exchange_rate": None,
        "fund_values": [],
    }
