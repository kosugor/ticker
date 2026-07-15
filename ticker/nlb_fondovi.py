from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import time
from typing import Mapping, Sequence

from ticker.funds import FundAdapterError, FundValue


ARCHIVE_URL = "https://www.nlbfondovi.rs/arhiva-vrednosti-investicione-jedinice"
FUNDS_URL = (
    "https://www.nlbfondovi.rs/content/nlbskladi/nlbfondovirs/sr/"
    "arhiva-vrednosti-investicione-jedinice/jcr:content/root/container/"
    "container/contentcontainer/fundexchangerate.funds.json"
)


@dataclass(frozen=True)
class _FundDefinition:
    fund_id: str
    name: str
    currency: str
    unit_field: str
    assets_field: str


_FUNDS = {
    "2001": _FundDefinition(
        "nlb-fondovi-novcani", "NLB Novčani", "RSD", "nav4Rsd", "subfundSizeRs"
    ),
    "2002": _FundDefinition(
        "nlb-fondovi-devizni", "NLB Devizni", "EUR", "nav4", "subfundSize"
    ),
    "2003": _FundDefinition(
        "nlb-fondovi-globalni-balansirani",
        "NLB Globalni Balansirani",
        "EUR",
        "nav4",
        "subfundSize",
    ),
    "2004": _FundDefinition(
        "nlb-fondovi-globalni-akcijski",
        "NLB Globalni akcijski",
        "EUR",
        "nav4",
        "subfundSize",
    ),
}


class NlbFondoviAdapter:
    fund_id = "nlb-fondovi"
    fund_ids = tuple(definition.fund_id for definition in _FUNDS.values())

    def fetch(self, target_date: date, session, timeout: float) -> Sequence[FundValue]:
        response = session.get(
            FUNDS_URL,
            headers={"Referer": ARCHIVE_URL},
            params={"timestamp": int(time.time() * 1000)},
            timeout=timeout,
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except (TypeError, ValueError) as error:
            raise FundAdapterError("Invalid NLB Fondovi JSON response") from error
        return parse_fund_values(payload, target_date, ARCHIVE_URL)


def _parse_date(value: object) -> date:
    if not isinstance(value, str):
        raise FundAdapterError("Missing NLB Fondovi value date")
    try:
        return date.fromisoformat("-".join(reversed(value.split("."))))
    except ValueError as error:
        raise FundAdapterError(f"Invalid NLB Fondovi value date: {value!r}") from error


def _parse_amount(value: object, field: str, fund_id: str) -> Decimal:
    if not isinstance(value, str) or not value.strip():
        raise FundAdapterError(f"Missing NLB Fondovi {field} for {fund_id}")
    normalized = value.replace("\N{NO-BREAK SPACE}", "").replace(" ", "")
    if "," in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    try:
        amount = Decimal(normalized)
    except InvalidOperation as error:
        raise FundAdapterError(
            f"Invalid NLB Fondovi {field} for {fund_id}: {value!r}"
        ) from error
    if amount <= 0:
        raise FundAdapterError(f"NLB Fondovi {field} for {fund_id} must be positive")
    return amount


def parse_fund_values(
    payload: object, target_date: date, source_url: str = ARCHIVE_URL
) -> list[FundValue]:
    if not isinstance(payload, Mapping):
        raise FundAdapterError("Invalid NLB Fondovi response payload")

    value_date = _parse_date(payload.get("date"))
    if value_date != target_date:
        return []

    funds = payload.get("funds")
    if not isinstance(funds, list):
        raise FundAdapterError("Missing NLB Fondovi funds list")

    records: list[FundValue] = []
    seen: set[str] = set()
    for item in funds:
        if not isinstance(item, Mapping) or not isinstance(item.get("fund"), Mapping):
            raise FundAdapterError("Invalid NLB Fondovi fund entry")
        fund = item["fund"]
        provider_id = str(fund.get("id", ""))
        definition = _FUNDS.get(provider_id)
        if definition is None:
            continue
        if definition.fund_id in seen:
            raise FundAdapterError(
                f"Duplicate NLB Fondovi fund entry detected: {definition.fund_id}"
            )
        if fund.get("name") != definition.name:
            raise FundAdapterError(
                f"Unexpected NLB Fondovi fund name for ID {provider_id}: {fund.get('name')!r}"
            )

        records.append(
            FundValue(
                fund_id=definition.fund_id,
                value_date=value_date,
                investment_unit_value=_parse_amount(
                    fund.get(definition.unit_field), "investment-unit value", definition.fund_id
                ),
                investment_unit_currency=definition.currency,
                fund_assets_value=_parse_amount(
                    fund.get(definition.assets_field), "fund-assets value", definition.fund_id
                ),
                fund_assets_currency=definition.currency,
                source_url=source_url,
            )
        )
        seen.add(definition.fund_id)

    return records
