#!/bin/bash

sqlite3 -csv \
  binance_data.db  \
  'select DATETIME(ROUND(createTime / 1000), '\''unixepoch'\'') AS isodate, fiatCurrency, indicatedAmount, amount, totalFee, method, status from fiat_withdrawals order by `createTime`'

sqlite3 -csv \
  binance_data.db  \
  'select DATETIME(ROUND(createTime / 1000), '\''unixepoch'\'') AS isodate, fromAsset, fromAmount, toAsset, toAmount, ratio, inverseRatio, orderStatus from convert_trades order by `createTime`'

sqlite3 -csv \
  binance_data.db  \
  'select DATETIME(ROUND(insertTime / 1000), '\''unixepoch'\'') AS isodate, amount, coin from deposits order by `insertTime`'

