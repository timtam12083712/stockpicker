"""Fetch crypto holdings from Swyftx (read-only API).

Uses the Swyftx REST API with a read-only bearer token.
All values returned in AUD — no currency conversion needed.
"""

import os
import requests
from datetime import date

from db.init_db import get_connection


SWYFTX_BASE = "https://api.swyftx.com.au"


def _get_headers():
    """Get auth headers for Swyftx API."""
    key = os.getenv("SWYFTX_API_KEY")
    if not key:
        return None
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def sync_swyftx(account_id):
    """Fetch all holdings from Swyftx and store in holdings table.

    Returns True on success, False on failure.
    """
    headers = _get_headers()
    if not headers:
        print("Swyftx API key not set. Add SWYFTX_API_KEY to .env")
        return False

    conn = get_connection()
    account = conn.execute(
        "SELECT * FROM broker_accounts WHERE id=? AND active=1", (account_id,)
    ).fetchone()
    if not account:
        print(f"Account {account_id} not found")
        conn.close()
        return False

    try:
        # Fetch asset info (names, prices)
        r_assets = requests.get(f"{SWYFTX_BASE}/markets/info/basic/", headers=headers, timeout=15)
        r_assets.raise_for_status()
        asset_map = {}
        for a in r_assets.json():
            asset_map[str(a["id"])] = {
                "name": a.get("name", ""),
                "code": a.get("code", ""),
                "price_aud": float(a.get("sell", 0) or 0),  # Use sell price (what you'd get)
            }

        # Fetch balances
        r_bal = requests.get(f"{SWYFTX_BASE}/user/balance/", headers=headers, timeout=15)
        r_bal.raise_for_status()
        balances = r_bal.json()

        # Clear existing holdings for this account
        conn.execute("DELETE FROM holdings WHERE account_id=?", (account_id,))

        position_count = 0
        for item in balances:
            qty = float(item.get("availableBalance", 0))
            if qty <= 0:
                continue

            aid = str(item.get("assetId"))
            asset = asset_map.get(aid, {})
            code = asset.get("code", f"ASSET_{aid}")
            name = asset.get("name", code)
            price = asset.get("price_aud", 0)

            # Asset ID 1 is AUD cash — skip or show as cash
            if aid == "1":
                code = "AUD"
                name = "Australian Dollar (Cash)"
                price = 1.0

            value = round(qty * price, 2)

            conn.execute(
                """INSERT INTO holdings
                   (account_id, symbol, name, asset_class, quantity,
                    avg_cost_native, current_price_native, current_price_aud,
                    market_value_native, market_value_aud,
                    unrealised_pnl_native, unrealised_pnl_aud, unrealised_pnl_pct,
                    sector, geography)
                   VALUES (?, ?, ?, 'crypto', ?, NULL, ?, ?, ?, ?, NULL, NULL, NULL, 'Crypto', 'AUS')""",
                (account_id, code, name, qty, price, price, value, value),
            )
            position_count += 1

        # Update last sync
        conn.execute(
            "UPDATE broker_accounts SET last_sync=datetime('now') WHERE id=?",
            (account_id,),
        )
        conn.commit()
        conn.close()
        print(f"Synced Swyftx: {position_count} assets")
        return True

    except Exception as e:
        conn.close()
        print(f"Swyftx sync failed: {e}")
        import traceback
        traceback.print_exc()
        return False
