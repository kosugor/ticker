#!/usr/bin/env python3
"""Import Intesa, Raiffeisen, and NLB Fondovi histories into ticker SQLite."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

from ticker.database import connect, insert_fund_value
from ticker.funds import FundAdapterError, FundValue
from ticker.http import build_session
from ticker.intesa_invest import (
    IntesaInvestAdapter,
    _fund_currency_from_fund_id,
    _fund_id_from_heading,
)
from ticker.nlb_fondovi import ARCHIVE_URL as NLB_ARCHIVE_URL
from ticker.nlb_fondovi import _FUNDS as NLB_FUNDS
from ticker.nlb_fondovi import _parse_amount as parse_nlb_amount
from ticker.raiffeisen_invest import _FUNDS


DEFAULT_DATABASE = Path("data/ticker.sqlite3")
DEFAULT_INTESA_CSV = Path(
    "/home/ubuntu/intesainvest-history/intesainvest_history.csv"
)
DEFAULT_RAIFFEISEN_CSV = Path(
    "/home/ubuntu/intesainvest-history/raiffeiseninvest_history.csv"
)
RAIFFEISEN_FUNDS_URL = "https://www.raiffeiseninvest.rs/nasi-fondovi/"
RAIFFEISEN_HISTORY_URL = (
    "https://www.raiffeiseninvest.rs/wp-json/wp/easervice/investments"
)
INTESA_COLUMNS = {
    "fund_name",
    "history_url",
    "date",
    "unit_value_rsd",
    "unit_value_eur",
    "assets_rsd",
    "assets_eur",
}
RAIFFEISEN_COLUMNS = {
    "fund_name",
    "fund_slug",
    "fund_code",
    "detail_url",
    "currency",
    "date",
    "timestamp",
    "unit_value",
}
NONCE_PATTERN = re.compile(r'\bwpApiSettings\s*=\s*\{.*?"nonce":"([^"]+)"')
NLB_HISTORY_SOURCE_URL = (
    "https://www.nlbfondovi.rs/investicioni-fondovi/nlb-devizni"
)
NLB_COMPONENT_PATTERN = re.compile(
    r'<div\b(?=[^>]*\bclass="[^"]*\bjs-unit-value-comparator\b[^"]*")'
    r'(?=[^>]*\bdata-service-path="([^"]+)")[^>]*>'
)


class ImportError(RuntimeError):
    """Raised when a generated history cannot be imported safely."""


@dataclass(frozen=True)
class ProviderResult:
    inserted: int
    skipped: int


@dataclass
class RaiffeisenSource:
    fund_id: str
    currency: str
    code: str
    detail_url: str
    units: dict[date, Decimal]


def _read_rows(
    path: Path, required_columns: set[str]
) -> Iterable[tuple[int, dict[str, str]]]:
    try:
        handle = path.open(newline="", encoding="utf-8-sig")
    except OSError as error:
        raise ImportError(f"could not open {path}: {error}") from error

    with handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or ())
        missing = required_columns - columns
        if missing:
            raise ImportError(
                f"{path} is missing CSV columns: {', '.join(sorted(missing))}"
            )
        try:
            for row_number, row in enumerate(reader, start=2):
                yield row_number, row
        except csv.Error as error:
            raise ImportError(f"invalid CSV in {path}: {error}") from error


def _parse_date(value: str, path: Path, row_number: int) -> date:
    try:
        return datetime.strptime(value.strip(), "%d.%m.%Y").date()
    except (AttributeError, ValueError) as error:
        raise ImportError(
            f"invalid date {value!r} in {path} row {row_number}"
        ) from error


def _parse_decimal(
    value: object, label: str, *, localized: bool = False
) -> Decimal:
    text = str(value).strip()
    if localized:
        text = (
            text.replace("\N{NO-BREAK SPACE}", "")
            .replace(" ", "")
            .replace(".", "")
            .replace(",", ".")
        )
    try:
        result = Decimal(text)
    except InvalidOperation as error:
        raise ImportError(f"invalid {label}: {value!r}") from error
    if not result.is_finite() or result <= 0:
        raise ImportError(f"{label} must be a positive finite number: {value!r}")
    return result


def load_intesa(path: Path) -> tuple[list[FundValue], int]:
    tracked_ids = set(IntesaInvestAdapter.fund_ids)
    records: dict[tuple[str, date], FundValue] = {}
    duplicates = 0

    for row_number, row in _read_rows(path, INTESA_COLUMNS):
        try:
            fund_id = _fund_id_from_heading(row["fund_name"].strip())
        except Exception as error:
            raise ImportError(
                f"invalid Intesa fund name in {path} row {row_number}: {error}"
            ) from error
        if fund_id not in tracked_ids:
            continue

        value_date = _parse_date(row["date"], path, row_number)
        key = (fund_id, value_date)
        if key in records:
            # Keep the first source row so the known duplicate is deterministic.
            duplicates += 1
            continue

        currency = _fund_currency_from_fund_id(fund_id)
        suffix = currency.casefold()
        records[key] = FundValue(
            fund_id=fund_id,
            value_date=value_date,
            investment_unit_value=_parse_decimal(
                row[f"unit_value_{suffix}"],
                f"Intesa unit value in {path} row {row_number}",
                localized=True,
            ),
            investment_unit_currency=currency,
            fund_assets_value=_parse_decimal(
                row[f"assets_{suffix}"],
                f"Intesa fund assets in {path} row {row_number}",
                localized=True,
            ),
            fund_assets_currency=currency,
            source_url=row["history_url"].strip(),
        )

    if not records:
        raise ImportError(f"no tracked Intesa funds found in {path}")
    return list(records.values()), duplicates


def load_raiffeisen_sources(path: Path) -> dict[str, RaiffeisenSource]:
    sources: dict[str, RaiffeisenSource] = {}
    for row_number, row in _read_rows(path, RAIFFEISEN_COLUMNS):
        slug = row["fund_slug"].strip()
        definition = _FUNDS.get(f"/fond/{slug}")
        if definition is None or row["currency"].strip() != definition.currency:
            continue

        code = row["fund_code"].strip()
        detail_url = row["detail_url"].strip()
        detail_path = urlparse(detail_url).path.rstrip("/")
        if detail_path != f"/fond/{slug}":
            raise ImportError(
                f"Raiffeisen detail URL does not match slug in {path} row {row_number}"
            )

        source = sources.setdefault(
            slug,
            RaiffeisenSource(
                fund_id=definition.fund_id,
                currency=definition.currency,
                code=code,
                detail_url=detail_url,
                units={},
            ),
        )
        if (source.code, source.detail_url) != (code, detail_url):
            raise ImportError(f"conflicting Raiffeisen metadata for {slug} in {path}")

        value_date = _parse_date(row["date"], path, row_number)
        unit_value = _parse_decimal(
            row["unit_value"], f"Raiffeisen unit value in {path} row {row_number}"
        )
        previous = source.units.setdefault(value_date, unit_value)
        if previous != unit_value:
            raise ImportError(
                f"conflicting Raiffeisen unit values for {slug} on {value_date}"
            )

    if not sources:
        raise ImportError(f"no tracked Raiffeisen funds found in {path}")
    return sources


def _fetch_raiffeisen_nonce(session: requests.Session, timeout: float) -> str:
    response = session.get(RAIFFEISEN_FUNDS_URL, timeout=timeout)
    response.raise_for_status()
    match = NONCE_PATTERN.search(response.text)
    if match is None:
        raise ImportError("Raiffeisen funds page did not contain a REST API nonce")
    return match.group(1)


def _raiffeisen_asset_field(currency: str) -> str:
    return "neto_imovina_rsd" if currency == "RSD" else "neto_imovina_val"


def fetch_raiffeisen(
    sources: dict[str, RaiffeisenSource], session: requests.Session, timeout: float
) -> tuple[list[FundValue], int]:
    nonce = _fetch_raiffeisen_nonce(session, timeout)
    records: list[FundValue] = []
    carried_assets = 0

    for slug, source in sources.items():
        first_date = min(source.units)
        last_date = max(source.units)
        response = session.get(
            RAIFFEISEN_HISTORY_URL,
            params={
                "from_date": first_date.isoformat(),
                "to_date": last_date.isoformat(),
                "fond_type": source.code,
                "_wpnonce": nonce,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        try:
            payload = response.json()
        except requests.exceptions.JSONDecodeError as error:
            raise ImportError(f"invalid Raiffeisen API JSON for {slug}") from error
        if not isinstance(payload, dict) or payload.get("success") is not True:
            message = payload.get("message") if isinstance(payload, dict) else payload
            raise ImportError(f"Raiffeisen API failed for {slug}: {message}")
        history = payload.get("data")
        if not isinstance(history, list):
            raise ImportError(f"Raiffeisen API returned invalid history for {slug}")

        api_assets: dict[date, Decimal | None] = {}
        asset_field = _raiffeisen_asset_field(source.currency)
        for item_number, item in enumerate(history, start=1):
            if not isinstance(item, dict):
                raise ImportError(
                    f"invalid Raiffeisen API row {item_number} for {slug}"
                )
            value_date = _parse_date(
                str(item.get("datum", "")),
                Path(f"Raiffeisen API ({slug})"),
                item_number,
            )
            if value_date not in source.units:
                continue
            raw_asset = item.get(asset_field)
            asset_value = (
                _parse_decimal(
                    raw_asset,
                    f"Raiffeisen API fund assets for {slug} on {value_date}",
                    localized=True,
                )
                if raw_asset is not None and str(raw_asset).strip()
                else None
            )
            if value_date in api_assets and api_assets[value_date] != asset_value:
                raise ImportError(
                    f"conflicting Raiffeisen API assets for {slug} on {value_date}"
                )
            api_assets[value_date] = asset_value

        missing_dates = set(source.units) - set(api_assets)
        if missing_dates:
            sample = ", ".join(str(item) for item in sorted(missing_dates)[:3])
            raise ImportError(
                f"Raiffeisen API omitted {len(missing_dates)} CSV dates for {slug}: {sample}"
            )

        # The API publishes repeated unit values on non-business dates while its
        # asset field is blank. Carry forward the most recent published assets,
        # matching the API's own repeated-value convention for those dates.
        assets: dict[date, Decimal] = {}
        last_assets: Decimal | None = None
        for value_date in sorted(source.units):
            asset_value = api_assets[value_date]
            if asset_value is not None:
                last_assets = asset_value
            elif last_assets is None:
                raise ImportError(
                    f"Raiffeisen API has no assets to carry forward for {slug} "
                    f"on {value_date}"
                )
            else:
                asset_value = last_assets
                carried_assets += 1
            assets[value_date] = asset_value
        records.extend(
            FundValue(
                fund_id=source.fund_id,
                value_date=value_date,
                investment_unit_value=unit_value,
                investment_unit_currency=source.currency,
                fund_assets_value=assets[value_date],
                fund_assets_currency=source.currency,
                source_url=source.detail_url,
            )
            for value_date, unit_value in source.units.items()
        )

    return records, carried_assets


def _fetch_nlb_history_url(session: requests.Session, timeout: float) -> str:
    response = session.get(NLB_HISTORY_SOURCE_URL, timeout=timeout)
    response.raise_for_status()
    match = NLB_COMPONENT_PATTERN.search(response.text)
    if match is None:
        raise ImportError("NLB fund page did not contain a history service path")

    provider_ids = ".".join(NLB_FUNDS)
    service_url = urljoin(NLB_HISTORY_SOURCE_URL, match.group(1))
    return f"{service_url}.fundsarchive.{provider_ids}.json"


def fetch_nlb(
    session: requests.Session, timeout: float, date_max: date | None = None
) -> list[FundValue]:
    last_date = date_max or date.today()
    history_url = _fetch_nlb_history_url(session, timeout)
    response = session.get(
        history_url,
        headers={"Referer": NLB_HISTORY_SOURCE_URL},
        params={"dateMin": "1990-01-01", "dateMax": last_date.isoformat()},
        timeout=timeout,
    )
    response.raise_for_status()
    try:
        payload = response.json()
    except (TypeError, ValueError) as error:
        raise ImportError("invalid NLB history API JSON") from error
    if not isinstance(payload, list):
        raise ImportError("NLB history API returned an invalid history")

    records: dict[tuple[str, date], FundValue] = {}
    found_provider_ids: set[str] = set()
    for row_number, row in enumerate(payload, start=1):
        if not isinstance(row, dict):
            raise ImportError(f"invalid NLB history row {row_number}")
        try:
            value_date = date.fromisoformat(str(row.get("date", "")))
        except ValueError as error:
            raise ImportError(
                f"invalid NLB history date in row {row_number}: {row.get('date')!r}"
            ) from error
        funds = row.get("funds")
        if not isinstance(funds, list):
            raise ImportError(f"missing NLB funds in history row {row_number}")

        for item_number, item in enumerate(funds, start=1):
            if not isinstance(item, dict):
                raise ImportError(
                    f"invalid NLB fund {item_number} in history row {row_number}"
                )
            provider_id = str(item.get("id", ""))
            definition = NLB_FUNDS.get(provider_id)
            if definition is None:
                continue
            key = (definition.fund_id, value_date)
            try:
                unit_value = parse_nlb_amount(
                    item.get(definition.unit_field),
                    "investment-unit value",
                    definition.fund_id,
                )
                assets_value = parse_nlb_amount(
                    item.get(definition.assets_field),
                    "fund-assets value",
                    definition.fund_id,
                )
            except FundAdapterError as error:
                raise ImportError(
                    f"invalid NLB history value for {definition.fund_id} "
                    f"on {value_date}: {error}"
                ) from error
            record = FundValue(
                fund_id=definition.fund_id,
                value_date=value_date,
                investment_unit_value=unit_value,
                investment_unit_currency=definition.currency,
                fund_assets_value=assets_value,
                fund_assets_currency=definition.currency,
                source_url=NLB_ARCHIVE_URL,
            )
            previous = records.setdefault(key, record)
            if previous != record:
                raise ImportError(
                    f"conflicting NLB history values for {definition.fund_id} "
                    f"on {value_date}"
                )
            found_provider_ids.add(provider_id)

    missing_ids = set(NLB_FUNDS) - found_provider_ids
    if missing_ids:
        raise ImportError(
            "NLB history API omitted tracked fund IDs: "
            + ", ".join(sorted(missing_ids))
        )
    return list(records.values())


def insert_records(connection, records: Iterable[FundValue]) -> ProviderResult:
    inserted = 0
    skipped = 0
    for record in records:
        record.validate(record.value_date)
        if insert_fund_value(connection, record):
            inserted += 1
        else:
            skipped += 1
    return ProviderResult(inserted=inserted, skipped=skipped)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Import Intesa, Raiffeisen, and NLB Fondovi histories into ticker SQLite."
        )
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
        help=f"ticker SQLite database (default: {DEFAULT_DATABASE})",
    )
    parser.add_argument(
        "--intesa-csv",
        type=Path,
        default=DEFAULT_INTESA_CSV,
        help=f"generated Intesa CSV (default: {DEFAULT_INTESA_CSV})",
    )
    parser.add_argument(
        "--raiffeisen-csv",
        type=Path,
        default=DEFAULT_RAIFFEISEN_CSV,
        help=f"generated Raiffeisen CSV (default: {DEFAULT_RAIFFEISEN_CSV})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="HTTP timeout per provider request in seconds (default: 60)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="HTTP retry count (default: 2)",
    )
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")
    if args.retries < 0:
        parser.error("--retries must not be negative")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        intesa_records, duplicate_count = load_intesa(args.intesa_csv)
        raiffeisen_sources = load_raiffeisen_sources(args.raiffeisen_csv)
        with build_session(args.retries) as session:
            raiffeisen_records, carried_assets = fetch_raiffeisen(
                raiffeisen_sources, session, args.timeout
            )
            nlb_records = fetch_nlb(session, args.timeout)

        with connect(args.database) as connection:
            intesa_result = insert_records(connection, intesa_records)
            raiffeisen_result = insert_records(connection, raiffeisen_records)
            nlb_result = insert_records(connection, nlb_records)
            final_total = connection.execute(
                "SELECT COUNT(*) FROM fund_values"
            ).fetchone()[0]
    except (ImportError, OSError, requests.RequestException) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(
        f"Intesa: inserted={intesa_result.inserted}, skipped={intesa_result.skipped}, "
        f"duplicates_collapsed={duplicate_count}"
    )
    print(
        f"Raiffeisen: inserted={raiffeisen_result.inserted}, "
        f"skipped={raiffeisen_result.skipped}, "
        f"assets_carried_forward={carried_assets}"
    )
    print(f"NLB: inserted={nlb_result.inserted}, skipped={nlb_result.skipped}")
    print(
        "Final: "
        f"inserted={intesa_result.inserted + raiffeisen_result.inserted + nlb_result.inserted}, "
        f"skipped={intesa_result.skipped + raiffeisen_result.skipped + nlb_result.skipped}, "
        f"fund_values_total={final_total}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
