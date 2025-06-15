# trading_bot/strategies/base_strategy.py
from abc import ABC, abstractmethod
from typing import Any, Dict

import pandas as pd


class BaseStrategy(ABC):
    def __init__(self, **params):
        self.params = params

    @abstractmethod
    def get_signal(self, market_data: pd.DataFrame) -> Dict[str, Any]:
        """
        The single, unified method for generating signals.
        """
        pass

    @abstractmethod
    def reset(self):
        """Resets the internal state of the strategy."""
        pass
