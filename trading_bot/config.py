# config.py

# -- Active Strategy To Run --
STRATEGY_NAME = "alpha_vortex_strategy"

# --- STRATEGY CONFIG ---
STRATEGY_SYMBOL = "XAUUSD"
STRATEGY_TIMEFRAME = "M5"

STRATEGY_PARAMS = {
    "sma_crossover": {"short_period": 10, "long_period": 20},
    "alpha_vortex_strategy": {
        # --- QQE Parameters (for Trend-Following) ---
        # Shorter QQE to react faster to trend shifts on low timeframes.
        "qqe_rsi_len": 9,
        "qqe_smooth_factor": 3,
        # --- RoRD Parameters (for Mean-Reversion) ---
        # Shorter RSI layers to increase sensitivity.
        "rord_rsi1_len": 9,
        "rord_rsi2_len": 9,
        # Very light T3 smoothing to keep it fast.
        "rord_t3_len": 3,
        "rord_t3_vf": 0.8,  # Higher vFactor for more responsiveness
        # Shorter lookbacks for Z-score to adapt to rapidly changing volatility.
        "rord_dev_len": 15,
        "rord_z_len": 15,
        # Standard Z-score threshold; we expect more frequent extremes on low TFs.
        "rord_z_thresh_hi": 2.0,
        "rord_z_thresh_lo": -2.0,
        # --- MFCV Parameters (The Regime Filter) ---
        # Shorter Hurst period to analyze the character of the last hour or two.
        "hurst_period": 60,
        # Tighter thresholds to more quickly classify the regime.
        "hurst_reverting_threshold": 0.48,
        "hurst_trending_threshold": 0.52,
    },
}

# --- RISK & TRADE MANAGEMENT CONFIG ---
RISK_CONFIG = {
    "USE_FIXED_LOT_SIZE": False,
    "RISK_PER_TRADE_PERCENT": 0.5,  # Lower risk per trade for higher frequency.
    "STOP_LOSS_PERCENT": 0.1,  # Tighter stops for scalping.
    "TAKE_PROFIT_PERCENT": 0.15,  # Aiming for a 1.5:1 R/R.
    "USE_TRAILING_STOP": True,
    "TRAILING_STOP_PERCENT": 0.08,
    "TRAILING_STOP_TRIGGER_PERCENT": 0.1,
    "PARTIAL_CLOSE_RULES": [],  # No partial closes for simple scalping.
    "MAX_OPEN_POSITIONS": 1,
    "STOP_LEVEL_BUFFER_MULTIPLIER": 2.5,  # Larger buffer multiplier for volatile scalping.
}

# --- OPERATIONAL & SAFETY CONFIG ---
MAGIC_NUMBER = 202402
HEARTBEAT_INTERVAL_SECONDS = 15
METATRADER_DIR_PATH = r"C:\\Users\\User\\AppData\\Roaming\\MetaQuotes\\Terminal\\B3FBDE368DD9733D40FCC49B61D1B808\\MQL4\\Files\\"
