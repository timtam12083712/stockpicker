"""Fetch and cache daily FX rates for currency conversion.

Uses yfinance for GBP/AUD and USD/AUD rates (free, no API key needed).
Falls back to cached rates if fetch fails.
"""

from datetime import date
import yfinance as yf
from db.init_db import get_connection


def fetch_fx_rates():
    """Fetch current GBP/AUD and USD/AUD rates from yfinance."""
    rates = {}

    try:
        gbp_aud = yf.Ticker("GBPAUD=X")
        rates["gbp_aud"] = gbp_aud.fast_info.last_price
    except Exception:
        rates["gbp_aud"] = None

    try:
        usd_aud = yf.Ticker("AUDUSD=X")
        # yfinance gives AUD/USD, we need USD/AUD (inverse)
        aud_usd = usd_aud.fast_info.last_price
        rates["usd_aud"] = round(1 / aud_usd, 6) if aud_usd else None
    except Exception:
        rates["usd_aud"] = None

    return rates


def get_fx_rates(target_date=None):
    """Get FX rates for a date, fetching if needed.

    Returns dict with 'gbp_aud' and 'usd_aud' keys.
    """
    if target_date is None:
        target_date = date.today().isoformat()

    conn = get_connection()

    # Check cache first
    row = conn.execute(
        "SELECT gbp_aud, usd_aud FROM fx_rates WHERE date=?", (target_date,)
    ).fetchone()

    if row and row["gbp_aud"] and row["usd_aud"]:
        conn.close()
        return {"gbp_aud": row["gbp_aud"], "usd_aud": row["usd_aud"]}

    # Fetch fresh rates
    rates = fetch_fx_rates()

    if rates.get("gbp_aud") and rates.get("usd_aud"):
        conn.execute(
            """INSERT OR REPLACE INTO fx_rates (date, gbp_aud, usd_aud, source)
               VALUES (?, ?, ?, 'yfinance')""",
            (target_date, rates["gbp_aud"], rates["usd_aud"]),
        )
        conn.commit()

    conn.close()

    # If fetch failed, try most recent cached rate
    if not rates.get("gbp_aud") or not rates.get("usd_aud"):
        conn = get_connection()
        row = conn.execute(
            "SELECT gbp_aud, usd_aud FROM fx_rates ORDER BY date DESC LIMIT 1"
        ).fetchone()
        conn.close()
        if row:
            rates["gbp_aud"] = rates.get("gbp_aud") or row["gbp_aud"]
            rates["usd_aud"] = rates.get("usd_aud") or row["usd_aud"]

    return rates


def convert_to_aud(amount, currency, rates=None):
    """Convert an amount to AUD using current rates."""
    if currency == "AUD":
        return amount
    if rates is None:
        rates = get_fx_rates()
    if currency == "GBP" and rates.get("gbp_aud"):
        return round(amount * rates["gbp_aud"], 2)
    if currency == "USD" and rates.get("usd_aud"):
        return round(amount * rates["usd_aud"], 2)
    return amount  # Fallback: return unconverted
