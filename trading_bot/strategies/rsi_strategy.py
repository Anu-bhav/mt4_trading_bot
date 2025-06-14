# strategies/rsi_strategy.py
import logging

import numpy as np
import pandas as pd
import talib

from .base_strategy import BaseStrategy


class RsiStrategy(BaseStrategy):
    """
    A mean-reversion strategy based on the Relative Strength Index (RSI).
    """

    def __init__(self, rsi_period=14, oversold_threshold=30, overbought_threshold=70):
        super().__init__(rsi_period=rsi_period, oversold_threshold=oversold_threshold, overbought_threshold=overbought_threshold)
        self.rsi_period = rsi_period
        self.oversold_threshold = oversold_threshold
        self.overbought_threshold = overbought_threshold
        self.reset()

    def reset(self):
        """Resets the state of the strategy."""
        logging.info("[Strategy State] RsiStrategy state has been reset.")
        self.last_zone = "NEUTRAL"

    def get_signal(self, market_data: pd.DataFrame) -> str:
        """Generates a signal based on RSI conditions."""
        if len(market_data) < self.rsi_period:
            return "HOLD"

        close_prices = np.asarray(market_data["close"].values, dtype=np.float64)
        rsi_values = talib.RSI(close_prices, timeperiod=self.rsi_period)

        current_rsi = pd.Series(rsi_values).iloc[-1]

        if pd.isna(current_rsi):
            return "HOLD"

        current_zone = "NEUTRAL"
        if current_rsi < self.oversold_threshold:
            current_zone = "OVERSOLD"
        elif current_rsi > self.overbought_threshold:
            current_zone = "OVERBOUGHT"

        final_signal = "HOLD"
        if current_zone == "NEUTRAL" and self.last_zone == "OVERSOLD":
            final_signal = "BUY"
        elif current_zone == "NEUTRAL" and self.last_zone == "OVERBOUGHT":
            final_signal = "SELL"

        self.last_zone = current_zone
        return final_signal
