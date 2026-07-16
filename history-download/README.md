# Investment fund history downloaders and SQLite importer

## Download Intesa Invest history

`download_intesainvest_history.py` discovers every fund listed on the Intesa
Invest website, follows each fund page's historical-values link, and combines
all table rows into one UTF-8 CSV file.

Run it with Python 3; no third-party packages are required:

```sh
python3 download_intesainvest_history.py
```

The default output is `intesainvest_history.csv`. To choose another path or HTTP
timeout:

```sh
python3 download_intesainvest_history.py --output history.csv --timeout 45
```

Run `python3 download_intesainvest_history.py --help` for all CLI options. The
command exits with a nonzero status if discovery, downloading, parsing, or CSV
writing fails.

## Download both histories

`download_all_histories.py` runs both site downloaders with the current Python
interpreter. By default it writes `intesainvest_history.csv` and
`raiffeiseninvest_history.csv` in the current directory:

```sh
python3 download_all_histories.py
```

Choose another output directory and pass an HTTP timeout to both downloaders
with:

```sh
python3 download_all_histories.py --output-dir histories --timeout 45
```

The wrapper stops immediately and exits with a nonzero status if either
downloader fails.

## Download Raiffeisen Invest history

`download_raiffeiseninvest_history.py` discovers all funds listed on the
Raiffeisen Invest website. It reads each fund's display name, currencies, and
embedded chart code from the detail page, then downloads the chart's full
history from the site's REST API. Multi-currency funds produce one row per
currency per date.

Run it with Python 3; no third-party packages are required:

```sh
python3 download_raiffeiseninvest_history.py
```

The default output is `raiffeiseninvest_history.csv`. To choose another path or
HTTP timeout:

```sh
python3 download_raiffeiseninvest_history.py \
  --output raiffeisen-history.csv \
  --timeout 45
```

The output columns are `fund_name`, `fund_slug`, `fund_code`, `detail_url`,
`currency`, `date`, `timestamp`, and `unit_value`. Run
`python3 download_raiffeiseninvest_history.py --help` for all CLI options. The
command exits with a nonzero status if discovery, downloading, parsing, or CSV
writing fails.

## Import the CSV into SQLite

Import `intesainvest_history.csv` into the `intesainvest_history` table in
`data/ticker.sqlite3` with:

```sh
python3 import_intesainvest_csv_to_sqlite.py
```

The importer creates the database and table when needed. It stores the source
date as `date_text` and also stores an ISO-formatted `date_iso` value. Exact
source rows are unique, so running the import again is safe and does not add
duplicates.

Choose different input, database, or table names with:

```sh
python3 import_intesainvest_csv_to_sqlite.py \
  --input history.csv \
  --database history.db \
  --table historical_values
```

Run `python3 import_intesainvest_csv_to_sqlite.py --help` for all CLI options.
The command exits with a nonzero status if CSV validation, date conversion, or
database writing fails.

## Import the Raiffeisen CSV into SQLite

Import `raiffeiseninvest_history.csv` into the `raiffeiseninvest_history` table in
`data/ticker.sqlite3` with:

```sh
python3 import_raiffeiseninvest_csv_to_sqlite.py
```

The importer creates the database and table when needed. It preserves every
source column, including `timestamp`, stores the source date as `date_text`, and
adds an ISO-formatted `date_iso`. Exact source rows are unique, so rerunning the
import does not add duplicates while distinct fund, currency, date, timestamp,
or value rows remain separate.

Choose different input, database, or table names with:

```sh
python3 import_raiffeiseninvest_csv_to_sqlite.py \
  --input raiffeisen-history.csv \
  --database raiffeisen-history.db \
  --table historical_values
```

Run `python3 import_raiffeiseninvest_csv_to_sqlite.py --help` for all CLI
options. The command exits with a nonzero status if CSV validation, date
conversion, or database writing fails.
