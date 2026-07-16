#!/usr/bin/env python3
"""Import UniCredit Invest historical values from CSV into SQLite."""

from fund_history_csv_to_sqlite import main


if __name__ == "__main__":
    raise SystemExit(main("UniCredit Invest", "unicreditinvest_history.csv", "unicreditinvest_history.db"))
