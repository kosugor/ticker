from datetime import date
from decimal import Decimal

import pytest

from ticker.eclectica_capital import EclecticaCapitalAdapter, _FUNDS, parse_fund_page
from ticker.funds import FundAdapterError, load_adapter


def page(
    definition,
    unit_date="13.07.2026.",
    assets_date="13.07.2026.",
    unit="10,16159",
    assets="2.632.674,15",
):
    marker = "€" if definition.currency == "EUR" else "RSD"
    return f"""
    <div class="fund-kpis">
      <div class="fund-kpi">
        <div class="fund-kpi-title">Vrednost investicione jedinice</div>
        <div class="fund-kpi-sub">( Na dan: {unit_date} )</div>
        <div class="fund-kpi-value"><span>{marker}</span> {unit}</div>
      </div>
      <div class="fund-kpi">
        <div class="fund-kpi-title">Vrednost imovine fonda</div>
        <div class="fund-kpi-sub">( Na dan: {assets_date} )</div>
        <div class="fund-kpi-value"><span>{marker}</span> {assets}</div>
      </div>
      <div class="fund-kpi">
        <div class="fund-kpi-title">Indikator rizika</div>
        <div class="fund-kpi-value">1</div>
      </div>
    </div>
    """


def test_parses_euro_and_rsd_fund_pages() -> None:
    euro = parse_fund_page(page(_FUNDS[1]), date(2026, 7, 13), _FUNDS[1])
    rsd = parse_fund_page(
        page(
            _FUNDS[0],
            unit="1.025,37573",
            assets="222.378.577,26",
        ),
        date(2026, 7, 13),
        _FUNDS[0],
    )

    assert euro is not None
    assert euro.fund_id == "eclectica-capital-euro-cash"
    assert euro.investment_unit_value == Decimal("10.16159")
    assert euro.fund_assets_value == Decimal("2632674.15")
    assert euro.investment_unit_currency == euro.fund_assets_currency == "EUR"
    assert rsd is not None
    assert rsd.investment_unit_value == Decimal("1025.37573")
    assert rsd.fund_assets_value == Decimal("222378577.26")
    assert rsd.investment_unit_currency == rsd.fund_assets_currency == "RSD"


def test_filters_other_date() -> None:
    assert parse_fund_page(page(_FUNDS[0]), date(2026, 7, 14), _FUNDS[0]) is None


def test_rejects_missing_kpi_mismatched_dates_and_invalid_amount() -> None:
    with pytest.raises(FundAdapterError, match="Missing or duplicate Eclectica"):
        parse_fund_page("<html></html>", date(2026, 7, 13), _FUNDS[0])
    with pytest.raises(FundAdapterError, match="value dates do not match"):
        parse_fund_page(
            page(_FUNDS[0], assets_date="12.07.2026."),
            date(2026, 7, 13),
            _FUNDS[0],
        )
    with pytest.raises(FundAdapterError, match="Vrednost investicione jedinice"):
        parse_fund_page(
            page(_FUNDS[0], unit="0,00000"), date(2026, 7, 13), _FUNDS[0]
        )
    with pytest.raises(FundAdapterError, match="Unexpected Eclectica Capital currency"):
        parse_fund_page(
            page(_FUNDS[1]).replace("<span>€</span>", "<span>RSD</span>"),
            date(2026, 7, 13),
            _FUNDS[1],
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


def test_adapter_fetches_both_fund_pages() -> None:
    session = Session()
    records = EclecticaCapitalAdapter().fetch(date(2026, 7, 13), session, 4.5)

    assert [record.fund_id for record in records] == [
        definition.fund_id for definition in _FUNDS
    ]
    assert session.calls == [(definition.url, 4.5) for definition in _FUNDS]
    assert all(response.checked for response in session.responses.values())


def test_loads_eclectica_capital_adapter() -> None:
    adapter = load_adapter("eclectica_capital")
    assert isinstance(adapter, EclecticaCapitalAdapter)
    assert adapter.fund_id == "eclectica-capital"
    assert len(adapter.fund_ids) == 2
