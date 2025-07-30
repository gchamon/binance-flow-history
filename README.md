# binance-flow-history

Extracts deposits, withdrawals and convertions historical data from binance and inserts in a SQLite database.

It uses python-binance to interact with binance API. Binance API has some quirks in which it will tell you how long
to wait before retrying when hitting rate limit with response header `Retry-After`, but it doesn't work for all endpoints.

This project tries to overcome this by retrying after the minute from the binance server date changes. This suggestion was
found [here](https://dev.binance.vision/t/retry-after-header-is-0-when-receiving-429-error/2407/5), and it seems to work.

The information about the transactions are incrementally added to the database, so after you pull your flow history from binance, you can just increment it by using the `--from-date`

**Be warned**: hitting API limits can cause a temporary ban. This project won't be responsible if you lock yourself out of the API.

## Usage

```
uv run main.py --help
usage: main.py [-h] [-d FROM_DATE]

options:
  -h, --help            show this help message and exit
  -d, --from-date FROM_DATE
                        Defaults to first month of current year: 2025-01
```

## Output

- binance_data.db

```bash
sqlite3 binance_data.db '.tables'
convert_trades    deposits          fiat_withdrawals
```

## Example usages

### Get a long flow history then add a single month

Let's say you want to pull the flow history from all the way back to 2023:

```sh
BINANCE_API_KEY={KEY} BINANCE_API_SECRET={SECRET} uv run main.py --from-date 2023-01
```

Then you need to add just July 2025:

```sh
BINANCE_API_KEY={KEY} BINANCE_API_SECRET={SECRET} uv run main.py --from-date 2025-07
```

This will add to the database just the history from 2025-07 along with the rest of the history.

### Get CSV history

Withdrawals:

```bash
sqlite3 -header -csv \
  binance_data.db  \
  'select DATETIME(ROUND(createTime / 1000), '\''unixepoch'\'') AS isodate, fiatCurrency, indicatedAmount, amount, totalFee, method, status from fiat_withdrawals order by `createTime`'
```

Convert:

```bash
sqlite3 -header -csv \
  binance_data.db  \
  'select DATETIME(ROUND(createTime / 1000), '\''unixepoch'\'') AS isodate, fromAsset, fromAmount, toAsset, toAmount, ratio, inverseRatio, orderStatus from convert_trades order by `createTime`'
```

Deposits:

```bash
sqlite3 -header -csv \
  binance_data.db  \
  'select DATETIME(ROUND(insertTime / 1000), '\''unixepoch'\'') AS isodate, amount, coin from deposits order by `insertTime`'
```

### Generate CSVs

You can use `generate-csvs.sh` to automatically generate the CSVs from the previous example:

```
bash generate-csvs.sh
```

It will output to the terminal the CSVs and also write to `convert.csv`, `deposit.csv` and `withdraw.csv` the tables from the database. To suppress terminal output, use `bash generate-csvs.sh > /dev/null`.
