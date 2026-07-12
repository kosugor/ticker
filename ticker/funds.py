from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

import requests


class FundAdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class FundValue:
    fund_id: str
    value_date: date
    investment_unit_value: Decimal
    investment_unit_currency: str
    fund_assets_value: Decimal
    fund_assets_currency: str
    source_url: str

    def validate(self, target_date: date) -> None:
        if self.value_date != target_date:
            raise FundAdapterError(
                f"Fund record date {self.value_date} does not match target {target_date}"
            )
        if not self.fund_id.strip() or not self.source_url.strip():
            raise FundAdapterError("Fund ID and source URL are required")
        if not self.investment_unit_currency.strip() or not self.fund_assets_currency.strip():
            raise FundAdapterError("Both published currencies are required")
        if self.investment_unit_value <= 0 or self.fund_assets_value <= 0:
            raise FundAdapterError("Fund values must be positive")


class FundAdapter(Protocol):
    fund_id: str

    def fetch(
        self, target_date: date, session: requests.Session, timeout: float
    ) -> FundValue | None: ...


def load_adapter(name: str | None) -> FundAdapter | None:
    if name is None:
        return None
    raise FundAdapterError(
        f"Unknown fund adapter {name!r}; no live fund-specific adapter is included"
    )

