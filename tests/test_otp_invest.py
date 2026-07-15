import json
from datetime import date
from decimal import Decimal

import pytest

from ticker.funds import FundAdapterError, load_adapter
from ticker.otp_invest import TABLE_API_URL, VALUES_URL, OtpInvestAdapter, parse_fund_values


VALUE_DATE = 1783900800000
UNIT_PAYLOAD = [
    {"type": "OTP Dynamic", "latestValue": 523.63129, "latestValueEur": 4.46161, "latestValueDate": VALUE_DATE},
    {"type": "OTP Balanced", "latestValue": 2469.14979, "latestValueEur": 21.03843, "latestValueDate": VALUE_DATE},
    {"type": "OTP Cash Dinar", "latestValue": 2278.14783, "latestValueEur": 19.41099, "latestValueDate": VALUE_DATE},
    {"type": "OTP ProActive", "latestValue": 1054.24676, "latestValueEur": 8.98273, "latestValueDate": VALUE_DATE},
    {"type": "OTP Euro Cash", "latestValue": 1231.91863, "latestValueEur": 10.49658, "latestValueDate": VALUE_DATE},
    {"type": "OTP Alternative", "latestValue": 11285.69447, "latestValueEur": 96.15993, "latestValueDate": VALUE_DATE},
]
ASSETS_PAYLOAD = [
    {"type": item["type"], "netValue": 1000000 + index, "netValueEur": 10000 + index, "netValueDate": VALUE_DATE}
    for index, item in enumerate(UNIT_PAYLOAD)
]


class Response:
    def __init__(self, payload):
        self.text = json.dumps(payload)
        self.checked = False

    def raise_for_status(self):
        self.checked = True


class Session:
    def __init__(self):
        self.calls = []
        self.responses = [Response(UNIT_PAYLOAD), Response(ASSETS_PAYLOAD)]

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses[len(self.calls) - 1]


def test_parses_all_funds_in_native_currencies() -> None:
    records = parse_fund_values(UNIT_PAYLOAD, ASSETS_PAYLOAD, date(2026, 7, 13))
    assert [record.fund_id for record in records] == [
        "otp-invest-dynamic", "otp-invest-balanced", "otp-invest-cash-dinar",
        "otp-invest-proactive", "otp-invest-euro-cash", "otp-invest-alternative",
    ]
    assert [record.investment_unit_currency for record in records] == [
        "RSD", "RSD", "RSD", "RSD", "EUR", "RSD",
    ]
    assert records[0].investment_unit_value == Decimal("523.63129")
    assert records[0].fund_assets_value == Decimal("1000000")
    assert records[4].investment_unit_value == Decimal("10.49658")
    assert records[4].fund_assets_value == Decimal("10004")
    assert all(record.source_url == VALUES_URL for record in records)


def test_returns_no_rows_for_other_date() -> None:
    assert parse_fund_values(UNIT_PAYLOAD, ASSETS_PAYLOAD, date(2026, 7, 14)) == []


def test_ignores_unknown_fund() -> None:
    unknown = [{"type": "Unknown"}]
    assert parse_fund_values(unknown, unknown, date(2026, 7, 13)) == []


def test_rejects_duplicate_known_fund() -> None:
    with pytest.raises(FundAdapterError, match="Duplicate OTP Invest investment-unit"):
        parse_fund_values(
            [UNIT_PAYLOAD[0], UNIT_PAYLOAD[0]], ASSETS_PAYLOAD, date(2026, 7, 13)
        )


def test_rejects_missing_assets_for_current_value() -> None:
    with pytest.raises(FundAdapterError, match="Missing OTP Invest fund-assets entry"):
        parse_fund_values([UNIT_PAYLOAD[0]], [], date(2026, 7, 13))


def test_rejects_mismatched_dates() -> None:
    assets = [{**ASSETS_PAYLOAD[0], "netValueDate": 1783987200000}]
    with pytest.raises(FundAdapterError, match="value dates do not match"):
        parse_fund_values([UNIT_PAYLOAD[0]], assets, date(2026, 7, 13))


@pytest.mark.parametrize("value", [None, "not-a-number", 0, -1])
def test_rejects_invalid_native_amount(value) -> None:
    assets = [{**ASSETS_PAYLOAD[0], "netValue": value}]
    with pytest.raises(FundAdapterError, match="fund-assets value"):
        parse_fund_values([UNIT_PAYLOAD[0]], assets, date(2026, 7, 13))


def test_adapter_fetches_both_json_datasets() -> None:
    session = Session()
    records = OtpInvestAdapter().fetch(date(2026, 7, 13), session, 4.5)
    assert len(records) == 6
    assert session.calls == [
        (
            TABLE_API_URL,
            {
                "headers": {"Referer": VALUES_URL},
                "params": {"apiEndpointUrl": "growthValueAll"},
                "timeout": 4.5,
            },
        ),
        (
            TABLE_API_URL,
            {
                "headers": {"Referer": VALUES_URL},
                "params": {"apiEndpointUrl": "netValueAll"},
                "timeout": 4.5,
            },
        ),
    ]
    assert all(response.checked for response in session.responses)


def test_loads_otp_adapter() -> None:
    adapter = load_adapter("otp_invest")
    assert isinstance(adapter, OtpInvestAdapter)
    assert adapter.fund_id == "otp-invest"
    assert len(adapter.fund_ids) == 6
