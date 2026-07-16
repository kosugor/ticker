#!/usr/bin/env python3
"""Download historical values for every fund listed by Intesa Invest."""

from __future__ import annotations

import argparse
import csv
import html
import os
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from history_csv import write_shared_csv
from ticker.intesa_invest import _fund_currency_from_fund_id, _fund_id_from_heading
from urllib.request import Request, urlopen


FUNDS_URL = "https://www.intesainvest.rs/fondovi"
DEFAULT_OUTPUT = "intesainvest_history.csv"
USER_AGENT = "intesainvest-history/1.0 (+https://www.intesainvest.rs/)"
CSV_COLUMNS = (
    "fund_name",
    "history_url",
    "date",
    "unit_value_rsd",
    "unit_value_eur",
    "assets_rsd",
    "assets_eur",
)


def clean_text(parts: Iterable[str]) -> str:
    """Join text fragments and normalize HTML whitespace."""
    return " ".join(html.unescape("".join(parts)).split())


class LinkParser(HTMLParser):
    """Collect links, including their human-readable anchor text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, clean_text(self._text)))
            self._href = None
            self._text = []


class HistoryTableParser(HTMLParser):
    """Parse rows from the tbody of the historical-values table."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._in_table = False
        self._table_depth = 0
        self._in_tbody = False
        self._in_row = False
        self._cell: list[str] | None = None
        self._row: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        tag = tag.lower()
        attributes = dict(attrs)
        if tag == "table":
            if self._in_table:
                self._table_depth += 1
            elif attributes.get("id") == "istorijske-vrednosti":
                self._in_table = True
                self._table_depth = 1
            return
        if not self._in_table:
            return
        if tag == "tbody":
            self._in_tbody = True
        elif tag == "tr" and self._in_tbody:
            self._in_row = True
            self._row = []
        elif tag in {"td", "th"} and self._in_row:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if not self._in_table:
            return
        if tag in {"td", "th"} and self._cell is not None:
            self._row.append(clean_text(self._cell))
            self._cell = None
        elif tag == "tr" and self._in_row:
            if self._row:
                self.rows.append(self._row)
            self._in_row = False
            self._row = []
        elif tag == "tbody":
            self._in_tbody = False
        elif tag == "table":
            self._table_depth -= 1
            if self._table_depth == 0:
                self._in_table = False


def fetch(url: str, timeout: float) -> str:
    request = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
    )
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def is_site_url(url: str) -> bool:
    return (urlparse(url).hostname or "").lower().removeprefix("www.") == "intesainvest.rs"


def find_fund_urls(page: str) -> list[str]:
    parser = LinkParser()
    parser.feed(page)
    urls: list[str] = []
    for href, _ in parser.links:
        url = urljoin(FUNDS_URL, href)
        parsed = urlparse(url)
        path_parts = [part for part in parsed.path.split("/") if part]
        if is_site_url(url) and len(path_parts) == 2 and path_parts[0] == "fondovi":
            canonical = parsed._replace(query="", fragment="").geturl()
            if canonical not in urls:
                urls.append(canonical)
    if not urls:
        raise ValueError(f"no fund detail links found at {FUNDS_URL}")
    return urls


def find_history_url(detail_url: str, page: str) -> str:
    parser = LinkParser()
    parser.feed(page)
    for href, _ in parser.links:
        url = urljoin(detail_url, href)
        if is_site_url(url) and "/istorijske-vrednosti/" in urlparse(url).path:
            return urlparse(url)._replace(fragment="").geturl()
    raise ValueError(f"no historical-values link found on {detail_url}")


def parse_history(page: str, history_url: str) -> list[dict[str, str]]:
    parser = HistoryTableParser()
    parser.feed(page)
    if not parser.rows:
        raise ValueError(f"no history rows found at {history_url}")

    records: list[dict[str, str]] = []
    for row_number, cells in enumerate(parser.rows, start=1):
        if len(cells) != 6:
            raise ValueError(
                f"unexpected {len(cells)}-cell row {row_number} at {history_url}"
            )
        records.append(dict(zip(CSV_COLUMNS, (cells[0], history_url, *cells[1:]))))
    return records


def write_csv(output: Path, records: list[dict[str, str]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            writer = csv.DictWriter(temporary, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(records)
        os.replace(temporary_name, output)
    except Exception:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
        raise


def download(output: Path, timeout: float) -> tuple[int, int]:
    fund_urls = find_fund_urls(fetch(FUNDS_URL, timeout))
    all_records: list[dict[str, str]] = []
    for index, detail_url in enumerate(fund_urls, start=1):
        print(f"[{index}/{len(fund_urls)}] Fetching {detail_url}", file=sys.stderr)
        history_url = find_history_url(detail_url, fetch(detail_url, timeout))
        records = parse_history(fetch(history_url, timeout), history_url)
        print(f"  {len(records)} rows from {history_url}", file=sys.stderr)
        all_records.extend(records)
    shared_records = []
    for record in all_records:
        fund_id = _fund_id_from_heading(record["fund_name"])
        currency = _fund_currency_from_fund_id(fund_id)
        suffix = currency.casefold()
        shared_records.append({
            "fund_id": fund_id,
            "fund_name": record["fund_name"],
            "source_url": record["history_url"],
            "date": record["date"],
            "unit_value": record[f"unit_value_{suffix}"],
            "unit_currency": currency,
            "fund_assets_value": record[f"assets_{suffix}"],
            "fund_assets_currency": currency,
        })
    write_shared_csv(output, shared_records, "intesa-invest")
    return len(fund_urls), len(all_records)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download historical values for every Intesa Invest fund."
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path(DEFAULT_OUTPUT),
        help=f"output CSV path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds (default: 30)",
    )
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        fund_count, row_count = download(args.output, args.timeout)
    except (HTTPError, URLError, OSError, UnicodeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {row_count} rows for {fund_count} funds to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
