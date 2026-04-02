# ASX Stock Picker

Personal AI-assisted ASX trading companion for learning active trading. Built to build intuition — not just returns.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up environment
cp .env.example .env
# Edit .env with your API keys

# 3. Initialize database and seed watchlist
python db/init_db.py

# 4. Run first data fetch
python data/fetch_prices.py

# 5. Run signal engine
python signals/evaluator.py

# 6. Start dashboard
python web/app.py
# Open http://localhost:5000
```

## Nightly Run

The nightly orchestrator runs the full pipeline: fetch → signals → AI summaries → alerts.

```bash
python scripts/nightly_run.py
```

Schedule this to run after ASX market close (4:00 PM AEST).

## Project Structure

```
stockpicker/
├── config.py              # All settings and defaults
├── db/                    # SQLite schema and database init
├── data/                  # yfinance fetch, SnapTrade sync, corporate actions
├── signals/               # Technical indicators, conditions, evaluator
├── ai/                    # Claude API signal summaries
├── alerts/                # Email (Resend) and push (Pushover) alerts
├── journal/               # Trade journal CRUD
├── web/                   # Flask dashboard
├── scripts/               # Nightly orchestrator
└── tests/                 # Test suite
```

## Data Sources

| Source | Purpose | Cost |
|--------|---------|------|
| yfinance | ASX EOD prices, dividends, splits | Free |
| SnapTrade | CommSec portfolio (read-only) | Free tier |
| TradingView | Visual charting (linked, not integrated) | Free |
| Claude API | AI signal summaries | ~A$1/mo |

## Tech Stack

Python 3.11 · Flask · SQLite · pandas-ta · yfinance · Anthropic SDK · Resend · Pushover
