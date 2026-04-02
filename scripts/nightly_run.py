"""Nightly orchestrator: fetch data → run signals → generate AI summaries → send alerts."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.fetch_prices import run_nightly_fetch
from signals.evaluator import run_signal_engine
from ai.summarizer import generate_signal_summary
from alerts.email_alert import send_signal_alert
from alerts.push_alert import send_signal_push
from db.init_db import get_connection


def run():
    print("=" * 50)
    print("ASX Stock Picker — Nightly Run")
    print("=" * 50)

    # Step 1: Fetch price data
    print("\n--- Step 1: Fetching price data ---")
    run_nightly_fetch()

    # Step 2: Run signal engine
    print("\n--- Step 2: Evaluating signals ---")
    fired_signals = run_signal_engine()

    if not fired_signals:
        print("\nNo signals to process. Done.")
        return

    # Step 3: Generate AI summaries and send alerts
    print(f"\n--- Step 3: Processing {len(fired_signals)} signal(s) ---")

    conn = get_connection()
    for sig in fired_signals:
        ticker = sig["ticker"]
        signal_name = sig["signal_name"]
        indicators = sig["indicators"]

        # Get stock name
        stock = conn.execute(
            "SELECT name FROM stocks WHERE ticker=?", (ticker,)
        ).fetchone()
        stock_name = stock["name"] if stock else ticker

        # Generate AI summary
        print(f"\n  Generating AI summary for {ticker} — {signal_name}...")
        summary = generate_signal_summary(ticker, signal_name, indicators, stock_name)

        # Update signal record with AI summary
        conn.execute(
            """UPDATE signals SET ai_summary=?, delivered=1
               WHERE ticker=? AND signal_name=? AND date=date('now') AND delivered=0""",
            (summary, ticker, signal_name),
        )

        # Send alerts
        send_signal_alert(ticker, signal_name, summary, indicators)
        send_signal_push(
            ticker, signal_name,
            indicators.get("current_price", 0),
            indicators.get("rsi"),
        )

    conn.commit()
    conn.close()

    print("\n" + "=" * 50)
    print("Nightly run complete.")
    print("=" * 50)


if __name__ == "__main__":
    run()
