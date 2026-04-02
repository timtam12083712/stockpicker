"""Signal evaluator — runs indicators and conditions for all watchlist stocks."""

import json

import pandas as pd

from db.init_db import get_connection
from data.corporate_actions import is_near_ex_dividend
from signals.indicators import calculate_indicators
from signals.conditions import ALL_CONDITIONS


def get_price_dataframe(ticker: str) -> pd.DataFrame:
    """Load price history for a ticker into a DataFrame."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT date, adj_close, volume FROM prices WHERE ticker=? ORDER BY date ASC",
        (ticker,),
    ).fetchall()
    conn.close()

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame([dict(r) for r in rows])


def is_signal_enabled(ticker: str, signal_name: str) -> bool:
    """Check if a signal is enabled for this ticker (or globally)."""
    conn = get_connection()

    # Check ticker-specific override first
    row = conn.execute(
        "SELECT enabled FROM signal_config WHERE ticker=? AND signal_name=?",
        (ticker, signal_name),
    ).fetchone()
    if row:
        conn.close()
        return bool(row["enabled"])

    # Check global setting
    row = conn.execute(
        "SELECT enabled FROM signal_config WHERE ticker IS NULL AND signal_name=?",
        (signal_name,),
    ).fetchone()
    conn.close()

    # Default: enabled
    return bool(row["enabled"]) if row else True


def evaluate_stock(ticker: str) -> list[dict]:
    """Evaluate all signal conditions for a single stock. Returns list of fired signals."""
    df = get_price_dataframe(ticker)
    if df.empty:
        return []

    indicators = calculate_indicators(df)
    if "error" in indicators:
        print(f"  {ticker}: {indicators['error']}")
        return []

    near_ex_div = is_near_ex_dividend(ticker)
    fired = []

    for condition_fn in ALL_CONDITIONS:
        result = condition_fn(indicators)
        if result is None:
            continue

        signal_name, signal_type = result

        # Suppress RSI alerts near ex-dividend dates
        if near_ex_div and signal_name in ("RSI oversold", "RSI overbought"):
            print(f"  {ticker}: Suppressing {signal_name} — near ex-dividend date")
            continue

        if not is_signal_enabled(ticker, signal_name):
            continue

        fired.append({
            "ticker": ticker,
            "signal_name": signal_name,
            "signal_type": signal_type,
            "indicators": indicators,
        })

    return fired


def store_signals(signals: list[dict]):
    """Store fired signals in the database."""
    conn = get_connection()
    for sig in signals:
        conn.execute(
            """INSERT INTO signals (ticker, date, signal_name, signal_type, indicator_values)
               VALUES (?, date('now'), ?, ?, ?)""",
            (
                sig["ticker"],
                sig["signal_name"],
                sig["signal_type"],
                json.dumps(sig["indicators"]),
            ),
        )
    conn.commit()
    conn.close()


def run_signal_engine() -> list[dict]:
    """Main entry: evaluate signals for all active watchlist stocks."""
    conn = get_connection()
    stocks = conn.execute("SELECT ticker FROM stocks WHERE active=1").fetchall()
    conn.close()

    all_signals = []
    for stock_row in stocks:
        ticker = stock_row["ticker"]
        signals = evaluate_stock(ticker)
        if signals:
            print(f"  {ticker}: {len(signals)} signal(s) fired")
            all_signals.extend(signals)

    if all_signals:
        store_signals(all_signals)
        print(f"\nTotal: {len(all_signals)} signals stored")
    else:
        print("\nNo signals fired tonight.")

    return all_signals


if __name__ == "__main__":
    run_signal_engine()
