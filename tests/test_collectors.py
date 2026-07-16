import sqlite3
from datetime import date
from decimal import Decimal

import pytest
from collect_exchange_rate import run as run_exchange
from collect_fund_value import run as run_fund
from ticker.config import Settings
from ticker.database import connect
from ticker.funds import FundAdapterError, FundValue


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
    fund_id = "intesa-invest"
    fund_ids = ("fund-1", "fund-2")

    def __init__(self, records):
        self.records = records
        self.calls = 0

    def fetch(self, target_date, session, timeout):
        self.calls += 1
        return self.records


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
    <tr><th class="kurs_date">zvanični za 13.7.2026.</th></tr>
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
    session = Session("""<tbody><th class="kurs_date">indikativni na 13.7.2026.</th>
                      <th>EUR/RSD</th><th class="kurs_e">999,9</th></tbody>""")
    assert run_exchange(config, date(2026, 7, 11), session) == "unavailable"
    with sqlite3.connect(config.database_path) as connection:
        assert connection.execute("SELECT count(*) FROM exchange_rates").fetchone()[0] == 0


def test_fund_stores_all_intesa_rows_and_skips_second_run(tmp_path) -> None:
    config = settings(tmp_path)
    records = [
        FundValue(
            fund_id="fund-1",
            value_date=date(2026, 7, 10),
            investment_unit_value=Decimal("123.45"),
            investment_unit_currency="EUR",
            fund_assets_value=Decimal("9876.54"),
            fund_assets_currency="EUR",
            source_url="https://www.intesainvest.rs/",
        ),
        FundValue(
            fund_id="fund-2",
            value_date=date(2026, 7, 10),
            investment_unit_value=Decimal("222.22"),
            investment_unit_currency="RSD",
            fund_assets_value=Decimal("333.33"),
            fund_assets_currency="RSD",
            source_url="https://www.intesainvest.rs/",
        ),
    ]
    adapter = Adapter(records)
    assert run_fund(config, date(2026, 7, 11), Session(), adapter) == "inserted"
    assert run_fund(config, date(2026, 7, 11), Session(), adapter) == "already-present"
    assert adapter.calls == 1
    with sqlite3.connect(config.database_path) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM fund_values"
        ).fetchone()
    assert row == (2,)


def test_legacy_fund_values_are_migrated_without_source_url(tmp_path) -> None:
    database_path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """CREATE TABLE fund_values (
                   fund_id TEXT NOT NULL,
                   value_date TEXT NOT NULL,
                   investment_unit_value TEXT NOT NULL,
                   investment_unit_currency TEXT NOT NULL,
                   fund_assets_value TEXT NOT NULL,
                   fund_assets_currency TEXT NOT NULL,
                   source_url TEXT NOT NULL,
                   fetched_at_utc TEXT NOT NULL,
                   PRIMARY KEY (fund_id, value_date)
               )"""
        )
        connection.execute(
            "INSERT INTO fund_values VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("old-fund", "2026-07-10", "1", "EUR", "2", "EUR", "https://example.test", "now"),
        )

    with connect(database_path) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(fund_values)")]
        row = connection.execute(
            """SELECT society.society_id, fund.fund_id, value.value_date
               FROM fund_values AS value
               JOIN funds AS fund ON fund.id = value.fund_id
               JOIN societies AS society ON society.id = fund.society_id"""
        ).fetchone()

    assert "source_url" not in columns
    assert row == ("legacy", "old-fund", "2026-07-10")


def test_fund_schema_normalizes_societies_and_funds(tmp_path) -> None:
    config = settings(tmp_path)
    adapter = Adapter([fund_record("fund-1"), fund_record("fund-2")])

    assert run_fund(config, date(2026, 7, 11), Session(), adapter) == "inserted"

    with sqlite3.connect(config.database_path) as connection:
        society_columns = [row[1] for row in connection.execute("PRAGMA table_info(societies)")]
        fund_columns = [row[1] for row in connection.execute("PRAGMA table_info(funds)")]
        value_columns = [row[1] for row in connection.execute("PRAGMA table_info(fund_values)")]
        rows = connection.execute(
            """SELECT society.id, fund.id, value.id, society.society_id, fund.fund_id
               FROM fund_values AS value
               JOIN funds AS fund ON fund.id = value.fund_id
               JOIN societies AS society ON society.id = fund.society_id
               ORDER BY fund.fund_id"""
        ).fetchall()

    assert society_columns[0] == "id"
    assert fund_columns[:2] == ["id", "society_id"]
    assert value_columns[:2] == ["id", "fund_id"]
    assert "source_url" not in value_columns
    assert rows == [
        (1, 1, 1, "intesa-invest", "fund-1"),
        (1, 2, 2, "intesa-invest", "fund-2"),
    ]


def test_fund_targets_calendar_yesterday_and_skips_fetch_when_present(tmp_path) -> None:
    config = settings(tmp_path)
    records = [
        FundValue(
            fund_id=fund_id,
            value_date=date(2026, 7, 12),
            investment_unit_value=Decimal("10.25"),
            investment_unit_currency="EUR",
            fund_assets_value=Decimal("1000.50"),
            fund_assets_currency="EUR",
            source_url="https://fund.example/",
        )
        for fund_id in Adapter.fund_ids
    ]
    adapter = Adapter(records)

    assert run_fund(config, date(2026, 7, 13), Session(), adapter) == "inserted"
    assert run_fund(config, date(2026, 7, 13), Session(), adapter) == "already-present"
    assert adapter.calls == 1


def test_fund_unconfigured_is_a_noop(tmp_path) -> None:
    assert run_fund(settings(tmp_path), date(2026, 7, 11)) == "not-configured"


class ProviderAdapter:
    def __init__(self, fund_id, records=None, error=None):
        self.fund_id = fund_id
        self.fund_ids = tuple(record.fund_id for record in records or ())
        self.records = records or []
        self.error = error
        self.calls = 0

    def fetch(self, target_date, session, timeout):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.records


def fund_record(fund_id: str) -> FundValue:
    return FundValue(
        fund_id=fund_id,
        value_date=date(2026, 7, 10),
        investment_unit_value=Decimal("10.25"),
        investment_unit_currency="EUR",
        fund_assets_value=Decimal("1000.50"),
        fund_assets_currency="EUR",
        source_url="https://fund.example/",
    )


def test_fund_collects_multiple_providers(tmp_path) -> None:
    config = settings(tmp_path)
    first = ProviderAdapter("provider-1", [fund_record("provider-1-fund")])
    second = ProviderAdapter("provider-2", [fund_record("provider-2-fund")])

    assert run_fund(config, date(2026, 7, 11), Session(), [first, second]) == "inserted"
    assert run_fund(config, date(2026, 7, 11), Session(), [first, second]) == "already-present"
    assert first.calls == second.calls == 1
    with sqlite3.connect(config.database_path) as connection:
        rows = connection.execute(
            "SELECT fund.fund_id FROM fund_values AS value "
            "JOIN funds AS fund ON fund.id = value.fund_id ORDER BY fund.fund_id"
        )
        ids = [row[0] for row in rows]
    assert ids == ["provider-1-fund", "provider-2-fund"]


def test_fund_partial_failure_commits_successful_provider(tmp_path) -> None:
    config = settings(tmp_path)
    failed = ProviderAdapter("provider-bad", error=RuntimeError("broken"))
    successful = ProviderAdapter("provider-good", [fund_record("provider-good-fund")])

    assert run_fund(config, date(2026, 7, 11), Session(), [failed, successful]) == "partial"
    with sqlite3.connect(config.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM fund_values").fetchone() == (1,)


def test_fund_raises_when_all_providers_fail(tmp_path) -> None:
    adapters = [
        ProviderAdapter("provider-1", error=RuntimeError("first")),
        ProviderAdapter("provider-2", error=RuntimeError("second")),
    ]
    with pytest.raises(FundAdapterError, match="All configured fund providers failed"):
        run_fund(settings(tmp_path), date(2026, 7, 11), Session(), adapters)
