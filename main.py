import argparse
from datetime import datetime
import json
import os
from pprint import PrettyPrinter
import sqlite3
import time
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from dateutil.relativedelta import relativedelta

from binance.client import Client
import binance.exceptions

T = TypeVar("T")

pp = PrettyPrinter(indent=4)


def pprint(title: str, message: Any) -> None:
    """Print formatted output with a title.

    Args:
        title: The header text to display before the formatted message
        message: The data to be pretty printed
    """
    print(title)
    pp.pprint(message)


client = Client(
    api_key=os.environ["BINANCE_API_KEY"],
    api_secret=os.environ["BINANCE_API_SECRET"],
)


def get_full_history(
    getter: Callable[..., Any],
    from_date: str,
    unwrapper: Callable[[Any], List[T]] = lambda x: x,
    month_interval: int = 1,
    delay: Optional[int] = None,
) -> List[T]:
    """Retrieve complete historical data from Binance API within a date range.

    Args:
        getter: API function to call for retrieving data
        from_date: Start date in format 'YYYY-MM'
        unwrapper: Function to extract relevant data from API response
        month_interval: Number of months to include in each API call
        delay: Optional delay between API calls in seconds

    Returns:
        List of historical data items
    """
    start_time = datetime.strptime(from_date, "%Y-%m")
    end_time = datetime.now()
    date_intervals = [
        start_time + relativedelta(months=m)
        for m in range(0, end_time.month - start_time.month + 1, month_interval)
    ]
    date_intervals.append(end_time + relativedelta(months=1))
    responses = [
        get_history(getter, cur_start, cur_end, delay)
        for cur_start, cur_end in zip(date_intervals[:-1], date_intervals[1:])
    ]
    full_history = [
        item for response in responses if response for item in unwrapper(response)
    ]
    return full_history


def get_min_from_headers(headers: Dict[str, str]) -> str:
    """Extract minutes from the Date header of API response.

    Args:
        headers: Response headers from Binance API

    Returns:
        Minutes portion of the timestamp as string
    """
    return headers["Date"][20:22]


def wait_server_minute_rollover(getter_response_headers: Dict[str, str]) -> None:
    """Wait until the server minute changes to avoid rate limiting.

    Args:
        getter_response_headers: Headers from the previous API response
    """
    print("waiting server minute rollover (max 1 min wait time)...")
    getter_date_min = get_min_from_headers(getter_response_headers)
    client.get_exchange_info()
    response_date_min = get_min_from_headers(client.response.headers)
    while getter_date_min == response_date_min:
        time.sleep(5)
        client.get_exchange_info()
        response_date_min = get_min_from_headers(client.response.headers)


def get_history(
    getter: Callable[..., T],
    start_time_date: datetime,
    end_time_date: datetime,
    delay: Optional[int] = None,
    retrying: bool = False,
) -> Optional[T]:
    """Retrieve historical data for a specific time period with retry logic.

    Args:
        getter: API function to call for retrieving data
        start_time_date: Start datetime
        end_time_date: End datetime
        delay: Optional delay between retries in seconds
        retrying: Flag indicating if this is a retry attempt

    Returns:
        API response data or None if request fails
    """
    start_time = int(start_time_date.timestamp() * 1000)
    end_time = int(end_time_date.timestamp() * 1000)
    try:
        result = getter(
            startTime=start_time,
            endTime=end_time,
        )
    except binance.exceptions.BinanceAPIException as e:
        if retrying is False:
            time.sleep(5)
            error_headers = client.response.headers
            if e.status_code == 429:
                print("hitting rate limit")
            wait_server_minute_rollover(error_headers)
            result = get_history(
                getter,
                start_time_date,
                end_time_date,
                delay,
                retrying=True,
            )
        else:
            raise
    if delay:
        time.sleep(delay)
    return result


def get_fiat_withdraw_history(**kwargs: Any) -> Dict[str, Any]:
    """Retrieve fiat withdrawal history from Binance API.

    Args:
        **kwargs: Additional parameters to pass to the API call

    Returns:
        Dictionary containing fiat withdrawal history data
    """
    kwargs["transactionType"] = "1-withdraw"
    return client.get_fiat_deposit_withdraw_history(**kwargs)


def create_tables(conn: sqlite3.Connection) -> None:
    """Create SQLite tables for storing Binance data.

    Args:
        conn: SQLite database connection
    """
    cursor = conn.cursor()

    # Fiat Withdrawals table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fiat_withdrawals (
        orderNo TEXT PRIMARY KEY,
        fiatCurrency TEXT,
        indicatedAmount REAL,
        amount REAL,
        totalFee REAL,
        method TEXT,
        status TEXT,
        createTime INTEGER,
        updateTime INTEGER
    )
    """)

    # Convert Trades table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS convert_trades (
        quoteId TEXT PRIMARY KEY,
        orderId INTEGER,
        orderStatus TEXT,
        fromAsset TEXT,
        fromAmount REAL,
        toAsset TEXT,
        toAmount REAL,
        ratio REAL,
        inverseRatio REAL,
        createTime INTEGER,
        orderType TEXT,
        side TEXT
    )
    """)

    # Deposits table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS deposits (
        id TEXT PRIMARY KEY,
        amount REAL,
        coin TEXT,
        network TEXT,
        status INTEGER,
        address TEXT,
        addressTag TEXT,
        txId TEXT,
        insertTime INTEGER,
        transferType INTEGER,
        confirmTimes TEXT,
        unlockConfirm INTEGER,
        walletType INTEGER
    )
    """)

    conn.commit()


def insert_fiat_withdrawals(
    conn: sqlite3.Connection, data: List[Dict[str, Any]]
) -> None:
    """Insert fiat withdrawal data into SQLite database.

    Args:
        conn: SQLite database connection
        data: List of fiat withdrawal records
    """
    cursor = conn.cursor()
    cursor.executemany(
        """
    INSERT OR REPLACE INTO fiat_withdrawals 
    (orderNo, fiatCurrency, indicatedAmount, amount, totalFee, method, status, 
     createTime, updateTime)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        [
            (
                item["orderNo"],
                item["fiatCurrency"],
                float(item["indicatedAmount"]),
                float(item["amount"]),
                float(item["totalFee"]),
                item["method"],
                item["status"],
                item["createTime"],
                item["updateTime"],
            )
            for item in data
        ],
    )
    conn.commit()


def insert_convert_trades(conn: sqlite3.Connection, data: List[Dict[str, Any]]) -> None:
    """Insert conversion trade data into SQLite database.

    Args:
        conn: SQLite database connection
        data: List of conversion trade records
    """
    cursor = conn.cursor()
    cursor.executemany(
        """
    INSERT OR REPLACE INTO convert_trades 
    (quoteId, orderId, orderStatus, fromAsset, fromAmount, toAsset, toAmount,
     ratio, inverseRatio, createTime, orderType, side)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        [
            (
                item["quoteId"],
                item["orderId"],
                item["orderStatus"],
                item["fromAsset"],
                float(item["fromAmount"]),
                item["toAsset"],
                float(item["toAmount"]),
                float(item["ratio"]),
                float(item["inverseRatio"]),
                item["createTime"],
                item["orderType"],
                item["side"],
            )
            for item in data
        ],
    )
    conn.commit()


def insert_deposits(conn: sqlite3.Connection, data: List[Dict[str, Any]]) -> None:
    """Insert deposit data into SQLite database.

    Args:
        conn: SQLite database connection
        data: List of deposit records
    """
    cursor = conn.cursor()
    cursor.executemany(
        """
    INSERT OR REPLACE INTO deposits 
    (id, amount, coin, network, status, address, addressTag, txId, insertTime,
     transferType, confirmTimes, unlockConfirm, walletType)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        [
            (
                item["id"],
                float(item["amount"]),
                item["coin"],
                item["network"],
                item["status"],
                item["address"],
                item["addressTag"],
                item["txId"],
                item["insertTime"],
                item["transferType"],
                item["confirmTimes"],
                item["unlockConfirm"],
                item["walletType"],
            )
            for item in data
        ],
    )
    conn.commit()


def parse_data(data_str: str) -> List[Dict[str, Any]]:
    """Parse JSON string data into Python objects.

    Args:
        data_str: JSON string to parse

    Returns:
        List of dictionaries containing parsed data
    """
    try:
        return json.loads(data_str.replace("'", '"'))
    except json.JSONDecodeError as e:
        print(f"Error parsing data: {e}")
        return []


def init_database(db_path: str = "binance_data.db") -> sqlite3.Connection:
    """Initialize SQLite database and create required tables.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        SQLite database connection
    """
    conn = sqlite3.connect(db_path)
    create_tables(conn)
    return conn


def main() -> None:
    """Main function to collect and store Binance trading data.

    Retrieves fiat withdrawals, conversion trades, and deposits from Binance API
    and stores them in a SQLite database. Data collection starts from either
    the specified date or January of the current year.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--from-date", type=str, required=False)
    args = parser.parse_args()
    from_date = args.from_date if args.from_date else f"{datetime.now().year}-01"

    fiat_withdrawals = get_full_history(
        get_fiat_withdraw_history,
        from_date,
        month_interval=1,
        unwrapper=lambda x: x["data"],
    )

    convert_trades = get_full_history(
        client.get_convert_trade_history, from_date, unwrapper=lambda x: x["list"]
    )

    deposits = get_full_history(client.get_deposit_history, from_date)
    # Initialize database and insert data
    conn = init_database()

    try:
        # Insert the data into respective tables
        insert_fiat_withdrawals(conn, fiat_withdrawals)
        insert_convert_trades(conn, convert_trades)
        insert_deposits(conn, deposits)

        # Optional: Print some basic statistics
        cursor = conn.cursor()

        print("\nData insertion complete. Basic statistics:")

        cursor.execute("SELECT COUNT(*) FROM fiat_withdrawals")
        print(f"Total fiat withdrawals: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM convert_trades")
        print(f"Total convert trades: {cursor.fetchone()[0]}")

        cursor.execute("SELECT COUNT(*) FROM deposits")
        print(f"Total deposits: {cursor.fetchone()[0]}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
