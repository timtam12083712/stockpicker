"""Flask web dashboard for ASX Stock Picker."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import time
import threading
from datetime import date
from markupsafe import Markup

import yfinance as yf
from flask import Flask, render_template, request, redirect, url_for, flash
from config import Config
from db.init_db import get_connection, init_db
from journal.trades import open_trade, close_trade, get_open_trades, get_trade_history, get_trade_stats
from data.corporate_actions import get_upcoming_dividends, get_recent_splits

app = Flask(__name__)
app.secret_key = Config.FLASK_SECRET_KEY

# Macro ticker cache (refreshes every 10 minutes)
_macro_cache = {"data": [], "ts": 0}
_macro_lock = threading.Lock()

MACRO_TICKERS = [
    ("^AXJO", "ASX 200"),
    ("^GSPC", "S&P 500"),
    ("^IXIC", "Nasdaq"),
    ("^DJI", "Dow"),
    ("^VIX", "VIX"),
    ("CL=F", "Oil (WTI)"),
    ("GC=F", "Gold"),
    ("AUDUSD=X", "AUD/USD"),
]


def get_macro_data():
    """Fetch macro indices/commodities with 10-min cache."""
    with _macro_lock:
        if time.time() - _macro_cache["ts"] < 600 and _macro_cache["data"]:
            return _macro_cache["data"]

    symbols = [t[0] for t in MACRO_TICKERS]
    labels = {t[0]: t[1] for t in MACRO_TICKERS}
    results = []
    try:
        tickers = yf.Tickers(" ".join(symbols))
        for sym in symbols:
            try:
                t = tickers.tickers[sym]
                info = t.fast_info
                price = info.last_price
                prev = info.previous_close
                change_pct = ((price - prev) / prev * 100) if prev else 0
                # Format price based on type
                if sym == "AUDUSD=X":
                    price_fmt = f"{price:.4f}"
                elif sym == "^VIX":
                    price_fmt = f"{price:.1f}"
                elif price > 1000:
                    price_fmt = f"{price:,.0f}"
                else:
                    price_fmt = f"{price:.2f}"
                results.append({
                    "symbol": sym,
                    "label": labels[sym],
                    "price": price_fmt,
                    "change_pct": round(change_pct, 2),
                })
            except Exception:
                continue
    except Exception:
        pass

    with _macro_lock:
        _macro_cache["data"] = results
        _macro_cache["ts"] = time.time()
    return results


# Economic cycle detection
_cycle_cache = {"data": None, "ts": 0}
_cycle_lock = threading.Lock()

# Cycle phases and their sector tilts (ASX-oriented)
CYCLE_PHASES = {
    "early_expansion": {
        "label": "Early Expansion",
        "description": "Recovery underway — rates low, earnings improving",
        "sectors": ["Financials", "Consumer Discretionary", "Real Estate", "Technology"],
        "color": "#34d399",
    },
    "mid_expansion": {
        "label": "Mid Expansion",
        "description": "Broad growth — capex rising, employment strong",
        "sectors": ["Technology", "Industrials", "Materials", "Communication Services"],
        "color": "#4f8ff7",
    },
    "late_expansion": {
        "label": "Late Expansion",
        "description": "Growth maturing — inflation rising, rates tightening",
        "sectors": ["Energy", "Materials", "Healthcare", "Industrials"],
        "color": "#fbbf24",
    },
    "contraction": {
        "label": "Contraction",
        "description": "Slowdown — yield curve flat/inverted, volatility elevated",
        "sectors": ["Utilities", "Consumer Staples", "Healthcare", "Gold Miners"],
        "color": "#f87171",
    },
    "trough": {
        "label": "Trough",
        "description": "Bottom forming — deep pessimism, policy easing",
        "sectors": ["Financials", "Consumer Discretionary", "Technology", "Real Estate"],
        "color": "#c084fc",
    },
}


def _detect_cycle_phase():
    """Heuristic economic cycle detection from market signals.

    Uses: yield curve (10Y-2Y), VIX level, S&P 500 trend vs 200-day MA.
    Returns a phase key from CYCLE_PHASES.
    """
    import pandas as pd

    score = 0  # positive = expansionary, negative = contractionary

    # 1) Yield curve: 10Y minus 2Y treasury yield
    try:
        tnx = yf.Ticker("^TNX")  # 10-year yield
        twy = yf.Ticker("2YY=F")  # 2-year yield
        y10 = tnx.fast_info.last_price
        y2 = twy.fast_info.last_price
        spread = y10 - y2
        if spread < -0.5:
            score -= 3  # deeply inverted
        elif spread < 0:
            score -= 1  # inverted
        elif spread > 1.5:
            score += 2  # steep — early recovery
        else:
            score += 1  # normal positive
    except Exception:
        spread = None

    # 2) VIX level
    try:
        vix = yf.Ticker("^VIX")
        vix_val = vix.fast_info.last_price
        if vix_val > 30:
            score -= 2  # high fear
        elif vix_val > 20:
            score -= 1  # elevated
        elif vix_val < 14:
            score += 2  # complacent / strong expansion
        else:
            score += 1  # normal
    except Exception:
        vix_val = None

    # 3) S&P 500 vs 200-day MA
    try:
        spx = yf.Ticker("^GSPC")
        hist = spx.history(period="1y")
        if len(hist) >= 200:
            ma200 = hist["Close"].rolling(200).mean().iloc[-1]
            current = hist["Close"].iloc[-1]
            pct_above = ((current - ma200) / ma200) * 100
            if pct_above > 10:
                score += 2  # well above — strong expansion
            elif pct_above > 0:
                score += 1  # above — expansion
            elif pct_above > -10:
                score -= 1  # below — weakening
            else:
                score -= 2  # well below — contraction
        else:
            pct_above = None
    except Exception:
        pct_above = None

    # 4) Map score to phase
    if score >= 4:
        phase = "mid_expansion"
    elif score >= 2:
        phase = "early_expansion"
    elif score >= 0:
        phase = "late_expansion"
    elif score >= -2:
        phase = "contraction"
    else:
        phase = "trough"

    return phase, score


def get_economic_cycle():
    """Get economic cycle phase with 10-min cache."""
    with _cycle_lock:
        if time.time() - _cycle_cache["ts"] < 600 and _cycle_cache["data"]:
            return _cycle_cache["data"]

    try:
        phase_key, score = _detect_cycle_phase()
        phase = CYCLE_PHASES[phase_key]
        result = {
            "phase": phase_key,
            "label": phase["label"],
            "description": phase["description"],
            "sectors": phase["sectors"],
            "color": phase["color"],
            "score": score,
        }
    except Exception:
        result = None

    with _cycle_lock:
        _cycle_cache["data"] = result
        _cycle_cache["ts"] = time.time()
    return result


def make_sparkline(prices, width=120, height=32):
    """Generate an inline SVG sparkline from a list of prices."""
    if not prices or len(prices) < 2:
        return ""
    mn, mx = min(prices), max(prices)
    rng = mx - mn or 1
    n = len(prices)
    points = []
    for i, p in enumerate(prices):
        x = round(i / (n - 1) * width, 1)
        y = round(height - (p - mn) / rng * (height - 2) - 1, 1)
        points.append(f"{x},{y}")
    polyline = " ".join(points)
    color = "#34d399" if prices[-1] >= prices[0] else "#f87171"
    # Fill area under the line
    fill_points = f"0,{height} {polyline} {width},{height}"
    fill_color = color.replace(")", ",0.1)").replace("#", "")
    svg = (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'class="sparkline" xmlns="http://www.w3.org/2000/svg">'
        f'<polygon points="{fill_points}" fill="{color}" opacity="0.12"/>'
        f'<polyline points="{polyline}" fill="none" stroke="{color}" '
        f'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
        f'</svg>'
    )
    return Markup(svg)


@app.route("/")
def dashboard():
    """Main dashboard — watchlist overview."""
    conn = get_connection()

    ytd_start = f"{date.today().year}-01-01"

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

        # YTD prices for sparkline
        ytd_prices = conn.execute(
            "SELECT adj_close FROM prices WHERE ticker=? AND date>=? ORDER BY date",
            (ticker, ytd_start),
        ).fetchall()
        sparkline_svg = make_sparkline([r["adj_close"] for r in ytd_prices])

        # YTD change %
        ytd_change = None
        if len(ytd_prices) >= 2:
            first, last = ytd_prices[0]["adj_close"], ytd_prices[-1]["adj_close"]
            if first:
                ytd_change = round((last - first) / first * 100, 1)

        # Get all recent signals with indicator data
        recent_signals = conn.execute(
            """SELECT signal_name, signal_type, indicator_values, ai_summary
               FROM signals WHERE ticker=? ORDER BY created_at DESC LIMIT 5""",
            (ticker,),
        ).fetchall()

        # Parse indicators from most recent signal
        indicators = {}
        signals_list = []
        for sig in recent_signals:
            sig_dict = dict(sig)
            if sig["indicator_values"]:
                try:
                    indicators = json.loads(sig["indicator_values"])
                except (json.JSONDecodeError, TypeError):
                    pass
            signals_list.append(sig_dict)

        # Calculate 52-week range position (0-100%)
        range_pct = None
        if indicators.get("high_52w") and indicators.get("low_52w") and indicators.get("current_price"):
            high = indicators["high_52w"]
            low = indicators["low_52w"]
            if high != low:
                range_pct = round((indicators["current_price"] - low) / (high - low) * 100, 1)

        stock_data.append({
            "stock": dict(s),
            "price": dict(latest_price) if latest_price else None,
            "signals": signals_list,
            "indicators": indicators,
            "range_pct": range_pct,
            "sparkline": sparkline_svg,
            "ytd_change": ytd_change,
        })

    conn.close()

    upcoming_divs = get_upcoming_dividends()
    recent_splits = get_recent_splits()

    macro = get_macro_data()
    cycle = get_economic_cycle()

    return render_template(
        "dashboard.html",
        stock_data=stock_data,
        upcoming_divs=upcoming_divs,
        recent_splits=recent_splits,
        macro=macro,
        cycle=cycle,
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
