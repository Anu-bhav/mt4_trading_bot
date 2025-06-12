# strategies/sma_crossover.py
import pandas as pd

# It's good practice to import any libraries you might need, like talib
# import talib
from .base_strategy import BaseStrategy


class SmaCrossover(BaseStrategy):
    """
    A self-contained SMA Crossover strategy.
    - Handles its own indicator calculations.
    - Includes detailed logging for debugging.
    - Uses stateful logic to fire only on the crossover event.
    """

    def __init__(self, short_period=10, long_period=20):
        super().__init__()
        self.short_period = short_period
        self.long_period = long_period

        # This new state variable will track the previous state to detect a fresh crossover.
        # Possible states: 'BUY' (short > long), 'SELL' (short < long), 'HOLD' (equal or initial)
        self.last_market_position = "HOLD"

        print(f"SmaCrossover Strategy initialized with periods: {self.short_period}/{self.long_period}")

    def get_signal(self, market_data: pd.DataFrame) -> str:
        """
        Generates a signal based on the market data.
        """
        # --- [DEBUG] Step 1: Confirm function call and data integrity ---
        print("\n--- Strategy.get_signal() called ---")
        if market_data.empty:
            print("[DEBUG] Decision: HOLD (DataFrame is empty)")
            return "HOLD"

        print(f"[DEBUG] Received DataFrame with {len(market_data)} rows.")

        # --- Step 2: Ensure we have enough data for calculations ---
        if len(market_data) < self.long_period:
            print(f"[DEBUG] Decision: HOLD (Not enough data. Need {self.long_period}, have {len(market_data)})")
            return "HOLD"

        # --- Step 3: Calculate Indicators ---
        close_prices = market_data["close"]
        short_sma = close_prices.rolling(window=self.short_period).mean().iloc[-1]
        long_sma = close_prices.rolling(window=self.long_period).mean().iloc[-1]

        # --- [DEBUG] Step 4: Check if indicators are valid ---
        if pd.isna(short_sma) or pd.isna(long_sma):
            print("[DEBUG] Decision: HOLD (SMA calculation resulted in NaN. Waiting for more data.)")
            return "HOLD"

        print(f"[DEBUG] Calculated Values: Short SMA={short_sma:.5f} | Long SMA={long_sma:.5f}")
        print(f"[DEBUG] Previous Market Position was: '{self.last_market_position}'")

        # --- Step 5: Determine the current market position based on SMAs ---
        if short_sma > long_sma:
            current_market_position = "BUY"
        elif short_sma < long_sma:
            current_market_position = "SELL"
        else:
            current_market_position = "HOLD"

        print(f"[DEBUG] Current Market Position is: '{current_market_position}'")

        # --- Step 6: Stateful Crossover Logic ---
        # Generate a BUY signal only if the market just crossed from SELL/HOLD to BUY
        if current_market_position == "BUY" and self.last_market_position != "BUY":
            final_signal = "BUY"
        # Generate a SELL signal only if the market just crossed from BUY/HOLD to SELL
        elif current_market_position == "SELL" and self.last_market_position != "SELL":
            final_signal = "SELL"
        # Otherwise, there is no new signal
        else:
            final_signal = "HOLD"

        # --- Step 7: Update state for the next bar ---
        self.last_market_position = current_market_position

        # --- [DEBUG] Step 8: Announce the final decision ---
        print(f"--- Final Strategy Signal: '{final_signal}' ---")
        return final_signal
