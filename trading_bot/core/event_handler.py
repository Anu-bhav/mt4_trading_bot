# event_handler.py


class EventHandler:
    # --- MODIFICATION HERE ---
    def __init__(self, dwx_client_instance, trade_manager):
        self.dwx = dwx_client_instance  # Store the reference to the dwx client
        self.trade_manager = trade_manager
        print("MyEventHandler initialized.")

    def on_tick(self, symbol, bid, ask):
        """This method is called by the dwx_client on every new tick."""
        pass

    def on_bar_data(self, symbol, time_frame, time, open_p, high_p, low_p, close_p, tick_volume):
        self.trade_manager.on_bar_data(symbol, time_frame, time, open_p, high_p, low_p, close_p, tick_volume)

    def on_historic_data(self, symbol, time_frame, data):
        """This event is triggered when historic data is received."""
        print(f"Historic data received for {symbol}_{time_frame}. Routing to TradeManager for preloading.")
        self.trade_manager.preload_data(symbol, time_frame, data)

    def on_historic_trades(self):
        """Called by the client when historic trade data is received."""
        # --- THIS LINE NOW WORKS CORRECTLY ---
        print(f"Historic trades received: {len(self.dwx.historic_trades)}")
        pass

    def on_order_event(self):
        self.trade_manager.update_position_status()

    def on_message(self, message):
        if message["type"] == "ERROR":
            print(f"MT4 ERROR: {message['error_type']} | {message['description']}")
