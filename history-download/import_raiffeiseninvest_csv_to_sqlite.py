#!/usr/bin/env python3
"""Import Raiffeisen Invest shared-format history into fund_values."""

from fund_history_csv_to_sqlite import DEFAULT_DATABASE, main


if __name__ == "__main__":
    raise SystemExit(main("Raiffeisen Invest", "raiffeiseninvest_history.csv", DEFAULT_DATABASE))
