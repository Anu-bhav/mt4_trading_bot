# trade_manager.py
import pandas as pd


class TradeManager:
    def __init__(self, dwx, strategy_object, config):
        self.dwx = dwx
        self.strategy = strategy_object
        self.config = config
        self.in_position = False
        self.market_data_df = pd.DataFrame(columns=["time", "open", "high", "low", "close", "tick_volume"])

        # This flag is now our synchronization gate.
        self.is_preloaded = False

        print("TradeManager initialized.")
        self.update_position_status()

    def preload_data(self, symbol, time_frame, data):
        if symbol != self.config.STRATEGY_SYMBOL or time_frame != self.config.STRATEGY_TIMEFRAME:
            return
        if not data:
            print("[ERROR] Preload failed: Received empty historical data from MT4.")
            return

        df = pd.DataFrame.from_dict(data, orient="index")
        df.reset_index(inplace=True)
        df.rename(columns={"index": "time"}, inplace=True)
        # ... (data type conversion is the same) ...
        df["open"] = pd.to_numeric(df["open"])
        df["high"] = pd.to_numeric(df["high"])
        df["low"] = pd.to_numeric(df["low"])
        df["close"] = pd.to_numeric(df["close"])
        df["tick_volume"] = pd.to_numeric(df["tick_volume"])
        df.sort_values(by="time", inplace=True)

        self.market_data_df = df
        self.is_preloaded = True

        print(f"SUCCESS: Preloaded {len(self.market_data_df)} historical bars for {symbol}.")

        # --- THIS IS THE NEW PROACTIVE LINE ---
        # After loading data, immediately check if there is a signal based on the latest historical bar.
        print("\n--- Performing initial analysis on preloaded data... ---")
        self.analyze_and_trade()

    # trade_manager.py

    def analyze_and_trade(self):
        """
        A new central function to run analysis and potentially trade.
        Can be called after preloading or on a new live bar.
        """
        signal = self.strategy.get_signal(self.market_data_df.copy())

        print(f"Signal Check: Received '{signal}' | In Position: {self.in_position}")

        # --- REFINED TRADING LOGIC ---

        # Case 1: We received a BUY signal and are NOT currently in a position.
        if signal == "BUY" and not self.in_position:
            print(">>> EXECUTION: BUY signal received and not in position. Opening trade!")
            self.dwx.open_order(
                symbol=self.config.STRATEGY_SYMBOL, order_type="buy", lots=self.config.LOT_SIZE, magic=self.config.MAGIC_NUMBER
            )

        # Case 2: We received a SELL signal and ARE currently in a position.
        # This acts as our exit signal for the buy trade.
        elif signal == "SELL" and self.in_position:
            print(">>> EXECUTION: SELL signal received and in position. Closing trade!")
            self.dwx.close_orders_by_magic(self.config.MAGIC_NUMBER)

        # Case 3: No valid signal for action.
        else:
            print("Decision: No action taken based on current signal and position status.")

    def on_bar_data(self, symbol, time_frame, time, open_p, high_p, low_p, close_p, tick_volume):
        if not self.is_preloaded:
            print("[INFO] Ignoring live bar. Waiting for historical data preload to complete.")
            return
        if symbol != self.config.STRATEGY_SYMBOL or time_frame != self.config.STRATEGY_TIMEFRAME:
            return
        if time in self.market_data_df["time"].values:
            return

        print(f"\n--- New Live Bar Received: {symbol} {time_frame} at {time} ---")

        # Append new live bar data
        self.market_data_df.loc[len(self.market_data_df)] = [time, open_p, high_p, low_p, close_p, tick_volume]

        # Keep the DataFrame from growing indefinitely
        max_rows = self.strategy.long_period + 200
        if len(self.market_data_df) > max_rows:
            self.market_data_df = self.market_data_df.iloc[-max_rows:]

        # Call our new central analysis function
        self.analyze_and_trade()

    def on_order_event(self):
        print("--- Order Event Triggered ---")
        self.update_position_status()

    def update_position_status(self):
        print("Updating position status...")
        open_trades = [t for t, o in self.dwx.open_orders.items() if int(o["magic"]) == self.config.MAGIC_NUMBER]
        # DEBUG: Show what trades were found (if any)
        print(f"Found {len(open_trades)} trades with magic number {self.config.MAGIC_NUMBER}.")
        self.in_position = len(open_trades) > 0
        print(f"TradeManager: In Position = {self.in_position}")
