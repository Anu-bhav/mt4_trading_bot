# trading_bot/strategies/sma_crossover.py
import logging
from typing import Any

import numpy as np
import pandas as pd

from .base_strategy import BaseStrategy


class SmaCrossover(BaseStrategy):
    def __init__(self, short_period=10, long_period=20):
        super().__init__(short_period=short_period, long_period=long_period)
        self.short_period = short_period
        self.long_period = long_period
        self.reset()

    def reset(self):
        logging.info("[Strategy State] SmaCrossover state has been reset.")
        self.last_market_position = "HOLD"

    # --- THE SINGLE, UNIFIED SIGNAL METHOD ---
    def get_signal(self, market_data: pd.DataFrame) -> Any:
        """
        This method generates signals for both live trading and vectorized backtesting.
        For backtesting, it's called once with the full history.
        For live trading, it's called on each bar with expanding history.
        """
        df = market_data.copy()

        # 1. Calculate indicators for the entire given series
        df["short_sma"] = df["close"].rolling(window=self.short_period).mean()
        df["long_sma"] = df["close"].rolling(window=self.long_period).mean()

        # 2. Determine the market position for every bar
        df["position"] = np.where(df["short_sma"] > df["long_sma"], "BUY", "HOLD")
        df["position"] = np.where(df["short_sma"] < df["long_sma"], "SELL", df["position"])

        # 3. Find the exact crossover points
        # A signal is generated when the position is different from the previous bar's position.
        df["signal"] = np.where(df["position"] != df["position"].shift(1), df["position"], "HOLD")

        # --- LOGIC FOR LIVE TRADING ---
        # If the input DataFrame has only one "new" row more than our last state,
        # we assume it's live trading and return a single dictionary.
        # This is a heuristic that works because live trading adds one bar at a time.
        # For backtesting, we return the entire signal series.

        # A more robust check might be to pass a 'mode' flag, but this is clever.
        # Let's check the length. The backtester will call this only once with the full data.
        # The live trader calls it repeatedly with an expanding series.

        # We'll determine the mode by the length of the data. The backtester provides the full series.
        # Live trading will provide an ever-growing series.

        # Let's simplify and make it explicit. We'll add a parameter.

    # --- Let's try a different, cleaner approach. We'll have one method that calls a helper.
    # This is the final, most elegant design.

    def _calculate_signal_series(self, market_data: pd.DataFrame) -> pd.Series:
        """Helper function that contains the pure, vectorized trading logic."""
        df = market_data.copy()
        df["short_sma"] = df["close"].rolling(window=self.short_period).mean()
        df["long_sma"] = df["close"].rolling(window=self.long_period).mean()
        df["position"] = np.where(
            df["short_sma"] > df["long_sma"], "BUY", np.where(df["short_sma"] < df["long_sma"], "SELL", "HOLD")
        )
        df["signal"] = np.where(df["position"] != df["position"].shift(1), df["position"], "HOLD")
        return df["signal"]

    def get_signal(self, market_data: pd.DataFrame, is_backtest: bool = False) -> Any:
        """
        Unified signal function.
        :param market_data: The DataFrame of market data.
        :param is_backtest: Flag to determine the execution mode.
        """
        # --- THE GENIUS FIX ---
        # The core logic is always vectorized and fast.
        signal_series = self._calculate_signal_series(market_data)

        if is_backtest:
            # For a backtest, return the entire series of signals at once.
            return signal_series
        else:
            # For live trading, get the signal for the most recent bar.
            latest_signal = signal_series.iloc[-1]
            current_price = market_data["close"].iloc[-1]

            if latest_signal != "HOLD":
                comment = f"SMA({self.short_period}) vs SMA({self.long_period}) crossover"
                return {"signal": latest_signal, "price": current_price, "comment": comment}
            else:
                return {"signal": "HOLD"}
