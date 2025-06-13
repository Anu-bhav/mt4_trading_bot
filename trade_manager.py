# trade_manager.py
import json
import logging
from os.path import join

import pandas as pd

from utils import risk_manager


class TradeManager:
    """
    The core engine responsible for analyzing signals, managing risk,
    executing trades, and managing open positions. This version uses a
    proactive, non-blocking state synchronization model for maximum robustness.
    """

    def __init__(self, dwx, strategy_object, config, required_history_bars: int):
        self.dwx = dwx
        self.strategy = strategy_object
        self.config = config
        self.risk_config = config.RISK_CONFIG
        self.required_history_bars = required_history_bars
        self.last_bar_timestamp = 0

        self.state_file_path = join(config.METATRADER_DIR_PATH, "DWX", "trade_manager_state.json")

        self.partials_taken = {}
        self.is_preloaded = False
        self.in_position = False

        self.market_data_df = pd.DataFrame(columns=["time", "open", "high", "low", "close", "tick_volume"])

        self.dwx.subscribe_symbols([self.config.STRATEGY_SYMBOL])

        self._load_state()

        print("TradeManager initialized.")

    def _load_state(self):
        """Loads the manager's state from a JSON file."""
        try:
            with open(self.state_file_path, "r") as f:
                state = json.load(f)
                self.partials_taken = {int(k): v for k, v in state.get("partials_taken", {}).items()}
                print("[State] Successfully loaded saved state.")
        except FileNotFoundError:
            print("[State] No state file found. Starting with a fresh state.")
        except Exception as e:
            print(f"[State] ERROR: Could not load state file. Starting fresh. Reason: {e}")

    def _save_state(self):
        """Saves the manager's current state to a JSON file."""
        try:
            with open(self.state_file_path, "w") as f:
                json.dump({"partials_taken": self.partials_taken}, f, indent=4)
            print("[State] Current state saved successfully.")
        except Exception as e:
            print(f"[State] ERROR: Could not save state file. Reason: {e}")

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
        df["time"] = pd.to_numeric(df["time"])
        for col in ["open", "high", "low", "close", "tick_volume"]:
            df[col] = pd.to_numeric(df[col])
        df.sort_values(by="time", inplace=True)

        self.market_data_df = df
        self.is_preloaded = True

        # Set the last bar timestamp from the preloaded data
        if not df.empty:
            self.last_bar_timestamp = df["time"].iloc[-1]

        print(f"SUCCESS: Preloaded {len(self.market_data_df)} historical bars for {symbol}.")
        print("\n--- Performing initial analysis on preloaded data... ---")
        self.analyze_and_trade()

    def analyze_and_trade(self):
        """
        Main decision-making logic. The single source of truth for state and action.
        """
        # 1. ALWAYS synchronize with the real world first.
        self.update_position_status()

        # 2. Manage any open positions based on the now-current state.
        if self.in_position:
            self.manage_open_positions()

        # 3. Get a signal from the strategy.
        signal = self.strategy.get_signal(self.market_data_df.copy())

        print(f"Signal Check: Received '{signal}' | In Position: {self.in_position}")

        # 4. Execute the decision tree.
        open_positions = self._get_open_positions()  # Get a fresh copy for this logic block
        if not self.in_position and signal in ["BUY", "SELL"]:
            if len(open_positions) < self.risk_config["MAX_OPEN_POSITIONS"]:
                self._execute_new_trade(signal)
        elif self.in_position:
            current_trade_type = list(open_positions.values())[0]["type"]
            if (signal == "BUY" and current_trade_type == "sell") or (signal == "SELL" and current_trade_type == "buy"):
                print(f">>> EXECUTION: Reversing signal '{signal}' received. Closing all trades!")
                self.dwx.close_orders_by_magic(self.config.MAGIC_NUMBER)
        else:
            print("Decision: No action taken.")

    def _execute_new_trade(self, signal: str):
        """
        Orchestrates the process of opening a new trade with correct, non-redundant logic.
        """
        signal = signal.lower()

        # 1. Check for readiness (account and market data)
        account_equity = self.dwx.account_info.get("equity", 0)
        if account_equity <= 0:
            logging.error("[EXECUTION ABORTED] Account equity not available.")
            return

        symbol_data = self.dwx.market_data.get(self.config.STRATEGY_SYMBOL, {})
        required_keys = ["ask", "bid", "digits", "stoplevel", "spread", "lot_min", "lot_max", "lot_step", "tick_value"]
        if not all(k in symbol_data for k in required_keys):
            logging.error("[EXECUTION ABORTED] Market data is incomplete.")
            return

        # 2. Determine the final, compliant Stop Loss price ONCE.
        stop_loss_price = self._get_stop_loss(signal, symbol_data)
        if stop_loss_price == 0.0:
            logging.error("[EXECUTION ABORTED] Could not calculate a valid stop loss.")
            return

        # 3. Calculate Lot Size using the final SL price.
        lot_size = self._get_lot_size(signal, stop_loss_price, account_equity, symbol_data)
        if lot_size <= 0:
            logging.error(f"[EXECUTION ABORTED] Calculated lot size is {lot_size:.2f}.")
            return

        # 4. Calculate Take Profit.
        take_profit_price = self._get_take_profit(signal, symbol_data)

        # 5. Send the order with the verified parameters.
        logging.info(f">>> EXECUTION: {signal.upper()} signal received. Sending order! [Lots: {lot_size}]")
        self.dwx.open_order(
            symbol=self.config.STRATEGY_SYMBOL,
            order_type=signal,
            lots=lot_size,
            price=0,  # Market order
            stop_loss=stop_loss_price,
            take_profit=take_profit_price,
            magic=self.config.MAGIC_NUMBER,
        )

    def manage_open_positions(self):
        """Manages trailing stops and partial closes for open trades."""
        if not self.in_position or self.market_data_df.empty:
            return
        state_changed = False
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
                new_sl = self._get_trailing_stop_price(order_type, current_price)
                if (order_type == "buy" and new_sl > current_sl) or (
                    order_type == "sell" and (new_sl < current_sl or current_sl == 0)
                ):
                    print(f"[Trailing Stop] Modifying order {ticket} SL to {new_sl:.5f}")
                    self.dwx.modify_order(ticket, stop_loss=new_sl)

            for i, rule in enumerate(self.risk_config["PARTIAL_CLOSE_RULES"]):
                vol_pct, profit_pct = rule
                if profit_percent >= profit_pct and self.partials_taken.get(ticket, {}).get(i) is None:
                    close_vol = round(order["lots"] * (vol_pct / 100.0), 2)
                    print(f"[Partial Close] Closing {close_vol:.2f} lots for order {ticket}")
                    self.dwx.close_order(ticket, lots=close_vol)
                    if ticket not in self.partials_taken:
                        self.partials_taken[ticket] = {}
                    self.partials_taken[ticket][i] = True
                    state_changed = True

        if state_changed:
            self._save_state()

    def on_bar_data(self, symbol, time_frame, time, open_p, high_p, low_p, close_p, tick_volume):
        """The main entry point for live bar data from the client."""
        try:
            time = int(time)
        except (ValueError, TypeError):
            print(f"Received invalid timestamp format, ignoring bar: {time}")
            return

        if not self.is_preloaded:
            return
        if symbol != self.config.STRATEGY_SYMBOL or time_frame != self.config.STRATEGY_TIMEFRAME:
            return

        # --- [Gotcha 2.2] Bad Candle / Corrupted Data Check ---
        if not (open_p > 0 and high_p > 0 and low_p > 0 and close_p > 0 and high_p >= low_p):
            print(f"[DATA WARNING] Received a bad/corrupted candle, ignoring: {symbol} {time}")
            return

        # Prevent processing duplicate bars
        if time <= self.last_bar_timestamp:
            return

        # --- [Gotcha 2.1] Gaps in Data (Missed Candle) Check ---
        if self.last_bar_timestamp > 0:  # Don't check on the very first bar
            time_diff_seconds = time - self.last_bar_timestamp

            # Get the expected interval for the timeframe
            try:
                tf_str = self.config.STRATEGY_TIMEFRAME
                if "M" in tf_str:
                    interval_seconds = int(tf_str.replace("M", "")) * 60
                elif "H" in tf_str:
                    interval_seconds = int(tf_str.replace("H", "")) * 3600
                else:
                    interval_seconds = 60  # Default to 1 minute
            except:
                interval_seconds = 60

            # --- THE NEW, ROBUST GAP HANDLING LOGIC ---
            if time_diff_seconds > (interval_seconds * 1.9):
                print(
                    f"[DATA WARNING] Data gap detected. Time since last bar: {time_diff_seconds}s. Expected ~{interval_seconds}s."
                )
                print("[ACTION] Resetting strategy state to prevent decisions based on stale data.")
                self.strategy.reset()  # Reset the strategy's internal memory

        # Update the timestamp of the last processed bar
        self.last_bar_timestamp = time

        print(f"\n--- New Live Bar Received: {symbol} {time_frame} at {time} ---")
        self.market_data_df.loc[len(self.market_data_df)] = [time, open_p, high_p, low_p, close_p, tick_volume]
        max_rows = self.required_history_bars + 200
        if len(self.market_data_df) > max_rows:
            self.market_data_df = self.market_data_df.iloc[-max_rows:]

        self.analyze_and_trade()

    def update_position_status(self):
        """Synchronizes the internal 'in_position' flag with the broker's reality."""
        open_positions = self._get_open_positions()
        is_now_in_position = len(open_positions) > 0
        if self.in_position and not is_now_in_position:
            print("[STATE CHANGE] Position has been closed. Resetting state.")
            self.partials_taken = {}
            self._save_state()
        self.in_position = is_now_in_position

    def _get_open_positions(self):
        """Helper to get all open market orders for this strategy's magic number."""
        return {
            t: o
            for t, o in self.dwx.open_orders.items()
            if int(o.get("magic", -1)) == self.config.MAGIC_NUMBER and o.get("type") in ["buy", "sell"]
        }

    # --- HELPER FUNCTIONS FOR CLEANER LOGIC ---
    def _get_stop_loss(self, signal: str, symbol_data: dict) -> float:
        """Calculates and validates the stop loss price."""
        entry_price = symbol_data.get("ask") if signal == "buy" else symbol_data.get("bid")

        # --- THE FIX: Add a guard clause to ensure entry_price is valid ---
        if entry_price is None or entry_price == 0:
            logging.error("Cannot calculate SL: Entry price is missing or zero.")
            return 0.0

        sl_percent = self.risk_config["STOP_LOSS_PERCENT"] / 100.0
        strategy_sl_price = entry_price * (1 - sl_percent) if signal == "buy" else entry_price * (1 + sl_percent)

        point_size = 1 / (10 ** symbol_data["digits"])
        broker_min_stop_distance = (symbol_data["stoplevel"] + symbol_data["spread"]) * point_size
        broker_sl_price = (
            (symbol_data["bid"] - broker_min_stop_distance)
            if signal == "buy"
            else (symbol_data["ask"] + broker_min_stop_distance)
        )

        if signal == "buy":
            final_sl_price = min(strategy_sl_price, broker_sl_price)
        else:
            final_sl_price = max(strategy_sl_price, broker_sl_price)

        logging.info(
            f"[SL CALC] Strategy SL: {strategy_sl_price:.{symbol_data['digits']}f}, Broker Min SL: {broker_sl_price:.{symbol_data['digits']}f}"
        )
        logging.info(f"[SL CALC] Final Compliant Stop Loss: {final_sl_price:.{symbol_data['digits']}f}")
        return final_sl_price

    def _get_take_profit(self, signal: str, symbol_data: dict) -> float:
        """Calculates the take profit price."""
        if self.risk_config["TAKE_PROFIT_PERCENT"] <= 0:
            return 0.0

        entry_price = symbol_data.get("ask") if signal == "buy" else symbol_data.get("bid")

        # --- THE FIX: Add a guard clause ---
        if entry_price is None or entry_price == 0:
            logging.error("Cannot calculate TP: Entry price is missing or zero.")
            return 0.0

        tp_percent = self.risk_config["TAKE_PROFIT_PERCENT"] / 100.0
        return entry_price * (1 + tp_percent) if signal == "buy" else entry_price * (1 - tp_percent)

    def _get_lot_size(self, signal: str, stop_loss_price: float, account_equity: float, symbol_data: dict) -> float:
        """Calculates and validates the lot size for a new trade."""
        if self.risk_config["USE_FIXED_LOT_SIZE"]:
            return self.risk_config["FIXED_LOT_SIZE"]

        entry_price = symbol_data.get("ask") if signal == "buy" else symbol_data.get("bid")

        # --- THE FIX: Add a guard clause ---
        if entry_price is None or entry_price == 0:
            logging.error("Cannot calculate Lot Size: Entry price is missing or zero.")
            return 0.0

        stop_loss_distance = abs(entry_price - stop_loss_price)

        tick_value = symbol_data["tick_value"]
        point_size = 1 / (10 ** symbol_data["digits"])
        value_per_point = tick_value / point_size

        lot_size = risk_manager.calculate_lot_size(
            account_balance=account_equity,
            risk_percent=self.risk_config["RISK_PER_TRADE_PERCENT"],
            stop_loss_price_distance=stop_loss_distance,
            value_per_point=value_per_point,
            min_lot=symbol_data["lot_min"],
            max_lot=symbol_data["max_lot"],
            lot_step=symbol_data["lot_step"],
        )

        logging.info(
            f"[Risk Calc] Inputs: Equity={account_equity}, Risk={self.risk_config['RISK_PER_TRADE_PERCENT']}%, SL Dist={stop_loss_distance}, Lot Size: {lot_size}"
        )
        return lot_size

    def _get_trailing_stop_price(self, order_type: str, current_price: float) -> float:
        """Calculates the new trailing stop loss price."""
        trailing_sl_percent = self.risk_config["TRAILING_STOP_PERCENT"] / 100.0
        return current_price * (1 - trailing_sl_percent) if order_type == "buy" else current_price * (1 + trailing_sl_percent)
