# trading_bot/strategies/alpha_vortex_strategy.py
import logging

import numpy as np
import pandas as pd
import talib

from ..utils.indicators import hurst_exponent, qqe, t3_ma
from .base_strategy import BaseStrategy


class AlphaVortexStrategy(BaseStrategy):
    """
    An advanced, multi-factor, regime-switching strategy that combines:
    1. MFCV (Hurst Exponent) for Market Regime Filtering (Trending vs. Mean-Reverting).
    2. QQE for Smoothed Trend-Following Entries.
    3. RoRD (Z-Score) for Extreme Mean-Reversion Entries.
    """

    def __init__(
        self,
        qqe_rsi_len=14,
        qqe_smooth_factor=5,
        rord_rsi1_len=14,
        rord_rsi2_len=14,
        rord_t3_len=5,
        rord_t3_vf=0.7,
        rord_dev_len=20,
        rord_z_len=20,
        rord_z_thresh_hi=2.0,
        rord_z_thresh_lo=-2.0,
        hurst_period=100,
        hurst_reverting_threshold=0.45,
        hurst_trending_threshold=0.55,
    ):
        params = locals()
        params.pop("self")
        super().__init__(**params)
        for key, value in params.items():
            setattr(self, key, value)
        self.reset()
        logging.info("AlphaVortexStrategy initialized.")

    def reset(self):
        logging.info("[Strategy State] AlphaVortex state has been reset.")

    def get_signal(self, market_data: pd.DataFrame) -> str:
        """Generates a signal based on the current market regime."""
        longest_lookback = max(self.qqe_rsi_len + self.qqe_smooth_factor, self.rord_rsi1_len, self.hurst_period) + 50
        if len(market_data) < longest_lookback:
            return "HOLD"

        df = market_data.copy()
        df.rename(columns={"Close": "close", "Low": "low", "High": "high"}, inplace=True, errors="ignore")
        close_prices = df["close"].astype(np.float64)

        # --- 1. REGIME FILTER (MFCV) ---
        hurst = hurst_exponent(close_prices, self.hurst_period)
        is_mean_reverting = hurst < self.hurst_reverting_threshold
        is_trending = hurst > self.hurst_trending_threshold

        logging.info(
            f"[AlphaVortex] Hurst={hurst:.3f} | Regime: {'Mean-Reverting' if is_mean_reverting else 'Trending' if is_trending else 'Random'}"
        )

        # --- If market is a random walk, do nothing ---
        if not is_mean_reverting and not is_trending:
            return "HOLD"

        # --- 2. CALCULATE INDICATORS FOR THE ACTIVE REGIME ---

        if is_trending:
            # --- QQE Trend-Following Logic ---
            qqe_fast, qqe_slow = qqe(close_prices, self.qqe_rsi_len, self.qqe_smooth_factor)

            # Check for NaN values before accessing
            if pd.isna(qqe_fast.iloc[-1]) or pd.isna(qqe_fast.iloc[-2]):
                return "HOLD"

            # A BUY signal is a fresh crossover of fast above slow
            if qqe_fast.iloc[-1] > qqe_slow.iloc[-1] and qqe_fast.iloc[-2] <= qqe_slow.iloc[-2]:
                logging.info("[AlphaVortex Signal] BUY: Trending Regime + QQE Bullish Crossover.")
                return "BUY"

            # A SELL signal is a fresh crossover of fast below slow
            if qqe_fast.iloc[-1] < qqe_slow.iloc[-1] and qqe_fast.iloc[-2] >= qqe_slow.iloc[-2]:
                logging.info("[AlphaVortex Signal] SELL: Trending Regime + QQE Bearish Crossover.")
                return "SELL"

        elif is_mean_reverting:
            # --- RoRD Mean-Reversion Logic ---
            rord_rsi1 = talib.RSI(close_prices, timeperiod=self.rord_rsi1_len)
            rord_rsi2 = talib.RSI(rord_rsi1.dropna(), timeperiod=self.rord_rsi2_len)
            rord_rsi2_t3 = t3_ma(rord_rsi2.dropna(), self.rord_t3_len, self.rord_t3_vf)

            rord_z = (rord_rsi2_t3 - talib.SMA(rord_rsi2_t3, self.rord_dev_len)) / talib.STDDEV(
                rord_rsi2_t3, self.rord_dev_len
            ).replace(0, np.nan)
            final_z = (rord_z - talib.SMA(rord_z, self.rord_z_len)) / talib.STDDEV(rord_z, self.rord_z_len).replace(0, np.nan)

            current_z = final_z.iloc[-1]
            prev_z = final_z.iloc[-2]

            if pd.isna(current_z) or pd.isna(prev_z):
                return "HOLD"

            logging.info(f"[AlphaVortex] Z-Score={current_z:.2f}")

            # A BUY signal is a fresh cross UP from an extreme low
            if current_z > self.rord_z_thresh_lo and prev_z <= self.rord_z_thresh_lo:
                logging.info("[AlphaVortex Signal] BUY: Mean-Reverting Regime + Z-Score Exiting Extreme Low.")
                return "BUY"

            # A SELL signal is a fresh cross DOWN from an extreme high
            if current_z < self.rord_z_thresh_hi and prev_z >= self.rord_z_thresh_hi:
                logging.info("[AlphaVortex Signal] SELL: Mean-Reverting Regime + Z-Score Exiting Extreme High.")
                return "SELL"

        return "HOLD"
