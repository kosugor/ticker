from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Sequence
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from ticker.funds import FundAdapterError, FundValue


HOME_URL = "https://www.raiffeiseninvest.rs/"
_DATE_PATTERN = re.compile(r"^(?P<day>\d{1,2})\.(?P<month>\d{1,2})\.(?P<year>\d{4})\.?$")
_AMOUNT_PATTERN = re.compile(
    r"(?P<amount>[0-9][0-9\.\s\N{NO-BREAK SPACE}]*,[0-9]+)\s+(?P<currency>[A-Z]{3})"
)


@dataclass(frozen=True)
class _FundDefinition:
    fund_id: str
    currency: str


_FUNDS = {
    "/fond/raiffeisen-cash": _FundDefinition("raiffeisen-invest-cash", "RSD"),
    "/fond/raiffeisen-euro-cash-4": _FundDefinition("raiffeisen-invest-euro-cash", "EUR"),
    "/fond/raiffeisen-dollar-bond": _FundDefinition("raiffeisen-invest-dollar-bond", "USD"),
    "/fond/raiffeisen-bond": _FundDefinition("raiffeisen-invest-bond", "EUR"),
    "/fond/raiffeisen-green": _FundDefinition("raiffeisen-invest-green", "EUR"),
    "/fond/raiffeisen-world": _FundDefinition("raiffeisen-invest-world", "EUR"),
    "/fond/raiffeisen-alternative": _FundDefinition("raiffeisen-invest-alternative", "EUR"),
    "/fond/raiffeisen-gold-alternative-otvoreni-alternativni-investicioni-fond-sa-jp": (
        _FundDefinition("raiffeisen-invest-gold-alternative", "EUR")
    ),
    "/fond/grawe-equity-global-1": _FundDefinition(
        "raiffeisen-invest-grawe-equity-global-1", "EUR"
    ),
    "/fond/grawe-equity-global-2": _FundDefinition(
        "raiffeisen-invest-grawe-equity-global-2", "EUR"
    ),
}


class RaiffeisenInvestAdapter:
    fund_id = "raiffeisen-invest"
    fund_ids = tuple(definition.fund_id for definition in _FUNDS.values())

    def fetch(self, target_date: date, session, timeout: float) -> Sequence[FundValue]:
        response = session.get(HOME_URL, timeout=timeout)
        response.raise_for_status()
        return parse_homepage_fund_values(response.text, target_date, HOME_URL)


def _normalized_label(value: str) -> str:
    return " ".join(value.casefold().split()).rstrip(":")


def _parse_date(value: str, fund_id: str) -> date:
    match = _DATE_PATTERN.match(value.strip())
    if match is None:
        raise FundAdapterError(f"Invalid Raiffeisen Invest value date for {fund_id}: {value!r}")
    try:
        return date(int(match.group("year")), int(match.group("month")), int(match.group("day")))
    except ValueError as error:
        raise FundAdapterError(
            f"Invalid Raiffeisen Invest value date for {fund_id}: {value!r}"
        ) from error


def _parse_amounts(value: str, fund_id: str, label: str) -> dict[str, Decimal]:
    amounts: dict[str, Decimal] = {}
    for amount_text, currency in _AMOUNT_PATTERN.findall(value):
        normalized = (
            amount_text.replace("\N{NO-BREAK SPACE}", "")
            .replace(" ", "")
            .replace(".", "")
            .replace(",", ".")
        )
        try:
            amount = Decimal(normalized)
        except InvalidOperation as error:
            raise FundAdapterError(
                f"Invalid {label} amount for {fund_id}: {amount_text!r}"
            ) from error
        if amount <= 0:
            raise FundAdapterError(f"{label} amount for {fund_id} must be positive")
        if currency in amounts:
            raise FundAdapterError(f"Duplicate {currency} {label} amount for {fund_id}")
        amounts[currency] = amount
    if not amounts:
        raise FundAdapterError(f"No {label} amounts found for {fund_id}")
    return amounts


def _required_field(fields: dict[str, str], label: str, fund_id: str) -> str:
    normalized = _normalized_label(label)
    if normalized not in fields:
        raise FundAdapterError(f"Missing {label} for {fund_id}")
    return fields[normalized]


def _native_amount(
    amounts: dict[str, Decimal], definition: _FundDefinition, label: str
) -> Decimal:
    if definition.currency not in amounts:
        raise FundAdapterError(
            f"{label} for {definition.fund_id} does not include currency {definition.currency}"
        )
    return amounts[definition.currency]


def parse_homepage_fund_values(
    html: str, target_date: date, source_url: str = HOME_URL
) -> list[FundValue]:
    soup = BeautifulSoup(html, "html.parser")
    records: list[FundValue] = []
    seen: set[str] = set()

    for card in soup.select("div.card"):
        link = card.find("a", href=True)
        if link is None:
            continue
        path = urlparse(link["href"]).path.rstrip("/")
        definition = _FUNDS.get(path)
        if definition is None:
            continue
        if definition.fund_id in seen:
            raise FundAdapterError(
                f"Duplicate Raiffeisen Invest fund entry detected: {definition.fund_id}"
            )
        seen.add(definition.fund_id)

        fields: dict[str, str] = {}
        for item in card.select(".data-item"):
            title = item.select_one(".data-item_title")
            value = item.select_one(".data-item_value")
            if title is not None and value is not None:
                fields[_normalized_label(title.get_text(" ", strip=True))] = value.get_text(
                    " ", strip=True
                )

        value_date = _parse_date(
            _required_field(fields, "Vrednosti na dan", definition.fund_id),
            definition.fund_id,
        )
        if value_date != target_date:
            continue

        unit_amounts = _parse_amounts(
            _required_field(fields, "Vrednost investicione jedinice", definition.fund_id),
            definition.fund_id,
            "investment-unit",
        )
        assets_amounts = _parse_amounts(
            _required_field(fields, "Vrednost imovine fonda", definition.fund_id),
            definition.fund_id,
            "fund-assets",
        )
        records.append(
            FundValue(
                fund_id=definition.fund_id,
                value_date=value_date,
                investment_unit_value=_native_amount(
                    unit_amounts, definition, "Investment unit value"
                ),
                investment_unit_currency=definition.currency,
                fund_assets_value=_native_amount(
                    assets_amounts, definition, "Fund assets value"
                ),
                fund_assets_currency=definition.currency,
                source_url=source_url,
            )
        )

    return records
