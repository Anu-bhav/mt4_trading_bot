# trading_bot/strategies/fractal_momentum_strategy.py
import pandas as pd
import talib
import logging
import numpy as np

from .base_strategy import BaseStrategy
from ..utils.indicators import t3_ma, hurst_exponent


class FractalMomentumStrategy(BaseStrategy):
    """
    An advanced strategy that merges RoRD's momentum acceleration analysis
    with MFCV's fractal market regime analysis.

    - Uses Hurst Exponent to identify a mean-reverting market state.
    - Uses RoRD's Z-Score and Divergence as the execution trigger within that state.
    """

    def __init__(
        self,
        rsi1_len=14,
        rsi2_len=14,
        t3_len=5,
        t3_vf=0.7,
        dev_len=20,
        z_len=20,
        z_thresh_hi=2.0,
        z_thresh_lo=-2.0,
        divergence_lookback=15,
        hurst_period=100,
        hurst_reverting_threshold=0.45,
        hurst_trending_threshold=0.75,
    ):
        params = locals()
        params.pop("self")
        super().__init__(**params)
        for key, value in params.items():
            setattr(self, key, value)
        self.reset()
        logging.info("FractalMomentumStrategy initialized.")

    def reset(self):
        logging.info("[Strategy State] Fractal Momentum state has been reset.")

    def _find_pivots(self, series: pd.Series, lookback: int):
        # ... (This helper function is the same as in the RoRD strategy)
        window = lookback + (lookback % 2 - 1)
        rolling_max = series.rolling(window=window, center=True, min_periods=1).max()
        rolling_min = series.rolling(window=window, center=True, min_periods=1).min()
        return series == rolling_max, series == rolling_min

    def get_signal(self, market_data: pd.DataFrame) -> str:
        """Generates a signal by combining RoRD and MFCV logic."""

        longest_lookback = (
            max(self.rsi1_len, self.rsi2_len, self.t3_len, self.dev_len, self.z_len, self.divergence_lookback, self.hurst_period)
            + 5
        )
        if len(market_data) < longest_lookback:
            return "HOLD"

        df = market_data.copy()
        df.rename(columns={"Close": "close", "Low": "low", "High": "high"}, inplace=True, errors="ignore")
        for col in ["close", "low", "high"]:
            df[col] = df[col].astype(np.float64)

        # --- 1. MFCV REGIME CALCULATION (The Filter) ---
        hurst = hurst_exponent(df["close"], self.hurst_period)
        is_mean_reverting = hurst < self.hurst_reverting_threshold
        is_strong_trend = hurst > self.hurst_trending_threshold

        # --- 2. RORD MOMENTUM CALCULATION (The Trigger) ---
        df["rsi1"] = talib.RSI(df["close"], timeperiod=self.rsi1_len)
        df["rsi2"] = talib.RSI(df["rsi1"].dropna(), timeperiod=self.rsi2_len)
        df["rsi2_t3"] = t3_ma(df["rsi2"].dropna(), self.t3_len, self.t3_vf)
        df["rsi2_sma"] = talib.SMA(df["rsi2_t3"], timeperiod=self.dev_len)
        df["rsi2_stdev"] = talib.STDDEV(df["rsi2_t3"], timeperiod=self.dev_len).replace(0, np.nan)
        df["rsi2_z"] = (df["rsi2_t3"] - df["rsi2_sma"]) / df["rsi2_stdev"]
        df["z_sma"] = talib.SMA(df["rsi2_z"], timeperiod=self.z_len)
        df["z_stdev"] = talib.STDDEV(df["rsi2_z"], timeperiod=self.z_len).replace(0, np.nan)
        df["final_z"] = (df["rsi2_z"] - df["z_sma"]) / df["z_stdev"]

        df_clean = df.dropna()
        if df_clean.empty:
            return "HOLD"

        current_z = df_clean["final_z"].iloc[-1]
        is_z_extreme_low = current_z < self.z_thresh_lo
        is_z_extreme_high = current_z > self.z_thresh_hi

        # Divergence Detection
        rsi_pivots_high, rsi_pivots_low = self._find_pivots(df_clean["rsi2_t3"], self.divergence_lookback)
        price_pivots_high, price_pivots_low = self._find_pivots(df_clean["high"], self.divergence_lookback)

        rsi_lows = df_clean["rsi2_t3"][rsi_pivots_low]
        price_lows = df_clean["low"][price_pivots_low]
        rsi_highs = df_clean["rsi2_t3"][rsi_pivots_high]
        price_highs = df_clean["high"][price_pivots_high]

        bullish_divergence = (
            len(price_lows) >= 2
            and len(rsi_lows) >= 2
            and (price_lows.iloc[-1] < price_lows.iloc[-2] and rsi_lows.iloc[-1] > rsi_lows.iloc[-2])
        )

        bearish_divergence = (
            len(price_highs) >= 2
            and len(rsi_highs) >= 2
            and (price_highs.iloc[-1] > price_highs.iloc[-2] and rsi_highs.iloc[-1] < rsi_highs.iloc[-2])
        )

        logging.info(
            f"[FMV Values] Hurst={hurst:.3f} | Z-score={current_z:.2f} | BullDiv={bullish_divergence} | BearDiv={bearish_divergence}"
        )

        # --- 3. FINAL COMBINED SIGNAL LOGIC ---

        # High-Conviction BUY Signal: Market must be mean-reverting AND RoRD gives a buy trigger.
        if is_mean_reverting and is_z_extreme_low and bullish_divergence:
            logging.info("[FMV Signal] BUY: Mean-Reverting Regime + Extreme Low Z-score + Bullish Divergence.")
            return "BUY"

        # High-Conviction SELL Signal: Market must be mean-reverting OR in an exhausted trend AND RoRD gives a sell trigger.
        if (is_mean_reverting or is_strong_trend) and is_z_extreme_high and bearish_divergence:
            logging.info(
                f"[FMV Signal] SELL: Regime (MR={is_mean_reverting}, Trend={is_strong_trend}) + Extreme High Z-score + Bearish Divergence."
            )
            return "SELL"

        return "HOLD"
