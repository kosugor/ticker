#!/usr/bin/env python3
"""Import NLB Fondovi historical values from CSV into SQLite."""

from fund_history_csv_to_sqlite import main


if __name__ == "__main__":
    raise SystemExit(main("NLB Fondovi", "nlbfondovi_history.csv", "nlbfondovi_history.db"))
