from datetime import date
from decimal import Decimal

import pytest

from ticker.funds import FundAdapterError, load_adapter
from ticker.vista_rica import VistaRicaAdapter, _FUNDS, parse_fund_page


def page(definition, value_date="14. 07. 2026", unit="114,72", assets="30.633.796,26"):
    currency = definition.currency.casefold()
    return f"""
    <section id="stanje">
      <span class="vistarica-fund-value" data-slug="{definition.slug}"
            data-column="latest_date">{value_date}</span>
      <span class="vistarica-fund-value" data-slug="{definition.slug}"
            data-column="unit_{currency}">{unit}</span>
      <span class="vistarica-fund-value" data-slug="{definition.slug}"
            data-column="fund_{currency}">{assets}</span>
    </section>
    """


def test_parses_eur_and_rsd_fund_pages() -> None:
    eur = parse_fund_page(page(_FUNDS[0]), date(2026, 7, 14), _FUNDS[0])
    rsd = parse_fund_page(
        page(_FUNDS[2], unit="10.928,37", assets="2.182.870.099,78"),
        date(2026, 7, 14),
        _FUNDS[2],
    )

    assert eur is not None
    assert eur.fund_id == "vista-rica-invest"
    assert eur.investment_unit_value == Decimal("114.72")
    assert eur.fund_assets_value == Decimal("30633796.26")
    assert eur.investment_unit_currency == eur.fund_assets_currency == "EUR"
    assert rsd is not None
    assert rsd.investment_unit_value == Decimal("10928.37")
    assert rsd.fund_assets_value == Decimal("2182870099.78")
    assert rsd.investment_unit_currency == rsd.fund_assets_currency == "RSD"


def test_filters_other_date_before_parsing_values() -> None:
    html = page(_FUNDS[0], value_date="13. 07. 2026", unit="broken")
    assert parse_fund_page(html, date(2026, 7, 14), _FUNDS[0]) is None


def test_rejects_missing_section_field_and_bad_values() -> None:
    with pytest.raises(FundAdapterError, match="Missing Vista Rica value section"):
        parse_fund_page("<html></html>", date(2026, 7, 14), _FUNDS[0])
    with pytest.raises(FundAdapterError, match="unit_eur"):
        parse_fund_page(
            page(_FUNDS[0]).replace('data-column="unit_eur"', 'data-column="changed"'),
            date(2026, 7, 14),
            _FUNDS[0],
        )
    with pytest.raises(FundAdapterError, match="investment-unit value"):
        parse_fund_page(
            page(_FUNDS[0], unit="not-a-number"), date(2026, 7, 14), _FUNDS[0]
        )
    with pytest.raises(FundAdapterError, match="Invalid Vista Rica value date"):
        parse_fund_page(
            page(_FUNDS[0], value_date="31. 02. 2026"),
            date(2026, 7, 14),
            _FUNDS[0],
        )


class Response:
    def __init__(self, text):
        self.text = text
        self.checked = False

    def raise_for_status(self):
        self.checked = True


class Session:
    def __init__(self):
        self.calls = []
        self.responses = {
            definition.url: Response(page(definition)) for definition in _FUNDS
        }

    def get(self, url, timeout):
        self.calls.append((url, timeout))
        return self.responses[url]


def test_adapter_fetches_each_fund_page() -> None:
    session = Session()
    records = VistaRicaAdapter().fetch(date(2026, 7, 14), session, 4.5)

    assert [record.fund_id for record in records] == [
        definition.fund_id for definition in _FUNDS
    ]
    assert session.calls == [(definition.url, 4.5) for definition in _FUNDS]
    assert all(response.checked for response in session.responses.values())


def test_loads_vista_rica_adapter() -> None:
    adapter = load_adapter("vista_rica")
    assert isinstance(adapter, VistaRicaAdapter)
    assert adapter.fund_id == "vista-rica"
    assert len(adapter.fund_ids) == 5
