#!/usr/bin/env python3
"""Import WVP Fondovi historical values from CSV into SQLite."""

from fund_history_csv_to_sqlite import DEFAULT_DATABASE, main


if __name__ == "__main__":
    raise SystemExit(main("WVP Fondovi", "wvpfondovi_history.csv", DEFAULT_DATABASE))
