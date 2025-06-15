# config.py
METATRADER_DIR_PATH = r"C:\\Users\\User\\AppData\\Roaming\\MetaQuotes\\Terminal\\B3FBDE368DD9733D40FCC49B61D1B808\\MQL4\\Files\\"

STRATEGY_SYMBOL = "BTCUSD"  # The symbol to trade, e.g., BTCUSD, EURUSD, etc.
STRATEGY_TIMEFRAME = "M1"

STRATEGY_NAME = "fractal_momentum_strategy"  # Options: sma_crossover, rsi_strategy, tick_counter_strategy, etc.

STRATEGY_PARAMS = {
    "sma_crossover": {"short_period": 10, "long_period": 20},
    # --- NEW STRATEGY CONFIGURATION ---
    "rsi_strategy": {"rsi_period": 14, "oversold_threshold": 48, "overbought_threshold": 51},
    # --- NEW DUMMY STRATEGY CONFIG ---
    "tick_counter_strategy": {},  # This strategy has no parameters
    # --- NEW RORD STRATEGY CONFIG ---
    "rord_strategy": {
        # RSI Layers
        "rsi1_len": 14,
        "rsi2_len": 14,
        # T3 Smoothing
        "t3_len": 5,
        "t3_vf": 0.7,
        # Z-Score Calculation
        "dev_len": 20,  # Lookback for SMA/StDev of RSI²
        "z_len": 20,  # Lookback for SMA/StDev of the Z-score itself
        # Signal Thresholds
        "z_thresh_hi": 2.0,
        "z_thresh_lo": -2.0,
        # Divergence Detection
        "divergence_lookback": 15,  # How far back to look for pivots
    },
    "fractal_momentum_strategy": {
        # --- RoRD Parameters ---
        "rsi1_len": 14,
        "rsi2_len": 14,
        "t3_len": 5,
        "t3_vf": 0.7,
        "dev_len": 20,
        "z_len": 20,
        "z_thresh_hi": 2.0,
        "z_thresh_lo": -2.0,
        "divergence_lookback": 15,
        # --- MFCV Parameters ---
        "hurst_period": 100,
        "hurst_reverting_threshold": 0.45,  # Looking for strong mean-reversion
        "hurst_trending_threshold": 0.75,  # Looking for strong trend exhaustion
    },
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

# --- RISK & TRADE MANAGEMENT CONFIG (Pure Percentage-Based) ---
# Expert Note: The values here represent the actual percentage.
# e.g., 1.0 means 1.0%, 0.2 means 0.2%. The code will handle the conversion.
# RISK_CONFIG = {
#     # --- Position Sizing ---
#     "USE_FIXED_LOT_SIZE": False,
#     "FIXED_LOT_SIZE": 0.01,
#     "RISK_PER_TRADE_PERCENT": 1.0,  # Risk 1.0% of account balance.
#     # --- Stop Loss & Take Profit (as percentages of entry price) ---
#     "STOP_LOSS_PERCENT": 0.2,  # A 0.2% stop loss from the entry price.
#     "TAKE_PROFIT_PERCENT": 0.6,  # A 0.6% take profit from the entry price. 0 means no TP.
#     # --- Trailing Stop Loss (as a percentage of the current price) ---
#     "USE_TRAILING_STOP": True,
#     "TRAILING_STOP_PERCENT": 0.2,  # The SL will trail by 0.2%.
#     "TRAILING_STOP_TRIGGER_PERCENT": 0.3,  # Trailing starts after a 0.3% profit.
#     # --- Partial Close Rules ---
#     # A list of rules: (volume_to_close_percent, profit_percent_trigger)
#     "PARTIAL_CLOSE_RULES": [
#         (50, 0.4),  # Close 50% of the trade volume when profit reaches 0.4%.
#         # (50, 0.2),  # Example: Close the next 50% at +0.2% profit.
#     ],
#     # --- Stacking / Pyramiding ---
#     "MAX_OPEN_POSITIONS": 1,
#     # --- NEW: Execution Safety Buffer Multiplier ---
#     # Multiplies the broker's min stop distance (stoplevel + spread) to create a larger buffer.
#     # A value of 1.5 means the final buffer will be 50% larger than the broker's minimum.
#     # For volatile instruments like crypto, a value between 1.5 and 2.5 is recommended.
#     "STOP_LEVEL_BUFFER_MULTIPLIER": 2.0,  # 2.0x the broker's minimum stop distance.
# }

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

MAGIC_NUMBER = 12345

# How often (in seconds) the Python script sends a heartbeat to the MT4 EA.
# This should be less than the 'pythonHeartbeatTimeoutSeconds' in the EA's settings. default is 180 seconds in EA.
HEARTBEAT_INTERVAL_SECONDS = 150
