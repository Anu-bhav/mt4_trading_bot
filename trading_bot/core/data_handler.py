# trading_bot/core/data_handler.py
import logging
from os import makedirs, path

import pandas as pd
import yfinance as yf

DATA_DIR = "data"


def get_yf_symbol(mt4_symbol: str) -> str:
    """Converts a typical MT4/broker symbol to a Yahoo Finance compatible ticker."""
    symbol = mt4_symbol.upper()
    if symbol == "GOLD" or symbol == "XAUUSD":
        return "GC=F"
    if symbol == "SILVER" or symbol == "XAGUSD":
        return "SI=F"
    if "USD" in symbol and not symbol.endswith("=X"):
        return f"{symbol.replace('USD', '')}-USD"
    if len(symbol) == 6 and symbol.isalpha():
        return f"{symbol[:3]}{symbol[3:]}=X"
    return symbol


def get_yf_interval(mt4_timeframe: str) -> str:
    """Converts an MT4 timeframe to a Yahoo Finance compatible interval."""
    tf_map = {"M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m", "H1": "60m", "H4": "1d", "D1": "1d", "W1": "1wk", "MN1": "1mo"}
    return tf_map.get(mt4_timeframe.upper(), "1d")


def download_and_get_data(mt4_symbol: str, mt4_timeframe: str) -> pd.DataFrame:
    """
    Downloads, caches, and robustly cleans historical data from Yahoo Finance.
    """
    if not path.exists(DATA_DIR):
        makedirs(DATA_DIR)

    file_path = path.join(DATA_DIR, f"{mt4_symbol.upper()}_{mt4_timeframe.upper()}.csv")

    data = None

    if path.exists(file_path):
        logging.info(f"Loading cached data from: {file_path}")
        try:
            data = pd.read_csv(file_path, index_col=0)
        except Exception as e:
            logging.warning(f"Could not read cached file. Re-downloading. Error: {e}")

    if data is None or data.empty:
        yf_symbol = get_yf_symbol(mt4_symbol)
        yf_interval = get_yf_interval(mt4_timeframe)
        logging.info(f"Downloading {yf_symbol} at {yf_interval} interval...")

        try:
            if yf_interval == "1m":
                period_to_download = "8d"
            elif yf_interval in ["2m", "5m", "15m", "30m", "60m", "90m", "1h"]:
                period_to_download = "60d"
            else:
                period_to_download = "2y"

            logging.info(f"Interval '{yf_interval}' detected. Requesting period='{period_to_download}'.")
            data = yf.download(
                tickers=yf_symbol, period=period_to_download, interval=yf_interval, auto_adjust=True, progress=False
            )

            if data.empty:
                raise ValueError(f"No data returned for {yf_symbol} at {yf_interval}.")

            data.to_csv(file_path)
            logging.info(f"Data downloaded and cached successfully at: {file_path}")

        except Exception as e:
            logging.error(f"FATAL ERROR: Could not download data for {yf_symbol}. Reason: {e}")
            return pd.DataFrame()

    return _clean_data(data)


# --- THIS IS THE DEFINITIVE, BULLETPROOF CLEANING FUNCTION ---
def _clean_data(data: pd.DataFrame) -> pd.DataFrame:
    """A helper function to robustly clean and type data."""
    if data.empty:
        return data

    # 1. Robustly flatten and clean column names
    # This handles both string and tuple (multi-level) column names.
    clean_columns = []
    for col in data.columns:
        # If col is a tuple (e.g., ('Open', 'GC=F')), take the first element.
        col_name = col[0] if isinstance(col, tuple) else col
        # Ensure it's a string and standardize it.
        clean_columns.append(str(col_name).capitalize())
    data.columns = clean_columns

    # 2. Convert the index to a proper DatetimeIndex.
    data.index = pd.to_datetime(data.index, errors="coerce", utc=True)
    data.dropna(axis=0, how="any", inplace=True)  # Drop rows with unparseable dates

    # 3. Ensure OHLCV columns exist and are numeric.
    required_cols = ["Open", "High", "Low", "Close", "Volume"]
    for col in required_cols:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")
        else:
            logging.error(f"Required column '{col}' not found after cleaning. Aborting.")
            return pd.DataFrame()

    # 4. Final drop of any rows that became NaN during numeric conversion.
    original_rows = len(data)
    data.dropna(subset=required_cols, inplace=True)
    cleaned_rows = len(data)
    if original_rows > cleaned_rows:
        logging.warning(f"Data cleaning removed {original_rows - cleaned_rows} rows with invalid values.")

    return data
