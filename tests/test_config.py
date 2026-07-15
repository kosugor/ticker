from pathlib import Path

import ticker.config as config


def test_settings_load_values_from_dotenv(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".env").write_text(
        "\n".join(
            (
                "TICKER_DATA_DIR=/var/lib/ticker",
                "TICKER_DATABASE=/tmp/custom.sqlite3",
                "TICKER_NBS_URL=https://example.test/rates",
                "TICKER_HTTP_TIMEOUT=8.5",
                "TICKER_HTTP_RETRIES=4",
                "TICKER_FUND_ADAPTER=intesa_invest,raiffeisen_invest",
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)

    settings = config.Settings.from_env()

    assert settings.database_path == Path("/tmp/custom.sqlite3")
    assert settings.log_path == Path("/var/lib/ticker/ticker.log")
    assert settings.lock_path == Path("/var/lib/ticker/ticker.lock")
    assert settings.nbs_url == "https://example.test/rates"
    assert settings.http_timeout == 8.5
    assert settings.http_retries == 4
    assert settings.fund_adapter == "intesa_invest,raiffeisen_invest"


def test_settings_use_defaults_without_dotenv(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)

    settings = config.Settings.from_env()

    data_dir = tmp_path / "data"
    assert settings.database_path == data_dir / "ticker.sqlite3"
    assert settings.log_path == data_dir / "ticker.log"
    assert settings.lock_path == data_dir / "ticker.lock"
    assert settings.nbs_url == config.DEFAULT_NBS_URL
    assert settings.http_timeout == 15
    assert settings.http_retries == 2
    assert settings.fund_adapter is None
