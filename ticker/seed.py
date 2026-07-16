from __future__ import annotations

import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_seed_ids(
    societies_path: Path | None = None, funds_path: Path | None = None
) -> tuple[dict[str, int], dict[str, int]]:
    """Load logical provider/fund keys mapped to their integer database IDs."""
    societies_path = societies_path or PROJECT_ROOT / "data/societies.csv"
    funds_path = funds_path or PROJECT_ROOT / "data/funds.csv"
    with societies_path.open(encoding="utf-8-sig", newline="") as handle:
        societies = {
            row["society_key"]: int(row["society_id"])
            for row in csv.DictReader(handle)
        }
    with funds_path.open(encoding="utf-8-sig", newline="") as handle:
        funds = {
            row["fund_key"]: int(row["fund_id"])
            for row in csv.DictReader(handle)
        }
    return societies, funds


def ensure_seeded_database(database_path: Path) -> None:
    """Create the schema and seed rows with their explicit integer IDs."""
    societies_path = PROJECT_ROOT / "data/societies.csv"
    funds_path = PROJECT_ROOT / "data/funds.csv"
    with societies_path.open(encoding="utf-8-sig", newline="") as handle:
        societies = list(csv.DictReader(handle))
    with funds_path.open(encoding="utf-8-sig", newline="") as handle:
        funds = list(csv.DictReader(handle))
    from ticker.database import connect

    with connect(database_path) as connection:
        connection.executemany(
            "INSERT OR IGNORE INTO societies (id, society_id) VALUES (?, ?)",
            ((int(row["society_id"]), row["society_key"]) for row in societies),
        )
        connection.executemany(
            "INSERT OR IGNORE INTO funds (id, society_id, fund_id) VALUES (?, ?, ?)",
            ((int(row["fund_id"]), int(row["society_id"]), row["fund_key"]) for row in funds),
        )
