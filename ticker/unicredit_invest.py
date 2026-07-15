from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Mapping, Sequence

from ticker.funds import FundAdapterError, FundValue


VALUES_URL = "https://unicreditinvest.rs/"
FUNDS_API_URL = "https://unicreditinvest.rs/api/fund"


@dataclass(frozen=True)
class _FundDefinition:
    fund_id: str
    currency: str


_FUNDS = {
    "onemarkets-uc-invest-cash-dinar-fund": _FundDefinition(
        "unicredit-invest-cash-dinar", "RSD"
    ),
    "onemarkets-uc-invest-cash-eur-fund": _FundDefinition(
        "unicredit-invest-cash-eur", "EUR"
    ),
}


class UniCreditInvestAdapter:
    fund_id = "unicredit-invest"
    fund_ids = tuple(definition.fund_id for definition in _FUNDS.values())

    def fetch(self, target_date: date, session, timeout: float) -> Sequence[FundValue]:
        response = session.get(
            FUNDS_API_URL,
            params=_request_params(target_date),
            timeout=timeout,
        )
        response.raise_for_status()
        return parse_fund_values(_load_json(response.text), target_date, VALUES_URL)


def _request_params(target_date: date) -> dict[str, object]:
    fields = ("name", "slug", "currency")
    value_fields = ("date", "priceRSD", "priceEUR", "netAssets", "netAssetsEUR")
    params: dict[str, object] = {
        f"fields[{index}]": field for index, field in enumerate(fields)
    }
    params.update(
        {
            f"populate[dailyValues][fields][{index}]": field
            for index, field in enumerate(value_fields)
        }
    )
    params["populate[dailyValues][filters][date][$eq]"] = target_date.isoformat()
    params["pagination[pageSize]"] = 25
    return params


def _load_json(value: str) -> object:
    try:
        return json.loads(value, parse_float=Decimal)
    except (TypeError, ValueError) as error:
        raise FundAdapterError("Invalid UniCredit Invest JSON response") from error


def _parse_date(value: object, fund_id: str) -> date:
    if not isinstance(value, str):
        raise FundAdapterError(
            f"Invalid UniCredit Invest value date for {fund_id}: {value!r}"
        )
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise FundAdapterError(
            f"Invalid UniCredit Invest value date for {fund_id}: {value!r}"
        ) from error


def _parse_amount(value: object, label: str, fund_id: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal, str)):
        raise FundAdapterError(f"Missing UniCredit Invest {label} for {fund_id}")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as error:
        raise FundAdapterError(
            f"Invalid UniCredit Invest {label} for {fund_id}: {value!r}"
        ) from error
    if not amount.is_finite() or amount <= 0:
        raise FundAdapterError(
            f"UniCredit Invest {label} for {fund_id} must be positive"
        )
    return amount


def _fund_rows(payload: object) -> list[Mapping[str, object]]:
    if not isinstance(payload, Mapping) or not isinstance(payload.get("data"), list):
        raise FundAdapterError("Invalid UniCredit Invest response payload")
    rows = payload["data"]
    if not all(isinstance(row, Mapping) for row in rows):
        raise FundAdapterError("Invalid UniCredit Invest fund entry")
    return rows


def parse_fund_values(
    payload: object,
    target_date: date,
    source_url: str = VALUES_URL,
) -> list[FundValue]:
    records: list[FundValue] = []
    seen: set[str] = set()

    for fund in _fund_rows(payload):
        slug = fund.get("slug")
        if not isinstance(slug, str) or slug not in _FUNDS:
            continue
        definition = _FUNDS[slug]
        if slug in seen:
            raise FundAdapterError(
                f"Duplicate UniCredit Invest fund entry detected: {slug}"
            )
        seen.add(slug)

        if fund.get("currency") != definition.currency:
            raise FundAdapterError(
                f"Unexpected UniCredit Invest currency for {definition.fund_id}: "
                f"{fund.get('currency')!r}"
            )
        daily_values = fund.get("dailyValues")
        if not isinstance(daily_values, list):
            raise FundAdapterError(
                f"Missing UniCredit Invest daily values for {definition.fund_id}"
            )

        matching_values: list[Mapping[str, object]] = []
        for value in daily_values:
            if not isinstance(value, Mapping):
                raise FundAdapterError(
                    f"Invalid UniCredit Invest daily value for {definition.fund_id}"
                )
            if _parse_date(value.get("date"), definition.fund_id) == target_date:
                matching_values.append(value)

        if not matching_values:
            continue
        if len(matching_values) > 1:
            raise FundAdapterError(
                f"Duplicate UniCredit Invest daily value for {definition.fund_id} "
                f"on {target_date}"
            )

        value = matching_values[0]
        unit_field = "priceEUR" if definition.currency == "EUR" else "priceRSD"
        assets_field = (
            "netAssetsEUR" if definition.currency == "EUR" else "netAssets"
        )
        records.append(
            FundValue(
                fund_id=definition.fund_id,
                value_date=target_date,
                investment_unit_value=_parse_amount(
                    value.get(unit_field), "investment-unit value", definition.fund_id
                ),
                investment_unit_currency=definition.currency,
                fund_assets_value=_parse_amount(
                    value.get(assets_field), "fund-assets value", definition.fund_id
                ),
                fund_assets_currency=definition.currency,
                source_url=source_url,
            )
        )

    return records
