#!/usr/bin/env python3
"""Import WVP Fondovi historical values from CSV into SQLite."""

from fund_history_csv_to_sqlite import main


if __name__ == "__main__":
    raise SystemExit(main("WVP Fondovi", "wvpfondovi_history.csv", "wvpfondovi_history.db"))
