"""Calculate technical indicators using pandas-ta on adjusted close prices."""

import pandas as pd
import pandas_ta as ta

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
    rsi = ta.rsi(close, length=Config.RSI_PERIOD)
    current_rsi = round(rsi.iloc[-1], 2) if rsi is not None and not rsi.empty else None

    # Moving averages
    sma_short = ta.sma(close, length=Config.SMA_SHORT)
    sma_long = ta.sma(close, length=Config.SMA_LONG)
    current_sma_short = round(sma_short.iloc[-1], 4) if sma_short is not None else None
    current_sma_long = round(sma_long.iloc[-1], 4) if sma_long is not None else None

    # MACD
    macd_df = ta.macd(close, fast=Config.MACD_FAST, slow=Config.MACD_SLOW, signal=Config.MACD_SIGNAL)
    if macd_df is not None and not macd_df.empty:
        macd_col = f"MACD_{Config.MACD_FAST}_{Config.MACD_SLOW}_{Config.MACD_SIGNAL}"
        signal_col = f"MACDs_{Config.MACD_FAST}_{Config.MACD_SLOW}_{Config.MACD_SIGNAL}"
        current_macd = round(macd_df[macd_col].iloc[-1], 4)
        current_macd_signal = round(macd_df[signal_col].iloc[-1], 4)
        prev_macd = round(macd_df[macd_col].iloc[-2], 4)
        prev_macd_signal = round(macd_df[signal_col].iloc[-2], 4)
    else:
        current_macd = current_macd_signal = prev_macd = prev_macd_signal = None

    # Bollinger Bands
    bb = ta.bbands(close, length=Config.BB_PERIOD, std=Config.BB_STD)
    if bb is not None and not bb.empty:
        bb_upper = round(bb.iloc[-1, 0], 4)  # BBU
        bb_lower = round(bb.iloc[-1, 2], 4)  # BBL
    else:
        bb_upper = bb_lower = None

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
        "prev_sma_50": round(sma_short.iloc[-2], 4) if sma_short is not None else None,
        "prev_sma_200": round(sma_long.iloc[-2], 4) if sma_long is not None else None,
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
