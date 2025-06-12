# strategies/rsi_strategy.py
import pandas as pd
import talib

from .base_strategy import BaseStrategy


class RsiStrategy(BaseStrategy):
    """
    A mean-reversion strategy based on the Relative Strength Index (RSI).
    It generates a BUY signal when the RSI crosses up from an oversold condition
    and a SELL signal when it crosses down from an overbought condition.
    """

    def __init__(self, rsi_period=14, oversold_threshold=30, overbought_threshold=70):
        super().__init__()
        self.rsi_period = rsi_period
        self.oversold_threshold = oversold_threshold
        self.overbought_threshold = overbought_threshold

        # State variable to track if we were previously in an oversold/overbought zone
        self.last_zone = "NEUTRAL"  # Can be 'OVERSOLD' or 'OVERBOUGHT'

        print(
            f"RsiStrategy initialized with Period={self.rsi_period}, OS={self.oversold_threshold}, OB={self.overbought_threshold}"
        )
        self.reset()  # Call reset on initialization for clean startup

    def reset(self):
        """Resets the state of the strategy."""
        print("[Strategy State] RsiStrategy state has been reset.")
        self.last_market_position = "HOLD"

    def get_signal(self, market_data: pd.DataFrame) -> str:
        """
        Generates a signal based on RSI conditions.
        """
        if len(market_data) < self.rsi_period:
            return "HOLD"

        close_prices = market_data["close"]

        # Calculate RSI using the TA-Lib library
        rsi_values = talib.RSI(close_prices.values.astype(float), timeperiod=self.rsi_period)
        current_rsi = rsi_values[-1]

        if pd.isna(current_rsi):
            return "HOLD"

        print(f"[Strategy Values] Current RSI={current_rsi:.2f} | Last Zone: '{self.last_zone}'")

        # Determine the current zone
        if current_rsi < self.oversold_threshold:
            current_zone = "OVERSOLD"
        elif current_rsi > self.overbought_threshold:
            current_zone = "OVERBOUGHT"
        else:
            current_zone = "NEUTRAL"

        final_signal = "HOLD"

        # Generate BUY signal on exit from oversold zone
        if current_zone == "NEUTRAL" and self.last_zone == "OVERSOLD":
            final_signal = "BUY"

        # Generate SELL signal on exit from overbought zone
        elif current_zone == "NEUTRAL" and self.last_zone == "OVERBOUGHT":
            final_signal = "SELL"

        # Update the state for the next bar
        self.last_zone = current_zone

        return final_signal
