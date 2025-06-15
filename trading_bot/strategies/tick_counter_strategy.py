# strategies/tick_counter_strategy.py
import pandas as pd

from .base_strategy import BaseStrategy


class TickCounterStrategy(BaseStrategy):
    """
    A dummy strategy designed for rapid testing of the trading framework.
    It generates signals based on a simple bar count, not market analysis.
    - BUY signal on the 5th, 15th, 25th, etc., bar.
    - SELL signal on the 10th, 20th, 30th, etc., bar.
    """

    def __init__(self):
        super().__init__()
        # This counter will track how many bars we have processed.
        self.bar_counter = 0
        logging.info("TickCounterStrategy initialized: A dummy strategy for testing.")
        self.reset()  # Call reset on initialization for clean startup

    def reset(self):
        """Resets the state of the strategy."""
        logging.info("[Strategy State] TickCounterStrategy state has been reset.")
        self.bar_counter = 0

    def get_signal(self, market_data: pd.DataFrame) -> str:
        """
        Generates a signal based on the bar count.
        """
        # We don't need to analyze the data, just increment our counter.
        self.bar_counter += 1

        logging.info(f"[Dummy Strategy] Bar Count: {self.bar_counter}")

        final_signal = "HOLD"

        # Generate a SELL signal every 10 bars to close any open position.
        if self.bar_counter % 10 == 0:
            final_signal = "SELL"
            logging.info("[Dummy Strategy] --- SELL Signal Triggered ---")

        # Generate a BUY signal every 5 bars (but not on the 10th bar)
        elif self.bar_counter % 5 == 0:
            final_signal = "BUY"
            logging.info("[Dummy Strategy] --- BUY Signal Triggered ---")

        return final_signal
