import sqlite3
from dataclasses import replace
from datetime import date
from decimal import Decimal

from collect_exchange_rate import run as run_exchange
from collect_fund_value import run as run_fund
from ticker.config import Settings
from ticker.funds import FundValue


class Response:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        return None


class Session:
    def __init__(self, text=""):
        self.text = text
        self.calls = 0

    def get(self, url, timeout):
        self.calls += 1
        return Response(self.text)


class Adapter:
    fund_id = "fund-1"

    def __init__(self, record):
        self.record = record
        self.calls = 0

    def fetch(self, target_date, session, timeout):
        self.calls += 1
        return self.record


def settings(tmp_path) -> Settings:
    return Settings(
        database_path=tmp_path / "db.sqlite3",
        log_path=tmp_path / "ticker.log",
        lock_path=tmp_path / "ticker.lock",
        nbs_url="https://example.invalid/nbs",
        http_timeout=1,
        http_retries=0,
        fund_adapter=None,
    )


def official_page() -> str:
    return """<table><tbody>
    <tr><th class="kurs_date">званични за 13.7.2026.</th></tr>
    <tr><th>EUR/RSD</th></tr><tr><th class="kurs_e">117,3638</th></tr>
    </tbody></table>"""


def test_exchange_insert_has_no_source_url_and_second_run_skips_http(tmp_path) -> None:
    config = settings(tmp_path)
    session = Session(official_page())
    assert run_exchange(config, date(2026, 7, 11), session) == "inserted"
    assert run_exchange(config, date(2026, 7, 11), session) == "already-present"
    assert session.calls == 1
    with sqlite3.connect(config.database_path) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(exchange_rates)")]
        row = connection.execute(
            "SELECT effective_date, middle_rate FROM exchange_rates"
        ).fetchone()
    assert "source_url" not in columns
    assert row == ("2026-07-13", "117.3638")


def test_indicative_only_is_not_stored(tmp_path) -> None:
    config = settings(tmp_path)
    session = Session("""<tbody><th class="kurs_date">индикативни на 13.7.2026.</th>
                      <th>EUR/RSD</th><th class="kurs_e">999,9</th></tbody>""")
    assert run_exchange(config, date(2026, 7, 11), session) == "unavailable"
    with sqlite3.connect(config.database_path) as connection:
        assert connection.execute("SELECT count(*) FROM exchange_rates").fetchone()[0] == 0


def test_fund_stores_both_values_in_separate_published_currencies(tmp_path) -> None:
    config = settings(tmp_path)
    record = FundValue(
        fund_id="fund-1",
        value_date=date(2026, 7, 10),
        investment_unit_value=Decimal("123.45"),
        investment_unit_currency="RSD",
        fund_assets_value=Decimal("9876.54"),
        fund_assets_currency="EUR",
        source_url="https://fund.example/value",
    )
    adapter = Adapter(record)
    assert run_fund(config, date(2026, 7, 11), Session(), adapter) == "inserted"
    assert run_fund(config, date(2026, 7, 11), Session(), adapter) == "already-present"
    assert adapter.calls == 1
    with sqlite3.connect(config.database_path) as connection:
        row = connection.execute(
            """SELECT investment_unit_value, investment_unit_currency,
                      fund_assets_value, fund_assets_currency FROM fund_values"""
        ).fetchone()
    assert row == ("123.45", "RSD", "9876.54", "EUR")


def test_fund_unconfigured_is_a_noop(tmp_path) -> None:
    assert run_fund(settings(tmp_path), date(2026, 7, 11)) == "not-configured"

