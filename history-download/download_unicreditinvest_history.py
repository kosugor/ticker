#!/usr/bin/env python3
"""Download all published UniCredit Invest daily values as CSV."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from history_csv import fetch, write_shared_csv

URL = "https://unicreditinvest.rs/api/fund?pagination%5BpageSize%5D=25&populate%5BdailyValues%5D=*"
FUNDS = {
    "onemarkets-uc-invest-cash-dinar-fund": ("unicredit-invest-cash-dinar", "RSD"),
    "onemarkets-uc-invest-cash-eur-fund": ("unicredit-invest-cash-eur", "EUR"),
}

def download(timeout: float) -> list[dict[str, object]]:
    payload = json.loads(fetch(URL, timeout))
    rows: list[dict[str, object]] = []
    for fund in payload.get("data", []):
        definition = FUNDS.get(fund.get("slug"))
        if definition is None:
            continue
        fund_id, currency = definition
        unit, assets = ("priceRSD", "netAssets") if currency == "RSD" else ("priceEUR", "netAssetsEUR")
        for value in fund.get("dailyValues", []):
            if value.get("date") and value.get(unit) is not None:
                rows.append({"fund_id": fund_id, "fund_name": fund.get("name", fund_id), "source_url": URL,
                             "date": value["date"], "unit_value": value[unit], "unit_currency": currency,
                             "fund_assets_value": value.get(assets, ""), "fund_assets_currency": currency})
    if not rows:
        raise ValueError("UniCredit Invest API returned no tracked history rows")
    return rows

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=Path("unicreditinvest_history.csv"))
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    try:
        rows = download(args.timeout); write_shared_csv(args.output, rows, "unicredit-invest")
    except (HTTPError, URLError, OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(1, f"error: {error}\n")
    print(f"Wrote {len(rows)} rows to {args.output}")
    return 0
if __name__ == "__main__": raise SystemExit(main())
