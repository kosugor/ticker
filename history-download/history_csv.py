"""Small standard-library helpers shared by the provider history downloaders."""

from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen


COLUMNS = (
    "fund_id", "fund_name", "source_url", "date", "unit_value",
    "unit_currency", "fund_assets_value", "fund_assets_currency",
)


def fetch(url: str, timeout: float, *, headers: dict[str, str] | None = None) -> bytes:
    request = Request(url, headers={"User-Agent": "ticker-history/1.0", **(headers or {})})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def write_csv(output: Path, rows: list[dict[str, object]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=output.parent,
                                         prefix=f".{output.name}.", suffix=".tmp", delete=False) as handle:
            temporary_name = handle.name
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary_name, output)
    except Exception:
        if temporary_name:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
        raise
