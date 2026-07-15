# Ticker collectors

Cron-friendly Python collectors for the official NBS EUR/RSD middle rate and
investment-fund values stored in SQLite.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Run both collectors:

```bash
.venv/bin/python run_collectors.py
```

The default database, log, and lock files are created under `data/`. Enable one
or more fund providers with a comma-separated adapter list in `.env`:

```dotenv
TICKER_FUND_ADAPTER=intesa_invest,raiffeisen_invest,nlb_fondovi,otp_invest
```

Configuration is read from the `.env` file in the project root.

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
| `TICKER_FUND_ADAPTER` | unset; comma-separated `intesa_invest`, `raiffeisen_invest`, `nlb_fondovi`, and/or `otp_invest` |

## Cron

Use absolute paths and Belgrade civil time. For example, to retry at 09:00,
12:00, 15:00, and 18:00 each day:

```cron
CRON_TZ=Europe/Belgrade
0 9,12,15,18 * * * cd /home/ubuntu/codex-workspace/ticker && /home/ubuntu/codex-workspace/ticker/.venv/bin/python run_collectors.py
```

The orchestrator always exits with status zero, as configured. Collector errors
and partial failures must therefore be monitored through `data/ticker.log`.
