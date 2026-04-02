"""Build and send the daily morning digest."""

from db.init_db import get_connection
from data.corporate_actions import get_upcoming_dividends, get_recent_splits
from alerts.email_alert import send_daily_digest


def build_watchlist_summary() -> str:
    """Build a text summary of watchlist stocks with active signals."""
    conn = get_connection()
    stocks = conn.execute(
        """SELECT s.ticker, s.name, s.sector,
                  (SELECT sig.signal_name FROM signals sig
                   WHERE sig.ticker = s.ticker
                   ORDER BY sig.created_at DESC LIMIT 1) as last_signal
           FROM stocks s WHERE s.active = 1
           ORDER BY s.sector, s.ticker""",
    ).fetchall()
    conn.close()

    lines = []
    for s in stocks:
        signal_note = f" ← {s['last_signal']}" if s["last_signal"] else ""
        lines.append(f"  {s['ticker']:10} {s['name']:25} [{s['sector']}]{signal_note}")

    return "\n".join(lines) if lines else "  No stocks in watchlist."


def build_positions_summary() -> str:
    """Build a text summary of open positions from trade journal."""
    conn = get_connection()
    open_trades = conn.execute(
        """SELECT ticker, direction, entry_date, entry_price, quantity
           FROM trades WHERE exit_date IS NULL
           ORDER BY entry_date DESC""",
    ).fetchall()
    conn.close()

    if not open_trades:
        return "  No open positions."

    lines = []
    for t in open_trades:
        lines.append(
            f"  {t['ticker']:10} {t['direction']:4} {t['quantity']} @ ${t['entry_price']:.2f} (entered {t['entry_date']})"
        )
    return "\n".join(lines)


def build_corporate_actions_summary() -> str:
    """Build a text summary of upcoming dividends and recent splits."""
    divs = get_upcoming_dividends(days_ahead=14)
    splits = get_recent_splits(days_back=30)

    lines = []
    for d in divs:
        lines.append(f"  {d['ticker']:10} Dividend ${d['value']:.4f} on {d['date']}")
    for s in splits:
        lines.append(f"  {s['ticker']:10} Split {s.get('raw_ratio', s['value'])} on {s['date']}")

    return "\n".join(lines) if lines else "  None upcoming."


def run_daily_digest():
    """Build and send the daily digest."""
    print("Building daily digest...")
    watchlist = build_watchlist_summary()
    positions = build_positions_summary()
    actions = build_corporate_actions_summary()
    send_daily_digest(watchlist, positions, actions)
    print("Daily digest complete.")


if __name__ == "__main__":
    run_daily_digest()
