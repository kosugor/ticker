#!/usr/bin/env python3
"""Import Intesa Invest shared-format history into fund_values."""

from fund_history_csv_to_sqlite import DEFAULT_DATABASE, main


if __name__ == "__main__":
    raise SystemExit(main("Intesa Invest", "intesainvest_history.csv", DEFAULT_DATABASE))
