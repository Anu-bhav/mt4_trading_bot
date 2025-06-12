# strategies/base_strategy.py
from abc import ABC, abstractmethod

import pandas as pd


class BaseStrategy(ABC):
    """
    Abstract Base Class for all trading strategies.
    It defines the structure that the TradeManager expects.
    """

    def __init__(self, **params):
        """
        Strategies can accept parameters for tuning.
        """
        self.params = params

    @abstractmethod
    def get_signal(self, market_data: pd.DataFrame) -> str:
        """
        The core method of any strategy. It receives a pandas DataFrame
        of market data and returns a trading signal.

        :param market_data: DataFrame with columns ['time', 'open', 'high', 'low', 'close', 'tick_volume']
        :return: str Signal ('BUY', 'SELL', or 'HOLD').
        """
        pass

    @abstractmethod
    def reset(self):
        """
        Resets the internal state of the strategy to its initial condition.
        This is crucial for handling events like data gaps.
        """
        pass
