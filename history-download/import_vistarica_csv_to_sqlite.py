#!/usr/bin/env python3
"""Import Vista Rica historical values from CSV into SQLite."""

from fund_history_csv_to_sqlite import main


if __name__ == "__main__":
    raise SystemExit(main("Vista Rica", "vistarica_history.csv", "vistarica_history.db"))
