"""Account management routes (multi-user safe)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from api.auth import UserInDB, get_current_active_user
from api.routers.trading import (
    _build_account_detail_payload,
    _build_account_list_payload,
    _empty_account_detail_payload,
    get_trading_service,
)
from core.database import get_database


router = APIRouter(deprecated=True)


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


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _get_primary_account_detail(user_id: int) -> dict:
    service = get_trading_service()
    accounts = service.account_mgr.get_user_accounts(user_id)
    if not accounts:
        return _empty_account_detail_payload()
    return _build_account_detail_payload(service, user_id, int(accounts[0].id))


def _positions_list_to_legacy_map(positions: object) -> dict:
    items = positions if isinstance(positions, list) else []
    legacy_positions = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").strip()
        if not ticker:
            continue
        legacy_positions[ticker] = {
            "shares": item.get("shares", 0),
            "avg_cost": item.get("avg_cost", 0.0),
            "market_value": _safe_float(item.get("market_value")),
            "unrealized_pnl": _safe_float(item.get("unrealized_pnl")),
        }
    return legacy_positions


def _build_legacy_paper_account_payload(user_id: int, detail: dict) -> dict:
    if not detail.get("account_id"):
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

    portfolio = detail.get("portfolio") or {}
    return {
        "user_id": user_id,
        "account_id": detail.get("account_id"),
        "account_name": detail.get("account_name"),
        "balance": _safe_float(portfolio.get("cash"), _safe_float(detail.get("balance"))),
        "frozen": _safe_float(detail.get("frozen")),
        "total_assets": _safe_float(portfolio.get("total_assets")),
        "initial_capital": _safe_float(detail.get("initial_capital")),
        "positions": _positions_list_to_legacy_map(detail.get("positions")),
    }


@router.get("/paper")
async def get_paper_account(current_user: UserInDB = Depends(get_current_active_user)):
    try:
        db = get_database()
        cursor = db.conn.cursor()
        user_id = _resolve_user_id(cursor, current_user)
        return _build_legacy_paper_account_payload(user_id, _get_primary_account_detail(user_id))
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
        account_id = _get_active_account_id(cursor, user_id)

        if account_id is None:
            return {"equity_history": []}

        service = get_trading_service()
        history = service.account_mgr.get_equity_history(account_id, days=days)

        return {
            "equity_history": [
                {
                    "date": r["date"],
                    "equity": r["equity"],
                    "cash": r["cash"],
                    "position_value": r.get("market_value", r.get("position_value")),
                }
                for r in history
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
        detail = _get_primary_account_detail(user_id)
        return {"positions": _positions_list_to_legacy_map(detail.get("positions"))}
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
        service = get_trading_service()
        payload = _build_account_list_payload(service, user_id)
        accounts = [
            {
                "id": item["account_id"],
                "name": item["account_name"],
                "balance": item["balance"],
                "frozen": item["frozen"],
                "total_assets": item["total_assets"],
                "initial_capital": item["initial_capital"],
                "status": item["status"],
                "created_at": item["created_at"],
            }
            for item in payload["accounts"]
        ]

        return {"accounts": accounts, "count": len(accounts)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list accounts: {str(e)}")
