from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from ticker.calendar import previous_business_day
from ticker.config import Settings
from ticker.database import connect, fund_value_exists, insert_fund_value
from ticker.funds import load_adapter
from ticker.http import build_session
from ticker.logging_config import configure_logging


LOGGER = logging.getLogger("collect_fund_value")


def run(settings: Settings, today=None, session=None, adapter=None) -> str:
    today = today or datetime.now(ZoneInfo("Europe/Belgrade")).date()
    target_date = previous_business_day(today)
    adapter = adapter if adapter is not None else load_adapter(settings.fund_adapter)
    if adapter is None:
        LOGGER.info("fund collector not configured")
        return "not-configured"

    with connect(settings.database_path) as connection:
        if fund_value_exists(connection, adapter.fund_id, target_date):
            LOGGER.info("fund value already present fund=%s date=%s", adapter.fund_id, target_date)
            return "already-present"

    session = session or build_session(settings.http_retries)
    record = adapter.fetch(target_date, session, settings.http_timeout)
    if record is None:
        LOGGER.info("complete fund value unavailable fund=%s date=%s", adapter.fund_id, target_date)
        return "unavailable"
    record.validate(target_date)

    with connect(settings.database_path) as connection:
        inserted = insert_fund_value(connection, record)
    outcome = "inserted" if inserted else "already-present"
    LOGGER.info("fund value %s fund=%s date=%s", outcome, adapter.fund_id, target_date)
    return outcome


def main() -> int:
    settings = Settings.from_env()
    configure_logging(settings.log_path)
    try:
        run(settings)
        return 0
    except Exception:
        LOGGER.exception("fund collector failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

