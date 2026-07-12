from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_NBS_URL = (
    "https://webappcenter.nbs.rs/ExchangeRateWebApp/ExchangeRateRsd/"
    "IndexNew_Partial_IndikativniKurs?lang=cir"
)


@dataclass(frozen=True)
class Settings:
    database_path: Path
    log_path: Path
    lock_path: Path
    nbs_url: str
    http_timeout: float
    http_retries: int
    fund_adapter: str | None

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("TICKER_DATA_DIR", PROJECT_ROOT / "data"))
        adapter = os.getenv("TICKER_FUND_ADAPTER", "").strip() or None
        return cls(
            database_path=Path(os.getenv("TICKER_DATABASE", data_dir / "ticker.sqlite3")),
            log_path=Path(os.getenv("TICKER_LOG", data_dir / "ticker.log")),
            lock_path=Path(os.getenv("TICKER_LOCK", data_dir / "ticker.lock")),
            nbs_url=os.getenv("TICKER_NBS_URL", DEFAULT_NBS_URL),
            http_timeout=float(os.getenv("TICKER_HTTP_TIMEOUT", "15")),
            http_retries=int(os.getenv("TICKER_HTTP_RETRIES", "2")),
            fund_adapter=adapter,
        )

