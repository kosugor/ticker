#!/usr/bin/env python3
"""Download the complete NLB Fondovi archive as CSV."""
from __future__ import annotations
import argparse, html, json, re
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from history_csv import fetch, write_csv

ARCHIVE_URL = "https://www.nlbfondovi.rs/investicioni-fondovi/nlb-devizni"
COMPONENT = re.compile(r'class="[^"]*js-unit-value-comparator[^"]*"[^>]*data-service-path="([^"]+)"|data-service-path="([^"]+)"[^>]*class="[^"]*js-unit-value-comparator')
FUNDS = {"2001": ("nlb-fondovi-novcani", "NLB Novčani", "RSD", "nav4Rsd", "subfundSizeRs"), "2002": ("nlb-fondovi-devizni", "NLB Devizni", "EUR", "nav4", "subfundSize"), "2003": ("nlb-fondovi-globalni-balansirani", "NLB Globalni Balansirani", "EUR", "nav4", "subfundSize"), "2004": ("nlb-fondovi-globalni-akcijski", "NLB Globalni akcijski", "EUR", "nav4", "subfundSize")}

def number(value: object) -> str:
    return str(value).replace("\u00a0", "").replace(" ", "").replace(".", "").replace(",", ".")
def download(timeout: float) -> list[dict[str, object]]:
    page = fetch(ARCHIVE_URL, timeout).decode("utf-8", "replace"); match = COMPONENT.search(page)
    if match is None: raise ValueError("NLB archive service path not found")
    service = urljoin(ARCHIVE_URL, html.unescape(match.group(1) or match.group(2)))
    url = f"{service}.fundsarchive.{'.'.join(FUNDS)}.json?" + urlencode({"dateMin":"1990-01-01", "dateMax":date.today().isoformat()})
    payload = json.loads(fetch(url, timeout, headers={"Referer": ARCHIVE_URL}))
    rows=[]
    for item in payload:
        for fund in item.get("funds", []):
            definition=FUNDS.get(str(fund.get("id")))
            if definition is None: continue
            fund_id,name,currency,unit,assets=definition
            rows.append({"fund_id":fund_id,"fund_name":name,"source_url":url,"date":item["date"],"unit_value":number(fund[unit]),"unit_currency":currency,"fund_assets_value":number(fund[assets]),"fund_assets_currency":currency})
    if not rows: raise ValueError("NLB archive returned no tracked rows")
    return rows
def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("-o","--output",type=Path,default=Path("nlbfondovi_history.csv")); parser.add_argument("--timeout",type=float,default=30); args=parser.parse_args()
    try: rows=download(args.timeout); write_csv(args.output, rows)
    except (HTTPError,URLError,OSError,ValueError,json.JSONDecodeError,KeyError) as error: parser.exit(1,f"error: {error}\n")
    print(f"Wrote {len(rows)} rows to {args.output}"); return 0
if __name__ == "__main__": raise SystemExit(main())
