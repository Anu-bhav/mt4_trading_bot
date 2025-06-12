# trade_manager.py
import pandas as pd

from utils import risk_manager


class TradeManager:
    # --- MODIFICATION IN THE __init__ SIGNATURE AND BODY ---
    def __init__(self, dwx, strategy_object, config, required_history_bars: int):
        self.dwx = dwx
        self.strategy = strategy_object
        self.config = config
        self.risk_config = config.RISK_CONFIG

        # Store the required history length
        self.required_history_bars = required_history_bars

        self.partials_taken = {}
        self.is_preloaded = False
        self.market_data_df = pd.DataFrame(columns=["time", "open", "high", "low", "close", "tick_volume"])

        self.dwx.subscribe_symbols([self.config.STRATEGY_SYMBOL])
        self.value_per_point = 0.0

        print("TradeManager initialized.")
        self.update_position_status()

    def _update_value_per_point(self):
        """
        Gets the instrument's contract value information dynamically.
        This is now robust for any instrument (Forex, commodities, etc.).
        """
        symbol_data = self.dwx.market_data.get(self.config.STRATEGY_SYMBOL)

        # Check if the data and all required keys are present
        if symbol_data and "tick_value" in symbol_data and "digits" in symbol_data:
            # --- THIS IS THE DYNAMIC LOGIC ---
            # We get the 'digits' value sent from the MT4 server.
            digits = symbol_data.get("digits")
            tick_value = symbol_data.get("tick_value")

            # A tick is the smallest possible price change.
            tick_size = 1 / (10**digits)

            # Value per point is how much money a 1.0 price move is worth for a 1.0 lot size.
            self.value_per_point = tick_value / tick_size

            print(f"[INFO] Properties for {self.config.STRATEGY_SYMBOL}: Digits={digits}, TickValue={tick_value}")
            print(f"[INFO] Calculated Value per Point updated to: {self.value_per_point}")
        else:
            print(
                f"[WARNING] Could not get complete market data for {self.config.STRATEGY_SYMBOL}. Risk calculations may be incorrect."
            )

    def preload_data(self, symbol, time_frame, data):
        if symbol != self.config.STRATEGY_SYMBOL or time_frame != self.config.STRATEGY_TIMEFRAME:
            return
        if not data:
            print("[ERROR] Preload failed: Received empty historical data from MT4.")
            return

        df = pd.DataFrame.from_dict(data, orient="index")
        df.reset_index(inplace=True)
        df.rename(columns={"index": "time"}, inplace=True)
        df["open"] = pd.to_numeric(df["open"])
        df["high"] = pd.to_numeric(df["high"])
        df["low"] = pd.to_numeric(df["low"])
        df["close"] = pd.to_numeric(df["close"])
        df["tick_volume"] = pd.to_numeric(df["tick_volume"])
        df.sort_values(by="time", inplace=True)

        self.market_data_df = df
        self.is_preloaded = True
        self._update_value_per_point()

        print(f"SUCCESS: Preloaded {len(self.market_data_df)} historical bars for {symbol}.")

        print("\n--- Performing initial analysis on preloaded data... ---")
        self.analyze_and_trade()

    def analyze_and_trade(self):
        """Main logic for analyzing market data and executing/managing trades."""
        self.manage_open_positions()

        signal = self.strategy.get_signal(self.market_data_df.copy())
        open_positions = self._get_open_positions()

        print(
            f"Signal Check: Received '{signal}' | Open Positions: {len(open_positions)} | Max Positions: {self.risk_config['MAX_OPEN_POSITIONS']}"
        )

        # Case 1: We are not in a position and there is room for more trades.
        if not self.in_position and len(open_positions) < self.risk_config["MAX_OPEN_POSITIONS"]:
            if signal in ["BUY", "SELL"]:
                self._execute_new_trade(signal)

        # Case 2: We are in a position. Check for an exit signal.
        elif self.in_position:
            # Assumes a reversing strategy: a BUY signal closes a SELL position, and vice-versa.
            current_trade_type = list(open_positions.values())[0]["type"]  # Get type of the first open trade
            if (signal == "BUY" and current_trade_type == "sell") or (signal == "SELL" and current_trade_type == "buy"):
                print(f">>> EXECUTION: Exit signal '{signal}' received. Closing all trades!")
                self.dwx.close_orders_by_magic(self.config.MAGIC_NUMBER)
        else:
            print("Decision: No action taken based on current signal and position status.")

    def _execute_new_trade(self, signal):
        """Handles the logic for opening a new trade."""
        # --- DEFENSIVE GUARD CLAUSE ---
        # Before doing anything, ensure we have the account equity information.
        account_equity = self.dwx.account_info.get("equity", 0)
        if account_equity <= 0:
            print("[ERROR] Account equity is 0 or not available yet. Aborting trade execution.")
            print("[INFO] This is normal on first startup, will resolve on the next tick/bar.")
            return

        current_price = self.market_data_df["close"].iloc[-1]
        sl_percent = self.risk_config["STOP_LOSS_PERCENT"] / 100.0
        tp_percent = self.risk_config["TAKE_PROFIT_PERCENT"] / 100.0

        if signal == "buy":
            stop_loss_price = current_price * (1 - sl_percent)
            take_profit_price = current_price * (1 + tp_percent) if self.risk_config["TAKE_PROFIT_PERCENT"] > 0 else 0
        elif signal == "sell":
            stop_loss_price = current_price * (1 + sl_percent)
            take_profit_price = current_price * (1 - tp_percent) if self.risk_config["TAKE_PROFIT_PERCENT"] > 0 else 0
        else:
            return

        stop_loss_distance = abs(current_price - stop_loss_price)

        if self.risk_config["USE_FIXED_LOT_SIZE"]:
            lot_size = self.risk_config["FIXED_LOT_SIZE"]
        else:
            if self.value_per_point <= 0:
                self._update_value_per_point()

            # --- ADDING DIAGNOSTIC PRINT ---
            print(
                f"[Risk Calc] Inputs: Equity={account_equity}, Risk={self.risk_config['RISK_PER_TRADE_PERCENT']}%, SL Dist={stop_loss_distance}, Val/Point={self.value_per_point}"
            )

            lot_size = risk_manager.calculate_lot_size(
                account_balance=account_equity,
                risk_percent=self.risk_config["RISK_PER_TRADE_PERCENT"],
                stop_loss_price_distance=stop_loss_distance,
                value_per_point=self.value_per_point,
            )

        if lot_size <= 0:
            print(f"[ERROR] Calculated lot size is {lot_size}. Aborting trade.")
            return

        print(f">>> EXECUTION: {signal.upper()} signal received. Sending order! [Lots: {lot_size}]")
        self.dwx.open_order(
            symbol=self.config.STRATEGY_SYMBOL,
            order_type=signal,
            lots=lot_size,
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
            current_sl = order["sl"]
            order_type = order["type"]

            # Calculate profit based on order type
            if order_type == "buy":
                profit_percent = ((current_price - open_price) / open_price) * 100.0
            elif order_type == "sell":
                profit_percent = ((open_price - current_price) / open_price) * 100.0
            else:
                continue

            # Trailing Stop Logic
            if self.risk_config["USE_TRAILING_STOP"] and profit_percent > self.risk_config["TRAILING_STOP_TRIGGER_PERCENT"]:
                trailing_sl_percent = self.risk_config["TRAILING_STOP_PERCENT"] / 100.0

                if order_type == "buy":
                    new_sl_price = current_price * (1 - trailing_sl_percent)
                    if new_sl_price > current_sl:
                        print(
                            f"[Trailing Stop] Modifying BUY order {ticket} SL to {new_sl_price:.5f} (+{profit_percent:.2f}% profit)"
                        )
                        self.dwx.modify_order(ticket, stop_loss=new_sl_price)
                elif order_type == "sell":
                    new_sl_price = current_price * (1 + trailing_sl_percent)
                    # For a sell, a higher SL price is a worse SL, so we check if new_sl < current_sl
                    if new_sl_price < current_sl or current_sl == 0:
                        print(
                            f"[Trailing Stop] Modifying SELL order {ticket} SL to {new_sl_price:.5f} (+{profit_percent:.2f}% profit)"
                        )
                        self.dwx.modify_order(ticket, stop_loss=new_sl_price)

            # Partial Close Logic
            for i, rule in enumerate(self.risk_config["PARTIAL_CLOSE_RULES"]):
                volume_percent_to_close, trigger_profit_percent = rule

                if profit_percent >= trigger_profit_percent and self.partials_taken.get(ticket, {}).get(i) is None:
                    volume_to_close = order["lots"] * volume_percent_to_close
                    print(
                        f"[Partial Close] Closing {volume_to_close:.2f} lots for order {ticket} at +{profit_percent:.2f}% profit."
                    )
                    self.dwx.close_order(ticket, lots=volume_to_close)

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

        # --- THIS LINE IS NOW ROBUST AND GENERIC ---
        # It uses the value passed during initialization.
        max_rows = self.required_history_bars + 200
        if len(self.market_data_df) > max_rows:
            self.market_data_df = self.market_data_df.iloc[-max_rows:]

        self.analyze_and_trade()

    def update_position_status(self):
        open_positions = self._get_open_positions()
        self.in_position = len(open_positions) > 0
        if not self.in_position:
            # If we are flat, reset the partials taken history
            self.partials_taken = {}

    def _get_open_positions(self):
        return {
            t: o
            for t, o in self.dwx.open_orders.items()
            if int(o["magic"]) == self.config.MAGIC_NUMBER and o["type"] in ["buy", "sell"]
        }
