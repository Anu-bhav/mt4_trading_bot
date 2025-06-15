# trading_bot/strategies/rord_strategy.py
import logging

import numpy as np
import pandas as pd
import talib

from ..utils.indicators import t3_ma
from .base_strategy import BaseStrategy


class RordStrategy(BaseStrategy):
    """
    Implements the trading logic of the RSI of RSI Deviation (RoRD) indicator.
    Generates signals based on a combination of extreme Z-score events and divergence.
    """

    def __init__(
        self,
        rsi1_len=14,
        rsi2_len=14,
        t3_len=5,
        t3_vf=0.7,
        dev_len=20,
        z_len=20,
        z_thresh_hi=2.0,
        z_thresh_lo=-2.0,
        divergence_lookback=15,
    ):
        params = locals()
        params.pop("self")
        super().__init__(**params)
        for key, value in params.items():
            setattr(self, key, value)
        self.reset()
        logging.info("RordStrategy initialized.")

    def reset(self):
        logging.info("[Strategy State] RoRD Strategy state has been reset.")

    def _find_pivots(self, series: pd.Series, lookback: int):
        """Helper to find pivot points using rolling windows, which is robust."""
        # Add a small buffer to the lookback to ensure center=True works as expected
        window = lookback + (lookback % 2 - 1)

        rolling_max = series.rolling(window=window, center=True, min_periods=1).max()
        rolling_min = series.rolling(window=window, center=True, min_periods=1).min()

        highs = series == rolling_max
        lows = series == rolling_min
        return highs, lows

    def get_signal(self, market_data: pd.DataFrame) -> str:
        """Generates a signal based on RoRD logic."""
        longest_lookback = max(self.rsi1_len, self.rsi2_len, self.t3_len, self.dev_len, self.z_len, self.divergence_lookback) + 5
        if len(market_data) < longest_lookback:
            return "HOLD"

        df = market_data.copy()
        df.rename(
            columns={"Close": "close", "Low": "low", "High": "high", "Open": "open", "Volume": "volume"},
            inplace=True,
            errors="ignore",
        )
        for col in ["close", "low", "high"]:
            df[col] = df[col].astype(np.float64)

        # --- RoRD CALCULATIONS ---
        df["rsi1"] = talib.RSI(df["close"], timeperiod=self.rsi1_len)
        df["rsi2"] = talib.RSI(df["rsi1"].dropna(), timeperiod=self.rsi2_len)
        df["rsi2_t3"] = t3_ma(df["rsi2"].dropna(), self.t3_len, self.t3_vf)

        df["rsi2_sma"] = talib.SMA(df["rsi2_t3"], timeperiod=self.dev_len)
        df["rsi2_stdev"] = talib.STDDEV(df["rsi2_t3"], timeperiod=self.dev_len).replace(0, np.nan)
        df["rsi2_z"] = (df["rsi2_t3"] - df["rsi2_sma"]) / df["rsi2_stdev"]

        df["z_sma"] = talib.SMA(df["rsi2_z"], timeperiod=self.z_len)
        df["z_stdev"] = talib.STDDEV(df["rsi2_z"], timeperiod=self.z_len).replace(0, np.nan)

        # --- THIS IS THE CORRECTED LINE ---
        df["final_z"] = (df["rsi2_z"] - df["z_sma"]) / df["z_stdev"]

        df_clean = df.dropna()
        if df_clean.empty:
            return "HOLD"

        current_z = df_clean["final_z"].iloc[-1]

        # --- Divergence Detection on the clean DataFrame ---
        rsi_pivots_high, rsi_pivots_low = self._find_pivots(df_clean["rsi2_t3"], self.divergence_lookback)
        price_pivots_high, price_pivots_low = self._find_pivots(df_clean["high"], self.divergence_lookback)

        rsi_lows = df_clean["rsi2_t3"][rsi_pivots_low]
        price_lows = df_clean["low"][price_pivots_low]
        rsi_highs = df_clean["rsi2_t3"][rsi_pivots_high]
        price_highs = df_clean["high"][price_pivots_high]

        bullish_divergence = False
        if len(price_lows) >= 2 and len(rsi_lows) >= 2:
            if price_lows.iloc[-1] < price_lows.iloc[-2] and rsi_lows.iloc[-1] > rsi_lows.iloc[-2]:
                bullish_divergence = True

        bearish_divergence = False
        if len(price_highs) >= 2 and len(rsi_highs) >= 2:
            if price_highs.iloc[-1] > price_highs.iloc[-2] and rsi_highs.iloc[-1] < rsi_highs.iloc[-2]:
                bearish_divergence = True

        logging.info(f"[RoRD Values] Z-score: {current_z:.2f} | BullDiv: {bullish_divergence} | BearDiv: {bearish_divergence}")

        # --- SIGNAL LOGIC ---
        if current_z < self.z_thresh_lo and bullish_divergence:
            logging.info("[RoRD Signal] Extreme Low Z-score + Bullish Divergence. BUY signal.")
            return "BUY"
        elif current_z > self.z_thresh_hi and bearish_divergence:
            logging.info("[RoRD Signal] Extreme High Z-score + Bearish Divergence. SELL signal.")
            return "SELL"

        return "HOLD"
