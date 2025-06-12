# config.py
METATRADER_DIR_PATH = r"C:\\Users\\User\\AppData\\Roaming\\MetaQuotes\\Terminal\\B3FBDE368DD9733D40FCC49B61D1B808\\MQL4\\Files\\"

BAR_DATA_SUBSCRIPTIONS = [["EURUSD", "M1"]]

STRATEGY_SYMBOL = "EURUSD"
STRATEGY_TIMEFRAME = "M1"

# Group strategy parameters together for clarity
STRATEGY_PARAMS = {
    "sma_crossover": {"short_period": 10, "long_period": 20},
    "rsi_strategy": {"rsi_period": 14, "overbought": 70, "oversold": 30},
}

# --- RISK & TRADE MANAGEMENT CONFIG (Pure Percentage-Based) ---
RISK_CONFIG = {
    # --- Position Sizing ---
    "USE_FIXED_LOT_SIZE": False,
    "FIXED_LOT_SIZE": 0.01,
    "RISK_PER_TRADE_PERCENT": 1.0,  # Risk 1% of account balance.
    # --- Stop Loss & Take Profit (as percentages of entry price) ---
    "STOP_LOSS_PERCENT": 20,  # e.g., 20% below/above entry price.
    "TAKE_PROFIT_PERCENT": 40,  # e.g., 40% above/below entry price. 0 means no TP.
    # --- Trailing Stop Loss (as a percentage of the current price) ---
    "USE_TRAILING_STOP": True,
    # The SL will trail behind the current price by this percentage distance.
    "TRAILING_STOP_PERCENT": 15,
    # Trailing only starts after the trade is this much in profit (as a percentage of entry price).
    "TRAILING_STOP_TRIGGER_PERCENT": 20,
    # --- Partial Close Rules ---
    # A list of rules. Each rule is a tuple: (volume_to_close_percent, profit_percent_trigger)
    # Example: Close 50% of the position when it reaches 20% in profit.
    "PARTIAL_CLOSE_RULES": [
        (50, 20),  # Close 50% at +20% profit
        (50, 30),  # You could add another rule to close the next 50% at +30% profit
    ],
    # --- Stacking / Pyramiding ---
    "MAX_OPEN_POSITIONS": 1,
}

MAGIC_NUMBER = 12345
