-- ASX Stock Picker — SQLite Schema

CREATE TABLE IF NOT EXISTS stocks (
    ticker      TEXT PRIMARY KEY,       -- e.g. BHP.AX
    name        TEXT NOT NULL,          -- e.g. BHP Group
    sector      TEXT,                   -- e.g. Mining
    user_note   TEXT,                   -- Personal note about why watching
    added_date  DATE NOT NULL DEFAULT (date('now')),
    active      BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS prices (
    ticker      TEXT NOT NULL REFERENCES stocks(ticker),
    date        DATE NOT NULL,
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL,
    adj_close   REAL,                   -- Use this for all indicator calculations
    volume      INTEGER,
    fetched_at  DATETIME NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (ticker, date)
);

CREATE TABLE IF NOT EXISTS corporate_actions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      TEXT NOT NULL REFERENCES stocks(ticker),
    action_type TEXT NOT NULL CHECK (action_type IN ('dividend', 'split')),
    date        DATE NOT NULL,
    value       REAL NOT NULL,          -- Dividend amount or split ratio
    raw_ratio   TEXT,                   -- For splits: e.g. '2:1'
    detected_at DATETIME NOT NULL DEFAULT (datetime('now')),
    UNIQUE (ticker, action_type, date)
);

CREATE TABLE IF NOT EXISTS signals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT NOT NULL REFERENCES stocks(ticker),
    date            DATE NOT NULL,
    signal_name     TEXT NOT NULL,
    signal_type     TEXT,               -- 'entry', 'exit', 'bullish', 'bearish', 'attention'
    indicator_values TEXT,              -- JSON blob of indicator values at signal time
    ai_summary      TEXT,
    delivered       BOOLEAN NOT NULL DEFAULT 0,
    created_at      DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT NOT NULL REFERENCES stocks(ticker),
    direction       TEXT NOT NULL CHECK (direction IN ('buy', 'sell')),
    entry_date      DATETIME NOT NULL,
    entry_price     REAL NOT NULL,
    quantity         INTEGER NOT NULL,
    brokerage_entry REAL DEFAULT 0,
    signals_at_entry TEXT,             -- JSON array of signal names active at entry
    entry_reasoning TEXT,              -- Free text, max ~200 words
    indicators_at_entry TEXT,          -- JSON: RSI, 50MA, 200MA, etc.
    corporate_action_note TEXT,
    target_exit_price REAL,
    stop_loss_price REAL,
    -- Exit fields (NULL until trade is closed)
    exit_date       DATETIME,
    exit_price      REAL,
    exit_reason     TEXT,
    signals_at_exit TEXT,
    brokerage_exit  REAL DEFAULT 0,
    dividends_received REAL DEFAULT 0,
    pnl_excl_brokerage REAL,          -- Auto-calculated on exit
    pnl_incl_brokerage REAL,          -- Auto-calculated on exit
    total_return    REAL,              -- P&L + dividends
    lessons_learned TEXT,
    signal_accuracy TEXT CHECK (signal_accuracy IN ('yes', 'no', 'partially', NULL)),
    created_at      DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS price_alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      TEXT NOT NULL REFERENCES stocks(ticker),
    target_price REAL NOT NULL,
    direction   TEXT NOT NULL CHECK (direction IN ('above', 'below')),
    triggered   BOOLEAN NOT NULL DEFAULT 0,
    triggered_at DATETIME,
    created_at  DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS portfolio_snapshot (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        DATE NOT NULL,
    ticker      TEXT NOT NULL REFERENCES stocks(ticker),
    quantity    INTEGER,
    avg_cost    REAL,
    current_price REAL,
    current_value REAL,
    unrealised_pnl REAL,
    unrealised_pnl_pct REAL,
    fetched_at  DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS signal_config (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      TEXT,                   -- NULL = global setting
    signal_name TEXT NOT NULL,
    enabled     BOOLEAN NOT NULL DEFAULT 1,
    UNIQUE (ticker, signal_name)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_prices_ticker_date ON prices(ticker, date);
CREATE INDEX IF NOT EXISTS idx_signals_ticker_date ON signals(ticker, date);
CREATE INDEX IF NOT EXISTS idx_signals_delivered ON signals(delivered);
CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker);
CREATE INDEX IF NOT EXISTS idx_corporate_actions_ticker ON corporate_actions(ticker, date);
