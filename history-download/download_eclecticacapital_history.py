#!/usr/bin/env python3
"""Download Eclectica Capital's chart histories embedded in fund pages."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from history_csv import fetch, write_csv

FUNDS = (("eclectica-capital-rsd-cash", "Eclectica RSD Cash UCITS fond", "RSD", "https://www.eclecticacapital.com/eclectica-rsd-cash-ucits-fund"),
         ("eclectica-capital-euro-cash", "Eclectica Euro Cash UCITS fond", "EUR", "https://www.eclecticacapital.com/eclectica-euro-cash-ucits-fund"))
DATA = re.compile(r"data:\s*JSON\.parse\('([^']+)'\)")

def download(timeout: float) -> list[dict[str, object]]:
    rows = []
    for fund_id, name, currency, url in FUNDS:
        page = fetch(url, timeout).decode("utf-8", "replace")
        match = DATA.search(page)
        if match is None: raise ValueError(f"no chart data found at {url}")
        values = json.loads(match.group(1).encode().decode("unicode_escape"))
        key = currency.lower()
        for value in values:
            if value.get("date") and value.get(key) is not None:
                rows.append({"fund_id": fund_id, "fund_name": name, "source_url": url, "date": value["date"],
                             "unit_value": value[key], "unit_currency": currency,
                             "fund_assets_value": "", "fund_assets_currency": currency})
    if not rows: raise ValueError("Eclectica Capital returned no history rows")
    return rows

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("-o","--output",type=Path,default=Path("eclecticacapital_history.csv")); parser.add_argument("--timeout",type=float,default=30); args=parser.parse_args()
    try: rows=download(args.timeout); write_csv(args.output, rows)
    except (HTTPError, URLError, OSError, ValueError, json.JSONDecodeError) as error: parser.exit(1, f"error: {error}\n")
    print(f"Wrote {len(rows)} rows to {args.output}"); return 0
if __name__ == "__main__": raise SystemExit(main())
