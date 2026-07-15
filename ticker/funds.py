from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol, Sequence

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
    fund_ids: tuple[str, ...]

    def fetch(
        self, target_date: date, session: requests.Session, timeout: float
    ) -> Sequence[FundValue]: ...


def load_adapter(name: str | None) -> FundAdapter | None:
    if name is None:
        return None
    if name == "intesa_invest":
        from ticker.intesa_invest import IntesaInvestAdapter

        return IntesaInvestAdapter()
    if name == "raiffeisen_invest":
        from ticker.raiffeisen_invest import RaiffeisenInvestAdapter

        return RaiffeisenInvestAdapter()
    if name == "nlb_fondovi":
        from ticker.nlb_fondovi import NlbFondoviAdapter

        return NlbFondoviAdapter()
    if name == "otp_invest":
        from ticker.otp_invest import OtpInvestAdapter

        return OtpInvestAdapter()
    if name == "unicredit_invest":
        from ticker.unicredit_invest import UniCreditInvestAdapter

        return UniCreditInvestAdapter()
    if name == "wvp_fondovi":
        from ticker.wvp_fondovi import WvpFondoviAdapter

        return WvpFondoviAdapter()
    raise FundAdapterError(
        f"Unknown fund adapter {name!r}; available adapters: "
        "intesa_invest, raiffeisen_invest, nlb_fondovi, otp_invest, "
        "unicredit_invest, wvp_fondovi"
    )


def load_adapters(names: str | None) -> tuple[FundAdapter, ...]:
    if names is None:
        return ()

    adapters: list[FundAdapter] = []
    seen: set[str] = set()
    for raw_name in names.split(","):
        name = raw_name.strip()
        if not name:
            raise FundAdapterError("Fund adapter names must not be empty")
        if name in seen:
            raise FundAdapterError(f"Duplicate fund adapter {name!r}")
        adapter = load_adapter(name)
        if adapter is not None:
            adapters.append(adapter)
        seen.add(name)
    return tuple(adapters)
