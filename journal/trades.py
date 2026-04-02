"""Trade journal CRUD operations."""

import json
from datetime import datetime

from db.init_db import get_connection


def open_trade(
    ticker: str,
    direction: str,
    entry_price: float,
    quantity: int,
    brokerage: float = 0,
    signals: list[str] | None = None,
    reasoning: str = "",
    indicators: dict | None = None,
    target_exit: float | None = None,
    stop_loss: float | None = None,
) -> int:
    """Record a new trade entry. Returns the trade ID."""
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO trades
           (ticker, direction, entry_date, entry_price, quantity, brokerage_entry,
            signals_at_entry, entry_reasoning, indicators_at_entry,
            target_exit_price, stop_loss_price)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            ticker,
            direction,
            datetime.now().isoformat(),
            entry_price,
            quantity,
            brokerage,
            json.dumps(signals or []),
            reasoning,
            json.dumps(indicators or {}),
            target_exit,
            stop_loss,
        ),
    )
    conn.commit()
    trade_id = cursor.lastrowid
    conn.close()
    return trade_id


def close_trade(
    trade_id: int,
    exit_price: float,
    brokerage: float = 0,
    exit_reason: str = "",
    signals_at_exit: list[str] | None = None,
    dividends: float = 0,
    lessons: str = "",
    signal_accuracy: str | None = None,
):
    """Close an existing trade and calculate P&L."""
    conn = get_connection()
    trade = conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
    if not trade:
        conn.close()
        raise ValueError(f"Trade {trade_id} not found")

    entry_price = trade["entry_price"]
    quantity = trade["quantity"]
    brokerage_entry = trade["brokerage_entry"]

    if trade["direction"] == "buy":
        pnl_excl = (exit_price - entry_price) * quantity
    else:
        pnl_excl = (entry_price - exit_price) * quantity

    pnl_incl = pnl_excl - brokerage_entry - brokerage
    total_return = pnl_incl + dividends

    conn.execute(
        """UPDATE trades SET
           exit_date=?, exit_price=?, exit_reason=?, signals_at_exit=?,
           brokerage_exit=?, dividends_received=?,
           pnl_excl_brokerage=?, pnl_incl_brokerage=?, total_return=?,
           lessons_learned=?, signal_accuracy=?
           WHERE id=?""",
        (
            datetime.now().isoformat(),
            exit_price,
            exit_reason,
            json.dumps(signals_at_exit or []),
            brokerage,
            dividends,
            round(pnl_excl, 2),
            round(pnl_incl, 2),
            round(total_return, 2),
            lessons,
            signal_accuracy,
            trade_id,
        ),
    )
    conn.commit()
    conn.close()


def get_open_trades() -> list[dict]:
    """Return all trades that haven't been closed."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM trades WHERE exit_date IS NULL ORDER BY entry_date DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_trade_history(ticker: str | None = None) -> list[dict]:
    """Return closed trades, optionally filtered by ticker."""
    conn = get_connection()
    if ticker:
        rows = conn.execute(
            "SELECT * FROM trades WHERE exit_date IS NOT NULL AND ticker=? ORDER BY exit_date DESC",
            (ticker,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM trades WHERE exit_date IS NOT NULL ORDER BY exit_date DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_trade_stats() -> dict:
    """Calculate summary stats across all closed trades."""
    conn = get_connection()
    closed = conn.execute(
        "SELECT * FROM trades WHERE exit_date IS NOT NULL"
    ).fetchall()
    conn.close()

    if not closed:
        return {"total_trades": 0}

    total_pnl = sum(t["total_return"] or 0 for t in closed)
    winners = [t for t in closed if (t["total_return"] or 0) > 0]
    losers = [t for t in closed if (t["total_return"] or 0) < 0]

    return {
        "total_trades": len(closed),
        "winners": len(winners),
        "losers": len(losers),
        "win_rate": round(len(winners) / len(closed) * 100, 1),
        "total_pnl": round(total_pnl, 2),
        "avg_pnl": round(total_pnl / len(closed), 2),
    }
