# Ticker collectors

Cron-friendly Python collectors for the official NBS EUR/RSD middle rate and
investment-fund values stored in SQLite.

## Setup

```bash
uv sync
```

Run both collectors:

```bash
uv run python run_collectors.py
```

The default database, log, and lock files are created under `data/`. Enable one
or more fund providers with a comma-separated adapter list in `.env`:

```dotenv
TICKER_FUND_ADAPTER=intesa_invest,raiffeisen_invest,nlb_fondovi,otp_invest,unicredit_invest,wvp_fondovi,vista_rica,eclectica_capital
```

Configuration is read from the `.env` file in the project root.

## Web dashboard and API

Start the FastAPI server from the project root:

```bash
uv run uvicorn ticker.api:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/` to use the dashboard. It shows the latest
exchange rate and fund values, with date and fund filters for browsing the
stored history. The UI uses server-hosted HTML, CSS, and JavaScript and does
not require a separate build step or frontend development server.

The API reads the SQLite file selected by `TICKER_DATABASE` (or the default
`data/ticker.sqlite3`) and provides these JSON endpoints:

- `GET /health`
- `GET /exchange-rates`
- `GET /fund-values`
- `GET /latest-values`

Interactive OpenAPI documentation is available at
`http://127.0.0.1:8000/docs` while the server is running.

## Configuration

| Variable | Default |
| --- | --- |
| `TICKER_DATA_DIR` | `<project>/data` |
| `TICKER_DATABASE` | `<data>/ticker.sqlite3` |
| `TICKER_LOG` | `<data>/ticker.log` |
| `TICKER_LOCK` | `<data>/ticker.lock` |
| `TICKER_NBS_URL` | Official NBS partial exchange-rate page |
| `TICKER_HTTP_TIMEOUT` | `15` seconds |
| `TICKER_HTTP_RETRIES` | `2` |
| `TICKER_FUND_ADAPTER` | unset; comma-separated `intesa_invest`, `raiffeisen_invest`, `nlb_fondovi`, `otp_invest`, `unicredit_invest`, `wvp_fondovi`, `vista_rica`, and/or `eclectica_capital` |

## Cron

Use absolute paths and Belgrade civil time. For example, to retry at 09:00,
12:00, 15:00, and 18:00 each day:

```cron
CRON_TZ=Europe/Belgrade
0 9,12,15,18 * * * cd /home/ubuntu/codex-workspace/ticker && /home/ubuntu/.local/bin/uv run python run_collectors.py
```

The orchestrator always exits with status zero, as configured. Collector errors
and partial failures must therefore be monitored through `data/ticker.log`.
