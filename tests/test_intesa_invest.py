from datetime import date
from decimal import Decimal

import pytest

from ticker.funds import FundAdapterError
from ticker.intesa_invest import HOME_URL, IntesaInvestAdapter, parse_homepage_fund_values


HTML = """
<html>
  <body>
    <main>
      <h5>INTESA INVEST COMFORT EURO</h5>
      <div>12.07.2026.</div>
      <div>Vrednost investicione jedinice</div>
      <div>9,25180 EUR 1.085,83 RSD</div>
      <div>Vrednost imovine fonda</div>
      <div>23.603.726,44 EUR 2.770.234.831,46 RSD</div>
      <h5>INTESA INVEST CASH DINAR</h5>
      <div>12.07.2026.</div>
      <div>Vrednost investicione jedinice</div>
      <div>10,96 EUR 1.286,30153 RSD</div>
      <div>Vrednost imovine fonda</div>
      <div>348.550.091,96 EUR 40.907.337.557,38 RSD</div>
    </main>
  </body>
</html>
"""


def test_parses_all_homepage_fund_rows() -> None:
    records = parse_homepage_fund_values(HTML, date(2026, 7, 12), HOME_URL)
    assert [record.fund_id for record in records] == [
        "intesa-invest-comfort-euro",
        "intesa-invest-cash-dinar",
    ]
    assert records[0].investment_unit_value == Decimal("9.25180")
    assert records[0].investment_unit_currency == "EUR"
    assert records[0].fund_assets_value == Decimal("23603726.44")
    assert records[0].fund_assets_currency == "EUR"
    assert records[1].investment_unit_value == Decimal("1286.30153")
    assert records[1].investment_unit_currency == "RSD"
    assert records[1].fund_assets_value == Decimal("40907337557.38")
    assert records[1].fund_assets_currency == "RSD"


def test_returns_no_rows_for_other_date() -> None:
    assert parse_homepage_fund_values(HTML, date(2026, 7, 13), HOME_URL) == []


def test_rejects_malformed_fund_block() -> None:
    broken = HTML.replace("Vrednost imovine fonda", "Broken")
    with pytest.raises(FundAdapterError, match="Missing fund-assets section"):
        parse_homepage_fund_values(broken, date(2026, 7, 12), HOME_URL)


def test_adapter_exposes_intesa_metadata() -> None:
    adapter = IntesaInvestAdapter()
    assert adapter.fund_id == "intesa-invest"
    assert "intesa-invest-cash-euro" in adapter.fund_ids
