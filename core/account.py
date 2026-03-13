"""Legacy account compatibility helpers.

This module remains as a bridge layer for older code paths that still expect
an in-memory account dict. New code should use `core.account_manager` and
`core.trading_service`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from core.database import get_database


def _default_account(initial_capital: float) -> Dict[str, Any]:
    return {
        "initial_capital": float(initial_capital),
        "cash": float(initial_capital),
        "positions": {},
        "equity_history": [],
        "trade_log": [],
    }


def _normalize_positions(raw_positions: Any) -> Dict[str, float]:
    if not isinstance(raw_positions, dict):
        return {}
    normalized: Dict[str, float] = {}
    for ticker, shares in raw_positions.items():
        key = str(ticker).strip().upper()
        if not key:
            continue
        try:
            normalized[key] = float(shares)
        except (TypeError, ValueError):
            continue
    return normalized


def _normalize_account_dict(raw: Dict[str, Any], initial_capital: float) -> Dict[str, Any]:
    base = _default_account(initial_capital)
    account = dict(raw)

    account_initial = account.get("initial_capital", base["initial_capital"])
    try:
        account_initial = float(account_initial)
    except (TypeError, ValueError):
        account_initial = base["initial_capital"]

    cash_value = account.get("cash", account_initial)
    try:
        cash_value = float(cash_value)
    except (TypeError, ValueError):
        cash_value = account_initial

    return {
        **account,
        "initial_capital": account_initial,
        "cash": cash_value,
        "positions": _normalize_positions(account.get("positions", {})),
        "equity_history": list(account.get("equity_history") or []),
        "trade_log": list(account.get("trade_log") or []),
    }


def _fetch_account_snapshot(account_id: Optional[int] = None, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    db = get_database()
    cursor = db.conn.cursor()

    if account_id is not None:
        cursor.execute(
            """
            SELECT id, user_id, account_name, balance, frozen, initial_capital,
                   (balance + frozen) AS total_assets
            FROM accounts
            WHERE id = ? AND status = 'active'
            LIMIT 1
            """,
            (account_id,),
        )
    elif user_id is not None:
        cursor.execute(
            """
            SELECT id, user_id, account_name, balance, frozen, initial_capital,
                   (balance + frozen) AS total_assets
            FROM accounts
            WHERE user_id = ? AND status = 'active'
            ORDER BY id ASC
            LIMIT 1
            """,
            (user_id,),
        )
    else:
        cursor.execute(
            """
            SELECT id, user_id, account_name, balance, frozen, initial_capital,
                   (balance + frozen) AS total_assets
            FROM accounts
            WHERE status = 'active'
            ORDER BY id ASC
            LIMIT 1
            """
        )

    row = cursor.fetchone()
    if not row:
        return None

    resolved_account_id = row["id"]
    cursor.execute(
        """
        SELECT ticker, shares
        FROM positions
        WHERE account_id = ? AND shares != 0
        """,
        (resolved_account_id,),
    )

    positions: Dict[str, float] = {}
    for pos in cursor.fetchall():
        ticker = str(pos["ticker"]).strip().upper()
        if not ticker:
            continue
        positions[ticker] = float(pos["shares"])

    return {
        "account_id": resolved_account_id,
        "user_id": row["user_id"],
        "account_name": row["account_name"],
        "initial_capital": float(row["initial_capital"]),
        "cash": float(row["balance"]),
        "frozen": float(row["frozen"]),
        "total_assets": float(row["total_assets"]),
        "positions": positions,
        "equity_history": [],
        "trade_log": [],
    }


def ensure_account_dict(
    raw: Dict[str, Any] | None, initial_capital: float = 1_000_000.0
) -> Dict[str, Any]:
    """Return a normalized account dict for legacy call sites.

    Priority:
    1. If `raw` already contains account state fields (cash/positions/etc),
       normalize and return it directly.
    2. If `raw` includes `account_id` or `user_id`, load that account snapshot.
    3. Otherwise return default structure (do not implicitly bind DB state).
    """
    if raw:
        # Respect explicit in-memory snapshot first.
        if any(k in raw for k in ("cash", "positions", "equity_history", "trade_log")):
            return _normalize_account_dict(raw, initial_capital)

        # If caller provides account context only, resolve from DB with that scope.
        try:
            account_id = raw.get("account_id")
            user_id = raw.get("user_id")
            scoped_account = _fetch_account_snapshot(
                account_id=int(account_id) if account_id is not None else None,
                user_id=int(user_id) if user_id is not None else None,
            )
            if scoped_account:
                return scoped_account
        except Exception:
            # Fall back to normalized raw payload.
            return _normalize_account_dict(raw, initial_capital)

    return _default_account(initial_capital)


def compute_equity(account: Dict[str, Any], latest_prices: Dict[str, float]) -> float:
    """Compute account equity from cash and current position market values."""
    cash = float(account.get("cash", 0.0))
    positions: Dict[str, float] = account.get("positions", {}) or {}
    equity_pos = 0.0
    for ticker, shares in positions.items():
        price = float(latest_prices.get(ticker, 0.0))
        equity_pos += float(shares) * price
    return cash + equity_pos


def append_equity_history(
    account: Dict[str, Any], equity: float, dt: datetime | None = None
) -> None:
    """Append one equity point into in-memory history and persist to DB if possible."""
    if dt is None:
        dt = datetime.now()

    hist: List[Dict[str, Any]] = list(account.get("equity_history") or [])
    hist.append({"date": dt.isoformat(), "equity": float(equity)})
    account["equity_history"] = hist

    try:
        db = get_database()
        account_id = account.get("account_id")
        if not account_id:
            return

        cash = float(account.get("cash", 0.0))
        cursor = db.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO equity_history
            (account_id, date, equity, cash, position_value)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                int(account_id),
                dt.strftime("%Y-%m-%d"),
                float(equity),
                cash,
                float(equity) - cash,
            ),
        )
        db.conn.commit()
    except Exception:
        # Keep compatibility behavior: do not fail caller when DB write fails.
        pass
