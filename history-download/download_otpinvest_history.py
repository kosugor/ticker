#!/usr/bin/env python3
"""Download OTP Invest's complete daily fund history as a normalized CSV."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

from history_csv import fetch, write_shared_csv


VALUES_URL = "https://www.otpinvest.rs/investicioni-fondovi/tabela-cena-fondova"
CHART_API_URL = "https://www.otpinvest.rs/api/chart-data"
DEFAULT_OUTPUT = "otpinvest_history.csv"
HISTORY_START = date(2000, 1, 1)
FUNDS = (
    ("otp_cash_dinar", "otp-invest-cash-dinar", "OTP Cash Dinar", "RSD"),
    ("otp_balanced", "otp-invest-balanced", "OTP Balanced", "RSD"),
    ("otp_dynamic", "otp-invest-dynamic", "OTP Dynamic", "RSD"),
    ("otp_proactive", "otp-invest-proactive", "OTP ProActive", "RSD"),
    ("otp_euro_cash", "otp-invest-euro-cash", "OTP Euro Cash", "EUR"),
    ("otp_alternative", "otp-invest-alternative", "OTP Alternative", "RSD"),
)


def chart_url(start: date, end: date, *, totals: bool, euros: bool) -> str:
    """Build an OTP chart API URL for one value and currency series."""
    query = urlencode(
        {
            "startDate": f"{start.isoformat()}T00:00:00.000Z",
            "endDate": f"{end.isoformat()}T23:59:59.999Z",
            "useTotal": str(totals).lower(),
            "useEur": str(euros).lower(),
        }
    )
    return f"{CHART_API_URL}?{query}"


def load_chart(url: str, timeout: float) -> list[Mapping[str, object]]:
    """Fetch and validate one chart series."""
    try:
        payload = json.loads(fetch(url, timeout, headers={"Referer": VALUES_URL}))
    except (TypeError, ValueError) as error:
        raise ValueError(f"invalid OTP Invest chart response from {url}") from error
    if not isinstance(payload, list) or any(not isinstance(row, Mapping) for row in payload):
        raise ValueError(f"invalid OTP Invest chart payload from {url}")
    return payload


def _date_from_timestamp(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"invalid OTP Invest chart date: {value!r}")
    return datetime.fromtimestamp(value / 1000, timezone.utc).date().isoformat()


def _positive_number(value: object) -> object | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return None
    return value


def values_by_date(rows: list[Mapping[str, object]]) -> dict[str, Mapping[str, object]]:
    """Index a chart response by its UTC calendar date."""
    indexed: dict[str, Mapping[str, object]] = {}
    for row in rows:
        value_date = _date_from_timestamp(row.get("date"))
        if value_date in indexed:
            raise ValueError(f"duplicate OTP Invest chart date: {value_date}")
        indexed[value_date] = row
    return indexed


def download(timeout: float, *, end: date | None = None) -> list[dict[str, object]]:
    """Return all published fund values in their respective native currencies."""
    end = end or date.today()
    if end < HISTORY_START:
        raise ValueError("end date must not be before 2000-01-01")

    series = {
        (totals, euros): values_by_date(
            load_chart(chart_url(HISTORY_START, end, totals=totals, euros=euros), timeout)
        )
        for totals in (False, True)
        for euros in (False, True)
    }
    records: list[dict[str, object]] = []
    for chart_key, fund_id, fund_name, currency in FUNDS:
        euros = currency == "EUR"
        unit_rows = series[(False, euros)]
        asset_rows = series[(True, euros)]
        source_url = chart_url(HISTORY_START, end, totals=False, euros=euros)
        for value_date, unit_row in unit_rows.items():
            unit_value = _positive_number(unit_row.get(chart_key))
            if unit_value is None:
                continue
            asset_value = _positive_number(asset_rows.get(value_date, {}).get(chart_key))
            records.append(
                {
                    "fund_id": fund_id,
                    "fund_name": fund_name,
                    "source_url": source_url,
                    "date": value_date,
                    "unit_value": unit_value,
                    "unit_currency": currency,
                    "fund_assets_value": asset_value if asset_value is not None else "",
                    "fund_assets_currency": currency,
                }
            )
    if not records:
        raise ValueError("OTP Invest chart API returned no fund history rows")
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=Path(DEFAULT_OUTPUT))
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")
    try:
        rows = download(args.timeout)
        write_shared_csv(args.output, rows, "otp-invest")
    except (HTTPError, URLError, OSError, ValueError) as error:
        parser.exit(1, f"error: {error}\n")
    print(f"Wrote {len(rows)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
