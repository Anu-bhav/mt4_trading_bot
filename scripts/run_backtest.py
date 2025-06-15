# run_backtest.py
import logging
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
from backtesting import Backtest

import trading_bot.config as cfg

# We can reuse the factory from our live main.py!
from scripts.run_live import strategy_factory
from trading_bot.backtesting.strategy_adapter import StrategyAdapter
from trading_bot.core.data_handler import download_and_get_data
from trading_bot.core.logger_setup import setup_logger


def run_backtest():
    """
    Main entry point for running a backtest with automated data download
    and interactive plotting.
    """
    setup_logger()  # Setup logging to capture output

    # --- 1. Choose the strategy to backtest ---
    # This is the same single line of code you use to control your live bot.
    strategy_name_to_run = "sma_crossover"

    logging.info(f"--- Starting Backtest for strategy: {strategy_name_to_run} ---")

    # --- 2. AUTOMATICALLY DOWNLOAD & LOAD DATA ---
    data = download_and_get_data(cfg.STRATEGY_SYMBOL, cfg.STRATEGY_TIMEFRAME)

    if data.empty:
        logging.error("Aborting backtest due to data download failure.")
        return

    # The backtesting.py library needs specific column names.
    # We rename them to ensure compatibility.
    # Note: yfinance auto_adjust=True removes 'Adj Close' and adjusts OHLC.
    data.rename(columns={"Open": "Open", "High": "High", "Low": "Low", "Close": "Close", "Volume": "Volume"}, inplace=True)
    data.columns = [col.lower().replace(" ", "_") for col in data.columns]

    # --- 3. Instantiate the User Strategy ---
    strategy_params = cfg.STRATEGY_PARAMS.get(strategy_name_to_run, {})
    user_strategy_object = strategy_factory(strategy_name_to_run, strategy_params)
    if not user_strategy_object:
        logging.error("Aborting backtest due to strategy loading failure.")
        return

    # --- 4. Inject the User Strategy into the Adapter ---
    # This is the magic step that makes our live strategy compatible with the backtester.
    StrategyAdapter.user_strategy = user_strategy_object

    # --- 5. Initialize and Run the Backtest ---
    bt = Backtest(
        data,
        StrategyAdapter,
        cash=10000,
        commission=0.002,  # Example 0.2% commission per trade
        trade_on_close=True,
        exclusive_orders=True,
    )

    stats = bt.run()

    # --- 6. Print and Plot Results ---
    logging.info("\n--- Backtest Results ---")
    logging.info(stats)

    logging.info("\n--- Trade Log ---")
    logging.info(stats["_trades"])

    logging.info("\nGenerating interactive plot... A new tab should open in your web browser.")
    bt.plot(plot_volume=True, plot_equity=True, plot_return=True, resample=False, open_browser=True)


if __name__ == "__main__":
    run_backtest()
