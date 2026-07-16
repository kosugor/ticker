#!/usr/bin/env python3
"""Download WVP Fondovi's official XLSX archives and combine them into CSV."""
from __future__ import annotations
import argparse, io, zipfile
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from xml.etree import ElementTree
from history_csv import fetch, write_shared_csv

URL="https://www.wvpfondovi.rs/wp-admin/admin-ajax.php"
FUNDS=(("wvp-fondovi-premium","WVP PREMIUM"),("wvp-fondovi-dynamic","WVP DYNAMIC"),("wvp-fondovi-balanced","WVP BALANCED"),("wvp-fondovi-cash","WVP CASH"),("wvp-fondovi-merkur-esg-balanced","MERKUR ESG FUND BALANCED"),("wvp-fondovi-merkur-esg-dynamic","MERKUR ESG FUND DYNAMIC"),("wvp-fondovi-merkur-esg-solid","MERKUR ESG FUND SOLID"),("wvp-fondovi-bond","WVP BOND"))
NS="{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
def cell_text(cell, strings):
    value=cell.findtext(NS+"v", "")
    return strings[int(value)] if cell.get("t")=="s" and value else value
def workbook_rows(blob: bytes):
    with zipfile.ZipFile(io.BytesIO(blob)) as book:
        strings=["".join(node.itertext()) for node in ElementTree.fromstring(book.read("xl/sharedStrings.xml")).findall(NS+"si")]
        sheet=ElementTree.fromstring(book.read("xl/worksheets/sheet1.xml"))
    for row in sheet.findall(".//"+NS+"row"):
        yield [cell_text(cell, strings) for cell in row.findall(NS+"c")]
def excel_date(value: str) -> str:
    return (date(1899, 12, 30) + timedelta(days=int(float(value)))).isoformat()

def download(timeout: float, start: date, end: date):
    rows=[]
    for fund_id,name in FUNDS:
        query=urlencode({"action":"wvp_export_xlsx","fund":name,"start_date":start.isoformat(),"end_date":end.isoformat()})
        values=list(workbook_rows(fetch(URL+"?"+query, timeout)))
        if not values or len(values[0]) != 7: raise ValueError(f"invalid WVP export for {name}")
        for item in values[1:]:
            if len(item)!=7: continue
            rows.append({"fund_id":fund_id,"fund_name":name,"source_url":URL+"?"+query,"date":excel_date(item[0]),"unit_value":item[4],"unit_currency":"RSD","fund_assets_value":item[2],"fund_assets_currency":"RSD"})
    return rows
def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("-o","--output",type=Path,default=Path("wvpfondovi_history.csv")); parser.add_argument("--timeout",type=float,default=30); parser.add_argument("--start",type=date.fromisoformat,default=date(1990,1,1)); parser.add_argument("--end",type=date.fromisoformat,default=date.today()); args=parser.parse_args()
    try: rows=download(args.timeout,args.start,args.end); write_shared_csv(args.output, rows, "wvp-fondovi")
    except (HTTPError,URLError,OSError,ValueError,KeyError,zipfile.BadZipFile,ElementTree.ParseError) as error: parser.exit(1,f"error: {error}\n")
    print(f"Wrote {len(rows)} rows to {args.output}"); return 0
if __name__ == "__main__": raise SystemExit(main())
