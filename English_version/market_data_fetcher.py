import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from binance import Client
from auth_client import get_binance_client


def fetch_minute_kline_data():
    # ==============================================
    # Configuration Parameters - Modify parameters here
    # ==============================================
    MAX_RECORD_COUNT = 10000  # Total number of records to fetch
    SYMBOL = "BNBUSDT"  # Trading pair
    LIMIT_PER_PAGE = 1000  # Max per page (Binance API limit, 1-1000)
    MAX_RETRY = 3  # Maximum retry attempts
    RETRY_INTERVAL = 1.5  # Retry interval (seconds)
    REQUEST_INTERVAL = 0.5  # Request interval to avoid API rate limits (seconds)
    TIMEOUT = 10  # Request timeout (seconds)
    # ==============================================

    # Parameter validation
    if not 1 <= LIMIT_PER_PAGE <= 1000:
        print(f"Error in limit per page: {LIMIT_PER_PAGE}, must be between 1 and 1000")
        return None
    if MAX_RETRY < 1 or RETRY_INTERVAL < 0 or REQUEST_INTERVAL < 0:
        print("Parameter error: Max retries must be > 0, intervals cannot be negative")
        return None
    if MAX_RECORD_COUNT < 1:
        print(f"Max record count must be > 0, currently: {MAX_RECORD_COUNT}")
        return None

    # Calculate total pages needed
    total_pages = (MAX_RECORD_COUNT + LIMIT_PER_PAGE - 1) // LIMIT_PER_PAGE
    print(f"Config: Fetching {MAX_RECORD_COUNT} minute K-lines for {SYMBOL}, split into {total_pages} pages")

    # Get Binance client
    client = get_binance_client()
    if not client:
        print("Login failed: Unable to get Binance client")
        return None
    client.session.timeout = TIMEOUT

    # Fetch K-line data with pagination
    all_klines = []
    # Fetch backwards starting from the current time
    current_end = int(datetime.now().timestamp() * 1000)
    total_fetched = 0
    page = 1

    print(f"Starting to fetch data...")

    while page <= total_pages and total_fetched < MAX_RECORD_COUNT:
        # Calculate the number of records needed for the current page
        remaining = MAX_RECORD_COUNT - total_fetched
        current_limit = min(LIMIT_PER_PAGE, remaining)

        # Calculate the start time for the current page (push back current_limit minutes)
        # Add 5 minutes buffer to avoid data duplication or omission due to time calculation errors
        current_start = current_end - (current_limit * 60000) - (5 * 60000)

        # Prepare request parameters
        params = {
            "symbol": SYMBOL,
            "interval": Client.KLINE_INTERVAL_1MINUTE,
            "limit": current_limit,
            "endTime": current_end,
            "startTime": current_start
        }

        # API request with retry mechanism
        klines = None
        for attempt in range(MAX_RETRY + 1):
            try:
                klines = client.get_klines(**params)
                break
            except Exception as e:
                if attempt < MAX_RETRY:
                    print(f"Request failed (Attempt {attempt + 1}/{MAX_RETRY + 1}): {str(e)[:50]}, retrying...")
                    time.sleep(RETRY_INTERVAL)
                    # Re-fetch client to handle potential connection issues
                    from auth_client import _global_client
                    _global_client = None
                    client = get_binance_client()
                    client.session.timeout = TIMEOUT
                else:
                    print(f"Max retries reached, request failed: {str(e)[:50]}")
                    return pd.DataFrame() if all_klines else None

        # Process fetched data
        if not klines:
            print("No data fetched, ending pagination requests")
            break

        # Filter out existing data (prevent duplicates)
        existing_timestamps = {x[0] for x in all_klines}
        new_klines = [k for k in klines if k[0] not in existing_timestamps]
        all_klines.extend(new_klines)
        total_fetched += len(new_klines)

        print(f"Page {page}: Fetched {len(new_klines)} records, cumulative {total_fetched}/{MAX_RECORD_COUNT}")

        # Update current end time to the earliest timestamp in the newly fetched data
        if new_klines:
            # Use the earliest timestamp in the new data as the end time for the next page
            current_end = min(k[0] for k in new_klines)
        else:
            # If no new data, push forward current_limit minutes
            current_end = current_start - (60000)

        # Check if there is more data available
        if len(klines) < current_limit:
            print(f"All available historical data fetched, total {total_fetched} records")
            break

        page += 1
        time.sleep(REQUEST_INTERVAL)

    if not all_klines:
        print("No K-line data fetched")
        return None

    # Data processing
    try:
        kline_matrix = np.array(all_klines, dtype=object)

        # Convert time columns
        timestamps = (kline_matrix[:, 0].astype(float) / 1000).astype('datetime64[s]')
        close_timestamps = (kline_matrix[:, 6].astype(float) / 1000).astype('datetime64[s]')

        # Convert numeric columns
        numeric_matrix = kline_matrix[:, [1, 2, 3, 4, 5, 7, 8, 9, 10]].astype(float)

        # Create DataFrame
        df = pd.DataFrame({
            "Timestamp": timestamps,
            "Open": numeric_matrix[:, 0],
            "High": numeric_matrix[:, 1],
            "Low": numeric_matrix[:, 2],
            "Close": numeric_matrix[:, 3],
            "Volume": numeric_matrix[:, 4],
            "Close_Time": close_timestamps,
            "Quote_Asset_Volume": numeric_matrix[:, 5],
            "Number_of_Trades": numeric_matrix[:, 6].astype(int),
            "Taker_Buy_Base_Asset_Volume": numeric_matrix[:, 7],
            "Taker_Buy_Quote_Asset_Volume": numeric_matrix[:, 8],
            "Ignore": kline_matrix[:, 11]
        })

        # Deduplicate and sort
        df = df.drop_duplicates("Timestamp").sort_values('Timestamp', ascending=False).reset_index(drop=True)
        print(f"Data processing complete: {len(df)} valid records")
        return df

    except Exception as e:
        print(f"Error during data processing: {str(e)}")
        return pd.DataFrame(all_klines) if all_klines else None


if __name__ == "__main__":
    df = fetch_minute_kline_data()
    if df is not None and not df.empty:
        print(f"\nFinal data shape: {df.shape}")
        print(f"Time range: from {df['Timestamp'].min()} to {df['Timestamp'].max()}")
        filename = "minute_klines.csv"
        df.to_csv(filename, encoding="utf-8-sig", index=False)
    print(df)