# trading_bot/backtesting/strategy_adapter.py
import logging

import pandas as pd
from backtesting import Strategy

from ..utils import risk_manager


class StrategyAdapter(Strategy):
    user_strategy: object = None
    risk_config: dict = None
    symbol_info: dict = None

    def init(self):
        logging.info("StrategyAdapter initialized (Event-Driven Simulation Mode).")
        if not self.user_strategy or not self.risk_config or not self.symbol_info:
            raise ValueError("Adapter requires user_strategy, risk_config, and symbol_info.")
        self.user_strategy.reset()

    def next(self):
        """
        This version correctly handles event-driven signals from the strategy.
        It does not assume a reversing system.
        """
        # 1. Prepare data for the strategy
        market_data_slice = self.data.df.iloc[: len(self.data)].copy()
        market_data_slice.columns = [col.lower() for col in market_data_slice.columns]

        # 2. Get the signal dictionary
        signal_dict = self.user_strategy.get_signal(market_data_slice)
        signal = signal_dict.get("signal", "HOLD").upper()

        # --- THE DEFINITIVE, SIMPLIFIED LOGIC ---

        # If we get a BUY signal, and we are flat, then BUY.
        if signal == "BUY" and not self.position:
            self._execute_backtest_trade("buy", signal_dict)

        # If we get a SELL signal, and we are flat, then SELL (short).
        elif signal == "SELL" and not self.position:
            self._execute_backtest_trade("sell", signal_dict)

    def _execute_backtest_trade(self, signal_type: str, signal_dict: dict):
        # This function is already correct from our previous iterations and needs no changes.
        entry_price = self.data.Close[-1]
        account_equity = self.equity
        trade_comment = signal_dict.get("comment", None)
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
        logging.info(
            f"[Backtest EXECUTION] Signal: {signal_type.upper()}, Size: {position_size_units} units, SL: {stop_loss_price:.2f}"
        )
        if signal_type == "buy":
            self.buy(size=position_size_units, sl=stop_loss_price, tp=take_profit_price, tag=trade_comment)
        elif signal_type == "sell":
            self.sell(size=position_size_units, sl=stop_loss_price, tp=take_profit_price, tag=trade_comment)
