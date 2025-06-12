# trade_manager.py
import pandas as pd

from utils import risk_manager


class TradeManager:
    """
    The core engine responsible for analyzing signals, managing risk,
    executing trades, and managing open positions.
    """

    def __init__(self, dwx, strategy_object, config, required_history_bars: int):
        self.dwx = dwx
        self.strategy = strategy_object
        self.config = config
        self.risk_config = config.RISK_CONFIG
        self.required_history_bars = required_history_bars

        self.partials_taken = {}
        self.is_preloaded = False
        self.in_position = False  # Initialize in_position state
        self.market_data_df = pd.DataFrame(columns=["time", "open", "high", "low", "close", "tick_volume"])

        self.dwx.subscribe_symbols([self.config.STRATEGY_SYMBOL])
        print("TradeManager initialized.")
        self.update_position_status()

    def preload_data(self, symbol, time_frame, data):
        """Processes historical data to populate the initial DataFrame."""
        if symbol != self.config.STRATEGY_SYMBOL or time_frame != self.config.STRATEGY_TIMEFRAME:
            return
        if not data:
            print("[ERROR] Preload failed: Received empty historical data.")
            return

        df = pd.DataFrame.from_dict(data, orient="index")
        df.reset_index(inplace=True)
        df.rename(columns={"index": "time"}, inplace=True)
        for col in ["open", "high", "low", "close", "tick_volume"]:
            df[col] = pd.to_numeric(df[col])
        df.sort_values(by="time", inplace=True)

        self.market_data_df = df
        self.is_preloaded = True

        print(f"SUCCESS: Preloaded {len(self.market_data_df)} historical bars for {symbol}.")
        print("\n--- Performing initial analysis on preloaded data... ---")
        self.analyze_and_trade()

    def analyze_and_trade(self):
        """Main decision-making logic."""
        self.manage_open_positions()

        signal = self.strategy.get_signal(self.market_data_df.copy())
        open_positions = self._get_open_positions()

        print(f"Signal Check: Received '{signal}' | Open Positions: {len(open_positions)}")

        if not self.in_position and len(open_positions) < self.risk_config["MAX_OPEN_POSITIONS"]:
            if signal in ["BUY", "SELL"]:
                self._execute_new_trade(signal)
        elif self.in_position:
            current_trade_type = list(open_positions.values())[0]["type"]
            if (signal == "BUY" and current_trade_type == "sell") or (signal == "SELL" and current_trade_type == "buy"):
                print(f">>> EXECUTION: Reversing signal '{signal}' received. Closing all trades!")
                self.dwx.close_orders_by_magic(self.config.MAGIC_NUMBER)
        # Added else block for clarity in logs
        else:
            print("Decision: No action taken (e.g., already in position and signal matches).")

    def _execute_new_trade(self, signal):
        """Handles the complete logic for validating and opening a new trade."""
        account_equity = self.dwx.account_info.get("equity", 0)
        if account_equity <= 0:
            print("[ERROR] Account equity is 0 or not available yet. Aborting trade execution.")
            return

        symbol_data = self.dwx.market_data.get(self.config.STRATEGY_SYMBOL, {})
        required_keys = ["ask", "bid", "digits", "stoplevel", "spread", "lot_min", "lot_max", "lot_step", "tick_value"]
        if not all(k in symbol_data for k in required_keys):
            print("[ERROR] Market data from server is incomplete. Cannot execute trade.")
            return

        live_ask = symbol_data["ask"]
        live_bid = symbol_data["bid"]
        digits = symbol_data["digits"]
        stop_level_points = symbol_data["stoplevel"]
        spread_points = symbol_data["spread"]
        point_size = 1 / (10**digits)

        signal = signal.lower()
        entry_price = live_ask if signal == "buy" else live_bid

        sl_percent = self.risk_config["STOP_LOSS_PERCENT"] / 100.0
        tp_percent = self.risk_config["TAKE_PROFIT_PERCENT"] / 100.0

        if signal == "buy":
            stop_loss_price = entry_price * (1 - sl_percent)
            take_profit_price = entry_price * (1 + tp_percent) if self.risk_config["TAKE_PROFIT_PERCENT"] > 0 else 0
        elif signal == "sell":
            stop_loss_price = entry_price * (1 + sl_percent)
            take_profit_price = entry_price * (1 - tp_percent) if self.risk_config["TAKE_PROFIT_PERCENT"] > 0 else 0
        else:
            return

        min_stop_distance_price = (stop_level_points + spread_points) * point_size
        print(f"[Broker Rules] Min Stop Distance: {min_stop_distance_price:.{digits}f}")

        if signal == "buy" and stop_loss_price > (live_bid - min_stop_distance_price):
            stop_loss_price = live_bid - min_stop_distance_price
        elif signal == "sell" and stop_loss_price < (live_ask + min_stop_distance_price):
            stop_loss_price = live_ask + min_stop_distance_price

        stop_loss_distance = abs(entry_price - stop_loss_price)
        tick_value = symbol_data["tick_value"]
        value_per_point = tick_value / point_size

        if self.risk_config["USE_FIXED_LOT_SIZE"]:
            lot_size = self.risk_config["FIXED_LOT_SIZE"]
        else:
            lot_size = risk_manager.calculate_lot_size(
                account_balance=account_equity,
                risk_percent=self.risk_config["RISK_PER_TRADE_PERCENT"],
                stop_loss_price_distance=stop_loss_distance,
                value_per_point=value_per_point,
                min_lot=symbol_data["lot_min"],
                max_lot=symbol_data["lot_max"],
                lot_step=symbol_data["lot_step"],
            )

        if lot_size <= 0:
            print(f"[ERROR] Calculated lot size is {lot_size:.2f}. Aborting trade.")
            return

        print(f">>> EXECUTION: {signal.upper()} signal received. Sending order! [Lots: {lot_size}]")
        self.dwx.open_order(
            symbol=self.config.STRATEGY_SYMBOL,
            order_type=signal,
            lots=lot_size,
            price=0,
            stop_loss=stop_loss_price,
            take_profit=take_profit_price,
            magic=self.config.MAGIC_NUMBER,
        )

    def manage_open_positions(self):
        """Manages all currently open trades for this strategy."""
        if not self.in_position or self.market_data_df.empty:
            return
        current_price = self.market_data_df["close"].iloc[-1]
        for ticket, order in self._get_open_positions().items():
            open_price = order["open_price"]
            current_sl = order["SL"]
            order_type = order["type"]
            profit_percent = (
                ((current_price - open_price) / open_price) * 100.0
                if order_type == "buy"
                else ((open_price - current_price) / open_price) * 100.0
            )

            if self.risk_config["USE_TRAILING_STOP"] and profit_percent > self.risk_config["TRAILING_STOP_TRIGGER_PERCENT"]:
                trailing_sl_percent = self.risk_config["TRAILING_STOP_PERCENT"] / 100.0
                if order_type == "buy":
                    new_sl = current_price * (1 - trailing_sl_percent)
                    if new_sl > current_sl:
                        self.dwx.modify_order(ticket, stop_loss=new_sl)
                elif order_type == "sell":
                    new_sl = current_price * (1 + trailing_sl_percent)
                    if new_sl < current_sl or current_sl == 0:
                        self.dwx.modify_order(ticket, stop_loss=new_sl)

            for i, rule in enumerate(self.risk_config["PARTIAL_CLOSE_RULES"]):
                vol_pct, profit_pct = rule
                if profit_percent >= profit_pct and self.partials_taken.get(ticket, {}).get(i) is None:
                    close_vol = order["lots"] * (vol_pct / 100.0)
                    self.dwx.close_order(ticket, lots=close_vol)
                    if ticket not in self.partials_taken:
                        self.partials_taken[ticket] = {}
                    self.partials_taken[ticket][i] = True

    def on_bar_data(self, symbol, time_frame, time, open_p, high_p, low_p, close_p, tick_volume):
        if not self.is_preloaded:
            return
        if symbol != self.config.STRATEGY_SYMBOL or time_frame != self.config.STRATEGY_TIMEFRAME:
            return
        if time in self.market_data_df["time"].values:
            return

        print(f"\n--- New Live Bar Received: {symbol} {time_frame} at {time} ---")
        self.market_data_df.loc[len(self.market_data_df)] = [time, open_p, high_p, low_p, close_p, tick_volume]
        max_rows = self.required_history_bars + 200
        if len(self.market_data_df) > max_rows:
            self.market_data_df = self.market_data_df.iloc[-max_rows:]
        self.analyze_and_trade()

    def update_position_status(self):
        """Updates the in_position flag and resets state if flat."""
        open_positions = self._get_open_positions()
        self.in_position = len(open_positions) > 0
        if not self.in_position:
            self.partials_taken = {}

    # --- THIS IS THE RESTORED HELPER FUNCTION ---
    def _get_open_positions(self):
        """
        Helper to get all open positions for this strategy's magic number.
        It only returns market orders (buy/sell), not pending ones.
        """
        return {
            ticket: order
            for ticket, order in self.dwx.open_orders.items()
            if int(order.get("magic", -1)) == self.config.MAGIC_NUMBER and order.get("type") in ["buy", "sell"]
        }
