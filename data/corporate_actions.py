"""Utilities for querying corporate actions (dividends and splits)."""

from datetime import datetime, timedelta

from db.init_db import get_connection


def get_upcoming_dividends(days_ahead: int = 14) -> list[dict]:
    """Return stocks with ex-dividend dates within the next N days."""
    conn = get_connection()
    today = datetime.now().strftime("%Y-%m-%d")
    cutoff = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    rows = conn.execute(
        """SELECT ca.ticker, s.name, ca.date, ca.value
           FROM corporate_actions ca
           JOIN stocks s ON s.ticker = ca.ticker
           WHERE ca.action_type = 'dividend'
             AND ca.date >= ? AND ca.date <= ?
           ORDER BY ca.date""",
        (today, cutoff),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_splits(days_back: int = 30) -> list[dict]:
    """Return stocks that had a split in the last N days."""
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    rows = conn.execute(
        """SELECT ca.ticker, s.name, ca.date, ca.value, ca.raw_ratio
           FROM corporate_actions ca
           JOIN stocks s ON s.ticker = ca.ticker
           WHERE ca.action_type = 'split'
             AND ca.date >= ?
           ORDER BY ca.date DESC""",
        (cutoff,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def is_near_ex_dividend(ticker: str, days: int = 3) -> bool:
    """Check if a stock is within N days of an ex-dividend date (suppress RSI alerts)."""
    conn = get_connection()
    today = datetime.now()
    start = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    end = (today + timedelta(days=days)).strftime("%Y-%m-%d")

    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM corporate_actions
           WHERE ticker = ? AND action_type = 'dividend'
             AND date >= ? AND date <= ?""",
        (ticker, start, end),
    ).fetchone()
    conn.close()
    return row["cnt"] > 0
