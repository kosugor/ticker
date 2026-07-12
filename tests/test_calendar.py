from datetime import date

from ticker.calendar import next_business_day, previous_business_day


def test_next_business_day_skips_weekend() -> None:
    assert next_business_day(date(2026, 7, 10)) == date(2026, 7, 13)


def test_next_business_day_skips_serbian_new_year_holidays() -> None:
    assert next_business_day(date(2025, 12, 31)) == date(2026, 1, 5)


def test_previous_business_day_skips_weekend() -> None:
    assert previous_business_day(date(2026, 7, 13)) == date(2026, 7, 10)

