# main.py
from calendar import c
import importlib
import time
from datetime import datetime, timedelta, timezone

import config as cfg
from api.dwx_client import dwx_client
from event_handler import MyEventHandler

# Import your strategies
from trade_manager import TradeManager


# --- THIS IS THE NEW STRATEGY FACTORY FUNCTION ---
def strategy_factory(strategy_name: str, config_params: dict):
    """
    Dynamically imports and instantiates a strategy class based on its name.

    Args:
        strategy_name (str): The name of the strategy (e.g., 'sma_crossover').
        config_params (dict): The dictionary of parameters for this strategy from config.py.

    Returns:
        An instantiated strategy object.

    """
    # Convert snake_case name to PascalCase for the class name.
    # e.g., 'sma_crossover' -> 'SmaCrossover'
    class_name = "".join(word.capitalize() for word in strategy_name.split("_"))

    try:
        # Dynamically import the module from the 'strategies' folder.
        # e.g., from strategies.sma_crossover import SmaCrossover
        module = importlib.import_module(f"strategies.{strategy_name}")

        # Get the class from the imported module.
        StrategyClass = getattr(module, class_name)

        # Instantiate the class with its parameters.
        # The ** operator unpacks the dictionary into keyword arguments.
        return StrategyClass(**config_params)

    except (ImportError, AttributeError) as e:
        print(f"[FATAL ERROR] Could not load strategy '{strategy_name}'.")
        print(f"Please ensure 'strategies/{strategy_name}.py' exists and contains a class named '{class_name}'.")
        print(f"Error details: {e}")
        return None


def main():
    print("Initializing trading bot...")

    dwx = dwx_client(event_handler=None, metatrader_dir_path=cfg.METATRADER_DIR_PATH, verbose=False)

    # --- Activate the Desired Strategy ---
    strategy_name = cfg.STRATEGY_NAME
    if strategy_name not in cfg.STRATEGY_PARAMS:
        print(f"[FATAL ERROR] Strategy '{strategy_name}' is not defined in the configuration.")
        return

    print(f"Activating strategy: {strategy_name}")
    strategy_params = cfg.STRATEGY_PARAMS[strategy_name]

    # --- THIS IS THE NEW LOGIC ---
    # Dynamically determine the longest lookback period the strategy needs.
    # This makes the TradeManager independent of parameter names like 'long_period' or 'rsi_period'.
    if strategy_params:
        required_history_bars = max(strategy_params.values())
    else:
        required_history_bars = 60  # A safe default if no params are given

    my_strategy_logic = strategy_factory(strategy_name, strategy_params)

    # Pass the calculated required history to the TradeManager
    my_trade_manager = TradeManager(dwx, my_strategy_logic, cfg, required_history_bars)

    my_event_handler = MyEventHandler(dwx, my_trade_manager)
    dwx.event_handler = my_event_handler

    dwx.start()
    while not dwx.START:
        time.sleep(1)
    print("DWX Client started.")

    print("Requesting historical data for preloading...")
    num_bars_to_fetch = required_history_bars + 200  # Use the same value for the fetch request
    timeframe_minutes = cfg.STRATEGY_TIMEFRAME.replace("M", "")
    timeframe_minutes = int(timeframe_minutes)
    minutes_to_fetch = num_bars_to_fetch * timeframe_minutes
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=minutes_to_fetch)
    dwx.get_historic_data(cfg.STRATEGY_SYMBOL, cfg.STRATEGY_TIMEFRAME, start_time.timestamp(), end_time.timestamp())

    # --- THIS IS THE NEW ROBUST WAITING LOOP ---
    # It replaces the unreliable time.sleep(5)
    print("Waiting for historical data preload to complete...")
    start_wait_time = time.time()
    timeout_seconds = 30  # Set a timeout to prevent an infinite loop

    while not my_trade_manager.is_preloaded:
        time.sleep(1)  # Check the flag once per second
        if time.time() - start_wait_time > timeout_seconds:
            print("[FATAL ERROR] Timed out waiting for historical data.")
            print("Please check the 'Experts' tab in your MT4 terminal for errors.")
            dwx.stop()  # Shut down the bot
            return

    print("Preload confirmed.")

    # NOW, it is safe to subscribe to live data.
    dwx.subscribe_symbols_bar_data(cfg.BAR_DATA_SUBSCRIPTIONS)
    print("Subscribed to live bar data.")

    # --- Main Loop ---
    print("\nBot is running. Press Ctrl+C to stop.")
    try:
        while dwx.ACTIVE:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping bot...")
        dwx.close_orders_by_magic(cfg.MAGIC_NUMBER)
        dwx.stop()
        time.sleep(2)


if __name__ == "__main__":
    main()
