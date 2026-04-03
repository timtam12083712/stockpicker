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


def _init_cycle_table():
    """Create cycle_history table if it doesn't exist."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cycle_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            phase TEXT NOT NULL,
            label TEXT NOT NULL,
            score INTEGER NOT NULL,
            description TEXT,
            sectors TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date)
        )
    """)
    conn.commit()
    conn.close()


def _save_cycle_snapshot(cycle):
    """Persist today's cycle phase if not already saved."""
    if not cycle:
        return
    _init_cycle_table()
    today = date.today().isoformat()
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO cycle_history (date, phase, label, score, description, sectors)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (today, cycle["phase"], cycle["label"], cycle["score"],
         cycle["description"], json.dumps(cycle["sectors"])),
    )
    conn.commit()
    conn.close()


def _get_cycle_history(limit=90):
    """Retrieve recent cycle history."""
    _init_cycle_table()
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM cycle_history ORDER BY date DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


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

        # All-time prices for sparkline
        all_prices = conn.execute(
            "SELECT adj_close FROM prices WHERE ticker=? ORDER BY date",
            (ticker,),
        ).fetchall()
        sparkline_svg = make_sparkline([r["adj_close"] for r in all_prices])

        # All-time change %
        alltime_change = None
        if len(all_prices) >= 2:
            first, last = all_prices[0]["adj_close"], all_prices[-1]["adj_close"]
            if first:
                alltime_change = round((last - first) / first * 100, 1)

        # Get recent signals, deduplicated by signal_name (keep latest)
        recent_signals = conn.execute(
            """SELECT signal_name, signal_type, indicator_values, ai_summary
               FROM signals WHERE ticker=?
               GROUP BY signal_name
               HAVING created_at = MAX(created_at)
               ORDER BY created_at DESC LIMIT 5""",
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
            "alltime_change": alltime_change,
        })

    conn.close()

    upcoming_divs = get_upcoming_dividends()
    recent_splits = get_recent_splits()

    macro = get_macro_data()
    cycle = get_economic_cycle()

    # Score macro conditions for each stock's sector
    from signals.macro_sensitivity import score_macro_conditions
    for item in stock_data:
        sector = item["stock"].get("sector", "")
        item["conditions"] = score_macro_conditions(sector, macro, cycle)

    return render_template(
        "dashboard.html",
        stock_data=stock_data,
        upcoming_divs=upcoming_divs,
        recent_splits=recent_splits,
        macro=macro,
        cycle=cycle,
    )


@app.route("/stock/<ticker>")
def stock_detail(ticker):
    """Stock detail page — products, drivers, macro sensitivities."""
    if not ticker.endswith(".AX"):
        ticker_full = ticker + ".AX"
    else:
        ticker_full = ticker
        ticker = ticker.replace(".AX", "")

    conn = get_connection()
    stock = conn.execute("SELECT * FROM stocks WHERE ticker=?", (ticker_full,)).fetchone()
    conn.close()
    if not stock:
        flash(f"Stock {ticker} not found.")
        return redirect(url_for("dashboard"))

    stock = dict(stock)

    # Get yfinance info for business summary
    try:
        t = yf.Ticker(ticker_full)
        info = t.info or {}
    except Exception:
        info = {}

    # Get sector profile
    from signals.macro_sensitivity import get_sector_profile, score_macro_conditions
    sector = info.get("sector", stock.get("sector", ""))
    profile = get_sector_profile(sector)

    # Score current conditions
    macro = get_macro_data()
    cycle = get_economic_cycle()
    conditions = score_macro_conditions(sector, macro, cycle)

    # Get fundamental signal card
    from signals.fundamentals import generate_signal_card
    signal_card = generate_signal_card(ticker_full)

    return render_template(
        "stock_detail.html",
        stock=stock,
        ticker=ticker,
        ticker_full=ticker_full,
        info=info,
        profile=profile,
        conditions=conditions,
        cycle=cycle,
        signal_card=signal_card,
    )


@app.route("/signals")
def signals():
    """Fundamental signals page — signal cards for each watchlist stock."""
    conn = get_connection()
    stocks = conn.execute(
        "SELECT ticker FROM stocks WHERE active=1 ORDER BY sector, ticker"
    ).fetchall()
    conn.close()

    tickers = [s["ticker"] for s in stocks]

    from signals.fundamentals import generate_all_signal_cards
    cards = generate_all_signal_cards(tickers)

    # Sort: buy candidates first, then watchlist, then avoid
    action_order = {"buy_candidate": 0, "watchlist": 1, "avoid": 2}
    cards.sort(key=lambda c: action_order.get(c["action"], 1))

    return render_template("signals.html", cards=cards)


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
    """Unified multi-broker portfolio view."""
    conn = get_connection()

    # Get all active broker accounts
    accounts = conn.execute(
        "SELECT * FROM broker_accounts WHERE active=1 ORDER BY broker_name"
    ).fetchall()
    accounts = [dict(a) for a in accounts]

    # Get holdings per account
    all_holdings = []
    broker_totals = []
    total_value_aud = 0
    total_pnl_aud = 0
    total_cost_aud = 0

    for acc in accounts:
        holdings = conn.execute(
            "SELECT * FROM holdings WHERE account_id=? ORDER BY market_value_aud DESC",
            (acc["id"],),
        ).fetchall()
        holdings = [dict(h) for h in holdings]

        acc_value = sum(h["market_value_aud"] or 0 for h in holdings)
        acc_pnl = sum(h["unrealised_pnl_aud"] or 0 for h in holdings)
        acc_cost = sum(
            (h["quantity"] or 0) * (h["avg_cost_native"] or 0)
            for h in holdings if h["avg_cost_native"]
        )

        broker_totals.append({
            "account": acc,
            "holdings": holdings,
            "total_value_aud": round(acc_value, 2),
            "total_pnl_aud": round(acc_pnl, 2),
            "holding_count": len(holdings),
        })

        total_value_aud += acc_value
        total_pnl_aud += acc_pnl
        all_holdings.extend(holdings)

    # Calculate total cost basis in AUD
    for acc_data in broker_totals:
        acc = acc_data["account"]
        from data.fx_rates import convert_to_aud
        for h in acc_data["holdings"]:
            if h["avg_cost_native"] and h["quantity"]:
                total_cost_aud += convert_to_aud(
                    h["quantity"] * h["avg_cost_native"],
                    acc["currency"]
                )

    total_pnl_pct = round((total_value_aud / total_cost_aud - 1) * 100, 1) if total_cost_aud > 0 else 0

    # Sector allocation
    sector_alloc = {}
    for h in all_holdings:
        sector = h.get("sector") or "Unknown"
        sector_alloc[sector] = sector_alloc.get(sector, 0) + (h["market_value_aud"] or 0)

    # Geography allocation
    geo_alloc = {}
    for h in all_holdings:
        geo = h.get("geography") or "OTHER"
        geo_alloc[geo] = geo_alloc.get(geo, 0) + (h["market_value_aud"] or 0)

    # Currency exposure
    currency_alloc = {}
    for acc_data in broker_totals:
        curr = acc_data["account"]["currency"]
        currency_alloc[curr] = currency_alloc.get(curr, 0) + acc_data["total_value_aud"]

    # FX rates for display
    from data.fx_rates import get_fx_rates, convert_to_aud
    fx = get_fx_rates()

    # Cash holdings
    cash_rows = conn.execute("SELECT * FROM cash_holdings ORDER BY currency, label").fetchall()
    cash_holdings = [dict(r) for r in cash_rows]

    total_cash_aud = 0
    for c in cash_holdings:
        c["amount_aud"] = convert_to_aud(c["amount"], c["currency"], fx)
        total_cash_aud += c["amount_aud"]
        # Add to currency allocation
        currency_alloc[c["currency"]] = currency_alloc.get(c["currency"], 0) + c["amount_aud"]

    total_value_aud += total_cash_aud

    # Recalculate P&L pct with cash included in total
    total_pnl_pct = round((total_pnl_aud / total_cost_aud) * 100, 1) if total_cost_aud > 0 else 0

    # Dual currency: convert everything to GBP as well
    gbp_rate = fx.get("gbp_aud", 1.0) or 1.0  # 1 GBP = X AUD
    aud_to_gbp = 1.0 / gbp_rate if gbp_rate else 1.0
    total_value_gbp = round(total_value_aud * aud_to_gbp, 2)
    total_pnl_gbp = round(total_pnl_aud * aud_to_gbp, 2)
    total_cost_gbp = round(total_cost_aud * aud_to_gbp, 2)
    total_cash_gbp = round(total_cash_aud * aud_to_gbp, 2)

    conn.close()

    return render_template(
        "portfolio.html",
        accounts=accounts,
        broker_totals=broker_totals,
        total_value_aud=round(total_value_aud, 2),
        total_value_gbp=total_value_gbp,
        total_pnl_aud=round(total_pnl_aud, 2),
        total_pnl_gbp=total_pnl_gbp,
        total_pnl_pct=total_pnl_pct,
        total_cost_aud=round(total_cost_aud, 2),
        total_cost_gbp=total_cost_gbp,
        total_cash_aud=round(total_cash_aud, 2),
        total_cash_gbp=total_cash_gbp,
        sector_alloc=sector_alloc,
        geo_alloc=geo_alloc,
        currency_alloc=currency_alloc,
        fx=fx,
        aud_to_gbp=aud_to_gbp,
        cash_holdings=cash_holdings,
        has_accounts=len(accounts) > 0 or len(cash_holdings) > 0,
    )


@app.route("/portfolio/sync")
def portfolio_sync():
    """Trigger a manual sync of all connected broker accounts."""
    from data.fetch_portfolio import sync_all_portfolios
    sync_all_portfolios()
    flash("Portfolio sync complete.")
    return redirect(url_for("portfolio"))


@app.route("/portfolio/add-broker", methods=["POST"])
def portfolio_add_broker():
    """Add a new broker account."""
    broker_name = request.form["broker_name"]
    account_label = request.form["account_label"]
    currency_map = {"commsec": "AUD", "ajbell": "GBP", "swyftx": "AUD", "etoro": "USD"}
    conn_map = {"commsec": "snaptrade", "ajbell": "snaptrade", "swyftx": "api", "etoro": "csv"}

    conn = get_connection()
    conn.execute(
        """INSERT INTO broker_accounts (broker_name, account_label, currency, connection_type)
           VALUES (?, ?, ?, ?)""",
        (broker_name, account_label, currency_map.get(broker_name, "AUD"), conn_map.get(broker_name, "csv")),
    )
    conn.commit()
    conn.close()
    flash(f"{account_label} added. Configure credentials in .env to connect.")
    return redirect(url_for("portfolio"))


@app.route("/portfolio/cash/add", methods=["POST"])
def portfolio_cash_add():
    """Add a cash holding."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO cash_holdings (label, currency, amount, notes) VALUES (?, ?, ?, ?)",
        (request.form["label"], request.form["currency"],
         float(request.form["amount"]), request.form.get("notes", "")),
    )
    conn.commit()
    conn.close()
    flash(f"Cash added: {request.form['label']}")
    return redirect(url_for("portfolio"))


@app.route("/portfolio/cash/delete/<int:cash_id>", methods=["POST"])
def portfolio_cash_delete(cash_id):
    """Delete a cash holding."""
    conn = get_connection()
    conn.execute("DELETE FROM cash_holdings WHERE id=?", (cash_id,))
    conn.commit()
    conn.close()
    flash("Cash entry removed.")
    return redirect(url_for("portfolio"))


@app.route("/portfolio/cash/edit/<int:cash_id>", methods=["POST"])
def portfolio_cash_edit(cash_id):
    """Update a cash holding."""
    conn = get_connection()
    conn.execute(
        "UPDATE cash_holdings SET label=?, currency=?, amount=?, notes=?, updated_at=datetime('now') WHERE id=?",
        (request.form["label"], request.form["currency"],
         float(request.form["amount"]), request.form.get("notes", ""), cash_id),
    )
    conn.commit()
    conn.close()
    flash("Cash entry updated.")
    return redirect(url_for("portfolio"))


@app.route("/ref")
def reference():
    """Reference hub — learning sections."""
    cycle = get_economic_cycle()
    return render_template("reference.html", cycle=cycle)


@app.route("/ref/indicators")
def ref_indicators():
    """Technical indicators and signals learning page."""
    return render_template("indicators.html")


@app.route("/ref/cycle")
def ref_cycle():
    """Economic cycle learning page — dynamic, shows current phase."""
    cycle = get_economic_cycle()
    _save_cycle_snapshot(cycle)
    history = _get_cycle_history()
    return render_template("cycle.html", cycle=cycle, phases=CYCLE_PHASES, history=history)


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
