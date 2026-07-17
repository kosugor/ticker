#!/usr/bin/env python3
"""Import OTP Invest historical values from CSV into SQLite."""

from fund_history_csv_to_sqlite import DEFAULT_DATABASE, main


if __name__ == "__main__":
    raise SystemExit(main("OTP Invest", "otpinvest_history.csv", DEFAULT_DATABASE))
