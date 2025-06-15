import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import importlib
import logging
import time
from datetime import datetime, timedelta, timezone
from threading import Thread

from trading_bot import config as cfg
from trading_bot.api.dwx_client import dwx_client
from trading_bot.core.event_handler import EventHandler
from trading_bot.core.logger_setup import setup_logger
from trading_bot.core.trade_manager import TradeManager


def strategy_factory(strategy_name: str, config_params: dict):
    """Dynamically imports and instantiates a strategy class based on its name."""
    class_name = "".join(word.capitalize() for word in strategy_name.split("_"))
    module_path = f"trading_bot.strategies.{strategy_name}"
    try:
        # --- THE FIX: Use the full, absolute package path ---
        module = importlib.import_module(module_path)

        StrategyClass = getattr(module, class_name)
        logging.info(f"Successfully loaded StrategyClass: {class_name} from module: {module.__name__}")
        return StrategyClass(**config_params)
    except (ImportError, AttributeError) as e:
        logging.error(f"[FATAL ERROR] Could not load strategy '{strategy_name}'.")
        logging.error(f"Please ensure the module path '{module_path}.py' and class '{class_name}' are correct.")
        logging.error(f"Details: {e}")
        return None


# --- NEW: Global variable to track config modification time ---
config_last_modified = os.path.getmtime(cfg.__file__)


def reload_config_and_update_bot(trade_manager):
    """
    Handles the logic of reloading the config and propagating changes.
    """
    global config_last_modified

    try:
        logging.info("Change detected in config.py. Attempting to reload...")

        # Force a reload of the config module
        importlib.reload(cfg)

        # Update the modification time tracker
        config_last_modified = os.path.getmtime(cfg.__file__)

        # Call the TradeManager's method to update itself with the new config
        trade_manager.update_config(cfg)

        logging.info("Configuration successfully reloaded and applied.")

    except Exception as e:
        logging.error(f"Failed to reload configuration. Error: {e}")
        # Restore the old modification time to prevent constant reload attempts on a broken config
        config_last_modified = time.time()


def watch_config_changes(trade_manager):
    """
    A function to be run in a background thread that polls the config file.
    """
    global config_last_modified

    while True:  # This loop will run for the lifetime of the bot
        try:
            current_modified = os.path.getmtime(cfg.__file__)
            if current_modified > config_last_modified:
                reload_config_and_update_bot(trade_manager)
        except FileNotFoundError:
            logging.warning("config.py not found. Cannot check for live updates.")

        time.sleep(5)  # Check for changes every 5 seconds


def main():
    """
    Main entry point for the trading bot.
    """
    setup_logger()
    logging.info("========================================================")
    logging.info("Initializing trading bot...")

    dwx = dwx_client(event_handler=None, metatrader_dir_path=cfg.METATRADER_DIR_PATH, verbose=False)

    strategy_name = cfg.STRATEGY_NAME
    if strategy_name not in cfg.STRATEGY_PARAMS:
        logging.error(f"[FATAL ERROR] Strategy '{strategy_name}' is not defined in the configuration.")
        return

    logging.info(f"Activating strategy: {strategy_name} for {cfg.STRATEGY_SYMBOL} on {cfg.STRATEGY_TIMEFRAME}")
    strategy_params = cfg.STRATEGY_PARAMS[strategy_name]

    required_history_bars = max(strategy_params.values()) if strategy_params else 0

    my_strategy_logic = strategy_factory(strategy_name, strategy_params)
    if not my_strategy_logic:
        logging.error("Halting due to strategy loading failure.")
        return

    my_trade_manager = TradeManager(dwx, my_strategy_logic, cfg, required_history_bars)
    my_event_handler = EventHandler(dwx, my_trade_manager)
    dwx.event_handler = my_event_handler

    dwx.start()
    while not dwx.START:
        time.sleep(1)
    logging.info("DWX Client started.")

    if required_history_bars > 0:
        logging.info("Requesting historical data for preloading...")
        num_bars_to_fetch = required_history_bars + 200
        try:
            timeframe_str = cfg.STRATEGY_TIMEFRAME
            if "M" in timeframe_str:
                timeframe_minutes = int(timeframe_str.replace("M", ""))
            elif "H" in timeframe_str:
                timeframe_minutes = int(timeframe_str.replace("H", "")) * 60
            elif "D" in timeframe_str:
                timeframe_minutes = int(timeframe_str.replace("D", "")) * 1440
            else:
                timeframe_minutes = 5  # Default fallback
        except Exception as e:
            logging.warning(f"Could not parse timeframe '{cfg.STRATEGY_TIMEFRAME}'. Defaulting to 15 mins. Error: {e}")
            timeframe_minutes = 5

        minutes_to_fetch = num_bars_to_fetch * timeframe_minutes
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=minutes_to_fetch)

        dwx.get_historic_data(cfg.STRATEGY_SYMBOL, cfg.STRATEGY_TIMEFRAME, int(start_time.timestamp()), int(end_time.timestamp()))

        logging.info("Waiting for historical data preload to complete...")
        start_wait_time = time.time()
        timeout_seconds = 30
        while not my_trade_manager.is_preloaded:
            time.sleep(1)
            if time.time() - start_wait_time > timeout_seconds:
                logging.error(
                    "[FATAL ERROR] Timed out waiting for historical data. Please check the 'Experts' tab in your MT4 terminal for errors."
                )
                dwx.stop()
                return
        logging.info("Preload confirmed.")
    else:
        my_trade_manager.is_preloaded = True
        logging.info("Strategy requires no historical data. Skipping preload.")

    bar_data_subscriptions = [[cfg.STRATEGY_SYMBOL, cfg.STRATEGY_TIMEFRAME]]
    dwx.subscribe_symbols_bar_data(bar_data_subscriptions)
    logging.info(f"Subscribed to live bar data for: {bar_data_subscriptions}")

    # --- NEW: Start the config watcher thread ---
    config_watcher_thread = Thread(target=watch_config_changes, args=(my_trade_manager,), daemon=True)
    config_watcher_thread.start()
    logging.info("Live config watcher has started.")

    logging.info("Bot is running. Press Ctrl+C to stop.")
    try:
        last_heartbeat_time = time.time()
        while dwx.ACTIVE:
            time.sleep(1)
            if time.time() - last_heartbeat_time > cfg.HEARTBEAT_INTERVAL_SECONDS:
                dwx._send_heartbeat()
                last_heartbeat_time = time.time()
    except KeyboardInterrupt:
        logging.info("\nStopping bot...")
        dwx.close_orders_by_magic(cfg.MAGIC_NUMBER)
        dwx.stop()
        time.sleep(2)
    except Exception as e:
        logging.critical(f"An unhandled exception occurred in the main loop: {e}")
        dwx.stop()


if __name__ == "__main__":
    main()
