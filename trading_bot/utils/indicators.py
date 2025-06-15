# trading_bot/utils/indicators.py
import logging

import numpy as np
import pandas as pd
import talib


def t3_ma(source: pd.Series, length: int = 5, v_factor: float = 0.7) -> pd.Series:
    if len(source) < length:
        return pd.Series([np.nan] * len(source), index=source.index)
    e1 = talib.EMA(source.to_numpy(), timeperiod=length)
    e2 = talib.EMA(e1, timeperiod=length)
    e3 = talib.EMA(e2, timeperiod=length)
    e4 = talib.EMA(e3, timeperiod=length)
    e5 = talib.EMA(e4, timeperiod=length)
    e6 = talib.EMA(e5, timeperiod=length)
    c1 = -(v_factor**3)
    c2 = 3 * v_factor**2 + 3 * v_factor**3
    c3 = -6 * v_factor**2 - 3 * v_factor - 3 * v_factor**3
    c4 = 1 + 3 * v_factor + v_factor**3 + 3 * v_factor**2
    result = c1 * e6 + c2 * e5 + c3 * e4 + c4 * e3
    return pd.Series(result, index=source.index)


# --- THIS IS THE NEW, ROBUST HURST EXPONENT FUNCTION ---
def hurst_exponent(prices: pd.Series, max_lag: int = 100) -> float:
    """
    Calculates the Hurst Exponent of a time series using Rescaled Range (R/S) analysis.

    :param prices: A pandas Series of prices.
    :param max_lag: The maximum number of lags to use for the analysis.
    :return: The Hurst Exponent as a float.
    """
    if len(prices) < max_lag:
        return 0.5  # Not enough data, return neutral value

    # Create a list of lags to analyze
    lags = range(2, max_lag)

    # Calculate the Rescaled Range for each lag
    # We use a helper list to store the R/S values for valid lags
    rescaled_ranges = []

    for lag in lags:
        # Create two subsets of the data, offset by the lag
        ts1 = prices[lag:]
        ts2 = prices[:-lag]

        # Calculate the differences
        diffs = np.subtract(ts1.values, ts2.values)

        # Calculate the standard deviation of the differences
        std_dev = np.std(diffs)

        # If std_dev is zero, the series is flat for this lag; skip it
        if std_dev == 0:
            continue

        # Calculate the cumulative sum of the differences (the "mean-adjusted" series)
        mean_diff = np.mean(diffs)
        cumulative_sum = np.cumsum(diffs - mean_diff)

        # Calculate the range (max - min of the cumulative sum)
        r = np.max(cumulative_sum) - np.min(cumulative_sum)

        # Calculate the Rescaled Range (R/S)
        rs_value = r / std_dev
        rescaled_ranges.append(rs_value)

    # If we have no valid R/S values, we cannot proceed
    if len(rescaled_ranges) < 2:
        return 0.5

    # --- Perform a log-log regression to find the Hurst Exponent ---
    # We fit a line to the log of the R/S values vs. the log of the lags.
    # The slope of this line is the Hurst Exponent.
    try:
        # The lags used correspond to the rescaled_ranges we calculated
        valid_lags = lags[: len(rescaled_ranges)]

        poly = np.polyfit(np.log(valid_lags), np.log(rescaled_ranges), 1)
        return poly[0]
    except (np.linalg.LinAlgError, ValueError) as e:
        logging.warning(f"Could not calculate Hurst Exponent due to numerical instability: {e}")
        return 0.5


def qqe(source: pd.Series, rsi_len: int = 14, rsi_smooth_factor: int = 5) -> tuple[pd.Series, pd.Series]:
    """
    Calculates the Quantitative Qualitative Estimation (QQE) indicator.

    Returns a tuple containing two pandas Series:
    1. QQE Fast (QQEF)
    2. QQE Slow (QQES)
    """
    if len(source) < rsi_len + rsi_smooth_factor:
        empty_series = pd.Series([np.nan] * len(source), index=source.index)
        return empty_series, empty_series

    # Calculate the core smoothed RSI
    rsi = talib.RSI(source, timeperiod=rsi_len)
    rsi_smoothed = talib.EMA(rsi, timeperiod=rsi_smooth_factor)

    # Calculate the absolute true range of the smoothed RSI
    atr_rsi = talib.ATR(rsi_smoothed, rsi_smoothed, rsi_smoothed, timeperiod=rsi_len)

    # Calculate the QQE lines
    qqe_fast = rsi_smoothed
    qqe_slow = pd.Series(np.nan, index=source.index)

    # The QQE Slow line has complex state-based logic
    for i in range(1, len(source)):
        q_up = rsi_smoothed.iloc[i] + atr_rsi.iloc[i] * 4.236
        q_down = rsi_smoothed.iloc[i] - atr_rsi.iloc[i] * 4.236

        prev_qqe_slow = qqe_slow.iloc[i - 1]

        if np.isnan(prev_qqe_slow):
            qqe_slow.iloc[i] = q_up  # Initial state
            continue

        if q_up < prev_qqe_slow:
            qqe_slow.iloc[i] = q_up
        elif rsi_smoothed.iloc[i] > prev_qqe_slow and rsi_smoothed.iloc[i - 1] < prev_qqe_slow:
            qqe_slow.iloc[i] = q_down
        elif q_down > prev_qqe_slow:
            qqe_slow.iloc[i] = q_down
        elif rsi_smoothed.iloc[i] < prev_qqe_slow and rsi_smoothed.iloc[i - 1] > prev_qqe_slow:
            qqe_slow.iloc[i] = q_up
        else:
            qqe_slow.iloc[i] = prev_qqe_slow

    return qqe_fast, qqe_slow
