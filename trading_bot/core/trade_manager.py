# trade_manager.py
import json
import logging
from datetime import datetime, timezone
from os.path import join
from tkinter import N

import pandas as pd

from ..utils import risk_manager


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

        logging.info("TradeManager initialized.")

        # --- NEW METHOD: update_config ---

    def update_config(self, new_config):
        """
        Updates internal settings from a newly reloaded config module.
        """
        logging.info("TradeManager is updating its configuration...")
        self.config = new_config
        self.risk_config = new_config.RISK_CONFIG

        # Propagate changes to the strategy object if its params have changed.
        # This is an advanced feature. A simple way is to just update its params.
        strategy_params = new_config.STRATEGY_PARAMS.get(new_config.STRATEGY_NAME, {})
        for key, value in strategy_params.items():
            if hasattr(self.strategy, key):
                setattr(self.strategy, key, value)
                logging.info(f"Updated strategy parameter '{key}' to '{value}'")

    def _load_state(self):
        """Loads the manager's state from a JSON file."""
        try:
            with open(self.state_file_path, "r") as f:
                state = json.load(f)
                self.partials_taken = {int(k): v for k, v in state.get("partials_taken", {}).items()}
                logging.info("[State] Successfully loaded saved state.")
        except FileNotFoundError:
            logging.info("[State] No state file found. Starting with a fresh state.")
        except Exception as e:
            logging.info(f"[State] ERROR: Could not load state file. Starting fresh. Reason: {e}")

    def _save_state(self):
        """Saves the manager's current state to a JSON file."""
        try:
            with open(self.state_file_path, "w") as f:
                json.dump({"partials_taken": self.partials_taken}, f, indent=4)
            logging.info("[State] Current state saved successfully.")
        except Exception as e:
            logging.info(f"[State] ERROR: Could not save state file. Reason: {e}")

    def preload_data(self, symbol, time_frame, data):
        """Processes historical data to populate the initial DataFrame."""
        if symbol != self.config.STRATEGY_SYMBOL or time_frame != self.config.STRATEGY_TIMEFRAME:
            return
        if not data:
            logging.info("[ERROR] Preload failed: Received empty historical data.")
            return

        df = pd.DataFrame.from_dict(data, orient="index")
        df.reset_index(inplace=True)
        df.rename(columns={"index": "time"}, inplace=True)
        df["time"] = pd.to_numeric(df["time"])
        df.columns = [col.lower() for col in df.columns]
        for col in ["open", "high", "low", "close", "tick_volume"]:
            df[col] = pd.to_numeric(df[col])
        df.sort_values(by="time", inplace=True)

        self.market_data_df = df
        self.is_preloaded = True

        # Set the last bar timestamp from the preloaded data
        if not df.empty:
            self.last_bar_timestamp = df["time"].iloc[-1]

        logging.info(f"SUCCESS: Preloaded {len(self.market_data_df)} historical bars for {symbol}.")
        logging.info("\n--- Performing initial analysis on preloaded data... ---")
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
        signal_dict = self.strategy.get_signal(self.market_data_df.copy(), is_backtest=False)
        signal = signal_dict.get("signal", "HOLD")

        logging.info(f"Signal Check: Received '{signal}' | In Position: {self.in_position}")

        # 4. Execute the decision tree.
        open_positions = self._get_open_positions()  # Get a fresh copy for this logic block
        if not self.in_position and signal in ["BUY", "SELL"]:
            if len(open_positions) < self.risk_config["MAX_OPEN_POSITIONS"]:
                self._execute_new_trade(signal, signal_dict.get("comment"))
        elif self.in_position:
            current_trade_type = list(open_positions.values())[0]["type"]
            if (signal == "BUY" and current_trade_type == "sell") or (signal == "SELL" and current_trade_type == "buy"):
                logging.info(f">>> EXECUTION: Reversing signal '{signal}' received. Closing all trades!")
                self.dwx.close_orders_by_magic(self.config.MAGIC_NUMBER)
        else:
            logging.info("Decision: No action taken.")

    def _execute_new_trade(self, signal: str, comment: str = None):
        """
        Orchestrates the process of opening a new trade with correct logic,
        price normalization, and proper context for MT4.
        """
        signal = signal.lower()

        # 1. Check for readiness.
        account_equity = self.dwx.account_info.get("equity", 0)
        symbol_data = self.dwx.market_data.get(self.config.STRATEGY_SYMBOL, {})
        required_keys = ["ask", "bid", "digits", "stoplevel", "spread", "lot_min", "lot_max", "lot_step", "tick_value"]
        if account_equity <= 0 or not all(k in symbol_data for k in required_keys):
            logging.error("[EXECUTION ABORTED] Prerequisite data (account or market) is not available.")
            return

        # 2. Determine the STRATEGY'S desired stop loss price.
        stop_loss_price = self._get_strategy_stop_loss(signal, symbol_data)
        if stop_loss_price == 0.0:
            logging.error("[EXECUTION ABORTED] Strategy did not provide a valid stop loss.")
            return

        # 3. CHECK FOR COMPLIANCE: Will the broker accept this stop?
        if not self._is_stop_loss_compliant(signal, stop_loss_price, symbol_data):
            logging.warning(
                "[EXECUTION ABORTED] Strategy's desired Stop Loss is too tight and violates broker rules. No trade will be placed."
            )
            return  # This is the key: we abort instead of adjusting.

        # 4. If compliant, proceed with lot size and TP calculation.
        lot_size = self._get_lot_size(signal, stop_loss_price, account_equity, symbol_data)
        if lot_size <= 0:
            return

        take_profit_price = self._get_take_profit(signal, symbol_data)

        # 5. Normalize and Execute
        digits = symbol_data["digits"]
        final_sl = round(stop_loss_price, digits)
        final_tp = round(take_profit_price, digits) if take_profit_price > 0 else 0.0
        # Add the comment to the execution log
        log_comment = f" | Comment: {comment}" if comment else ""
        logging.info(
            f">>> EXECUTION: {signal.upper()} signal received. Sending order! [Lots: {lot_size}, SL: {final_sl}, TP: {final_tp}]{log_comment}"
        )
        self.dwx.open_order(
            symbol=self.config.STRATEGY_SYMBOL,
            order_type=signal,
            lots=lot_size,
            price=0,
            stop_loss=final_sl,
            take_profit=final_tp,
            magic=self.config.MAGIC_NUMBER,
            comment=comment or f"PythonBot v1.0",
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
                    logging.info(f"[Trailing Stop] Modifying order {ticket} SL to {new_sl:.5f}")
                    self.dwx.modify_order(ticket, stop_loss=new_sl)

            for i, rule in enumerate(self.risk_config["PARTIAL_CLOSE_RULES"]):
                vol_pct, profit_pct = rule
                if profit_percent >= profit_pct and self.partials_taken.get(ticket, {}).get(i) is None:
                    close_vol = round(order["lots"] * (vol_pct / 100.0), 2)
                    logging.info(f"[Partial Close] Closing {close_vol:.2f} lots for order {ticket}")
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
            logging.info(f"Received invalid timestamp format, ignoring bar: {time}")
            return

        if not self.is_preloaded:
            return
        if symbol != self.config.STRATEGY_SYMBOL or time_frame != self.config.STRATEGY_TIMEFRAME:
            return

        # --- [Gotcha 2.2] Bad Candle / Corrupted Data Check ---
        if not (open_p > 0 and high_p > 0 and low_p > 0 and close_p > 0 and high_p >= low_p):
            logging.info(f"[DATA WARNING] Received a bad/corrupted candle, ignoring: {symbol} {time}")
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
                logging.info(
                    f"[DATA WARNING] Data gap detected. Time since last bar: {time_diff_seconds}s. Expected ~{interval_seconds}s."
                )
                logging.info("[ACTION] Resetting strategy state to prevent decisions based on stale data.")
                self.strategy.reset()  # Reset the strategy's internal memory

        # Update the timestamp of the last processed bar
        self.last_bar_timestamp = time

        utc_datetime = datetime.fromtimestamp(time, tz=timezone.utc)
        readable_date = utc_datetime.strftime("%Y-%m-%d %H:%M:%S %Z")

        logging.info(f"\n--- New Live Bar Received: {symbol} {time_frame} at {readable_date} ---")
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
            logging.info("[STATE CHANGE] Position has been closed. Resetting state.")
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
        """
        Calculates the stop loss price, applying a dynamic, multiplied safety
        buffer to the broker's minimum stop level.
        """
        entry_price = symbol_data.get("ask") if signal == "buy" else symbol_data.get("bid")
        if not entry_price:
            return 0.0

        # 1. Calculate the strategy's desired stop loss
        sl_percent = self.risk_config["STOP_LOSS_PERCENT"] / 100.0
        strategy_sl_price = entry_price * (1 - sl_percent) if signal == "buy" else entry_price * (1 + sl_percent)

        # 2. Calculate the broker's boundary with our new multiplier for safety
        point_size = 1 / (10 ** symbol_data["digits"])
        buffer_multiplier = self.risk_config.get("STOP_LEVEL_BUFFER_MULTIPLIER", 1.5)  # Default to 1.5

        # The total safe distance is the broker's rule * our safety multiplier
        min_stop_distance_points = (symbol_data["stoplevel"] + symbol_data["spread"]) * buffer_multiplier
        min_stop_distance_price = min_stop_distance_points * point_size

        broker_boundary_price = (
            (symbol_data["bid"] - min_stop_distance_price) if signal == "buy" else (symbol_data["ask"] + min_stop_distance_price)
        )

        # 3. The "Widest Stop Wins" logic
        final_sl_price = 0.0
        if signal == "buy":
            if strategy_sl_price < broker_boundary_price:
                final_sl_price = strategy_sl_price
            else:
                final_sl_price = broker_boundary_price
        elif signal == "sell":
            if strategy_sl_price > broker_boundary_price:
                final_sl_price = strategy_sl_price
            else:
                final_sl_price = broker_boundary_price

        logging.info(
            f"[SL CALC] Strategy Desired SL: {strategy_sl_price:.{symbol_data['digits']}f}, Broker Boundary (w/ Buffer): {broker_boundary_price:.{symbol_data['digits']}f}"
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
            lot_min=symbol_data["lot_min"],
            lot_max=symbol_data["lot_max"],
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

    def _get_strategy_stop_loss(self, signal: str, symbol_data: dict) -> float:
        """Calculates ONLY the strategy's desired stop loss based on percentage."""
        entry_price = symbol_data.get("ask") if signal == "buy" else symbol_data.get("bid")
        if not entry_price:
            return 0.0

        sl_percent = self.risk_config["STOP_LOSS_PERCENT"] / 100.0
        strategy_sl_price = entry_price * (1 - sl_percent) if signal == "buy" else entry_price * (1 + sl_percent)

        logging.info(f"[SL CALC] Strategy Desired SL: {strategy_sl_price:.{symbol_data['digits']}f}")
        return strategy_sl_price

    def _is_stop_loss_compliant(self, signal: str, strategy_sl_price: float, symbol_data: dict) -> bool:
        """Checks if the strategy's desired SL is valid according to broker rules."""
        point_size = 1 / (10 ** symbol_data["digits"])
        buffer_multiplier = self.risk_config.get("STOP_LEVEL_BUFFER_MULTIPLIER", 1.1)

        min_stop_distance_points = (symbol_data["stoplevel"] + symbol_data["spread"]) * buffer_multiplier
        min_stop_distance_price = min_stop_distance_points * point_size

        broker_boundary_price = (
            (symbol_data["bid"] - min_stop_distance_price) if signal == "buy" else (symbol_data["ask"] + min_stop_distance_price)
        )

        logging.info(f"[SL CHECK] Broker required boundary: {broker_boundary_price:.{symbol_data['digits']}f}")

        if signal == "buy":
            # For a BUY, the SL must be at or below the boundary.
            return strategy_sl_price <= broker_boundary_price
        else:  # signal == 'sell'
            # For a SELL, the SL must be at or above the boundary.
            return strategy_sl_price >= broker_boundary_price
