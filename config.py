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

LOT_SIZE = 0.01
MAGIC_NUMBER = 12345
