from datetime import date
from decimal import Decimal

import pytest

from ticker.funds import FundAdapterError, load_adapters
from ticker.raiffeisen_invest import (
    HOME_URL,
    RaiffeisenInvestAdapter,
    parse_homepage_fund_values,
)


FUNDS = (
    ("raiffeisen-cash", "raiffeisen-invest-cash", "RSD", "2.418,43", "25.464.397.207,48"),
    ("raiffeisen-euro-cash-4", "raiffeisen-invest-euro-cash", "EUR", "10,89", "679.004.101,16"),
    ("raiffeisen-dollar-bond", "raiffeisen-invest-dollar-bond", "USD", "9,97", "9.791.729,78"),
    ("raiffeisen-bond", "raiffeisen-invest-bond", "EUR", "10,87", "55.879.548,20"),
    ("raiffeisen-green", "raiffeisen-invest-green", "EUR", "10,92", "1.122.378,48"),
    ("raiffeisen-world", "raiffeisen-invest-world", "EUR", "15,88", "15.416.450,35"),
    ("raiffeisen-alternative", "raiffeisen-invest-alternative", "EUR", "142,76", "89.388.072,51"),
    (
        "raiffeisen-gold-alternative-otvoreni-alternativni-investicioni-fond-sa-jp",
        "raiffeisen-invest-gold-alternative",
        "EUR",
        "9,06",
        "606.384,44",
    ),
    (
        "grawe-equity-global-1",
        "raiffeisen-invest-grawe-equity-global-1",
        "EUR",
        "15,41",
        "7.706.833,53",
    ),
    (
        "grawe-equity-global-2",
        "raiffeisen-invest-grawe-equity-global-2",
        "EUR",
        "15,43",
        "7.714.353,09",
    ),
)


def card(slug: str, currency: str, unit: str, assets: str, value_date="13.07.2026") -> str:
    other_currency = "RSD" if currency != "RSD" else None
    unit_value = f"{unit} {currency}"
    assets_value = f"{assets} {currency}"
    if other_currency:
        unit_value += f" | 1.278,07 {other_currency}"
        assets_value += f" 79.690.501.528,02 {other_currency}"
    return f"""
    <div class="card"><a href="https://www.raiffeiseninvest.rs/fond/{slug}/">
      <div class="data-item"><p class="data-item_title">Vrednosti na dan:</p>
        <p class="data-item_value"><span>{value_date}</span></p></div>
      <div class="data-item"><p class="data-item_title">Vrednost investicione jedinice:</p>
        <p class="data-item_value">{unit_value}</p></div>
      <div class="data-item"><p class="data-item_title">Vrednost imovine fonda:</p>
        <p class="data-item_value">{assets_value}</p></div>
    </a></div>"""


HTML = "<html><body>" + "".join(
    card(slug, currency, unit, assets) for slug, _, currency, unit, assets in FUNDS
) + "</body></html>"


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


def test_parses_all_homepage_funds_in_native_currencies() -> None:
    records = parse_homepage_fund_values(HTML, date(2026, 7, 13), HOME_URL)
    assert [record.fund_id for record in records] == [item[1] for item in FUNDS]
    assert [record.investment_unit_currency for record in records] == [item[2] for item in FUNDS]
    assert records[0].investment_unit_value == Decimal("2418.43")
    assert records[0].fund_assets_value == Decimal("25464397207.48")
    assert records[2].investment_unit_value == Decimal("9.97")
    assert records[2].fund_assets_currency == "USD"
    assert records[-1].fund_assets_value == Decimal("7714353.09")


def test_filters_other_dates_and_ignores_unknown_funds() -> None:
    html = card("raiffeisen-cash", "RSD", "2.418,43", "25.464.397.207,48", "12.07.2026")
    html += card("new-fund", "EUR", "1,00", "2,00")
    assert parse_homepage_fund_values(html, date(2026, 7, 13)) == []


def test_rejects_duplicate_known_fund() -> None:
    duplicate = card("raiffeisen-cash", "RSD", "2.418,43", "25.464.397.207,48")
    with pytest.raises(FundAdapterError, match="Duplicate Raiffeisen Invest"):
        parse_homepage_fund_values(duplicate + duplicate, date(2026, 7, 13))


def test_rejects_missing_native_currency() -> None:
    html = card("raiffeisen-dollar-bond", "EUR", "9,97", "9.791.729,78")
    with pytest.raises(FundAdapterError, match="does not include currency USD"):
        parse_homepage_fund_values(html, date(2026, 7, 13))


def test_rejects_missing_required_field() -> None:
    broken = card("raiffeisen-cash", "RSD", "2.418,43", "25.464.397.207,48").replace(
        "Vrednost imovine fonda:", "Broken:"
    )
    with pytest.raises(FundAdapterError, match="Missing Vrednost imovine fonda"):
        parse_homepage_fund_values(broken, date(2026, 7, 13))


def test_adapter_fetches_homepage_once() -> None:
    session = Session()
    records = RaiffeisenInvestAdapter().fetch(date(2026, 7, 13), session, 4.5)
    assert len(records) == 10
    assert session.calls == [(HOME_URL, 4.5)]
    assert session.response.checked


def test_loads_comma_separated_adapters() -> None:
    adapters = load_adapters(" intesa_invest, raiffeisen_invest ")
    assert [adapter.fund_id for adapter in adapters] == ["intesa-invest", "raiffeisen-invest"]


@pytest.mark.parametrize("names", ["intesa_invest,", "intesa_invest,intesa_invest"])
def test_rejects_invalid_adapter_lists(names) -> None:
    with pytest.raises(FundAdapterError):
        load_adapters(names)


def test_rejects_invalid_date() -> None:
    html = card("raiffeisen-cash", "RSD", "2.418,43", "25.464.397.207,48", "31.02.2026")
    with pytest.raises(FundAdapterError, match="Invalid Raiffeisen Invest value date"):
        parse_homepage_fund_values(html, date(2026, 7, 13))


def test_rejects_non_positive_amount() -> None:
    html = card("raiffeisen-cash", "RSD", "0,00", "25.464.397.207,48")
    with pytest.raises(FundAdapterError, match="must be positive"):
        parse_homepage_fund_values(html, date(2026, 7, 13))
