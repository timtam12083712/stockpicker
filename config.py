import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Database
    DATABASE_PATH = os.getenv("DATABASE_PATH", "db/stockpicker.db")

    # API Keys
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    SNAPTRADE_CLIENT_ID = os.getenv("SNAPTRADE_CLIENT_ID")
    SNAPTRADE_CLIENT_SECRET = os.getenv("SNAPTRADE_CLIENT_SECRET")
    SNAPTRADE_USER_ID = os.getenv("SNAPTRADE_USER_ID")
    SNAPTRADE_USER_SECRET = os.getenv("SNAPTRADE_USER_SECRET")
    RESEND_API_KEY = os.getenv("RESEND_API_KEY")
    PUSHOVER_USER_KEY = os.getenv("PUSHOVER_USER_KEY")
    PUSHOVER_API_TOKEN = os.getenv("PUSHOVER_API_TOKEN")

    # Alert recipients
    ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO")
    ALERT_EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM", "alerts@stockpicker.local")

    # Flask
    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

    # Watchlist limits
    MAX_WATCHLIST_STOCKS = 20

    # Signal defaults
    RSI_PERIOD = 14
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    SMA_SHORT = 50
    SMA_LONG = 200
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9
    BB_PERIOD = 20
    BB_STD = 2
    VOLUME_SPIKE_MULTIPLIER = 2.0
    NEAR_52W_LOW_PCT = 0.05
    NEAR_52W_HIGH_PCT = 0.03

    # Data fetch
    HISTORY_PERIOD_DAYS = 365
    SEED_HISTORY_DAYS = 730
    FETCH_DELAY_SECONDS = 1.0
    SPLIT_REFETCH_DAYS = 60

    # Claude model
    CLAUDE_MODEL = "claude-sonnet-4-6"

    # yfinance ASX suffix
    ASX_SUFFIX = ".AX"
