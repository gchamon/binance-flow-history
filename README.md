# binance-flow-history

Extracts deposits, withdrawals and convertions historical data from binance and inserts in a SQLite database.

It uses python-binance to interact with binance API. Binance API has some quirks in which it will tell you how long
to wait before retrying when hitting rate limit with response header `Retry-After`, but it doesn't work for all endpoints.

This project tries to overcome this by retrying after the minute from the binance server date changes. This suggestion was
found [here](), and it seems to work.

**Be warned**: hitting API limits can cause a temporary ban. This project won't be responsible if you lock yourself out of the API.

# Usage

```sh
BINANCE_API_KEY={KEY} BINANCE_API_SECRET={SECRET} uv run main.py --from-date 2023-01
```

# Output

- binance_data.db

```bash
sqlite3 binance_data.db '.tables'
convert_trades    deposits          fiat_withdrawals
```

# Example usages

## CSV history

Withdrawals:

```bash
sqlite3 -csv \
  binance_data.db  \
  'select DATETIME(ROUND(createTime / 1000), '\''unixepoch'\'') AS isodate, fiatCurrency, indicatedAmount, amount, totalFee, method, status from fiat_withdrawals order by `createTime`'
```

Convert:

```bash
sqlite3 -csv \
  binance_data.db  \
  'select DATETIME(ROUND(createTime / 1000), '\''unixepoch'\'') AS isodate, fromAsset, fromAmount, toAsset, toAmount, ratio, inverseRatio, orderStatus from convert_trades order by `createTime`'
```

Deposits:

```bash
sqlite3 -csv \
  binance_data.db  \
  'select DATETIME(ROUND(insertTime / 1000), '\''unixepoch'\'') AS isodate, amount, coin from deposits order by `insertTime`'
```

