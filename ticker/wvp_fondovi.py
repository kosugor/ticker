from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Sequence

from bs4 import BeautifulSoup

from ticker.funds import FundAdapterError, FundValue


DAILY_OVERVIEW_URL = "https://www.wvpfondovi.rs/dnevni-pregled/"
_HEADERS = (
    "Fond",
    "Datum",
    "Neto vrednost imovine fonda (RSD)",
    "Neto vrednost imovine fonda (EUR)",
    "Cena investicione jedinice (RSD)",
    "Cena investicione jedinice (EUR)",
    "Dnevna promena",
)
_FUNDS = {
    "WVP PREMIUM": "wvp-fondovi-premium",
    "WVP DYNAMIC": "wvp-fondovi-dynamic",
    "WVP BALANCED": "wvp-fondovi-balanced",
    "WVP CASH": "wvp-fondovi-cash",
    "MERKUR ESG FUND BALANCED": "wvp-fondovi-merkur-esg-balanced",
    "MERKUR ESG FUND DYNAMIC": "wvp-fondovi-merkur-esg-dynamic",
    "MERKUR ESG FUND SOLID": "wvp-fondovi-merkur-esg-solid",
    "WVP BOND": "wvp-fondovi-bond",
}


class WvpFondoviAdapter:
    fund_id = "wvp-fondovi"
    fund_ids = tuple(_FUNDS.values())

    def fetch(self, target_date: date, session, timeout: float) -> Sequence[FundValue]:
        response = session.get(DAILY_OVERVIEW_URL, timeout=timeout)
        response.raise_for_status()
        return parse_daily_overview(response.text, target_date, DAILY_OVERVIEW_URL)


def _parse_date(value: str, fund_id: str) -> date:
    try:
        return date.fromisoformat("-".join(reversed(value.strip().split("."))))
    except ValueError as error:
        raise FundAdapterError(
            f"Invalid WVP Fondovi value date for {fund_id}: {value!r}"
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
            f"Invalid WVP Fondovi {label} for {fund_id}: {value!r}"
        ) from error
    if amount <= 0:
        raise FundAdapterError(f"WVP Fondovi {label} for {fund_id} must be positive")
    return amount


def parse_daily_overview(
    html: str, target_date: date, source_url: str = DAILY_OVERVIEW_URL
) -> list[FundValue]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.wvp-fund-details-table")
    if table is None:
        raise FundAdapterError("Missing WVP Fondovi daily-overview table")

    headers = tuple(
        header.get_text(" ", strip=True) for header in table.select("thead th")
    )
    if headers != _HEADERS:
        raise FundAdapterError(f"Unexpected WVP Fondovi table headers: {headers!r}")

    records: list[FundValue] = []
    seen: set[str] = set()
    for row in table.select("tbody tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.select("td")]
        if len(cells) != len(_HEADERS):
            raise FundAdapterError("Invalid WVP Fondovi daily-overview row")

        name = cells[0]
        fund_id = _FUNDS.get(name)
        if fund_id is None:
            continue
        if fund_id in seen:
            raise FundAdapterError(
                f"Duplicate WVP Fondovi fund entry detected: {fund_id}"
            )
        seen.add(fund_id)

        value_date = _parse_date(cells[1], fund_id)
        if value_date != target_date:
            continue
        records.append(
            FundValue(
                fund_id=fund_id,
                value_date=value_date,
                investment_unit_value=_parse_amount(
                    cells[4], "investment-unit value", fund_id
                ),
                investment_unit_currency="RSD",
                fund_assets_value=_parse_amount(cells[2], "fund-assets value", fund_id),
                fund_assets_currency="RSD",
                source_url=source_url,
            )
        )

    return records
