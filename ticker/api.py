from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ticker.config import Settings
from ticker.database import connect


EXCHANGE_RATE_COLUMNS = "effective_date, eur_unit, middle_rate, fetched_at_utc"
FUND_VALUE_COLUMNS = (
    "society.society_id AS society_id, fund.fund_id, value.value_date, "
    "value.investment_unit_value, value.investment_unit_currency, "
    "value.fund_assets_value, value.fund_assets_currency, value.fetched_at_utc"
)
FUND_VALUE_FROM = """fund_values AS value
JOIN funds AS fund ON fund.id = value.fund_id
JOIN societies AS society ON society.id = fund.society_id"""
STATIC_DIR = Path(__file__).with_name("static")


def _as_dicts(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _as_dict(cursor: sqlite3.Cursor) -> dict[str, Any] | None:
    rows = _as_dicts(cursor)
    return rows[0] if rows else None


def create_app(settings: Settings | None = None) -> FastAPI:
    configured_settings = settings or Settings.from_env()
    app = FastAPI(title="Ticker API")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def homepage() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/exchange-rates")
    def exchange_rates(
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        parameters: list[str] = []
        if start_date is not None:
            conditions.append("effective_date >= ?")
            parameters.append(start_date.isoformat())
        if end_date is not None:
            conditions.append("effective_date <= ?")
            parameters.append(end_date.isoformat())

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with connect(configured_settings.database_path) as connection:
            return _as_dicts(
                connection.execute(
                    f"""SELECT {EXCHANGE_RATE_COLUMNS}
                        FROM exchange_rates
                        {where_clause}
                        ORDER BY effective_date DESC""",
                    parameters,
                )
            )

    @app.get("/fund-values")
    def fund_values(
        start_date: date | None = None,
        end_date: date | None = None,
        fund_id: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        parameters: list[str] = []
        if start_date is not None:
            conditions.append("value.value_date >= ?")
            parameters.append(start_date.isoformat())
        if end_date is not None:
            conditions.append("value.value_date <= ?")
            parameters.append(end_date.isoformat())
        if fund_id is not None:
            conditions.append("fund.fund_id = ?")
            parameters.append(fund_id)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with connect(configured_settings.database_path) as connection:
            return _as_dicts(
                connection.execute(
                    f"""SELECT {FUND_VALUE_COLUMNS}
                        FROM {FUND_VALUE_FROM}
                        {where_clause}
                        ORDER BY value.value_date DESC, fund.fund_id ASC""",
                    parameters,
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
                        FROM {FUND_VALUE_FROM}
                        WHERE value.value_date = (SELECT MAX(value_date) FROM fund_values)
                        ORDER BY fund.fund_id ASC"""
                )
            )

        return {
            "exchange_rate": exchange_rate,
            "fund_values": latest_fund_values,
        }

    return app


app = create_app()
