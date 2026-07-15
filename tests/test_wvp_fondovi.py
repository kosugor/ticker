from datetime import date
from decimal import Decimal

import pytest

from ticker.funds import FundAdapterError, load_adapter
from ticker.wvp_fondovi import DAILY_OVERVIEW_URL, WvpFondoviAdapter, parse_daily_overview


FUNDS = (
    ("WVP PREMIUM", "wvp-fondovi-premium", "2.325.742.523,44", "1.847,92326"),
    ("WVP DYNAMIC", "wvp-fondovi-dynamic", "1.369.644.089,30", "1.656,65513"),
    (
        "WVP BALANCED",
        "wvp-fondovi-balanced",
        "623.022.037,43",
        "1.445,87321",
    ),
    ("WVP CASH", "wvp-fondovi-cash", "778.166.707,77", "1.263,29377"),
    (
        "MERKUR ESG FUND BALANCED",
        "wvp-fondovi-merkur-esg-balanced",
        "149.457.249,50",
        "1.466,32927",
    ),
    ("MERKUR ESG FUND DYNAMIC", "wvp-fondovi-merkur-esg-dynamic", "186.402.909,32", "1.802,58153"),
    ("MERKUR ESG FUND SOLID", "wvp-fondovi-merkur-esg-solid", "120.954.893,12", "1.221,46991"),
    ("WVP BOND", "wvp-fondovi-bond", "1.153.142.806,10", "1.533,16912"),
)


def table(rows=FUNDS, value_date="13.07.2026") -> str:
    body = "".join(
        f"<tr><td>{name}</td><td>{value_date}</td><td>{assets}</td>"
        f"<td>1,00</td><td>{unit}</td><td>1,00</td><td>0.00%</td></tr>"
        for name, _, assets, unit in rows
    )
    return f"""
    <table class="wvp-fund-details-table">
      <thead><tr>
        <th>Fond</th><th>Datum</th>
        <th>Neto vrednost imovine fonda (RSD)</th>
        <th>Neto vrednost imovine fonda (EUR)</th>
        <th>Cena investicione jedinice (RSD)</th>
        <th>Cena investicione jedinice (EUR)</th><th>Dnevna promena</th>
      </tr></thead><tbody>{body}</tbody>
    </table>"""


HTML = table()


class Response:
    text = HTML

    def __init__(self):
        self.checked = False

    def raise_for_status(self):
        self.checked = True


class Session:
    def __init__(self):
        self.calls = []
        self.response = Response()

    def get(self, url, timeout):
        self.calls.append((url, timeout))
        return self.response


def test_parses_all_funds_in_rsd() -> None:
    records = parse_daily_overview(HTML, date(2026, 7, 13))
    assert [record.fund_id for record in records] == [item[1] for item in FUNDS]
    assert all(record.investment_unit_currency == "RSD" for record in records)
    assert all(record.fund_assets_currency == "RSD" for record in records)
    assert records[0].investment_unit_value == Decimal("1847.92326")
    assert records[0].fund_assets_value == Decimal("2325742523.44")
    assert records[-1].investment_unit_value == Decimal("1533.16912")
    assert all(record.source_url == DAILY_OVERVIEW_URL for record in records)


def test_filters_other_dates_and_ignores_unknown_funds() -> None:
    unknown = (("NEW FUND", "unused", "2,00", "1,00"),)
    assert parse_daily_overview(table(unknown), date(2026, 7, 13)) == []
    assert parse_daily_overview(HTML, date(2026, 7, 14)) == []


def test_rejects_duplicate_known_fund() -> None:
    with pytest.raises(FundAdapterError, match="Duplicate WVP Fondovi"):
        parse_daily_overview(table((FUNDS[0], FUNDS[0])), date(2026, 7, 13))


def test_rejects_missing_table_or_changed_headers() -> None:
    with pytest.raises(FundAdapterError, match="Missing WVP Fondovi"):
        parse_daily_overview("<html></html>", date(2026, 7, 13))
    with pytest.raises(FundAdapterError, match="Unexpected WVP Fondovi table headers"):
        parse_daily_overview(HTML.replace("Dnevna promena", "Changed"), date(2026, 7, 13))


@pytest.mark.parametrize("value", ["not-a-number", "0,00000"])
def test_rejects_invalid_amount(value) -> None:
    broken = table((("WVP PREMIUM", "unused", "2.000,00", value),))
    with pytest.raises(FundAdapterError, match="investment-unit value"):
        parse_daily_overview(broken, date(2026, 7, 13))


def test_rejects_invalid_date() -> None:
    with pytest.raises(FundAdapterError, match="Invalid WVP Fondovi value date"):
        parse_daily_overview(table(value_date="31.02.2026"), date(2026, 7, 13))


def test_adapter_fetches_daily_overview_once() -> None:
    session = Session()
    records = WvpFondoviAdapter().fetch(date(2026, 7, 13), session, 4.5)
    assert len(records) == 8
    assert session.calls == [(DAILY_OVERVIEW_URL, 4.5)]
    assert session.response.checked


def test_loads_wvp_adapter() -> None:
    adapter = load_adapter("wvp_fondovi")
    assert isinstance(adapter, WvpFondoviAdapter)
    assert adapter.fund_id == "wvp-fondovi"
    assert len(adapter.fund_ids) == 8
