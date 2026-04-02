"""Fetch daily OHLCV + corporate actions from yfinance for all active watchlist stocks."""

import json
import time
from datetime import datetime, timedelta

import yfinance as yf

from config import Config
from db.init_db import get_connection


def fetch_stock_data(ticker: str, days: int = Config.HISTORY_PERIOD_DAYS) -> dict | None:
    """Fetch OHLCV and actions for a single ticker. Returns dict or None on failure."""
    try:
        stock = yf.Ticker(ticker)
        end = datetime.now()
        start = end - timedelta(days=days)

        hist = stock.history(start=start, end=end, auto_adjust=True)
        if hist.empty:
            print(f"  WARNING: No data returned for {ticker}")
            return None

        actions = stock.actions
        return {"history": hist, "actions": actions}

    except Exception as e:
        print(f"  ERROR fetching {ticker}: {e}")
        return None


def store_prices(ticker: str, hist) -> int:
    """Store price history into the prices table. Returns rows inserted."""
    conn = get_connection()
    rows = 0
    for date, row in hist.iterrows():
        date_str = date.strftime("%Y-%m-%d")
        conn.execute(
            """INSERT OR REPLACE INTO prices
               (ticker, date, open, high, low, close, adj_close, volume)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ticker,
                date_str,
                round(row.get("Open", 0), 4),
                round(row.get("High", 0), 4),
                round(row.get("Low", 0), 4),
                round(row.get("Close", 0), 4),
                round(row.get("Close", 0), 4),  # auto_adjust=True means Close IS adj_close
                int(row.get("Volume", 0)),
            ),
        )
        rows += 1
    conn.commit()
    conn.close()
    return rows


def store_corporate_actions(ticker: str, actions) -> int:
    """Store dividends and splits from yfinance actions feed. Returns rows inserted."""
    if actions is None or actions.empty:
        return 0

    conn = get_connection()
    rows = 0
    for date, row in actions.iterrows():
        date_str = date.strftime("%Y-%m-%d")
        dividends = row.get("Dividends", 0)
        splits = row.get("Stock Splits", 0)

        if dividends > 0:
            conn.execute(
                """INSERT OR IGNORE INTO corporate_actions
                   (ticker, action_type, date, value)
                   VALUES (?, 'dividend', ?, ?)""",
                (ticker, date_str, round(dividends, 4)),
            )
            rows += 1

        if splits > 0:
            ratio_str = f"{int(splits)}:1" if splits == int(splits) else str(splits)
            conn.execute(
                """INSERT OR IGNORE INTO corporate_actions
                   (ticker, action_type, date, value, raw_ratio)
                   VALUES (?, 'split', ?, ?, ?)""",
                (ticker, date_str, splits, ratio_str),
            )
            rows += 1

    conn.commit()
    conn.close()
    return rows


def detect_recent_splits(ticker: str, days: int = 30) -> bool:
    """Check if a split was detected in the last N days."""
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM corporate_actions WHERE ticker=? AND action_type='split' AND date>=?",
        (ticker, cutoff),
    ).fetchone()
    conn.close()
    return row["cnt"] > 0


def run_nightly_fetch():
    """Main entry point: fetch data for all active watchlist stocks."""
    conn = get_connection()
    stocks = conn.execute("SELECT ticker FROM stocks WHERE active=1").fetchall()
    conn.close()

    if not stocks:
        print("No active stocks in watchlist. Run db/init_db.py to seed.")
        return

    print(f"Fetching data for {len(stocks)} stocks...")

    for stock_row in stocks:
        ticker = stock_row["ticker"]
        print(f"\n  Fetching {ticker}...")

        data = fetch_stock_data(ticker)
        if data is None:
            continue

        price_rows = store_prices(ticker, data["history"])
        action_rows = store_corporate_actions(ticker, data["actions"])
        print(f"    Stored {price_rows} price rows, {action_rows} corporate actions")

        # If recent split detected, re-fetch extended history
        if detect_recent_splits(ticker):
            print(f"    Split detected — re-fetching {Config.SPLIT_REFETCH_DAYS} days of history")
            extended = fetch_stock_data(ticker, days=Config.SPLIT_REFETCH_DAYS)
            if extended:
                store_prices(ticker, extended["history"])

        time.sleep(Config.FETCH_DELAY_SECONDS)

    print("\nNightly fetch complete.")


if __name__ == "__main__":
    run_nightly_fetch()
