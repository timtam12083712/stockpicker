"""Fetch portfolio holdings from brokers.

Supports:
- CommSec via SnapTrade (read-only)
- AJ Bell via SnapTrade (read-only, GBP → AUD conversion)
- Swyftx via direct API (read-only, crypto)
- eToro via CSV import (manual)
"""

from datetime import datetime, date

from config import Config
from db.init_db import get_connection
from data.fx_rates import get_fx_rates, convert_to_aud


# ──────────────────────────────────────────────
# SnapTrade (CommSec + AJ Bell)
# ──────────────────────────────────────────────

def _get_snaptrade_client():
    """Initialise the SnapTrade client.

    Note: SnapTrade SDK uses consumer_key for the secret and client_id for the ID.
    """
    if not Config.SNAPTRADE_CLIENT_ID or not Config.SNAPTRADE_CLIENT_SECRET:
        return None
    try:
        from snaptrade_client import SnapTrade
        return SnapTrade(
            consumer_key=Config.SNAPTRADE_CLIENT_SECRET,
            client_id=Config.SNAPTRADE_CLIENT_ID,
        )
    except Exception as e:
        print(f"SnapTrade client init failed: {e}")
        return None


def register_snaptrade_user(user_id):
    """Register a new user with SnapTrade. Run once during setup.

    Returns dict with 'userId' and 'userSecret'.
    """
    client = _get_snaptrade_client()
    if not client:
        print("SnapTrade not configured. Set SNAPTRADE_CLIENT_ID and SNAPTRADE_CLIENT_SECRET in .env")
        return None

    try:
        response = client.authentication.register_snap_trade_user(
            user_id=user_id,
        )
        data = response.body if hasattr(response, 'body') else response
        user_id_val = data.get("userId") or data.get("user_id") if isinstance(data, dict) else getattr(data, 'user_id', None)
        user_secret_val = data.get("userSecret") or data.get("user_secret") if isinstance(data, dict) else getattr(data, 'user_secret', None)
        print(f"SnapTrade user registered: {user_id_val}")
        return {"userId": user_id_val, "userSecret": user_secret_val}
    except Exception as e:
        print(f"SnapTrade user registration failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_snaptrade_login_url(account_id):
    """Get the SnapTrade redirect URL for connecting a brokerage.

    The user opens this URL in their browser to authenticate with their
    broker (CommSec, AJ Bell, etc.). Credentials go to SnapTrade, not us.
    """
    conn = get_connection()
    account = conn.execute(
        "SELECT * FROM broker_accounts WHERE id=? AND connection_type='snaptrade'",
        (account_id,)
    ).fetchone()
    conn.close()

    if not account:
        print(f"Account {account_id} not found or not a SnapTrade account")
        return None

    client = _get_snaptrade_client()
    if not client:
        return None

    try:
        response = client.authentication.login_snap_trade_user(
            user_id=account["snaptrade_user_id"],
            user_secret=account["snaptrade_user_secret"],
        )
        data = response.body if hasattr(response, 'body') else response
        url = data.get("redirectURI") or data.get("redirect_uri") if isinstance(data, dict) else getattr(data, 'redirect_uri', None)
        return url
    except Exception as e:
        print(f"SnapTrade login URL failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def sync_snaptrade_account(account_id):
    """Fetch holdings from a SnapTrade-connected brokerage account.

    Works for both CommSec (AUD) and AJ Bell (GBP).
    """
    conn = get_connection()
    account = conn.execute(
        "SELECT * FROM broker_accounts WHERE id=? AND connection_type='snaptrade' AND active=1",
        (account_id,)
    ).fetchone()

    if not account:
        print(f"Account {account_id} not found or inactive")
        conn.close()
        return False

    client = _get_snaptrade_client()
    if not client:
        conn.close()
        return False

    account = dict(account)
    currency = account["currency"]
    rates = get_fx_rates()

    try:
        # First, discover the SnapTrade brokerage account ID if we don't have it
        if not account.get("snaptrade_account_id"):
            acct_list = client.account_information.list_user_accounts(
                user_id=account["snaptrade_user_id"],
                user_secret=account["snaptrade_user_secret"],
            )
            # Response is a list of account objects
            accounts_data = acct_list.body if hasattr(acct_list, 'body') else acct_list
            if accounts_data:
                # Use first account if multiple; store the ID
                first_acct = accounts_data[0]
                st_acct_id = first_acct.get("id") or getattr(first_acct, 'id', None)
                if st_acct_id:
                    conn.execute(
                        "UPDATE broker_accounts SET snaptrade_account_id=? WHERE id=?",
                        (str(st_acct_id), account_id),
                    )
                    conn.commit()
                    account["snaptrade_account_id"] = str(st_acct_id)
                    print(f"  Discovered SnapTrade account ID: {st_acct_id}")

        # Fetch holdings for this specific account
        response = client.account_information.get_user_holdings(
            account_id=account["snaptrade_account_id"],
            user_id=account["snaptrade_user_id"],
            user_secret=account["snaptrade_user_secret"],
        )
        holdings_data = response.body if hasattr(response, 'body') else response

        # Clear existing holdings for this account
        conn.execute("DELETE FROM holdings WHERE account_id=?", (account_id,))

        # Extract positions list from response
        positions = []
        if isinstance(holdings_data, dict):
            positions = holdings_data.get("positions", [])
        elif isinstance(holdings_data, list):
            positions = holdings_data
        else:
            positions = getattr(holdings_data, 'positions', []) or []

        position_count = 0
        for position in positions:
                # Extract fields — handle both dict and object access
                # Parse position — SnapTrade returns deeply nested dicts
                pos = position if isinstance(position, dict) else dict(position)

                # Symbol is nested: position.symbol.symbol.symbol (yes, three levels)
                sym_outer = pos.get("symbol", {})
                if isinstance(sym_outer, dict):
                    sym_inner = sym_outer.get("symbol", {})
                    if isinstance(sym_inner, dict):
                        symbol = sym_inner.get("symbol", "") or sym_inner.get("raw_symbol", "")
                        name = sym_inner.get("description", symbol)
                    else:
                        symbol = str(sym_inner)
                        name = sym_outer.get("description", symbol)
                else:
                    symbol = str(sym_outer)
                    name = symbol

                qty = pos.get("units") or pos.get("quantity") or 0
                price_native = pos.get("price") or 0
                avg_cost = pos.get("average_purchase_price")

                if not symbol or qty == 0:
                    continue

                price_aud = convert_to_aud(price_native, currency, rates)
                value_native = qty * price_native
                value_aud = qty * price_aud

                pnl_native = None
                pnl_aud = None
                pnl_pct = None
                if avg_cost and avg_cost > 0 and qty > 0:
                    cost_native = qty * avg_cost
                    pnl_native = value_native - cost_native
                    pnl_aud = convert_to_aud(pnl_native, currency, rates)
                    pnl_pct = round((value_native / cost_native - 1) * 100, 2)

                geo = "AUS" if currency == "AUD" else "GBR" if currency == "GBP" else "USA"

                conn.execute(
                    """INSERT INTO holdings
                       (account_id, symbol, name, asset_class, quantity,
                        avg_cost_native, current_price_native, current_price_aud,
                        market_value_native, market_value_aud,
                        unrealised_pnl_native, unrealised_pnl_aud, unrealised_pnl_pct,
                        sector, geography)
                       VALUES (?, ?, ?, 'stock', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (account_id, symbol, name, qty,
                     avg_cost, price_native, price_aud,
                     round(value_native, 2), round(value_aud, 2),
                     round(pnl_native, 2) if pnl_native is not None else None,
                     round(pnl_aud, 2) if pnl_aud is not None else None,
                     pnl_pct,
                     None, geo),
                )
                position_count += 1

        # Update last sync time
        conn.execute(
            "UPDATE broker_accounts SET last_sync=datetime('now') WHERE id=?",
            (account_id,),
        )
        conn.commit()
        conn.close()
        print(f"Synced {account['account_label']}: {position_count} positions")
        return True

    except Exception as e:
        conn.close()
        print(f"SnapTrade sync failed for {account['account_label']}: {e}")
        import traceback
        traceback.print_exc()
        return False


def save_broker_snapshot(account_id):
    """Save a daily snapshot of total portfolio value for a broker account."""
    conn = get_connection()

    account = conn.execute(
        "SELECT currency FROM broker_accounts WHERE id=?", (account_id,)
    ).fetchone()
    if not account:
        conn.close()
        return

    rates = get_fx_rates()
    fx_rate = 1.0
    if account["currency"] == "GBP":
        fx_rate = rates.get("gbp_aud", 1.0)
    elif account["currency"] == "USD":
        fx_rate = rates.get("usd_aud", 1.0)

    totals = conn.execute(
        """SELECT
            COALESCE(SUM(market_value_native), 0) as total_native,
            COALESCE(SUM(market_value_aud), 0) as total_aud,
            COALESCE(SUM(CASE WHEN avg_cost_native IS NOT NULL
                THEN quantity * avg_cost_native ELSE 0 END), 0) as total_cost_native,
            COALESCE(SUM(unrealised_pnl_aud), 0) as total_pnl
           FROM holdings WHERE account_id=?""",
        (account_id,),
    ).fetchone()

    today = date.today().isoformat()
    cost_aud = convert_to_aud(totals["total_cost_native"], account["currency"], rates)

    conn.execute(
        """INSERT OR REPLACE INTO broker_snapshots
           (date, account_id, total_value_native, total_value_aud,
            total_cost_basis_aud, total_pnl_aud, fx_rate_used)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (today, account_id, totals["total_native"], totals["total_aud"],
         cost_aud, totals["total_pnl"], fx_rate),
    )
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# Sync all connected accounts
# ──────────────────────────────────────────────

def sync_all_portfolios():
    """Sync all active broker accounts."""
    conn = get_connection()
    accounts = conn.execute(
        "SELECT id, broker_name, account_label, connection_type FROM broker_accounts WHERE active=1"
    ).fetchall()
    conn.close()

    if not accounts:
        print("No broker accounts configured.")
        print("Use the Portfolio page to add CommSec or AJ Bell via SnapTrade.")
        return

    for acc in accounts:
        acc = dict(acc)
        print(f"Syncing {acc['account_label']} ({acc['broker_name']})...")

        if acc["connection_type"] == "snaptrade":
            success = sync_snaptrade_account(acc["id"])
            if success:
                save_broker_snapshot(acc["id"])
        elif acc["connection_type"] == "api" and acc["broker_name"] == "swyftx":
            from data.fetch_swyftx import sync_swyftx
            success = sync_swyftx(acc["id"])
            if success:
                save_broker_snapshot(acc["id"])
        elif acc["connection_type"] == "api":
            print(f"  API sync not yet implemented for {acc['broker_name']}")
        elif acc["connection_type"] == "csv":
            print(f"  CSV import — drop file in import folder for {acc['broker_name']}")


# ──────────────────────────────────────────────
# Setup helpers
# ──────────────────────────────────────────────

def add_broker_account(broker_name, account_label, currency, connection_type,
                       snaptrade_user_id=None, snaptrade_user_secret=None):
    """Add a new broker account to the database."""
    conn = get_connection()
    conn.execute(
        """INSERT INTO broker_accounts
           (broker_name, account_label, currency, connection_type,
            snaptrade_user_id, snaptrade_user_secret)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (broker_name, account_label, currency, connection_type,
         snaptrade_user_id, snaptrade_user_secret),
    )
    conn.commit()
    account_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    print(f"Added broker account: {account_label} (ID: {account_id})")
    return account_id


def setup_snaptrade_accounts(user_id="stockpicker_user"):
    """Interactive setup for SnapTrade broker connections.

    Run this once to:
    1. Register a SnapTrade user
    2. Create CommSec and AJ Bell account entries
    3. Get login URLs for broker authentication
    """
    # Step 1: Register user
    result = register_snaptrade_user(user_id)
    if not result:
        return

    st_user_id = result["userId"]
    st_user_secret = result["userSecret"]

    print(f"\nSnapTrade user registered.")
    print(f"User ID: {st_user_id}")
    print(f"User Secret: {st_user_secret}")
    print(f"\nSave these in your .env file:")
    print(f"  SNAPTRADE_USER_ID={st_user_id}")
    print(f"  SNAPTRADE_USER_SECRET={st_user_secret}")

    # Step 2: Create account entries
    commsec_id = add_broker_account(
        "commsec", "CommSec Main", "AUD", "snaptrade",
        st_user_id, st_user_secret,
    )
    ajbell_id = add_broker_account(
        "ajbell", "AJ Bell ISA", "GBP", "snaptrade",
        st_user_id, st_user_secret,
    )

    print(f"\nBroker accounts created:")
    print(f"  CommSec (ID: {commsec_id})")
    print(f"  AJ Bell (ID: {ajbell_id})")

    # Step 3: Get login URLs
    print(f"\nNext steps:")
    print(f"1. Open the SnapTrade connection portal to link your brokers")
    print(f"2. Use the Portfolio page in the app to connect each broker")
    print(f"3. After connecting, run sync to fetch your holdings")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        setup_snaptrade_accounts()
    else:
        sync_all_portfolios()
