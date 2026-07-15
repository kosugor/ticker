from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import re
from typing import Sequence

from bs4 import BeautifulSoup

from ticker.funds import FundAdapterError, FundValue


HOME_URL = "https://www.eclecticacapital.com/"


@dataclass(frozen=True)
class _FundDefinition:
    fund_id: str
    url: str
    currency: str


_FUNDS = (
    _FundDefinition(
        "eclectica-capital-rsd-cash",
        "https://www.eclecticacapital.com/eclectica-rsd-cash-ucits-fund",
        "RSD",
    ),
    _FundDefinition(
        "eclectica-capital-euro-cash",
        "https://www.eclecticacapital.com/eclectica-euro-cash-ucits-fund",
        "EUR",
    ),
)

_UNIT_LABEL = "Vrednost investicione jedinice"
_ASSETS_LABEL = "Vrednost imovine fonda"


class EclecticaCapitalAdapter:
    fund_id = "eclectica-capital"
    fund_ids = tuple(definition.fund_id for definition in _FUNDS)

    def fetch(self, target_date: date, session, timeout: float) -> Sequence[FundValue]:
        records: list[FundValue] = []
        for definition in _FUNDS:
            response = session.get(definition.url, timeout=timeout)
            response.raise_for_status()
            record = parse_fund_page(response.text, target_date, definition)
            if record is not None:
                records.append(record)
        return records


def _parse_date(value: str, fund_id: str) -> date:
    match = re.search(r"Na dan:\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\.", value)
    if match is None:
        raise FundAdapterError(
            f"Invalid Eclectica Capital value date for {fund_id}: {value!r}"
        )
    try:
        return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
    except ValueError as error:
        raise FundAdapterError(
            f"Invalid Eclectica Capital value date for {fund_id}: {value!r}"
        ) from error


def _parse_amount(
    value: str, label: str, definition: _FundDefinition
) -> Decimal:
    has_euro_marker = "€" in value
    has_rsd_marker = "RSD" in value
    expected_marker = has_euro_marker if definition.currency == "EUR" else has_rsd_marker
    if not expected_marker or (has_euro_marker and has_rsd_marker):
        raise FundAdapterError(
            f"Unexpected Eclectica Capital currency for {definition.fund_id}: {value!r}"
        )
    normalized = (
        value.replace("\N{NO-BREAK SPACE}", "")
        .replace("€", "")
        .replace("RSD", "")
        .replace(" ", "")
        .replace(".", "")
        .replace(",", ".")
    )
    try:
        amount = Decimal(normalized)
    except InvalidOperation as error:
        raise FundAdapterError(
            f"Invalid Eclectica Capital {label} for {definition.fund_id}: {value!r}"
        ) from error
    if not amount.is_finite() or amount <= 0:
        raise FundAdapterError(
            f"Eclectica Capital {label} for {definition.fund_id} must be positive"
        )
    return amount


def _kpi(page, label: str, definition: _FundDefinition) -> tuple[date, Decimal]:
    matches = []
    for card in page.select(".fund-kpi"):
        title = card.select_one(".fund-kpi-title")
        if title is not None and title.get_text(" ", strip=True) == label:
            matches.append(card)
    if len(matches) != 1:
        raise FundAdapterError(
            f"Missing or duplicate Eclectica Capital {label} for {definition.fund_id}"
        )

    card = matches[0]
    date_node = card.select_one(".fund-kpi-sub")
    value_node = card.select_one(".fund-kpi-value")
    if date_node is None or value_node is None:
        raise FundAdapterError(
            f"Incomplete Eclectica Capital {label} for {definition.fund_id}"
        )
    value_date = _parse_date(date_node.get_text(" ", strip=True), definition.fund_id)
    amount = _parse_amount(value_node.get_text(" ", strip=True), label, definition)
    return value_date, amount


def parse_fund_page(
    html: str, target_date: date, definition: _FundDefinition
) -> FundValue | None:
    soup = BeautifulSoup(html, "html.parser")
    unit_date, unit_value = _kpi(soup, _UNIT_LABEL, definition)
    assets_date, assets_value = _kpi(soup, _ASSETS_LABEL, definition)
    if unit_date != assets_date:
        raise FundAdapterError(
            f"Eclectica Capital value dates do not match for {definition.fund_id}"
        )
    if unit_date != target_date:
        return None

    return FundValue(
        fund_id=definition.fund_id,
        value_date=unit_date,
        investment_unit_value=unit_value,
        investment_unit_currency=definition.currency,
        fund_assets_value=assets_value,
        fund_assets_currency=definition.currency,
        source_url=definition.url,
    )
