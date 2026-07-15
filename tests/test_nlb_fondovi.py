from datetime import date
from decimal import Decimal

import pytest

from ticker.funds import FundAdapterError, load_adapter
from ticker.nlb_fondovi import (
    ARCHIVE_URL,
    FUNDS_URL,
    NlbFondoviAdapter,
    parse_fund_values,
)


PAYLOAD = {
    "funds": [
        {
            "fund": {
                "id": "2002",
                "name": "NLB Devizni",
                "nav4": "10,17809",
                "nav4Rsd": "1194,53912",
                "subfundSize": "31119049,31",
                "subfundSizeRs": "3652249879,99",
            }
        },
        {
            "fund": {
                "id": "2001",
                "name": "NLB Novčani",
                "nav4": "14,60415",
                "nav4Rsd": "1713,99870",
                "subfundSize": "22881745,67",
                "subfundSizeRs": "2685488622,07",
            }
        },
        {
            "fund": {
                "id": "2003",
                "name": "NLB Globalni Balansirani",
                "nav4": "10,96559",
                "nav4Rsd": "1286,96285",
                "subfundSize": "5015661,75",
                "subfundSizeRs": "588657122,49",
            }
        },
        {
            "fund": {
                "id": "2004",
                "name": "NLB Globalni akcijski",
                "nav4": "114,94250",
                "nav4Rsd": "13490,08902",
                "subfundSize": "2654484,79",
                "subfundSizeRs": "311540421,97",
            }
        },
    ],
    "date": "13.07.2026",
}


class Response:
    def __init__(self):
        self.checked = False

    def raise_for_status(self):
        self.checked = True

    def json(self):
        return PAYLOAD


class Session:
    def __init__(self):
        self.calls = []
        self.response = Response()

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_parses_all_funds_in_native_currencies() -> None:
    records = parse_fund_values(PAYLOAD, date(2026, 7, 13))
    assert [record.fund_id for record in records] == [
        "nlb-fondovi-devizni",
        "nlb-fondovi-novcani",
        "nlb-fondovi-globalni-balansirani",
        "nlb-fondovi-globalni-akcijski",
    ]
    assert [record.investment_unit_currency for record in records] == [
        "EUR",
        "RSD",
        "EUR",
        "EUR",
    ]
    assert records[0].investment_unit_value == Decimal("10.17809")
    assert records[0].fund_assets_value == Decimal("31119049.31")
    assert records[1].investment_unit_value == Decimal("1713.99870")
    assert records[1].fund_assets_value == Decimal("2685488622.07")
    assert all(record.source_url == ARCHIVE_URL for record in records)


def test_returns_no_rows_for_other_date() -> None:
    assert parse_fund_values(PAYLOAD, date(2026, 7, 14)) == []


def test_ignores_unknown_fund() -> None:
    payload = {"date": "13.07.2026", "funds": [{"fund": {"id": "9999"}}]}
    assert parse_fund_values(payload, date(2026, 7, 13)) == []


def test_rejects_duplicate_known_fund() -> None:
    payload = {**PAYLOAD, "funds": [PAYLOAD["funds"][0], PAYLOAD["funds"][0]]}
    with pytest.raises(FundAdapterError, match="Duplicate NLB Fondovi"):
        parse_fund_values(payload, date(2026, 7, 13))


def test_rejects_changed_known_fund_name() -> None:
    payload = {
        "date": "13.07.2026",
        "funds": [{"fund": {**PAYLOAD["funds"][0]["fund"], "name": "Changed"}}],
    }
    with pytest.raises(FundAdapterError, match="Unexpected NLB Fondovi fund name"):
        parse_fund_values(payload, date(2026, 7, 13))


@pytest.mark.parametrize("value", ["", "not-a-number", "0,00000"])
def test_rejects_invalid_native_amount(value) -> None:
    payload = {
        "date": "13.07.2026",
        "funds": [
            {"fund": {**PAYLOAD["funds"][0]["fund"], "subfundSize": value}}
        ],
    }
    with pytest.raises(FundAdapterError, match="fund-assets value"):
        parse_fund_values(payload, date(2026, 7, 13))


def test_adapter_fetches_json_with_required_referer(monkeypatch) -> None:
    monkeypatch.setattr("ticker.nlb_fondovi.time.time", lambda: 1784116800.123)
    session = Session()
    records = NlbFondoviAdapter().fetch(date(2026, 7, 13), session, 4.5)
    assert len(records) == 4
    assert session.calls == [
        (
            FUNDS_URL,
            {
                "headers": {"Referer": ARCHIVE_URL},
                "params": {"timestamp": 1784116800123},
                "timeout": 4.5,
            },
        )
    ]
    assert session.response.checked


def test_loads_nlb_adapter() -> None:
    adapter = load_adapter("nlb_fondovi")
    assert isinstance(adapter, NlbFondoviAdapter)
    assert adapter.fund_id == "nlb-fondovi"
    assert len(adapter.fund_ids) == 4
