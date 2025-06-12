# event_handler.py
class MyEventHandler:
    def __init__(self, trade_manager):
        self.trade_manager = trade_manager
        print("MyEventHandler initialized.")

    def on_bar_data(self, symbol, time_frame, time, open_p, high_p, low_p, close_p, tick_volume):
        self.trade_manager.on_bar_data(symbol, time_frame, time, open_p, high_p, low_p, close_p, tick_volume)

    # --- THIS IS THE NEW PART ---
    def on_historic_data(self, symbol, time_frame, data):
        """
        This event is triggered when historic data is received.
        We pass it to the TradeManager to be processed.
        """
        print(f"Historic data received for {symbol}_{time_frame}. Routing to TradeManager for preloading.")
        self.trade_manager.preload_data(symbol, time_frame, data)

    def on_order_event(self):
        self.trade_manager.on_order_event()

    def on_message(self, message):
        if message["type"] == "ERROR":
            print(f"MT4 ERROR: {message['description']}")
