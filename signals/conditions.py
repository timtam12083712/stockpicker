"""Signal condition definitions — each returns (signal_name, signal_type) or None."""

from config import Config


def check_rsi_oversold(ind: dict) -> tuple | None:
    if ind.get("rsi") is not None and ind["rsi"] < Config.RSI_OVERSOLD:
        return ("RSI oversold", "entry")
    return None


def check_rsi_overbought(ind: dict) -> tuple | None:
    if ind.get("rsi") is not None and ind["rsi"] > Config.RSI_OVERBOUGHT:
        return ("RSI overbought", "exit")
    return None


def check_golden_cross(ind: dict) -> tuple | None:
    sma50, sma200 = ind.get("sma_50"), ind.get("sma_200")
    prev50, prev200 = ind.get("prev_sma_50"), ind.get("prev_sma_200")
    if all(v is not None for v in [sma50, sma200, prev50, prev200]):
        if prev50 <= prev200 and sma50 > sma200:
            return ("Golden cross", "bullish")
    return None


def check_death_cross(ind: dict) -> tuple | None:
    sma50, sma200 = ind.get("sma_50"), ind.get("sma_200")
    prev50, prev200 = ind.get("prev_sma_50"), ind.get("prev_sma_200")
    if all(v is not None for v in [sma50, sma200, prev50, prev200]):
        if prev50 >= prev200 and sma50 < sma200:
            return ("Death cross", "bearish")
    return None


def check_price_above_50ma(ind: dict) -> tuple | None:
    price = ind.get("current_price")
    sma50 = ind.get("sma_50")
    if price is not None and sma50 is not None and price > sma50:
        return ("Price above 50MA", "bullish")
    return None


def check_price_below_50ma(ind: dict) -> tuple | None:
    price = ind.get("current_price")
    sma50 = ind.get("sma_50")
    if price is not None and sma50 is not None and price < sma50:
        return ("Price below 50MA", "bearish")
    return None


def check_macd_crossover(ind: dict) -> tuple | None:
    macd, sig = ind.get("macd"), ind.get("macd_signal")
    prev_macd, prev_sig = ind.get("prev_macd"), ind.get("prev_macd_signal")
    if all(v is not None for v in [macd, sig, prev_macd, prev_sig]):
        if prev_macd <= prev_sig and macd > sig:
            return ("MACD crossover", "bullish")
    return None


def check_macd_crossunder(ind: dict) -> tuple | None:
    macd, sig = ind.get("macd"), ind.get("macd_signal")
    prev_macd, prev_sig = ind.get("prev_macd"), ind.get("prev_macd_signal")
    if all(v is not None for v in [macd, sig, prev_macd, prev_sig]):
        if prev_macd >= prev_sig and macd < sig:
            return ("MACD crossunder", "bearish")
    return None


def check_volume_spike(ind: dict) -> tuple | None:
    ratio = ind.get("volume_ratio")
    if ratio is not None and ratio > Config.VOLUME_SPIKE_MULTIPLIER:
        return ("Volume spike", "attention")
    return None


def check_near_52w_low(ind: dict) -> tuple | None:
    price, low = ind.get("current_price"), ind.get("low_52w")
    if price is not None and low is not None and low > 0:
        if (price - low) / low <= Config.NEAR_52W_LOW_PCT:
            return ("Near 52-week low", "entry")
    return None


def check_near_52w_high(ind: dict) -> tuple | None:
    price, high = ind.get("current_price"), ind.get("high_52w")
    if price is not None and high is not None and high > 0:
        if (high - price) / high <= Config.NEAR_52W_HIGH_PCT:
            return ("Near 52-week high", "exit")
    return None


# All conditions in evaluation order
ALL_CONDITIONS = [
    check_rsi_oversold,
    check_rsi_overbought,
    check_golden_cross,
    check_death_cross,
    check_price_above_50ma,
    check_price_below_50ma,
    check_macd_crossover,
    check_macd_crossunder,
    check_volume_spike,
    check_near_52w_low,
    check_near_52w_high,
]
