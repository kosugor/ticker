from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Sequence

from bs4 import BeautifulSoup

from ticker.funds import FundAdapterError, FundValue


HOME_URL = "https://www.intesainvest.rs/"
_FUND_HEADING_PREFIX = "INTESA INVEST "
_DATE_PATTERN = re.compile(r"^(?P<day>\d{1,2})\.(?P<month>\d{1,2})\.(?P<year>\d{4})\.$")
_AMOUNT_PATTERN = re.compile(
    r"(?P<amount>[0-9][0-9\.\s ]*,[0-9]+|[0-9][0-9\.\s ]*)\s+(?P<currency>[A-Z]{3})"
)


class IntesaInvestAdapter:
    fund_id = "intesa-invest"
    fund_ids = (
        "intesa-invest-comfort-euro",
        "intesa-invest-cash-dinar",
        "intesa-invest-cash-euro",
        "intesa-invest-global-balanced",
        "intesa-invest-equity-alternative",
        "intesa-invest-gold-silver-alternative",
    )

    def fetch(self, target_date: date, session, timeout: float) -> Sequence[FundValue]:
        response = session.get(HOME_URL, timeout=timeout)
        response.raise_for_status()
        return parse_homepage_fund_values(response.text, target_date, HOME_URL)


def _normalized_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    if not slug:
        raise FundAdapterError(f"Could not derive a fund slug from {value!r}")
    return slug


def _fund_id_from_heading(heading: str) -> str:
    if not heading.startswith(_FUND_HEADING_PREFIX):
        raise FundAdapterError(f"Unexpected Intesa Invest heading: {heading!r}")
    return f"intesa-invest-{_slugify(heading[len(_FUND_HEADING_PREFIX):].strip())}"


def _fund_currency_from_fund_id(fund_id: str) -> str:
    return "RSD" if "dinar" in fund_id else "EUR"


def _parse_date(value: str) -> date | None:
    match = _DATE_PATTERN.match(value)
    if match is None:
        return None
    try:
        return date(int(match.group("year")), int(match.group("month")), int(match.group("day")))
    except ValueError as error:
        raise FundAdapterError(f"Invalid Intesa Invest value date: {value!r}") from error


def _parse_amounts(value: str) -> dict[str, Decimal]:
    pairs: dict[str, Decimal] = {}
    for amount_text, currency in _AMOUNT_PATTERN.findall(value):
        normalized = amount_text.replace(" ", "").replace(" ", "").replace(".", "").replace(",", ".")
        try:
            amount = Decimal(normalized)
        except InvalidOperation as error:
            raise FundAdapterError(f"Invalid Intesa Invest amount: {amount_text!r}") from error
        if amount <= 0:
            raise FundAdapterError(f"Intesa Invest amount must be positive: {amount_text!r}")
        pairs[currency] = amount
    if not pairs:
        raise FundAdapterError(f"No currency amounts found in Intesa Invest line: {value!r}")
    return pairs


def _parse_amount_lines(
    lines: list[str], start: int, fund_id: str, label: str
) -> tuple[dict[str, Decimal], int]:
    amounts: dict[str, Decimal] = {}
    cursor = start
    while cursor < len(lines) and _AMOUNT_PATTERN.search(lines[cursor]):
        amounts.update(_parse_amounts(lines[cursor]))
        cursor += 1
    if not amounts:
        raise FundAdapterError(f"Missing {label} value for {fund_id}")
    return amounts, cursor


def _value_for_currency(amounts: dict[str, Decimal], currency: str, fund_id: str, label: str) -> Decimal:
    if currency not in amounts:
        raise FundAdapterError(f"{label} for {fund_id} does not include currency {currency}")
    return amounts[currency]


def parse_homepage_fund_values(
    html: str, target_date: date, source_url: str = HOME_URL
) -> list[FundValue]:
    soup = BeautifulSoup(html, "html.parser")
    lines = [line.strip() for line in soup.stripped_strings if line.strip()]
    records: list[FundValue] = []
    seen: set[str] = set()
    index = 0

    while index < len(lines):
        heading = lines[index]
        if not heading.startswith(_FUND_HEADING_PREFIX):
            index += 1
            continue

        fund_id = _fund_id_from_heading(heading)
        fund_currency = _fund_currency_from_fund_id(fund_id)
        value_date: date | None = None
        unit_amounts: dict[str, Decimal] | None = None
        assets_amounts: dict[str, Decimal] | None = None
        cursor = index + 1

        while cursor < len(lines):
            current = lines[cursor]
            if current.startswith(_FUND_HEADING_PREFIX):
                break

            maybe_date = _parse_date(current)
            if value_date is None and maybe_date is not None:
                value_date = maybe_date
                cursor += 1
                continue

            normalized = _normalized_text(current)
            if normalized == "vrednost investicione jedinice":
                unit_amounts, cursor = _parse_amount_lines(
                    lines, cursor + 1, fund_id, "investment-unit"
                )
                continue
            if normalized == "vrednost imovine fonda":
                assets_amounts, cursor = _parse_amount_lines(
                    lines, cursor + 1, fund_id, "fund-assets"
                )
                continue

            cursor += 1

        if value_date != target_date:
            index = cursor
            continue
        if fund_id in seen:
            raise FundAdapterError(f"Duplicate Intesa Invest fund entry detected: {fund_id}")
        if unit_amounts is None:
            raise FundAdapterError(f"Missing investment-unit section for {fund_id}")
        if assets_amounts is None:
            raise FundAdapterError(f"Missing fund-assets section for {fund_id}")

        investment_unit_value = _value_for_currency(
            unit_amounts, fund_currency, fund_id, "Investment unit value"
        )
        fund_assets_value = _value_for_currency(assets_amounts, fund_currency, fund_id, "Fund assets value")
        records.append(
            FundValue(
                fund_id=fund_id,
                value_date=value_date,
                investment_unit_value=investment_unit_value,
                investment_unit_currency=fund_currency,
                fund_assets_value=fund_assets_value,
                fund_assets_currency=fund_currency,
                source_url=source_url,
            )
        )
        seen.add(fund_id)
        index = cursor

    return records
