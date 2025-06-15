# trading_bot/backtesting/strategy_adapter.py
import logging

import pandas as pd
from backtesting import Strategy

# Import our own risk manager to reuse the same logic
from ..utils import risk_manager


class StrategyAdapter(Strategy):
    """
    An adapter that allows any strategy written for our live framework
    to be backtested using the backtesting.py library without modification.
    It simulates the live environment by feeding an expanding DataFrame to the strategy.
    """

    # --- These will be populated by the backtest engine ---
    user_strategy: object = None
    risk_config: dict = None
    symbol_info: dict = None

    def init(self):
        """
        Called once at the start of the backtest. We just reset the strategy.
        """
        logging.info("StrategyAdapter initialized (Live Simulation Mode).")
        if not self.user_strategy or not self.risk_config or not self.symbol_info:
            raise ValueError("Adapter requires user_strategy, risk_config, and symbol_info to be set.")

        self.user_strategy.reset()

    def next(self):
        """
        Called for each bar. This perfectly simulates the live trading loop.
        """
        # 1. Prepare the expanding DataFrame slice, exactly like the live TradeManager.
        # This is "slow" but guarantees logical consistency.
        market_data_slice = self.data.df.iloc[: len(self.data)].copy()
        market_data_slice.columns = [col.lower() for col in market_data_slice.columns]

        # 2. Get the structured signal from the strategy.
        signal_dict = self.user_strategy.get_signal(market_data_slice)

        signal = signal_dict.get("signal", "HOLD").upper()

        # 3. Translate the signal into a trade using our dynamic risk management.
        if signal == "BUY" and not self.position.is_long:
            if self.position.is_short:
                self.position.close()
            self._execute_backtest_trade("buy", signal_dict)

        elif signal == "SELL" and not self.position.is_short:
            if self.position.is_long:
                self.position.close()
            self._execute_backtest_trade("sell", signal_dict)

        elif self.position.is_long and signal == "SELL":
            self.position.close()
        elif self.position.is_short and signal == "BUY":
            self.position.close()

    def _execute_backtest_trade(self, signal_type: str, signal_dict: dict):
        """A miniature version of the TradeManager's execution logic."""
        entry_price = self.data.Close[-1]
        account_equity = self.equity

        sl_percent = self.risk_config["STOP_LOSS_PERCENT"] / 100.0
        stop_loss_price = entry_price * (1 - sl_percent) if signal_type == "buy" else entry_price * (1 + sl_percent)
        stop_loss_distance = abs(entry_price - stop_loss_price)

        point_size = 1 / (10 ** self.symbol_info["digits"])
        value_per_point = self.symbol_info["tick_value"] / point_size

        fx_lot_size = risk_manager.calculate_lot_size(
            account_balance=account_equity,
            risk_percent=self.risk_config["RISK_PER_TRADE_PERCENT"],
            stop_loss_price_distance=stop_loss_distance,
            value_per_point=value_per_point,
            lot_min=0.01,
            lot_max=1000,
            lot_step=0.01,
        )

        if fx_lot_size <= 0:
            return

        contract_size = self.symbol_info.get("contract_size", 1)
        position_size_units = int(round(fx_lot_size * contract_size))

        if position_size_units < 1:
            return

        tp_percent = self.risk_config["TAKE_PROFIT_PERCENT"] / 100.0
        take_profit_price = entry_price * (1 + tp_percent) if signal_type == "buy" else entry_price * (1 - tp_percent)
        if self.risk_config["TAKE_PROFIT_PERCENT"] <= 0:
            take_profit_price = None

        trade_comment = signal_dict.get("comment", None)
        logging.info(
            f"[Backtest EXECUTION] Signal: {signal_type.upper()}, Size: {position_size_units} units, SL: {stop_loss_price:.2f}"
        )

        if signal_type == "buy":
            self.buy(size=position_size_units, sl=stop_loss_price, tp=take_profit_price, tag=trade_comment)
        elif signal_type == "sell":
            self.sell(size=position_size_units, sl=stop_loss_price, tp=take_profit_price, tag=trade_comment)
