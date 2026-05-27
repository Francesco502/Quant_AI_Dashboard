"""Trading route helpers — extracted from routers/trading.py.

Audit logging, serialization, account/portfolio builders, and auto-trading utilities.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core.asset_metadata import get_asset_pool_tickers
from core.auto_trading_guardrails import is_auto_trading_allowed
from core.auto_paper_trading import (
    AUTO_TRADING_UNIVERSE_LABELS,
    UNIVERSE_MODE_ASSET_POOL,
    UNIVERSE_MODE_CN_A_SHARE,
    UNIVERSE_MODE_MANUAL,
    run_auto_trading_cycle,
)
from core.daemon import load_status as load_daemon_status, save_status as save_daemon_status
from core.database import get_database
from core.review_audit import get_review_audit_service
from core.strategy_catalog import list_backtestable_strategies
from core.time_utils import local_now_iso

LEGACY_AUTO_ACCOUNT_NAME = "Auto Paper Trading"
DEFAULT_AUTO_ACCOUNT_NAME = "全市场自动模拟交易"

# Use an Event (not a Lock) to track whether auto-trading is currently running.
# The Event is set() before launching the background thread and clear()ed when
# the thread exits — no cross-thread lock ownership inversion.
_AUTO_TRADING_RUNNING = threading.Event()


class _AutoTradingRunLockCompat:
    """Compatibility shim for callers that still expect the old lock object."""

    def __init__(self, event: threading.Event):
        self._event = event

    def locked(self) -> bool:
        return self._event.is_set()

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        if self._event.is_set():
            return False
        self._event.set()
        return True

    def release(self) -> None:
        self._event.clear()


_AUTO_TRADING_RUN_LOCK = _AutoTradingRunLockCompat(_AUTO_TRADING_RUNNING)

from api.auth import UserInDB

logger = logging.getLogger(__name__)

def _record_trading_audit(
    current_user: UserInDB,
    *,
    action: str,
    resource: str,
    resource_type: str,
    details: Optional[Dict[str, Any]] = None,
    success: bool = True,
    error_message: Optional[str] = None,
) -> None:
    try:
        get_review_audit_service().record_event(
            user=current_user.username,
            action=action,
            resource=resource,
            resource_type=resource_type,
            details=details or {},
            success=success,
            error_message=error_message,
        )
    except Exception:  # noqa: BLE001
        logger.debug("Failed to write trading audit event", exc_info=True)

def _get_user_id_by_username(username: str) -> Optional[int]:
    cursor = get_database().conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    if not row:
        return None
    return int(row["id"] if hasattr(row, "keys") else row[0])

def _normalize_symbol_list(items: Optional[List[str]], uppercase: bool = True) -> Optional[List[str]]:
    if items is None:
        return None
    normalized = []
    for item in items:
        symbol = str(item or "").strip()
        symbol = symbol.upper() if uppercase else symbol
        if symbol and symbol not in normalized:
            normalized.append(symbol)
    return normalized

def _serialize_order(order: Any) -> Dict[str, Any]:
    return {
        "order_id": order.order_id,
        "symbol": order.symbol,
        "side": order.side.value,
        "order_type": order.order_type.value,
        "quantity": order.quantity,
        "status": order.status.value,
        "filled_quantity": order.filled_quantity,
        "avg_fill_price": order.avg_fill_price,
        "created_at": order.created_time.isoformat() if getattr(order, "created_time", None) else None,
    }

def _normalize_account_name(name: Optional[str]) -> str:
    normalized = str(name or "").strip()
    if not normalized or normalized == LEGACY_AUTO_ACCOUNT_NAME:
        return DEFAULT_AUTO_ACCOUNT_NAME
    return normalized

def _safe_float(value: Any, default: Optional[float] = 0.0) -> Optional[float]:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default

def _serialize_datetime(value: Any) -> Any:
    if hasattr(value, "isoformat") and callable(getattr(value, "isoformat")):
        try:
            return value.isoformat()
        except Exception:
            return value
    return value

def _empty_account_detail_payload() -> Dict[str, Any]:
    return {
        "account_id": None,
        "account_name": None,
        "balance": 0.0,
        "frozen": 0.0,
        "initial_capital": 0.0,
        "currency": "CNY",
        "status": None,
        "created_at": None,
        "portfolio": None,
        "positions": [],
        "trade_history": [],
    }

def _build_portfolio_from_positions(account: Any, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
    position_value = sum(_safe_float(position.get("market_value"), 0.0) or 0.0 for position in positions)
    cash = _safe_float(getattr(account, "balance", 0.0), 0.0) or 0.0
    frozen = _safe_float(getattr(account, "frozen", 0.0), 0.0) or 0.0
    return {
        "account_id": int(getattr(account, "id")),
        "account_name": _normalize_account_name(getattr(account, "account_name", None)),
        "total_assets": cash + frozen + position_value,
        "cash": cash,
        "frozen": frozen,
        "position_value": position_value,
        "market_value": position_value,
        "positions": positions,
        "updated_at": local_now_iso(),
    }

def _build_account_detail_payload(
    service: TradingService,
    user_id: int,
    account_id: int,
    *,
    refresh_prices: bool = False,
) -> Dict[str, Any]:
    account = service.account_mgr.get_account(account_id, user_id)
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在或无权访问")

    positions = service.get_positions(user_id, account_id, refresh_prices=refresh_prices)

    return {
        "account_id": account_id,
        "account_name": _normalize_account_name(account.account_name),
        "balance": _safe_float(account.balance),
        "frozen": _safe_float(account.frozen),
        "initial_capital": _safe_float(account.initial_capital),
        "currency": getattr(account, "currency", "CNY"),
        "status": getattr(account, "status", None),
        "created_at": _serialize_datetime(getattr(account, "created_at", None)),
        "portfolio": _build_portfolio_from_positions(account, positions),
        "positions": positions,
        "trade_history": service.account_mgr.get_trade_history(account_id, limit=100),
    }

def _build_account_summary_payload(
    service: TradingService,
    user_id: int,
    account: Any,
    *,
    refresh_prices: bool = False,
) -> Dict[str, Any]:
    account_id = int(account.id)
    account_name = _normalize_account_name(getattr(account, "account_name", None))
    portfolio = service.get_portfolio(user_id, account_id, refresh_prices=refresh_prices)
    market_value = _safe_float(
        (portfolio or {}).get("market_value", (portfolio or {}).get("position_value")),
        0.0,
    )
    total_assets = _safe_float(
        (portfolio or {}).get("total_assets"),
        _safe_float(getattr(account, "balance", 0.0), 0.0)
        + _safe_float(getattr(account, "frozen", 0.0), 0.0)
        + _safe_float(market_value, 0.0),
    )

    return {
        "id": account_id,
        "account_id": account_id,
        "name": account_name,
        "account_name": account_name,
        "balance": _safe_float(getattr(account, "balance", 0.0), 0.0),
        "cash": _safe_float(getattr(account, "balance", 0.0), 0.0),
        "frozen": _safe_float(getattr(account, "frozen", 0.0), 0.0),
        "market_value": _safe_float(market_value, 0.0),
        "total_assets": _safe_float(total_assets, 0.0),
        "initial_capital": _safe_float(getattr(account, "initial_capital", 0.0), 0.0),
        "currency": getattr(account, "currency", "CNY"),
        "status": getattr(account, "status", None),
        "created_at": _serialize_datetime(getattr(account, "created_at", None)),
    }

def _build_account_list_payload(service: TradingService, user_id: int, *, refresh_prices: bool = False) -> Dict[str, Any]:
    accounts = service.account_mgr.get_user_accounts(user_id)
    summaries = [
        _build_account_summary_payload(service, user_id, account, refresh_prices=refresh_prices)
        for account in accounts
    ]
    return {"accounts": summaries, "count": len(summaries)}

def _build_universe_summary(trading_cfg: Dict[str, Any], *, user_id: Optional[int] = None) -> Dict[str, Any]:
    mode = str(trading_cfg.get("universe_mode") or "").strip().lower()
    if mode not in AUTO_TRADING_UNIVERSE_LABELS:
        mode = UNIVERSE_MODE_MANUAL if trading_cfg.get("universe") else UNIVERSE_MODE_ASSET_POOL

    if mode == UNIVERSE_MODE_MANUAL:
        tickers = _normalize_symbol_list(trading_cfg.get("universe") or []) or []
        return {
            "mode": mode,
            "label": AUTO_TRADING_UNIVERSE_LABELS[mode],
            "ticker_count": len(tickers),
            "preview": tickers[:12],
        }

    if mode == UNIVERSE_MODE_ASSET_POOL:
        limit = int(trading_cfg.get("universe_limit", 0) or 0)
        tickers = get_asset_pool_tickers(limit=limit or None, user_id=user_id)
        return {
            "mode": mode,
            "label": AUTO_TRADING_UNIVERSE_LABELS[mode],
            "ticker_count": len(tickers),
            "preview": tickers[:12],
        }

    configured_limit = int(trading_cfg.get("universe_limit", 0) or 0)
    return {
        "mode": UNIVERSE_MODE_CN_A_SHARE,
        "label": AUTO_TRADING_UNIVERSE_LABELS[UNIVERSE_MODE_CN_A_SHARE],
        "ticker_count": configured_limit if configured_limit > 0 else None,
        "preview": [],
    }

def _build_auto_trading_payload(
    service: TradingService,
    trading_cfg: Dict[str, Any],
    *,
    refresh_prices: bool = False,
) -> Dict[str, Any]:
    username = str(trading_cfg.get("username", "admin")).strip() or "admin"
    account_name = _normalize_account_name(trading_cfg.get("account_name"))
    user_id = _get_user_id_by_username(username)
    available_strategies = list_backtestable_strategies()
    config_snapshot = dict(trading_cfg)
    config_snapshot["account_name"] = account_name
    universe_summary = _build_universe_summary(config_snapshot, user_id=user_id)
    config_snapshot.setdefault("universe_mode", universe_summary["mode"])
    config_snapshot.setdefault("universe_limit", int(config_snapshot.get("universe_limit", 0) or 0))

    payload: Dict[str, Any] = {
        "config": config_snapshot,
        "daemon": load_daemon_status(),
        "available_strategies": available_strategies,
        "account": None,
        "universe_summary": universe_summary,
        "safety": {
            "auto_trading_allowed": is_auto_trading_allowed(),
            "required_env": "ALLOW_AUTO_TRADING=true",
        },
    }

    if user_id is None:
        payload["account"] = {"username": username, "account_name": account_name, "found": False}
        return payload

    account = service.account_mgr.get_account_by_name(user_id, account_name)
    if not account:
        payload["account"] = {
            "username": username,
            "user_id": user_id,
            "account_name": account_name,
            "found": False,
        }
        return payload

    positions = service.get_positions(user_id, account.id, refresh_prices=refresh_prices)
    payload["account"] = {
        "username": username,
        "user_id": user_id,
        "account_id": account.id,
        "account_name": _normalize_account_name(account.account_name),
        "balance": account.balance,
        "initial_capital": account.initial_capital,
        "portfolio": _build_portfolio_from_positions(account, positions),
        "positions": positions,
        "recent_trades": service.account_mgr.get_trade_history(account.id, limit=12),
        "recent_orders": [_serialize_order(order) for order in service.get_orders_by_account(user_id, account.id)[:12]],
        "found": True,
    }
    return payload

def _run_auto_trading_cycle_in_background(
    config: Dict[str, Any],
    *,
    reset_account: bool = False,
    initial_balance: Optional[float] = None,
) -> None:
    try:
        from api.routers.trading import get_trading_service

        service = get_trading_service()
        trading_cfg = dict(config.get("trading", {}))

        username = str(trading_cfg.get("username", "admin")).strip() or "admin"
        user_id = _get_user_id_by_username(username)
        if user_id is None:
            raise ValueError(f"自动交易用户不存在: {username}")

        account_name = _normalize_account_name(trading_cfg.get("account_name"))
        account = service.account_mgr.get_or_create_account(
            user_id=user_id,
            name=account_name,
            initial_balance=float(trading_cfg.get("initial_capital", 100000.0)),
        )

        if reset_account:
            service.reset_account(
                user_id=user_id,
                account_id=account.id,
                initial_balance=float(initial_balance or trading_cfg.get("initial_capital", 100000.0)),
                account_name=account_name,
            )

        result = run_auto_trading_cycle(config, service)
        save_daemon_status(
            {
                "trading_run_state": "idle",
                "last_trading_run": result.get("timestamp"),
                "last_trading_result": result,
                "last_trading_error": None,
                "last_manual_test": "completed",
            }
        )
    except Exception as exc:
        logger.error("立即执行自动交易失败: %s", exc, exc_info=True)
        save_daemon_status(
            {
                "trading_run_state": "failed",
                "last_trading_error": str(exc),
                "last_manual_test": "failed",
            }
        )
    finally:
        _AUTO_TRADING_RUNNING.clear()
