from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Mapping, Sequence

from ticker.funds import FundAdapterError, FundValue


VALUES_URL = "https://www.otpinvest.rs/investicioni-fondovi/tabela-cena-fondova"
TABLE_API_URL = "https://www.otpinvest.rs/api/table-data"
_UNIT_ENDPOINT = "growthValueAll"
_ASSETS_ENDPOINT = "netValueAll"


@dataclass(frozen=True)
class _FundDefinition:
    fund_id: str
    currency: str


_FUNDS = {
    "OTP Dynamic": _FundDefinition("otp-invest-dynamic", "RSD"),
    "OTP Balanced": _FundDefinition("otp-invest-balanced", "RSD"),
    "OTP Cash Dinar": _FundDefinition("otp-invest-cash-dinar", "RSD"),
    "OTP ProActive": _FundDefinition("otp-invest-proactive", "RSD"),
    "OTP Euro Cash": _FundDefinition("otp-invest-euro-cash", "EUR"),
    "OTP Alternative": _FundDefinition("otp-invest-alternative", "RSD"),
}


class OtpInvestAdapter:
    fund_id = "otp-invest"
    fund_ids = tuple(definition.fund_id for definition in _FUNDS.values())

    def fetch(self, target_date: date, session, timeout: float) -> Sequence[FundValue]:
        headers = {"Referer": VALUES_URL}
        unit_response = session.get(
            TABLE_API_URL,
            headers=headers,
            params={"apiEndpointUrl": _UNIT_ENDPOINT},
            timeout=timeout,
        )
        unit_response.raise_for_status()
        assets_response = session.get(
            TABLE_API_URL,
            headers=headers,
            params={"apiEndpointUrl": _ASSETS_ENDPOINT},
            timeout=timeout,
        )
        assets_response.raise_for_status()
        return parse_fund_values(
            _load_json(unit_response.text, "investment-unit"),
            _load_json(assets_response.text, "fund-assets"),
            target_date,
            VALUES_URL,
        )


def _load_json(value: str, label: str) -> object:
    try:
        return json.loads(value, parse_float=Decimal)
    except (TypeError, ValueError) as error:
        raise FundAdapterError(f"Invalid OTP Invest {label} JSON response") from error


def _rows_by_name(payload: object, label: str) -> dict[str, Mapping[str, object]]:
    if not isinstance(payload, list):
        raise FundAdapterError(f"Invalid OTP Invest {label} response payload")

    rows: dict[str, Mapping[str, object]] = {}
    for item in payload:
        if not isinstance(item, Mapping):
            raise FundAdapterError(f"Invalid OTP Invest {label} fund entry")
        name = item.get("type")
        if not isinstance(name, str) or name not in _FUNDS:
            continue
        if name in rows:
            raise FundAdapterError(f"Duplicate OTP Invest {label} entry detected: {name}")
        rows[name] = item
    return rows


def _parse_date(value: object, label: str, fund_id: str) -> date:
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise FundAdapterError(f"Invalid OTP Invest {label} date for {fund_id}: {value!r}")
    try:
        milliseconds = Decimal(value)
        if milliseconds != milliseconds.to_integral_value():
            raise ValueError
        return datetime.fromtimestamp(int(milliseconds) / 1000, timezone.utc).date()
    except (InvalidOperation, OSError, OverflowError, ValueError) as error:
        raise FundAdapterError(
            f"Invalid OTP Invest {label} date for {fund_id}: {value!r}"
        ) from error


def _parse_amount(value: object, label: str, fund_id: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal, str)):
        raise FundAdapterError(f"Missing OTP Invest {label} for {fund_id}")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as error:
        raise FundAdapterError(
            f"Invalid OTP Invest {label} for {fund_id}: {value!r}"
        ) from error
    if not amount.is_finite() or amount <= 0:
        raise FundAdapterError(f"OTP Invest {label} for {fund_id} must be positive")
    return amount


def parse_fund_values(
    unit_payload: object,
    assets_payload: object,
    target_date: date,
    source_url: str = VALUES_URL,
) -> list[FundValue]:
    unit_rows = _rows_by_name(unit_payload, "investment-unit")
    assets_rows = _rows_by_name(assets_payload, "fund-assets")
    records: list[FundValue] = []

    for name, definition in _FUNDS.items():
        unit_row = unit_rows.get(name)
        if unit_row is None:
            continue
        value_date = _parse_date(
            unit_row.get("latestValueDate"), "investment-unit", definition.fund_id
        )
        if value_date != target_date:
            continue

        assets_row = assets_rows.get(name)
        if assets_row is None:
            raise FundAdapterError(
                f"Missing OTP Invest fund-assets entry for {definition.fund_id}"
            )
        assets_date = _parse_date(
            assets_row.get("netValueDate"), "fund-assets", definition.fund_id
        )
        if assets_date != value_date:
            raise FundAdapterError(
                f"OTP Invest value dates do not match for {definition.fund_id}: "
                f"{value_date} and {assets_date}"
            )

        unit_field = "latestValueEur" if definition.currency == "EUR" else "latestValue"
        assets_field = "netValueEur" if definition.currency == "EUR" else "netValue"
        records.append(
            FundValue(
                fund_id=definition.fund_id,
                value_date=value_date,
                investment_unit_value=_parse_amount(
                    unit_row.get(unit_field), "investment-unit value", definition.fund_id
                ),
                investment_unit_currency=definition.currency,
                fund_assets_value=_parse_amount(
                    assets_row.get(assets_field), "fund-assets value", definition.fund_id
                ),
                fund_assets_currency=definition.currency,
                source_url=source_url,
            )
        )

    return records
