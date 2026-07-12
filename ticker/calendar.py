from __future__ import annotations

from datetime import date, timedelta

import holidays


def serbian_holidays(years: set[int] | None = None) -> holidays.HolidayBase:
    return holidays.country_holidays("RS", years=years, observed=True)


def is_business_day(day: date, calendar: holidays.HolidayBase | None = None) -> bool:
    calendar = calendar or serbian_holidays({day.year})
    return day.weekday() < 5 and day not in calendar


def next_business_day(day: date) -> date:
    candidate = day + timedelta(days=1)
    calendar = serbian_holidays({candidate.year, candidate.year + 1})
    while not is_business_day(candidate, calendar):
        candidate += timedelta(days=1)
    return candidate


def previous_business_day(day: date) -> date:
    candidate = day - timedelta(days=1)
    calendar = serbian_holidays({candidate.year, candidate.year - 1})
    while not is_business_day(candidate, calendar):
        candidate -= timedelta(days=1)
    return candidate

