# scripts/run_backtest.py
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
from datetime import datetime

import pandas as pd
from backtesting import Backtest

# Import the same strategy factory used by the live trading script
from scripts.run_live import strategy_factory
from trading_bot import config as cfg
from trading_bot.backtesting.strategy_adapter import StrategyAdapter
from trading_bot.core.data_handler import download_and_get_data
from trading_bot.core.logger_setup import setup_logger


def run_backtest():
    """
    Main entry point for running a backtest with automated data download,
    dynamic strategy loading, and interactive plotting.
    """
    setup_logger()

    # --- 1. DYNAMICALLY CHOOSE THE STRATEGY FROM CONFIG ---
    strategy_name_to_run = cfg.STRATEGY_NAME

    logging.info(f"--- Starting Backtest for strategy: {strategy_name_to_run} ---")

    # --- 2. AUTOMATICALLY DOWNLOAD & LOAD DATA ---
    data = download_and_get_data(cfg.STRATEGY_SYMBOL, cfg.STRATEGY_TIMEFRAME)

    if data.empty:
        logging.error("Aborting backtest due to data download failure.")
        return

    # Standardize column names for processing, then rename for the backtesting library
    new_columns = []
    for col in data.columns:
        if isinstance(col, tuple):
            col = col[0]
        new_columns.append(str(col).lower().replace(" ", "_"))
    data.columns = new_columns

    rename_map = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
    data.rename(columns=rename_map, inplace=True)

    # --- 3. INSTANTIATE THE USER STRATEGY USING THE FACTORY ---
    strategy_params = cfg.STRATEGY_PARAMS.get(strategy_name_to_run, {})
    user_strategy_object = strategy_factory(strategy_name_to_run, strategy_params)
    if not user_strategy_object:
        logging.error("Aborting backtest due to strategy loading failure.")
        return

    # --- 4. INJECT THE USER STRATEGY INTO THE ADAPTER ---
    StrategyAdapter.user_strategy = user_strategy_object
    StrategyAdapter.risk_config = cfg.RISK_CONFIG  # Give adapter access to risk settings
    StrategyAdapter.symbol_info = {"digits": 2, "tick_value": 0.01, "contract_size": 100}
    # --- 5. INITIALIZE AND RUN THE BACKTEST ---
    bt = Backtest(data, StrategyAdapter, cash=10000, commission=0.002, trade_on_close=True, exclusive_orders=True)

    stats = bt.run()

    # --- 6. PRINT AND PLOT RESULTS ---
    logging.info("\n--- Backtest Results ---")
    print(stats)

    logging.info("\n--- Trade Log ---")
    print(stats["_trades"])

    # 1. Create a unique filename for the plot based on the strategy and current time
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    plot_filename = f"logs/backtest_{strategy_name_to_run}_{timestamp}.html"

    logging.info(f"\nGenerating interactive plot... Saving to: {plot_filename}")

    # 2. Call plot() with the new filename
    bt.plot(filename=plot_filename, plot_volume=True, plot_equity=True, plot_return=True, resample=False, open_browser=True)


if __name__ == "__main__":
    run_backtest()
