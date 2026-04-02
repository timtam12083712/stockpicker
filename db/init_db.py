"""Initialize the SQLite database from schema.sql."""

import os
import sqlite3
from pathlib import Path

from config import Config


def get_db_path() -> str:
    """Return absolute path to the database file."""
    base_dir = Path(__file__).resolve().parent.parent
    return str(base_dir / Config.DATABASE_PATH)


def get_connection() -> sqlite3.Connection:
    """Return a database connection with row factory enabled."""
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables from schema.sql."""
    schema_path = Path(__file__).resolve().parent / "schema.sql"
    with open(schema_path) as f:
        schema_sql = f.read()

    conn = get_connection()
    conn.executescript(schema_sql)
    conn.close()
    print(f"Database initialized at {get_db_path()}")


def seed_watchlist():
    """Seed the starter watchlist from the spec."""
    starters = [
        ("BHP.AX", "BHP Group", "Mining", "Iron ore bellwether, regular dividends"),
        ("RIO.AX", "Rio Tinto", "Mining", "Major miner, BHP comparison"),
        ("CBA.AX", "Commonwealth Bank", "Financials", "Largest bank, dividend-heavy"),
        ("WBC.AX", "Westpac", "Financials", "Second major bank, CBA comparison"),
        ("CSL.AX", "CSL Limited", "Healthcare", "Premier growth stock, no dividend"),
        ("WES.AX", "Wesfarmers", "Consumer", "Bunnings/Kmart, defensive, regular dividends"),
        ("WOW.AX", "Woolworths", "Consumer", "Defensive consumer staple"),
        ("REA.AX", "REA Group", "Technology", "Property tech, growth-oriented"),
        ("WDS.AX", "Woodside Energy", "Energy", "LNG exposure, commodity sensitive"),
        ("QAN.AX", "Qantas Airways", "Industrials", "Cyclical, sentiment-sensitive"),
        ("GMG.AX", "Goodman Group", "Property", "Data centre and logistics REIT"),
        ("FMG.AX", "Fortescue", "Mining", "Pure iron ore, higher volatility"),
    ]
    conn = get_connection()
    conn.executemany(
        "INSERT OR IGNORE INTO stocks (ticker, name, sector, user_note) VALUES (?, ?, ?, ?)",
        starters,
    )
    conn.commit()
    conn.close()
    print(f"Seeded {len(starters)} stocks into watchlist")


if __name__ == "__main__":
    init_db()
    seed_watchlist()
