#!/bin/bash

echo withdraw.csv:
sqlite3 -header -csv \
  binance_data.db  \
  'select DATETIME(ROUND(createTime / 1000), '\''unixepoch'\'') AS isodate, fiatCurrency, indicatedAmount, amount, totalFee, method, status from fiat_withdrawals order by `createTime`' | tee withdraw.csv

echo convert.csv:
sqlite3 -header -csv \
  binance_data.db  \
  'select DATETIME(ROUND(createTime / 1000), '\''unixepoch'\'') AS isodate, fromAsset, fromAmount, toAsset, toAmount, ratio, inverseRatio, orderStatus from convert_trades order by `createTime`' | tee convert.csv

echo deposit.csv:
sqlite3 -header -csv \
  binance_data.db  \
  'select DATETIME(ROUND(insertTime / 1000), '\''unixepoch'\'') AS isodate, amount, coin from deposits order by `insertTime`' | tee deposit.csv

