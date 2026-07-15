from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import re
from typing import Sequence

from bs4 import BeautifulSoup

from ticker.funds import FundAdapterError, FundValue


HOME_URL = "https://vistarica.rs/"


@dataclass(frozen=True)
class _FundDefinition:
    fund_id: str
    url: str
    slug: str
    currency: str


_FUNDS = (
    _FundDefinition(
        "vista-rica-invest",
        "https://vistarica.rs/vista-rica-invest/",
        "vistarica_invest",
        "EUR",
    ),
    _FundDefinition(
        "vista-rica-corporate",
        "https://vistarica.rs/aif-vista-rica-corporate/",
        "vistarica_corporate",
        "EUR",
    ),
    _FundDefinition(
        "vista-rica-cash",
        "https://vistarica.rs/vista-cash-fond/",
        "vistarica_cash",
        "RSD",
    ),
    _FundDefinition(
        "vista-rica-euro-cash",
        "https://vistarica.rs/vista-euro-cash-fond/",
        "vistarica_euro_cash",
        "EUR",
    ),
    _FundDefinition(
        "vista-rica-origin",
        "https://vistarica.rs/vista-rica-origin/",
        "vistarica_origin",
        "EUR",
    ),
)


class VistaRicaAdapter:
    fund_id = "vista-rica"
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


def _field(section, definition: _FundDefinition, column: str) -> str:
    fields = section.select(
        f'.vistarica-fund-value[data-slug="{definition.slug}"]'
        f'[data-column="{column}"]'
    )
    if len(fields) != 1:
        raise FundAdapterError(
            f"Missing or duplicate Vista Rica {column} for {definition.fund_id}"
        )
    return fields[0].get_text(" ", strip=True)


def _parse_date(value: str, fund_id: str) -> date:
    match = re.fullmatch(
        r"\s*(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\s*\.?\s*", value
    )
    if match is None:
        raise FundAdapterError(f"Invalid Vista Rica value date for {fund_id}: {value!r}")
    try:
        return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
    except ValueError as error:
        raise FundAdapterError(
            f"Invalid Vista Rica value date for {fund_id}: {value!r}"
        ) from error


def _parse_amount(value: str, label: str, fund_id: str) -> Decimal:
    normalized = (
        value.replace("\N{NO-BREAK SPACE}", "")
        .replace(" ", "")
        .replace(".", "")
        .replace(",", ".")
    )
    try:
        amount = Decimal(normalized)
    except InvalidOperation as error:
        raise FundAdapterError(
            f"Invalid Vista Rica {label} for {fund_id}: {value!r}"
        ) from error
    if not amount.is_finite() or amount <= 0:
        raise FundAdapterError(f"Vista Rica {label} for {fund_id} must be positive")
    return amount


def parse_fund_page(
    html: str, target_date: date, definition: _FundDefinition
) -> FundValue | None:
    soup = BeautifulSoup(html, "html.parser")
    section = soup.select_one("#stanje")
    if section is None:
        raise FundAdapterError(f"Missing Vista Rica value section for {definition.fund_id}")

    value_date = _parse_date(
        _field(section, definition, "latest_date"), definition.fund_id
    )
    if value_date != target_date:
        return None

    currency_column = definition.currency.casefold()
    return FundValue(
        fund_id=definition.fund_id,
        value_date=value_date,
        investment_unit_value=_parse_amount(
            _field(section, definition, f"unit_{currency_column}"),
            "investment-unit value",
            definition.fund_id,
        ),
        investment_unit_currency=definition.currency,
        fund_assets_value=_parse_amount(
            _field(section, definition, f"fund_{currency_column}"),
            "fund-assets value",
            definition.fund_id,
        ),
        fund_assets_currency=definition.currency,
        source_url=definition.url,
    )
