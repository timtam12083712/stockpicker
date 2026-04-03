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

-- ===== Phase 2: Multi-broker portfolio =====

CREATE TABLE IF NOT EXISTS broker_accounts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    broker_name     TEXT NOT NULL CHECK (broker_name IN ('commsec', 'ajbell', 'swyftx', 'etoro')),
    account_label   TEXT NOT NULL,          -- User-friendly name e.g. 'CommSec Main'
    currency        TEXT NOT NULL DEFAULT 'AUD' CHECK (currency IN ('AUD', 'GBP', 'USD')),
    connection_type TEXT NOT NULL CHECK (connection_type IN ('snaptrade', 'api', 'csv')),
    snaptrade_user_id TEXT,                 -- SnapTrade user ID (for snaptrade connections)
    snaptrade_user_secret TEXT,             -- SnapTrade user secret
    snaptrade_account_id TEXT,              -- SnapTrade brokerage account ID
    api_key_ref     TEXT,                   -- Reference name for API key env var (not the key itself)
    last_sync       DATETIME,
    active          BOOLEAN NOT NULL DEFAULT 1,
    created_at      DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS holdings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id      INTEGER NOT NULL REFERENCES broker_accounts(id),
    symbol          TEXT NOT NULL,          -- Ticker or crypto symbol e.g. BHP.AX / BTC
    name            TEXT,                   -- Full company or coin name
    asset_class     TEXT DEFAULT 'stock' CHECK (asset_class IN ('stock', 'crypto', 'etf', 'cfd', 'other')),
    quantity        REAL NOT NULL,
    avg_cost_native REAL,                   -- Average purchase price in account currency
    current_price_native REAL,              -- Latest price in account currency
    current_price_aud REAL,                 -- Converted to AUD at today's rate
    market_value_native REAL,               -- quantity * current_price_native
    market_value_aud REAL,                  -- quantity * current_price_aud
    unrealised_pnl_native REAL,
    unrealised_pnl_aud REAL,
    unrealised_pnl_pct REAL,
    sector          TEXT,
    geography       TEXT DEFAULT 'AUS' CHECK (geography IN ('AUS', 'GBR', 'USA', 'OTHER')),
    synced_at       DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS fx_rates (
    date            DATE PRIMARY KEY,
    gbp_aud         REAL,                   -- 1 GBP = X AUD
    usd_aud         REAL,                   -- 1 USD = X AUD
    source          TEXT DEFAULT 'yfinance',
    fetched_at      DATETIME NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS broker_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            DATE NOT NULL,
    account_id      INTEGER NOT NULL REFERENCES broker_accounts(id),
    total_value_native REAL,
    total_value_aud REAL,
    total_cost_basis_aud REAL,
    total_pnl_aud   REAL,
    fx_rate_used    REAL,
    UNIQUE(date, account_id)
);

CREATE TABLE IF NOT EXISTS etoro_imports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    filename        TEXT NOT NULL,
    import_date     DATETIME NOT NULL DEFAULT (datetime('now')),
    rows_imported   INTEGER DEFAULT 0,
    date_range_from DATE,
    date_range_to   DATE,
    status          TEXT DEFAULT 'success' CHECK (status IN ('success', 'partial', 'error'))
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_prices_ticker_date ON prices(ticker, date);
CREATE INDEX IF NOT EXISTS idx_signals_ticker_date ON signals(ticker, date);
CREATE INDEX IF NOT EXISTS idx_signals_delivered ON signals(delivered);
CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker);
CREATE INDEX IF NOT EXISTS idx_corporate_actions_ticker ON corporate_actions(ticker, date);
CREATE INDEX IF NOT EXISTS idx_holdings_account ON holdings(account_id);
CREATE INDEX IF NOT EXISTS idx_broker_snapshots_date ON broker_snapshots(date, account_id);
