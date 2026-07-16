from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from ticker.config import Settings
from ticker.database import connect, insert_fund_value
from ticker.funds import FundAdapterError, load_adapters
from ticker.http import build_session
from ticker.logging_config import configure_logging


LOGGER = logging.getLogger("collect_fund_value")


def _count_existing_funds(connection, society_id, fund_ids, target_date):
    if not fund_ids:
        return 0
    placeholders = ", ".join("?" for _ in fund_ids)
    query = (
        "SELECT COUNT(DISTINCT fund.id) FROM fund_values AS value "
        "JOIN funds AS fund ON fund.id = value.fund_id "
        "JOIN societies AS society ON society.id = fund.society_id "
        f"WHERE society.society_id = ? AND value.value_date = ? AND fund.fund_id IN ({placeholders})"
    )
    row = connection.execute(query, (society_id, target_date.isoformat(), *fund_ids)).fetchone()
    return int(row[0] if row is not None else 0)


def _configured_adapters(settings: Settings, adapter):
    if adapter is None:
        return load_adapters(settings.fund_adapter)
    if hasattr(adapter, "fetch"):
        return (adapter,)
    return tuple(adapter)


def _run_adapter(settings, target_date, session, adapter) -> str:
    fund_ids = tuple(getattr(adapter, "fund_ids", ()))
    provider = getattr(adapter, "fund_id", type(adapter).__name__)
    with connect(settings.database_path) as connection:
        if fund_ids and _count_existing_funds(connection, provider, fund_ids, target_date) == len(fund_ids):
            LOGGER.info(
                "fund values already present provider=%s count=%d date=%s",
                provider,
                len(fund_ids),
                target_date,
            )
            return "already-present"

    records = list(adapter.fetch(target_date, session, settings.http_timeout))
    if not records:
        LOGGER.info("fund values unavailable provider=%s date=%s", provider, target_date)
        return "unavailable"

    for record in records:
        record.validate(target_date)

    with connect(settings.database_path) as connection:
        inserted = False
        for record in records:
            inserted = insert_fund_value(connection, provider, record) or inserted
    outcome = "inserted" if inserted else "already-present"
    LOGGER.info(
        "fund values %s provider=%s count=%d date=%s",
        outcome,
        provider,
        len(records),
        target_date,
    )
    return outcome


def run(settings: Settings, today=None, session=None, adapter=None) -> str:
    today = today or datetime.now(ZoneInfo("Europe/Belgrade")).date()
    target_date = today - timedelta(days=1)
    adapters = _configured_adapters(settings, adapter)
    if not adapters:
        LOGGER.info("fund collector not configured")
        return "not-configured"

    session = session or build_session(settings.http_retries)
    outcomes: list[str] = []
    errors: list[tuple[str, Exception]] = []
    for current_adapter in adapters:
        provider = getattr(current_adapter, "fund_id", type(current_adapter).__name__)
        try:
            outcomes.append(_run_adapter(settings, target_date, session, current_adapter))
        except Exception as error:
            errors.append((provider, error))
            LOGGER.exception("fund provider failed provider=%s date=%s", provider, target_date)

    if errors and not outcomes:
        providers = ", ".join(provider for provider, _ in errors)
        raise FundAdapterError(
            f"All configured fund providers failed: {providers}"
        ) from errors[0][1]
    if errors:
        LOGGER.warning(
            "fund collection partially completed failed_providers=%s date=%s",
            [provider for provider, _ in errors],
            target_date,
        )
        return "partial"
    if "inserted" in outcomes:
        return "inserted"
    if "unavailable" in outcomes:
        return "unavailable"
    return "already-present"


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
