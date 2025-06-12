# config.py
METATRADER_DIR_PATH = r"C:\\Users\\User\\AppData\\Roaming\\MetaQuotes\\Terminal\\B3FBDE368DD9733D40FCC49B61D1B808\\MQL4\\Files\\"

BAR_DATA_SUBSCRIPTIONS = [["GOLD", "M1"]]

STRATEGY_SYMBOL = "GOLD"
STRATEGY_TIMEFRAME = "M1"

STRATEGY_PARAMS = {
    "sma_crossover": {"short_period": 10, "long_period": 20},
    # --- NEW STRATEGY CONFIGURATION ---
    "rsi_strategy": {"rsi_period": 14, "oversold_threshold": 30, "overbought_threshold": 70},
}

# --- RISK & TRADE MANAGEMENT CONFIG (Pure Percentage-Based) ---
# Expert Note: The values here represent the actual percentage.
# e.g., 1.0 means 1.0%, 0.2 means 0.2%. The code will handle the conversion.
RISK_CONFIG = {
    # --- Position Sizing ---
    "USE_FIXED_LOT_SIZE": False,
    "FIXED_LOT_SIZE": 0.01,
    "RISK_PER_TRADE_PERCENT": 1.0,  # Risk 1.0% of account balance.
    # --- Stop Loss & Take Profit (as percentages of entry price) ---
    "STOP_LOSS_PERCENT": 0.2,  # A 0.2% stop loss from the entry price.
    "TAKE_PROFIT_PERCENT": 0.4,  # A 0.4% take profit from the entry price. 0 means no TP.
    # --- Trailing Stop Loss (as a percentage of the current price) ---
    "USE_TRAILING_STOP": True,
    "TRAILING_STOP_PERCENT": 0.15,  # The SL will trail by 0.15%.
    "TRAILING_STOP_TRIGGER_PERCENT": 0.2,  # Trailing starts after a 0.2% profit.
    # --- Partial Close Rules ---
    # A list of rules: (volume_to_close_percent, profit_percent_trigger)
    "PARTIAL_CLOSE_RULES": [
        (50, 0.2),  # Close 50% of the trade volume when profit reaches 0.2%.
        # (50, 0.3)  # Example: Close the next 50% at +0.3% profit.
    ],
    # --- Stacking / Pyramiding ---
    "MAX_OPEN_POSITIONS": 1,
}

MAGIC_NUMBER = 12345
