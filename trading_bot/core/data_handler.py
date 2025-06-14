# data_handler.py
import logging
from os import makedirs, path

import pandas as pd
import yfinance as yf

DATA_DIR = "data"


def get_yf_symbol(mt4_symbol: str) -> str:
    """Converts a typical MT4/broker symbol to a Yahoo Finance compatible ticker."""
    if mt4_symbol.upper() == "GOLD" or mt4_symbol.upper() == "XAUUSD":
        return "GC=F"  # Gold Futures ticker
    if mt4_symbol.upper() == "SILVER" or mt4_symbol.upper() == "XAGUSD":
        return "SI=F"  # Silver Futures ticker

    # For Forex pairs like EURUSD, GBPJPY, etc.
    if len(mt4_symbol) == 6 and mt4_symbol.isalpha():
        return f"{mt4_symbol[:3]}-{mt4_symbol[3:]}=X"

    # For Crypto pairs like BTCUSD, ETHUSD, etc.
    if "USD" in mt4_symbol.upper() and len(mt4_symbol) > 3:
        return f"{mt4_symbol.upper().replace('USD', '')}-USD"

    return mt4_symbol.upper()  # Fallback for stock tickers etc.


def get_yf_interval(mt4_timeframe: str) -> str:
    """Converts an MT4 timeframe to a Yahoo Finance compatible interval."""
    # Note: Yahoo Finance has limited intervals. We map to the closest available one.
    tf_map = {
        "M1": "1m",
        "M5": "5m",
        "M15": "15m",
        "M30": "30m",
        "H1": "60m",
        "H4": "1d",  # YF doesn't have 4h, mapping to daily as a fallback
        "D1": "1d",
        "W1": "1wk",
        "MN1": "1mo",
    }
    return tf_map.get(mt4_timeframe.upper(), "1d")  # Default to daily if not found


def download_and_get_data(mt4_symbol: str, mt4_timeframe: str) -> pd.DataFrame:
    """
    Main function to download and cache historical data from Yahoo Finance.
    It checks if a local CSV file exists first. If not, it downloads,
    saves, and then returns the data.
    """
    if not path.exists(DATA_DIR):
        makedirs(DATA_DIR)

    file_path = path.join(DATA_DIR, f"{mt4_symbol}_{mt4_timeframe}.csv")

    # 1. Check if the data is already cached locally
    if path.exists(file_path):
        logging.info(f"Loading cached data from: {file_path}")
        try:
            return pd.read_csv(file_path, index_col=0, parse_dates=True)
        except Exception as e:
            logging.warning(f"Could not read cached file {file_path}. Re-downloading. Error: {e}")

    # 2. If not cached, download from Yahoo Finance
    yf_symbol = get_yf_symbol(mt4_symbol)
    yf_interval = get_yf_interval(mt4_timeframe)

    logging.info(f"No cached data found. Downloading {yf_symbol} at {yf_interval} interval from Yahoo Finance...")

    try:
        # Note: 'period' can be 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max
        # For intraday data (1m, 5m, etc.), Yahoo limits downloads to the last 7-60 days.
        data = yf.download(tickers=yf_symbol, period="1mo", interval=yf_interval, auto_adjust=True)

        if data.empty:
            raise ValueError(f"No data returned from Yahoo Finance for ticker {yf_symbol}.")

        # 3. Save the downloaded data to a CSV for future use
        data.to_csv(file_path)
        logging.info(f"Data downloaded and cached successfully at: {file_path}")

        return data

    except Exception as e:
        logging.error(f"FATAL ERROR: Could not download data for {yf_symbol}. Reason: {e}")
        return pd.DataFrame()  # Return empty dataframe on failure
