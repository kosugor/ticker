from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup


class NbsParseError(ValueError):
    pass


@dataclass(frozen=True)
class OfficialExchangeRate:
    effective_date: date
    rate: Decimal


_DATE_PATTERN = re.compile(r"(?P<day>\d{1,2})\.(?P<month>\d{1,2})\.(?P<year>\d{4})\.")
_OFFICIAL_MARKERS = ("званични", "zvanični", "zvanicni")
_INDICATIVE_MARKERS = ("индикативни", "indikativni")


def _normalized_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _section_kind(heading: str) -> str | None:
    normalized = _normalized_text(heading)
    if any(marker in normalized for marker in _INDICATIVE_MARKERS):
        return "indicative"
    if any(marker in normalized for marker in _OFFICIAL_MARKERS):
        return "official"
    return None


def _parse_date(heading: str) -> date:
    match = _DATE_PATTERN.search(heading)
    if not match:
        raise NbsParseError(f"NBS section has no publication date: {heading!r}")
    try:
        return date(int(match["year"]), int(match["month"]), int(match["day"]))
    except ValueError as error:
        raise NbsParseError(f"NBS section has invalid publication date: {heading!r}") from error


def _parse_decimal(value: str) -> Decimal:
    normalized = value.strip().replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        result = Decimal(normalized)
    except InvalidOperation as error:
        raise NbsParseError(f"Invalid NBS exchange rate: {value!r}") from error
    if result <= 0:
        raise NbsParseError(f"NBS exchange rate must be positive: {value!r}")
    return result


def parse_official_eur_rate(html: str, target_date: date) -> OfficialExchangeRate | None:
    """Return the target official EUR/RSD rate; indicative sections are ignored."""
    soup = BeautifulSoup(html, "html.parser")
    matches: list[OfficialExchangeRate] = []

    for section in soup.select("tbody"):
        heading_node = section.select_one(".kurs_date")
        if heading_node is None:
            continue
        heading = heading_node.get_text(" ", strip=True)
        if _section_kind(heading) != "official":
            continue

        pair_node = next(
            (node for node in section.select("th, td") if _normalized_text(node.get_text()) == "eur/rsd"),
            None,
        )
        if pair_node is None:
            continue

        effective_date = _parse_date(heading)
        if effective_date != target_date:
            continue
        rate_node = section.select_one(".kurs_e")
        if rate_node is None:
            raise NbsParseError("Official EUR/RSD section has no middle-rate value")
        matches.append(OfficialExchangeRate(effective_date, _parse_decimal(rate_node.get_text())))

    if not matches:
        return None
    if len(matches) != 1:
        raise NbsParseError(f"Expected one official EUR/RSD rate, found {len(matches)}")
    return matches[0]

