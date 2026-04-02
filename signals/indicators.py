"""Calculate technical indicators using the 'ta' library on adjusted close prices."""

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator, MACD
from ta.volatility import BollingerBands

from config import Config


def calculate_indicators(prices_df: pd.DataFrame) -> dict:
    """
    Calculate all indicators for a stock given its price history DataFrame.

    Expects columns: date, adj_close, volume (sorted by date ascending).
    Returns a dict of current indicator values.
    """
    if len(prices_df) < Config.SMA_LONG:
        return {"error": f"Need at least {Config.SMA_LONG} days of data"}

    close = prices_df["adj_close"]
    volume = prices_df["volume"]

    # RSI
    rsi_ind = RSIIndicator(close=close, window=Config.RSI_PERIOD)
    rsi_series = rsi_ind.rsi()
    current_rsi = round(rsi_series.iloc[-1], 2) if not rsi_series.empty else None

    # Moving averages
    sma_short_ind = SMAIndicator(close=close, window=Config.SMA_SHORT)
    sma_long_ind = SMAIndicator(close=close, window=Config.SMA_LONG)
    sma_short = sma_short_ind.sma_indicator()
    sma_long = sma_long_ind.sma_indicator()

    current_sma_short = round(sma_short.iloc[-1], 4) if not sma_short.empty else None
    current_sma_long = round(sma_long.iloc[-1], 4) if not sma_long.empty else None
    prev_sma_short = round(sma_short.iloc[-2], 4) if len(sma_short) >= 2 else None
    prev_sma_long = round(sma_long.iloc[-2], 4) if len(sma_long) >= 2 else None

    # MACD
    macd_ind = MACD(close=close, window_fast=Config.MACD_FAST, window_slow=Config.MACD_SLOW, window_sign=Config.MACD_SIGNAL)
    macd_line = macd_ind.macd()
    macd_signal_line = macd_ind.macd_signal()

    current_macd = round(macd_line.iloc[-1], 4) if not macd_line.empty else None
    current_macd_signal = round(macd_signal_line.iloc[-1], 4) if not macd_signal_line.empty else None
    prev_macd = round(macd_line.iloc[-2], 4) if len(macd_line) >= 2 else None
    prev_macd_signal = round(macd_signal_line.iloc[-2], 4) if len(macd_signal_line) >= 2 else None

    # Bollinger Bands
    bb = BollingerBands(close=close, window=Config.BB_PERIOD, window_dev=Config.BB_STD)
    bb_upper_series = bb.bollinger_hband()
    bb_lower_series = bb.bollinger_lband()
    bb_upper = round(bb_upper_series.iloc[-1], 4) if not bb_upper_series.empty else None
    bb_lower = round(bb_lower_series.iloc[-1], 4) if not bb_lower_series.empty else None

    # Volume analysis
    vol_avg_20 = volume.tail(20).mean()
    current_volume = volume.iloc[-1]
    volume_ratio = round(current_volume / vol_avg_20, 2) if vol_avg_20 > 0 else None

    # 52-week high/low
    year_data = close.tail(252)
    high_52w = round(year_data.max(), 4)
    low_52w = round(year_data.min(), 4)

    current_price = round(close.iloc[-1], 4)
    prev_price = round(close.iloc[-2], 4)
    daily_change_pct = round((current_price - prev_price) / prev_price * 100, 2)

    return {
        "current_price": current_price,
        "daily_change_pct": daily_change_pct,
        "rsi": current_rsi,
        "sma_50": current_sma_short,
        "sma_200": current_sma_long,
        "prev_sma_50": prev_sma_short,
        "prev_sma_200": prev_sma_long,
        "macd": current_macd,
        "macd_signal": current_macd_signal,
        "prev_macd": prev_macd,
        "prev_macd_signal": prev_macd_signal,
        "bb_upper": bb_upper,
        "bb_lower": bb_lower,
        "volume_ratio": volume_ratio,
        "high_52w": high_52w,
        "low_52w": low_52w,
    }
