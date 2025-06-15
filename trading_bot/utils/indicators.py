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
    Calculates the Hurst Exponent of a time series in a numerically stable way.
    """
    if len(prices) < max_lag:
        return 0.5

    lags = range(2, max_lag)

    # Calculate variances for all lags
    variances = [np.var(np.subtract(prices[lag:], prices[:-lag])) for lag in lags]

    # --- The Fix: Filter out zero variances before taking the log ---
    # Create pairs of (lag, variance) and filter
    lag_variance_pairs = [(lag, var) for lag, var in zip(lags, variances) if var > 0]

    # If we don't have enough valid points to fit a line, we can't calculate.
    if len(lag_variance_pairs) < 2:
        return 0.5  # Return neutral value for flat/unstable series

    # Unpack the valid pairs
    valid_lags, valid_variances = zip(*lag_variance_pairs)

    # Now we can safely take the log and perform the regression (polyfit).
    try:
        # R/S analysis uses standard deviation, which is sqrt of variance
        tau = np.sqrt(valid_variances)
        poly = np.polyfit(np.log(valid_lags), np.log(tau), 1)
        return poly[0]  # The slope of the log-log plot is the Hurst Exponent
    except (np.linalg.LinAlgError, ValueError) as e:
        logging.warning(f"Could not calculate Hurst Exponent due to numerical instability: {e}")
        return 0.5  # Return neutral value on mathematical error


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
