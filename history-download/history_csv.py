"""Shared seed-ID mapping and CSV format for history downloaders."""

from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOCIETIES_CSV = PROJECT_ROOT / "data/societies.csv"
FUNDS_CSV = PROJECT_ROOT / "data/funds.csv"
CSV_COLUMNS = (
    "society_id", "fund_id", "fund_name", "source_url", "date",
    "unit_value", "unit_currency", "fund_assets_value", "fund_assets_currency",
)


def fetch(url: str, timeout: float, *, headers: dict[str, str] | None = None) -> bytes:
    request = Request(url, headers={"User-Agent": "ticker-history/1.0", **(headers or {})})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def write_csv(output: Path, rows: list[dict[str, object]]) -> None:
    """Write the shared format when rows already contain integer IDs."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def seed_ids() -> tuple[dict[str, int], dict[str, int]]:
    with SOCIETIES_CSV.open(encoding="utf-8-sig", newline="") as handle:
        societies = {row["society_key"]: int(row["society_id"]) for row in csv.DictReader(handle)}
    with FUNDS_CSV.open(encoding="utf-8-sig", newline="") as handle:
        funds = {row["fund_key"]: int(row["fund_id"]) for row in csv.DictReader(handle)}
    return societies, funds


def write_shared_csv(output: Path, rows: list[dict[str, object]], society_key: str) -> None:
    societies, funds = seed_ids()
    try:
        society_id = societies[society_key]
    except KeyError as error:
        raise ValueError(f"society {society_key!r} is missing from {SOCIETIES_CSV}") from error
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            fund_key = str(row["fund_id"])
            if fund_key not in funds:
                raise ValueError(f"fund {fund_key!r} is missing from {FUNDS_CSV}")
            writer.writerow({
                "society_id": society_id,
                "fund_id": funds[fund_key],
                "fund_name": row["fund_name"],
                "source_url": row["source_url"],
                "date": row["date"],
                "unit_value": row["unit_value"],
                "unit_currency": row["unit_currency"],
                "fund_assets_value": row["fund_assets_value"],
                "fund_assets_currency": row["fund_assets_currency"],
            })
