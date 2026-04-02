"""Send push notifications via Pushover."""

import requests

from config import Config

PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"


def send_push_notification(title: str, message: str):
    """Send a push notification via Pushover."""
    if not Config.PUSHOVER_USER_KEY or not Config.PUSHOVER_API_TOKEN:
        print(f"  Push skipped — Pushover not configured. {title}")
        return

    resp = requests.post(
        PUSHOVER_API_URL,
        data={
            "token": Config.PUSHOVER_API_TOKEN,
            "user": Config.PUSHOVER_USER_KEY,
            "title": title,
            "message": message,
        },
    )

    if resp.status_code == 200:
        print(f"  Push sent: {title}")
    else:
        print(f"  Push failed ({resp.status_code}): {resp.text}")


def send_signal_push(ticker: str, signal_name: str, price: float, rsi: float | None):
    """Send a one-liner push notification for a signal."""
    title = f"{ticker}: {signal_name}"
    msg = f"${price}"
    if rsi is not None:
        msg += f" | RSI: {rsi}"
    send_push_notification(title, msg)
