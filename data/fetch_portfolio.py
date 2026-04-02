"""Fetch portfolio holdings from SnapTrade (CommSec read-only connection)."""

from datetime import datetime

from config import Config
from db.init_db import get_connection


def sync_portfolio():
    """
    Sync portfolio holdings from SnapTrade.

    TODO: Implement once SnapTrade account is connected.
    Requires:
    - SNAPTRADE_CLIENT_ID and SNAPTRADE_CLIENT_SECRET in .env
    - SnapTrade user registration and CommSec brokerage connection
    - snaptrade-python-sdk installed

    Steps:
    1. Authenticate with SnapTrade
    2. Fetch holdings for connected CommSec account
    3. Store snapshot in portfolio_snapshot table
    """
    print("SnapTrade sync not yet configured.")
    print("Set up your SnapTrade account and add credentials to .env")
    print("See: https://docs.snaptrade.com/docs/getting-started")


def store_portfolio_snapshot(holdings: list[dict]):
    """Store a daily portfolio snapshot."""
    conn = get_connection()
    today = datetime.now().strftime("%Y-%m-%d")

    for h in holdings:
        conn.execute(
            """INSERT INTO portfolio_snapshot
               (date, ticker, quantity, avg_cost, current_price, current_value,
                unrealised_pnl, unrealised_pnl_pct)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                today,
                h["ticker"],
                h["quantity"],
                h["avg_cost"],
                h["current_price"],
                h["current_value"],
                h["unrealised_pnl"],
                h["unrealised_pnl_pct"],
            ),
        )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    sync_portfolio()
