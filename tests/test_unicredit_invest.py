import json
from datetime import date
from decimal import Decimal

import pytest

from ticker.funds import FundAdapterError, load_adapter
from ticker.unicredit_invest import (
    FUNDS_API_URL,
    VALUES_URL,
    UniCreditInvestAdapter,
    parse_fund_values,
)


TARGET_DATE = date(2026, 7, 13)
PAYLOAD = {
    "data": [
        {
            "slug": "onemarkets-uc-invest-cash-dinar-fund",
            "currency": "RSD",
            "dailyValues": [{
                "date": "2026-07-13",
                "priceRSD": 1018.92,
                "priceEUR": None,
                "netAssets": 730808766.34,
                "netAssetsEUR": None,
            }],
        },
        {
            "slug": "onemarkets-uc-invest-cash-eur-fund",
            "currency": "EUR",
            "dailyValues": [{
                "date": "2026-07-13",
                "priceRSD": 1181.78,
                "priceEUR": 10.07,
                "netAssets": 491434893.36,
                "netAssetsEUR": 4187278.30,
            }],
        },
    ],
}


class Response:
    def __init__(self, payload):
        self.text = json.dumps(payload)
        self.checked = False

    def raise_for_status(self):
        self.checked = True


class Session:
    def __init__(self, payload=PAYLOAD):
        self.response = Response(payload)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_parses_all_funds_in_native_currencies() -> None:
    records = parse_fund_values(PAYLOAD, TARGET_DATE)
    assert [record.fund_id for record in records] == [
        "unicredit-invest-cash-dinar",
        "unicredit-invest-cash-eur",
    ]
    assert [record.investment_unit_currency for record in records] == ["RSD", "EUR"]
    assert records[0].investment_unit_value == Decimal("1018.92")
    assert records[0].fund_assets_value == Decimal("730808766.34")
    assert records[1].investment_unit_value == Decimal("10.07")
    assert records[1].fund_assets_value == Decimal("4187278.3")
    assert all(record.source_url == VALUES_URL for record in records)


def test_returns_no_rows_for_other_date() -> None:
    assert parse_fund_values(PAYLOAD, date(2026, 7, 14)) == []


def test_ignores_unknown_fund() -> None:
    assert parse_fund_values({"data": [{"slug": "unknown"}]}, TARGET_DATE) == []


def test_rejects_duplicate_known_fund() -> None:
    payload = {"data": [PAYLOAD["data"][0], PAYLOAD["data"][0]]}
    with pytest.raises(FundAdapterError, match="Duplicate UniCredit Invest fund entry"):
        parse_fund_values(payload, TARGET_DATE)


def test_rejects_duplicate_daily_value() -> None:
    fund = {**PAYLOAD["data"][0]}
    fund["dailyValues"] = fund["dailyValues"] * 2
    with pytest.raises(FundAdapterError, match="Duplicate UniCredit Invest daily value"):
        parse_fund_values({"data": [fund]}, TARGET_DATE)


def test_rejects_unexpected_currency() -> None:
    fund = {**PAYLOAD["data"][0], "currency": "EUR"}
    with pytest.raises(FundAdapterError, match="Unexpected UniCredit Invest currency"):
        parse_fund_values({"data": [fund]}, TARGET_DATE)


@pytest.mark.parametrize("value", [None, "not-a-number", 0, -1])
def test_rejects_invalid_native_amount(value) -> None:
    fund = {**PAYLOAD["data"][0]}
    fund["dailyValues"] = [{**fund["dailyValues"][0], "netAssets": value}]
    with pytest.raises(FundAdapterError, match="fund-assets value"):
        parse_fund_values({"data": [fund]}, TARGET_DATE)


def test_adapter_fetches_filtered_json_dataset() -> None:
    session = Session()
    records = UniCreditInvestAdapter().fetch(TARGET_DATE, session, 4.5)
    assert len(records) == 2
    assert session.response.checked
    url, kwargs = session.calls[0]
    assert url == FUNDS_API_URL
    assert kwargs["timeout"] == 4.5
    assert kwargs["params"]["populate[dailyValues][filters][date][$eq]"] == "2026-07-13"
    assert kwargs["params"]["pagination[pageSize]"] == 25


def test_loads_unicredit_adapter() -> None:
    adapter = load_adapter("unicredit_invest")
    assert isinstance(adapter, UniCreditInvestAdapter)
    assert adapter.fund_id == "unicredit-invest"
    assert adapter.fund_ids == (
        "unicredit-invest-cash-dinar",
        "unicredit-invest-cash-eur",
    )
