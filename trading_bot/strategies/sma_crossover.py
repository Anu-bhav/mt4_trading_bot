# strategies/sma_crossover.py
import pandas as pd
import numpy as np
import logging

from .base_strategy import BaseStrategy


class SmaCrossover(BaseStrategy):
    """
    A self-contained SMA Crossover strategy with stateful logic.
    """

    def __init__(self, short_period=10, long_period=20):
        super().__init__(short_period=short_period, long_period=long_period)
        self.short_period = short_period
        self.long_period = long_period
        self.reset()

    def reset(self):
        """Resets the state of the strategy."""
        logging.info("[Strategy State] SmaCrossover state has been reset.")
        self.last_market_position = "HOLD"

    def get_signal(self, market_data: pd.DataFrame) -> str:
        """Generates a signal based on the market data."""
        if len(market_data) < self.long_period:
            return "HOLD"

        close_prices = market_data["close"].astype(np.float64)  # Use "Close" for backtesting data

        short_sma = close_prices.rolling(window=self.short_period).mean().iloc[-1]
        long_sma = close_prices.rolling(window=self.long_period).mean().iloc[-1]

        if pd.isna(short_sma) or pd.isna(long_sma):
            return "HOLD"

        epsilon = 1e-9

        if (short_sma - long_sma) > epsilon:
            current_market_position = "BUY"
        elif (long_sma - short_sma) > epsilon:
            current_market_position = "SELL"
        else:
            current_market_position = "HOLD"

        final_signal = "HOLD"
        if current_market_position == "BUY" and self.last_market_position != "BUY":
            final_signal = "BUY"
        elif current_market_position == "SELL" and self.last_market_position != "SELL":
            final_signal = "SELL"

        self.last_market_position = current_market_position
        return final_signal
