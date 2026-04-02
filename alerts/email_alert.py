"""Send signal alerts and daily digest via Resend email."""

import resend

from config import Config


def send_signal_alert(ticker: str, signal_name: str, summary: str, indicators: dict):
    """Send a signal alert email."""
    if not Config.RESEND_API_KEY:
        print(f"  Email skipped — RESEND_API_KEY not set. Signal: {signal_name} for {ticker}")
        return

    resend.api_key = Config.RESEND_API_KEY

    subject = f"ASX Signal: {ticker} — {signal_name}"
    body = f"""{ticker} — {signal_name}

{summary}

Key indicators:
  Price: ${indicators.get('current_price', 'N/A')}
  RSI: {indicators.get('rsi', 'N/A')}
  50MA: ${indicators.get('sma_50', 'N/A')}
  200MA: ${indicators.get('sma_200', 'N/A')}
  Volume: {indicators.get('volume_ratio', 'N/A')}x avg

View on TradingView: https://www.tradingview.com/chart/?symbol=ASX:{ticker.replace('.AX', '')}
"""

    resend.Emails.send({
        "from": Config.ALERT_EMAIL_FROM,
        "to": Config.ALERT_EMAIL_TO,
        "subject": subject,
        "text": body,
    })
    print(f"  Email sent: {subject}")


def send_daily_digest(watchlist_summary: str, open_positions: str, corporate_actions: str):
    """Send the morning digest email."""
    if not Config.RESEND_API_KEY:
        print("  Digest email skipped — RESEND_API_KEY not set")
        return

    resend.api_key = Config.RESEND_API_KEY

    body = f"""ASX Stock Picker — Daily Digest

WATCHLIST OVERVIEW
{watchlist_summary}

OPEN POSITIONS
{open_positions}

UPCOMING CORPORATE ACTIONS (next 14 days)
{corporate_actions}
"""

    resend.Emails.send({
        "from": Config.ALERT_EMAIL_FROM,
        "to": Config.ALERT_EMAIL_TO,
        "subject": "ASX Daily Digest",
        "text": body,
    })
    print("  Daily digest email sent")
