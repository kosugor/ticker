from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from ticker.calendar import next_business_day
from ticker.config import Settings
from ticker.database import connect, exchange_rate_exists, insert_exchange_rate
from ticker.http import build_session
from ticker.logging_config import configure_logging
from ticker.nbs import NbsParseError, parse_official_eur_rate


LOGGER = logging.getLogger("collect_exchange_rate")


def run(settings: Settings, today=None, session=None) -> str:
    today = today or datetime.now(ZoneInfo("Europe/Belgrade")).date()
    target_date = next_business_day(today)

    with connect(settings.database_path) as connection:
        if exchange_rate_exists(connection, target_date):
            LOGGER.info("official EUR/RSD rate already present date=%s", target_date)
            return "already-present"

    session = session or build_session(settings.http_retries)
    response = session.get(settings.nbs_url, timeout=settings.http_timeout)
    response.raise_for_status()
    record = parse_official_eur_rate(response.text, target_date)
    if record is None:
        LOGGER.info("official EUR/RSD rate not yet available date=%s", target_date)
        return "unavailable"

    with connect(settings.database_path) as connection:
        inserted = insert_exchange_rate(connection, record.effective_date, record.rate)
    outcome = "inserted" if inserted else "already-present"
    LOGGER.info("official EUR/RSD rate %s date=%s", outcome, target_date)
    return outcome


def main() -> int:
    settings = Settings.from_env()
    configure_logging(settings.log_path)
    try:
        run(settings)
        return 0
    except (NbsParseError, Exception):
        LOGGER.exception("exchange-rate collector failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

