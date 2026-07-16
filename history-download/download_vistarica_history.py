#!/usr/bin/env python3
"""Download Vista Rica's published fund-value snapshot as history CSV rows."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from history_csv import fetch, write_shared_csv

BASE="https://vistarica.rs/wp-json/vistarica-sync/v1/fund-value"
FUNDS=(("vista-rica-invest","Vista Rica Invest","vistarica_invest","EUR"),("vista-rica-corporate","Vista Rica Corporate","vistarica_corporate","EUR"),("vista-rica-cash","Vista Cash","vistarica_cash","RSD"),("vista-rica-euro-cash","Vista Euro Cash","vistarica_euro_cash","EUR"),("vista-rica-origin","Vista Rica Origin","vistarica_origin","EUR"))
def value(slug, column, timeout): return json.loads(fetch(BASE+"?"+urlencode({"slug":slug,"column":column}),timeout))["value"]
def download(timeout: float):
    rows=[]
    for fund_id,name,slug,currency in FUNDS:
        suffix=currency.lower(); source=BASE+"?"+urlencode({"slug":slug})
        rows.append({"fund_id":fund_id,"fund_name":name,"source_url":source,"date":value(slug,"latest_date",timeout),"unit_value":value(slug,"unit_"+suffix,timeout),"unit_currency":currency,"fund_assets_value":value(slug,"fund_"+suffix,timeout),"fund_assets_currency":currency})
    return rows
def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("-o","--output",type=Path,default=Path("vistarica_history.csv")); parser.add_argument("--timeout",type=float,default=30); args=parser.parse_args()
    try: rows=download(args.timeout); write_shared_csv(args.output, rows, "vista-rica")
    except (HTTPError,URLError,OSError,ValueError,KeyError,json.JSONDecodeError) as error: parser.exit(1,f"error: {error}\n")
    print(f"Wrote {len(rows)} rows to {args.output}"); return 0
if __name__ == "__main__": raise SystemExit(main())
