from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


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
        values = dotenv_values(PROJECT_ROOT / ".env")

        def value(name: str, default: str | Path) -> str:
            configured = values.get(name)
            return str(default) if configured is None else configured

        data_dir = Path(value("TICKER_DATA_DIR", PROJECT_ROOT / "data"))
        adapter = value("TICKER_FUND_ADAPTER", "").strip() or None
        return cls(
            database_path=Path(value("TICKER_DATABASE", data_dir / "ticker.sqlite3")),
            log_path=Path(value("TICKER_LOG", data_dir / "ticker.log")),
            lock_path=Path(value("TICKER_LOCK", data_dir / "ticker.lock")),
            nbs_url=value("TICKER_NBS_URL", DEFAULT_NBS_URL),
            http_timeout=float(value("TICKER_HTTP_TIMEOUT", "15")),
            http_retries=int(value("TICKER_HTTP_RETRIES", "2")),
            fund_adapter=adapter,
        )

