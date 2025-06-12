# main.py
import time
from datetime import datetime, timedelta, timezone

import config as cfg
from api.dwx_client import dwx_client
from event_handler import MyEventHandler
from strategies.sma_crossover import SmaCrossover
from trade_manager import TradeManager


def main():
    dwx = dwx_client(event_handler=None, metatrader_dir_path=cfg.METATRADER_DIR_PATH, verbose=True)
    strategy_params = cfg.STRATEGY_PARAMS["sma_crossover"]
    my_strategy_logic = SmaCrossover(**strategy_params)
    my_trade_manager = TradeManager(dwx, my_strategy_logic, cfg)
    my_event_handler = MyEventHandler(my_trade_manager)
    dwx.event_handler = my_event_handler

    dwx.start()
    while not dwx.START:
        time.sleep(1)
    print("DWX Client started.")

    # Request historical data
    print("Requesting historical data for preloading...")
    # ... (logic to calculate start_time and end_time is the same) ...
    long_period = cfg.STRATEGY_PARAMS["sma_crossover"]["long_period"]
    num_bars_to_fetch = long_period + 200
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
        # ... (rest of the code is the same) ...
        print("\nStopping bot...")
        dwx.close_orders_by_magic(cfg.MAGIC_NUMBER)
        dwx.stop()
        time.sleep(2)


if __name__ == "__main__":
    main()
