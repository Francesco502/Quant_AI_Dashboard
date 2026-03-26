"""Account management routes (multi-user safe)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from api.auth import UserInDB, get_current_active_user
from core.account_manager import AccountManager
from core.database import get_database


router = APIRouter()
LEGACY_AUTO_ACCOUNT_NAME = "Auto Paper Trading"
DEFAULT_AUTO_ACCOUNT_NAME = "全市场自动模拟交易"


def _resolve_user_id(cursor, current_user: UserInDB) -> int:
    user_id = getattr(current_user, "id", None)
    if user_id is not None:
        return int(user_id)

    username = getattr(current_user, "username", None)
    if not username:
        raise HTTPException(status_code=401, detail="Unable to resolve current user")

    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    if not row or row["id"] is None:
        raise HTTPException(status_code=401, detail="User not found")
    return int(row["id"])


def _get_active_account_id(cursor, user_id: int) -> Optional[int]:
    cursor.execute(
        """
        SELECT id
        FROM accounts
        WHERE user_id = ? AND status = 'active'
        ORDER BY id ASC
        LIMIT 1
        """,
        (user_id,),
    )
    row = cursor.fetchone()
    return int(row["id"]) if row else None


def _normalize_account_name(name: Optional[str]) -> Optional[str]:
    if name is None:
        return None
    normalized = str(name).strip()
    if not normalized or normalized == LEGACY_AUTO_ACCOUNT_NAME:
        return DEFAULT_AUTO_ACCOUNT_NAME
    return normalized


@router.get("/paper")
async def get_paper_account(current_user: UserInDB = Depends(get_current_active_user)):
    try:
        db = get_database()
        cursor = db.conn.cursor()
        user_id = _resolve_user_id(cursor, current_user)
        account_mgr = AccountManager(db)

        cursor.execute(
            """
            SELECT id, account_name, balance, frozen, initial_capital,
                   (balance + frozen) as total_assets
            FROM accounts
            WHERE user_id = ? AND status = 'active'
            ORDER BY id ASC
            LIMIT 1
            """,
            (user_id,),
        )
        row = cursor.fetchone()

        if not row:
            return {
                "user_id": user_id,
                "account_id": None,
                "account_name": None,
                "balance": 0.0,
                "frozen": 0.0,
                "total_assets": 0.0,
                "initial_capital": 0.0,
                "positions": {},
                "equity_history": [],
            }

        account_id = int(row["id"])
        positions_list = account_mgr.get_positions(account_id, refresh_prices=True)
        positions = {}
        total_position_value = 0.0
        for position in positions_list:
            total_position_value += float(position.market_value or 0.0)
            positions[position.ticker] = {
                "shares": position.shares,
                "avg_cost": position.avg_cost,
                "market_value": float(position.market_value or 0.0),
                "unrealized_pnl": float(position.unrealized_pnl or 0.0),
            }

        return {
            "user_id": user_id,
            "account_id": account_id,
            "account_name": _normalize_account_name(row["account_name"]),
            "balance": row["balance"],
            "frozen": row["frozen"],
            "total_assets": float(row["balance"] or 0.0) + float(row["frozen"] or 0.0) + total_position_value,
            "initial_capital": row["initial_capital"],
            "positions": positions,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get account: {str(e)}")


@router.get("/paper/equity")
async def get_equity_history(
    days: int = 90,
    current_user: UserInDB = Depends(get_current_active_user),
):
    try:
        db = get_database()
        cursor = db.conn.cursor()
        user_id = _resolve_user_id(cursor, current_user)
        account_mgr = AccountManager(db)
        account_id = _get_active_account_id(cursor, user_id)

        if account_id is None:
            return {"equity_history": []}

        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        cursor.execute(
            """
            SELECT date, equity, cash, position_value
            FROM equity_history
            WHERE account_id = ? AND date >= ?
            ORDER BY date ASC
            """,
            (account_id, start_date),
        )

        return {
            "equity_history": [
                {
                    "date": r["date"],
                    "equity": r["equity"],
                    "cash": r["cash"],
                    "position_value": r["position_value"],
                }
                for r in cursor.fetchall()
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get equity history: {str(e)}")


@router.get("/paper/positions")
async def get_positions(current_user: UserInDB = Depends(get_current_active_user)):
    try:
        db = get_database()
        cursor = db.conn.cursor()
        user_id = _resolve_user_id(cursor, current_user)
        account_id = _get_active_account_id(cursor, user_id)
        account_mgr = AccountManager(db)

        if account_id is None:
            return {"positions": {}}

        positions = {}
        for position in account_mgr.get_positions(account_id, refresh_prices=True):
            positions[position.ticker] = {
                "shares": position.shares,
                "avg_cost": position.avg_cost,
                "market_value": float(position.market_value or 0.0),
                "unrealized_pnl": float(position.unrealized_pnl or 0.0),
            }

        return {"positions": positions}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get positions: {str(e)}")


@router.get("/paper/trades")
async def get_trade_log(
    limit: Optional[int] = None,
    current_user: UserInDB = Depends(get_current_active_user),
):
    try:
        db = get_database()
        cursor = db.conn.cursor()
        user_id = _resolve_user_id(cursor, current_user)
        account_id = _get_active_account_id(cursor, user_id)

        if account_id is None:
            return {"trades": [], "count": 0}

        query = """
            SELECT th.*, o.symbol, o.side, o.price, o.quantity
            FROM trade_history th
            LEFT JOIN orders o ON th.order_id = o.order_id
            WHERE th.account_id = ?
            ORDER BY th.trade_time DESC
        """
        params = [account_id]
        if limit is not None:
            query += " LIMIT ?"
            params.append(int(limit))

        cursor.execute(query, tuple(params))

        trades = []
        for r in cursor.fetchall():
            trades.append(
                {
                    "trade_id": r["id"],
                    "ticker": r["symbol"] or r["ticker"],
                    "action": r["side"] or r["action"],
                    "price": r["price"] or r["trade_price"],
                    "shares": r["quantity"] or r["shares"],
                    "trade_time": r["trade_time"],
                    "pnl": r["pnl"],
                }
            )

        return {"trades": trades, "count": len(trades)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get trades: {str(e)}")


@router.get("/list")
async def list_user_accounts(current_user: UserInDB = Depends(get_current_active_user)):
    try:
        db = get_database()
        cursor = db.conn.cursor()
        user_id = _resolve_user_id(cursor, current_user)

        cursor.execute(
            """
            SELECT id, account_name, balance, frozen, initial_capital, status, created_at
            FROM accounts
            WHERE user_id = ?
            ORDER BY id ASC
            """,
            (user_id,),
        )

        accounts = []
        for row in cursor.fetchall():
            account_id = int(row["id"])
            positions = account_mgr.get_positions(account_id, refresh_prices=True)
            total_position_value = sum(float(position.market_value or 0.0) for position in positions)
            accounts.append(
                {
                    "id": account_id,
                    "name": _normalize_account_name(row["account_name"]),
                    "balance": row["balance"],
                    "frozen": row["frozen"],
                    "total_assets": float(row["balance"] or 0.0) + float(row["frozen"] or 0.0) + total_position_value,
                    "initial_capital": row["initial_capital"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                }
            )

        return {"accounts": accounts, "count": len(accounts)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list accounts: {str(e)}")
