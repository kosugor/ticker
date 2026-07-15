from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import FastAPI

from ticker.config import Settings
from ticker.database import connect


EXCHANGE_RATE_COLUMNS = "effective_date, eur_unit, middle_rate, fetched_at_utc"
FUND_VALUE_COLUMNS = (
    "fund_id, value_date, investment_unit_value, investment_unit_currency, "
    "fund_assets_value, fund_assets_currency, source_url, fetched_at_utc"
)


def _as_dicts(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _as_dict(cursor: sqlite3.Cursor) -> dict[str, Any] | None:
    rows = _as_dicts(cursor)
    return rows[0] if rows else None


def create_app(settings: Settings | None = None) -> FastAPI:
    configured_settings = settings or Settings.from_env()
    app = FastAPI(title="Ticker API")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/exchange-rates")
    def exchange_rates() -> list[dict[str, Any]]:
        with connect(configured_settings.database_path) as connection:
            return _as_dicts(
                connection.execute(
                    f"""SELECT {EXCHANGE_RATE_COLUMNS}
                        FROM exchange_rates
                        ORDER BY effective_date DESC"""
                )
            )

    @app.get("/fund-values")
    def fund_values() -> list[dict[str, Any]]:
        with connect(configured_settings.database_path) as connection:
            return _as_dicts(
                connection.execute(
                    f"""SELECT {FUND_VALUE_COLUMNS}
                        FROM fund_values
                        ORDER BY value_date DESC, fund_id ASC"""
                )
            )

    @app.get("/latest-values")
    def latest_values() -> dict[str, Any]:
        with connect(configured_settings.database_path) as connection:
            exchange_rate = _as_dict(
                connection.execute(
                    f"""SELECT {EXCHANGE_RATE_COLUMNS}
                        FROM exchange_rates
                        ORDER BY effective_date DESC
                        LIMIT 1"""
                )
            )
            latest_fund_values = _as_dicts(
                connection.execute(
                    f"""SELECT {FUND_VALUE_COLUMNS}
                        FROM fund_values
                        WHERE value_date = (SELECT MAX(value_date) FROM fund_values)
                        ORDER BY fund_id ASC"""
                )
            )

        return {
            "exchange_rate": exchange_rate,
            "fund_values": latest_fund_values,
        }

    return app


app = create_app()
