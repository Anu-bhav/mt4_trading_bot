# trading_bot/strategies/alpha_vortex_strategy.py
import logging
from typing import Any, Dict

import numpy as np
import pandas as pd
import talib

# We assume your custom indicators are in trading_bot/utils/
from ..utils.indicators import hurst_exponent, qqe, t3_ma
from .base_strategy import BaseStrategy


class AlphaVortexStrategy(BaseStrategy):
    """
    An advanced, multi-factor, regime-switching strategy. This version is designed
    to work identically in both live trading and backtesting by recalculating
    on each new bar of data it receives.
    """

    def __init__(
        self,
        qqe_rsi_len=14,
        qqe_smooth_factor=5,
        rord_rsi1_len=14,
        rord_rsi2_len=14,
        rord_t3_len=5,
        rord_t3_vf=0.7,
        rord_dev_len=50,
        rord_z_len=50,
        rord_z_thresh_hi=2.5,
        rord_z_thresh_lo=-2.5,
        hurst_period=150,
        hurst_reverting_threshold=0.40,
        hurst_trending_threshold=0.60,
    ):
        # Store all parameters.
        params = locals()
        params.pop("self")
        super().__init__(**params)
        for key, value in params.items():
            setattr(self, key, value)

        self.reset()
        logging.info("AlphaVortexStrategy initialized with its parameters.")

    def reset(self):
        """Resets the stateful parts of the strategy."""
        logging.info("[Strategy State] AlphaVortex state has been reset.")
        # This state is crucial for detecting FRESH crossovers.
        self.last_qqe_cross_state = "HOLD"  # Can be 'BULL' or 'BEAR'
        self.last_z_cross_state = "HOLD"  # Can be 'ABOVE_HI', 'BELOW_LO', 'NEUTRAL'

    def get_signal(self, market_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Generates a structured signal dictionary based on the current market regime.
        This is called on every bar for both live trading and backtesting.
        """
        # Determine the longest lookback period required by any indicator.
        longest_lookback = (
            max(
                self.qqe_rsi_len + self.qqe_smooth_factor,
                self.rord_rsi1_len,
                self.rord_dev_len,
                self.rord_z_len,
                self.hurst_period,
            )
            + 5
        )  # Add a small buffer

        if len(market_data) < longest_lookback:
            return {"signal": "HOLD"}

        df = market_data.copy()
        df.columns = [col.lower() for col in df.columns]
        close_prices = df["close"].astype(np.float64)
        current_price = close_prices.iloc[-1]

        # --- 1. REGIME FILTER (MFCV) ---
        hurst = hurst_exponent(close_prices, self.hurst_period)
        is_mean_reverting = hurst < self.hurst_reverting_threshold
        is_trending = hurst > self.hurst_trending_threshold

        regime = "Random"
        if is_mean_reverting:
            regime = "Mean-Reverting"
        if is_trending:
            regime = "Trending"

        logging.info(f"[AlphaVortex] Hurst={hurst:.3f} | Regime: {regime}")

        if not is_mean_reverting and not is_trending:
            return {"signal": "HOLD"}

        # --- 2. GENERATE SIGNAL BASED ON ACTIVE REGIME ---

        if is_trending:
            qqe_fast, qqe_slow = qqe(close_prices, self.qqe_rsi_len, self.qqe_smooth_factor)
            if pd.isna(qqe_fast.iloc[-1]) or pd.isna(qqe_slow.iloc[-1]):
                return {"signal": "HOLD"}

            # Determine current QQE state
            current_qqe_state = "BULL" if qqe_fast.iloc[-1] > qqe_slow.iloc[-1] else "BEAR"

            # Check for a fresh crossover
            if current_qqe_state == "BULL" and self.last_qqe_cross_state != "BULL":
                self.last_qqe_cross_state = "BULL"
                comment = f"Trending Regime (Hurst={hurst:.2f}) + QQE Bullish Crossover"
                logging.info(f"[AlphaVortex Signal] {comment}")
                return {"signal": "BUY", "price": current_price, "comment": comment}

            if current_qqe_state == "BEAR" and self.last_qqe_cross_state != "BEAR":
                self.last_qqe_cross_state = "BEAR"
                comment = f"Trending Regime (Hurst={hurst:.2f}) + QQE Bearish Crossover"
                logging.info(f"[AlphaVortex Signal] {comment}")
                return {"signal": "SELL", "price": current_price, "comment": comment}

            # If no new crossover, update state and hold
            self.last_qqe_cross_state = current_qqe_state

        elif is_mean_reverting:
            rord_rsi1 = talib.RSI(close_prices, timeperiod=self.rord_rsi1_len)
            rord_rsi2 = talib.RSI(rord_rsi1.dropna(), timeperiod=self.rord_rsi2_len)
            rord_rsi2_t3 = t3_ma(rord_rsi2.dropna(), self.rord_t3_len, self.rord_t3_vf)
            rord_z = (rord_rsi2_t3 - talib.SMA(rord_rsi2_t3, self.rord_dev_len)) / talib.STDDEV(
                rord_rsi2_t3, self.rord_dev_len
            ).replace(0, np.nan)
            final_z = (rord_z - talib.SMA(rord_z, self.rord_z_len)) / talib.STDDEV(rord_z, self.rord_z_len).replace(0, np.nan)
            current_z = final_z.iloc[-1]

            if pd.isna(current_z):
                return {"signal": "HOLD"}
            logging.info(f"[AlphaVortex] Z-Score={current_z:.2f}")

            # Determine current Z-Score zone
            current_z_state = "NEUTRAL"
            if current_z > self.rord_z_thresh_hi:
                current_z_state = "ABOVE_HI"
            if current_z < self.rord_z_thresh_lo:
                current_z_state = "BELOW_LO"

            # Check for a fresh exit from an extreme zone
            if current_z_state == "NEUTRAL" and self.last_z_cross_state == "BELOW_LO":
                self.last_z_cross_state = "NEUTRAL"
                comment = f"Mean-Reverting (Hurst={hurst:.2f}) + Z-Score Exiting Low ({current_z:.2f})"
                logging.info(f"[AlphaVortex Signal] {comment}")
                return {"signal": "BUY", "price": current_price, "comment": comment}

            if current_z_state == "NEUTRAL" and self.last_z_cross_state == "ABOVE_HI":
                self.last_z_cross_state = "NEUTRAL"
                comment = f"Mean-Reverting (Hurst={hurst:.2f}) + Z-Score Exiting High ({current_z:.2f})"
                logging.info(f"[AlphaVortex Signal] {comment}")
                return {"signal": "SELL", "price": current_price, "comment": comment}

            # If no new crossover, update state and hold
            self.last_z_cross_state = current_z_state

        return {"signal": "HOLD"}
