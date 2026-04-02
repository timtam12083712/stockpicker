"""Flask web dashboard for ASX Stock Picker."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, render_template, request, redirect, url_for, flash
from config import Config
from db.init_db import get_connection, init_db
from journal.trades import open_trade, close_trade, get_open_trades, get_trade_history, get_trade_stats
from data.corporate_actions import get_upcoming_dividends, get_recent_splits

app = Flask(__name__)
app.secret_key = Config.FLASK_SECRET_KEY


@app.route("/")
def dashboard():
    """Main dashboard — watchlist overview."""
    conn = get_connection()

    stocks = conn.execute(
        "SELECT * FROM stocks WHERE active=1 ORDER BY sector, ticker"
    ).fetchall()

    # Get latest indicators for each stock
    stock_data = []
    for s in stocks:
        ticker = s["ticker"]
        latest_price = conn.execute(
            "SELECT * FROM prices WHERE ticker=? ORDER BY date DESC LIMIT 1",
            (ticker,),
        ).fetchone()

        latest_signal = conn.execute(
            "SELECT signal_name, signal_type, created_at FROM signals WHERE ticker=? ORDER BY created_at DESC LIMIT 1",
            (ticker,),
        ).fetchone()

        stock_data.append({
            "stock": dict(s),
            "price": dict(latest_price) if latest_price else None,
            "signal": dict(latest_signal) if latest_signal else None,
        })

    conn.close()

    upcoming_divs = get_upcoming_dividends()
    recent_splits = get_recent_splits()

    return render_template(
        "dashboard.html",
        stock_data=stock_data,
        upcoming_divs=upcoming_divs,
        recent_splits=recent_splits,
    )


@app.route("/signals")
def signals():
    """Signal history page."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT s.*, st.name as stock_name
           FROM signals s JOIN stocks st ON st.ticker = s.ticker
           ORDER BY s.created_at DESC LIMIT 100"""
    ).fetchall()
    conn.close()
    return render_template("signals.html", signals=[dict(r) for r in rows])


@app.route("/journal")
def journal():
    """Trade journal page."""
    open_trades = get_open_trades()
    closed_trades = get_trade_history()
    stats = get_trade_stats()
    return render_template(
        "journal.html",
        open_trades=open_trades,
        closed_trades=closed_trades,
        stats=stats,
    )


@app.route("/journal/new", methods=["GET", "POST"])
def journal_new():
    """New trade entry form."""
    if request.method == "POST":
        trade_id = open_trade(
            ticker=request.form["ticker"],
            direction=request.form["direction"],
            entry_price=float(request.form["entry_price"]),
            quantity=int(request.form["quantity"]),
            brokerage=float(request.form.get("brokerage", 0)),
            reasoning=request.form.get("reasoning", ""),
            target_exit=float(request.form["target_exit"]) if request.form.get("target_exit") else None,
            stop_loss=float(request.form["stop_loss"]) if request.form.get("stop_loss") else None,
        )
        flash(f"Trade #{trade_id} recorded.")
        return redirect(url_for("journal"))

    conn = get_connection()
    stocks = conn.execute("SELECT ticker, name FROM stocks WHERE active=1 ORDER BY ticker").fetchall()
    conn.close()
    return render_template("journal_new.html", stocks=[dict(s) for s in stocks])


@app.route("/journal/close/<int:trade_id>", methods=["GET", "POST"])
def journal_close(trade_id):
    """Close an open trade."""
    if request.method == "POST":
        close_trade(
            trade_id=trade_id,
            exit_price=float(request.form["exit_price"]),
            brokerage=float(request.form.get("brokerage", 0)),
            exit_reason=request.form.get("exit_reason", ""),
            lessons=request.form.get("lessons", ""),
            signal_accuracy=request.form.get("signal_accuracy"),
        )
        flash(f"Trade #{trade_id} closed.")
        return redirect(url_for("journal"))

    conn = get_connection()
    trade = conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
    conn.close()
    return render_template("journal_close.html", trade=dict(trade))


@app.route("/portfolio")
def portfolio():
    """Portfolio view from latest snapshot."""
    conn = get_connection()
    latest_date = conn.execute(
        "SELECT MAX(date) as d FROM portfolio_snapshot"
    ).fetchone()

    holdings = []
    if latest_date and latest_date["d"]:
        holdings = conn.execute(
            "SELECT * FROM portfolio_snapshot WHERE date=? ORDER BY ticker",
            (latest_date["d"],),
        ).fetchall()
        holdings = [dict(h) for h in holdings]

    conn.close()
    return render_template("portfolio.html", holdings=holdings)


@app.route("/watchlist/add", methods=["POST"])
def watchlist_add():
    """Add a stock to the watchlist."""
    ticker = request.form["ticker"].upper().strip()
    if not ticker.endswith(".AX"):
        ticker += ".AX"

    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) as cnt FROM stocks WHERE active=1").fetchone()["cnt"]
    if count >= Config.MAX_WATCHLIST_STOCKS:
        flash(f"Watchlist full ({Config.MAX_WATCHLIST_STOCKS} stocks max).")
        conn.close()
        return redirect(url_for("dashboard"))

    conn.execute(
        "INSERT OR REPLACE INTO stocks (ticker, name, sector, user_note, active) VALUES (?, ?, ?, ?, 1)",
        (ticker, request.form.get("name", ticker), request.form.get("sector", ""), request.form.get("note", "")),
    )
    conn.commit()
    conn.close()
    flash(f"{ticker} added to watchlist.")
    return redirect(url_for("dashboard"))


@app.route("/watchlist/remove/<ticker>", methods=["POST"])
def watchlist_remove(ticker):
    """Soft-delete a stock from the watchlist."""
    conn = get_connection()
    conn.execute("UPDATE stocks SET active=0 WHERE ticker=?", (ticker,))
    conn.commit()
    conn.close()
    flash(f"{ticker} removed from watchlist.")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
