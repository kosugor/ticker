#!/usr/bin/env python3
"""Download historical values for every fund listed by Raiffeisen Invest."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen


FUNDS_URL = "https://www.raiffeiseninvest.rs/nasi-fondovi/"
INVESTMENTS_URL = "https://www.raiffeiseninvest.rs/wp-json/wp/easervice/investments"
DEFAULT_OUTPUT = "raiffeiseninvest_history.csv"
USER_AGENT = "intesainvest-history/1.0 (+https://www.raiffeiseninvest.rs/)"
CSV_COLUMNS = (
    "fund_name", "fund_slug", "fund_code", "detail_url", "currency",
    "date", "timestamp", "unit_value",
)


def clean_text(parts: Iterable[str]) -> str:
    """Join text fragments and normalize HTML whitespace."""
    return " ".join(html.unescape("".join(parts)).split())


class LinkParser(HTMLParser):
    """Collect link targets from a page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)


class FundPageParser(HTMLParser):
    """Extract the display name and chart component properties."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.name = ""
        self.chart_attrs: dict[str, str] | None = None
        self._in_title = False
        self._title_depth = 0
        self._title_parts: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        tag = tag.lower()
        attributes = dict(attrs)
        title_classes = (attributes.get("class") or "").split()
        if tag == "h1" and "title-1" in title_classes:
            self._in_title = True
            self._title_depth = 1
            self._title_parts = []
        elif self._in_title:
            self._title_depth += 1
        if tag == "fond-chart":
            if self.chart_attrs is not None:
                raise ValueError("multiple <fond-chart> components found")
            self.chart_attrs = {
                key: value for key, value in attrs if value is not None
            }

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._in_title:
            return
        self._title_depth -= 1
        if self._title_depth == 0:
            self.name = clean_text(self._title_parts)
            self._in_title = False


@dataclass(frozen=True)
class Fund:
    name: str
    slug: str
    code: str
    detail_url: str
    currencies: tuple[str, ...]
    establishment_date: str
    today: str


def fetch(url: str, timeout: float, accept: str = "text/html") -> bytes:
    request = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": accept},
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_text(url: str, timeout: float) -> str:
    raw = fetch(url, timeout, "text/html,application/xhtml+xml")
    return raw.decode("utf-8", errors="replace")


def is_site_url(url: str) -> bool:
    hostname = (urlparse(url).hostname or "").lower().removeprefix("www.")
    return hostname == "raiffeiseninvest.rs"


def find_fund_urls(page: str) -> list[str]:
    parser = LinkParser()
    parser.feed(page)
    urls: list[str] = []
    for href in parser.hrefs:
        url = urljoin(FUNDS_URL, href)
        parsed = urlparse(url)
        parts = [part for part in parsed.path.split("/") if part]
        if is_site_url(url) and len(parts) == 2 and parts[0] == "fond":
            path = parsed.path.rstrip("/") + "/"
            canonical = parsed._replace(
                query="", fragment="", path=path
            ).geturl()
            if canonical not in urls:
                urls.append(canonical)
    if not urls:
        raise ValueError(f"no fund detail links found at {FUNDS_URL}")
    return urls


def component_value(
    attrs: dict[str, str], name: str, detail_url: str
) -> object:
    value = attrs.get(name)
    if value is None:
        raise ValueError(f"missing {name} on <fond-chart> at {detail_url}")
    try:
        return json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"invalid {name} on <fond-chart> at {detail_url}: {value!r}"
        ) from error


def parse_fund(detail_url: str, page: str) -> Fund:
    parser = FundPageParser()
    parser.feed(page)
    if not parser.name:
        raise ValueError(f"no fund display name found at {detail_url}")
    if parser.chart_attrs is None:
        raise ValueError(f"no <fond-chart> component found at {detail_url}")

    code = component_value(parser.chart_attrs, ":fond", detail_url)
    currencies = component_value(parser.chart_attrs, ":currency", detail_url)
    establishment = component_value(
        parser.chart_attrs, ":establishment-date", detail_url
    )
    today = component_value(parser.chart_attrs, ":today", detail_url)
    if not isinstance(code, str) or not code:
        raise ValueError(f"invalid fund code at {detail_url}")
    if not isinstance(currencies, list) or not currencies or not all(
        isinstance(currency, str) and currency for currency in currencies
    ):
        raise ValueError(f"invalid currency list at {detail_url}")
    if not isinstance(establishment, str) or not isinstance(today, str):
        raise ValueError(f"invalid chart date at {detail_url}")

    slug = [part for part in urlparse(detail_url).path.split("/") if part][-1]
    return Fund(
        name=parser.name,
        slug=slug,
        code=code,
        detail_url=detail_url,
        currencies=tuple(currencies),
        establishment_date=establishment,
        today=today,
    )


def find_nonce(page: str) -> str:
    pattern = r'\bwpApiSettings\s*=\s*\{.*?"nonce":"([^"]+)"'
    match = re.search(pattern, page)
    if not match:
        raise ValueError(f"no REST API nonce found at {FUNDS_URL}")
    return match.group(1)


def history_url(fund: Fund, nonce: str) -> str:
    query = urlencode(
        {
            "from_date": fund.establishment_date,
            "to_date": fund.today,
            "fond_type": fund.code,
            "_wpnonce": nonce,
        }
    )
    return f"{INVESTMENTS_URL}?{query}"


def parse_history(fund: Fund, payload: bytes) -> list[dict[str, object]]:
    try:
        response = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid history response for {fund.name}") from error
    if not isinstance(response, dict) or response.get("success") is not True:
        message = (
            response.get("message", "unknown API error")
            if isinstance(response, dict)
            else "unexpected response"
        )
        raise ValueError(f"history request failed for {fund.name}: {message}")
    data = response.get("data")
    if not isinstance(data, list) or not data:
        raise ValueError(f"no history rows returned for {fund.name}")

    records: list[dict[str, object]] = []
    for row_number, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"invalid history row {row_number} for {fund.name}")
        currency_values = {
            item.get("valuta_dom"): item.get("cijena_udjela_dom_orig"),
            item.get("valuta"): item.get("cijena_udjela_val_orig"),
        }
        for currency in fund.currencies:
            unit_value = currency_values.get(currency)
            date = item.get("datum")
            timestamp = item.get("timestamp")
            if unit_value is None or date is None or timestamp is None:
                raise ValueError(
                    f"missing {currency} value in history row {row_number} "
                    f"for {fund.name}"
                )
            records.append(
                {
                    "fund_name": fund.name,
                    "fund_slug": fund.slug,
                    "fund_code": fund.code,
                    "detail_url": fund.detail_url,
                    "currency": currency,
                    "date": date,
                    "timestamp": timestamp,
                    "unit_value": unit_value,
                }
            )
    return records


def write_csv(output: Path, records: list[dict[str, object]]) -> None:
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
    listing_page = fetch_text(FUNDS_URL, timeout)
    nonce = find_nonce(listing_page)
    fund_urls = find_fund_urls(listing_page)
    all_records: list[dict[str, object]] = []
    for index, detail_url in enumerate(fund_urls, start=1):
        print(f"[{index}/{len(fund_urls)}] Fetching {detail_url}", file=sys.stderr)
        fund = parse_fund(detail_url, fetch_text(detail_url, timeout))
        payload = fetch(history_url(fund, nonce), timeout, "application/json")
        records = parse_history(fund, payload)
        print(
            f"  {len(records)} rows for {fund.name} "
            f"({', '.join(fund.currencies)})",
            file=sys.stderr,
        )
        all_records.extend(records)
    write_csv(output, all_records)
    return len(fund_urls), len(all_records)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download historical values for every Raiffeisen Invest fund."
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=Path(DEFAULT_OUTPUT),
        help=f"output CSV path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--timeout", type=float, default=30.0,
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
    except (HTTPError, URLError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {row_count} rows for {fund_count} funds to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
