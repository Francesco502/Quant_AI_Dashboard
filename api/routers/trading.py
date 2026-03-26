"""
交易 API 路由 - 新版本

支持的功能：
- 订单管理（创建、查询、修改、取消）
- 4种订单类型（市价、限价、止损、止损限价）
- 账户管理（多用户多账户）
- 风控检查
- 持仓管理
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.encoders import jsonable_encoder
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
import logging
import threading
from datetime import datetime

from core.trading_service import TradingService, TradingError, InsufficientFundsError, InsufficientSharesError
from core.account_manager import AccountManager
from core.order_manager import OrderManager
from core.risk_monitor import RiskMonitor
from core.interfaces.broker_adapter import BrokerAdapter
from core.brokers.paper_broker import PaperBrokerAdapter
from core.database import get_database

from api.auth import get_current_active_user, require_admin, UserInDB
from core.order_types import OrderSide, OrderType, OrderStatus
from core.auto_paper_trading import (
    AUTO_TRADING_UNIVERSE_LABELS,
    UNIVERSE_MODE_ASSET_POOL,
    UNIVERSE_MODE_CN_A_SHARE,
    UNIVERSE_MODE_MANUAL,
    run_auto_trading_cycle,
)
from core.asset_metadata import get_asset_pool_tickers
from core.daemon import load_config as load_daemon_config, load_status as load_daemon_status, save_config as save_daemon_config, save_status as save_daemon_status
from core.strategy_catalog import list_backtestable_strategies
from core.time_utils import local_now_iso, local_now_str, local_today_str

logger = logging.getLogger(__name__)
router = APIRouter(tags=["trading"])
_AUTO_TRADING_RUN_LOCK = threading.Lock()
LEGACY_AUTO_ACCOUNT_NAME = "Auto Paper Trading"
DEFAULT_AUTO_ACCOUNT_NAME = "全市场自动模拟交易"


# ==================== Request Models ====================

class SubmitOrderRequest(BaseModel):
    """提交订单请求"""
    account_id: int = Field(..., description="账户ID")
    symbol: str = Field(..., description="标的代码")
    side: str = Field(..., description="方向: BUY/SELL")
    order_type: str = Field(default="MARKET", description="订单类型: MARKET/LIMIT/STOP/STOP_LIMIT")
    quantity: int = Field(..., ge=1, description="数量")
    price: Optional[float] = Field(default=None, description="限价（限价单必需）")
    stop_price: Optional[float] = Field(default=None, description="止损价（止损单必需）")
    strategy_id: Optional[str] = Field(default=None, description="策略ID")


class OrderUpdateRequest(BaseModel):
    """修改订单请求"""
    quantity: Optional[int] = Field(default=None, description="新数量")
    price: Optional[float] = Field(default=None, description="新价格（限价单）")


class CreateAccountRequest(BaseModel):
    """创建账户请求"""
    name: str = Field(..., description="账户名称")
    initial_balance: float = Field(default=100000.0, description="初始资金")


# ==================== 订单管理 ====================

class ResetAccountRequest(BaseModel):
    """重置账户请求"""
    initial_balance: float = Field(default=100000.0, gt=0, description="重置后的初始资金")
    account_name: Optional[str] = Field(default=None, description="可选的新账户名称")


class AutoTradingConfigUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    interval_minutes: Optional[int] = Field(default=None, ge=5, le=1440)
    username: Optional[str] = None
    account_name: Optional[str] = None
    initial_capital: Optional[float] = Field(default=None, gt=0)
    strategy_ids: Optional[List[str]] = None
    universe_mode: Optional[str] = None
    universe: Optional[List[str]] = None
    universe_limit: Optional[int] = Field(default=None, ge=0, le=6000)
    max_positions: Optional[int] = Field(default=None, ge=1, le=20)
    evaluation_days: Optional[int] = Field(default=None, ge=30, le=720)
    min_total_return: Optional[float] = None
    min_sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = Field(default=None, ge=0, le=1)
    top_n_strategies: Optional[int] = Field(default=None, ge=1, le=10)


class AutoTradingRunRequest(BaseModel):
    reset_account: bool = False
    initial_balance: Optional[float] = Field(default=None, gt=0)


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


def _build_universe_summary(trading_cfg: Dict[str, Any]) -> Dict[str, Any]:
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
        tickers = get_asset_pool_tickers(limit=limit or None)
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


def _build_auto_trading_payload(service: TradingService, trading_cfg: Dict[str, Any]) -> Dict[str, Any]:
    username = str(trading_cfg.get("username", "admin")).strip() or "admin"
    account_name = _normalize_account_name(trading_cfg.get("account_name"))
    user_id = _get_user_id_by_username(username)
    available_strategies = list_backtestable_strategies()
    config_snapshot = dict(trading_cfg)
    config_snapshot["account_name"] = account_name
    universe_summary = _build_universe_summary(config_snapshot)
    config_snapshot.setdefault("universe_mode", universe_summary["mode"])
    config_snapshot.setdefault("universe_limit", int(config_snapshot.get("universe_limit", 0) or 0))

    payload: Dict[str, Any] = {
        "config": config_snapshot,
        "daemon": load_daemon_status(),
        "available_strategies": available_strategies,
        "account": None,
        "universe_summary": universe_summary,
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

    payload["account"] = {
        "username": username,
        "user_id": user_id,
        "account_id": account.id,
        "account_name": _normalize_account_name(account.account_name),
        "balance": account.balance,
        "initial_capital": account.initial_capital,
        "portfolio": service.get_portfolio(user_id, account.id, refresh_prices=False),
        "positions": service.get_positions(user_id, account.id, refresh_prices=False),
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
        if _AUTO_TRADING_RUN_LOCK.locked():
            _AUTO_TRADING_RUN_LOCK.release()


@router.post("/orders")
async def submit_order(
    request: SubmitOrderRequest,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    提交订单（支持4种订单类型）

    - 市价单：立即按最新价成交
    - 限价单：按指定价格或更好价格成交
    - 止损单：价格触及触发价后转为市价单
    - 止损限价单：价格触及触发价后转为限价单
    """
    try:
        service = get_trading_service()

        result = service.submit_order(
            user_id=current_user.id,
            account_id=request.account_id,
            symbol=request.symbol,
            side=OrderSide(request.side.upper()),
            order_type=OrderType(request.order_type.upper()),
            quantity=request.quantity,
            price=request.price,
            stop_price=request.stop_price,
            strategy_id=request.strategy_id
        )

        return result

    except InsufficientFundsError as e:
        raise HTTPException(status_code=400, detail=f"资金不足: {str(e)}")
    except InsufficientSharesError as e:
        raise HTTPException(status_code=400, detail=f"持仓不足: {str(e)}")
    except TradingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"订单提交失败: {e}")
        raise HTTPException(status_code=500, detail=f"订单执行失败: {str(e)}")


@router.get("/orders/{order_id}")
async def get_order_status(
    order_id: str,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """查询订单状态"""
    try:
        service = get_trading_service()
        order = service.get_order(order_id)

        if not order:
            raise HTTPException(status_code=404, detail="订单不存在")

        # 验证权限
        account = service.account_mgr.get_account(int(order.account_id), current_user.id)
        if not account:
            raise HTTPException(status_code=403, detail="无权访问此订单")

        return {
            "order_id": order.order_id,
            "status": order.status.value,
            "symbol": order.symbol,
            "side": order.side.value,
            "order_type": order.order_type.value,
            "quantity": order.quantity,
            "filled_quantity": order.filled_quantity,
            "price": order.price,
            "stop_price": order.stop_price,
            "avg_fill_price": order.avg_fill_price,
            "created_at": order.created_time.isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询订单失败: {str(e)}")


@router.get("/orders")
async def list_orders(
    account_id: Optional[int] = Query(default=None, description="账户ID"),
    status: Optional[str] = Query(default=None, description="订单状态"),
    limit: int = Query(default=50, le=100, description="返回数量"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """查询订单列表"""
    try:
        service = get_trading_service()

        # 验证账户访问权限
        if account_id:
            if not service.account_mgr.account_exists(account_id, current_user.id):
                raise HTTPException(status_code=403, detail="无权访问此账户")

        orders = service.get_orders_by_account(
            user_id=current_user.id,
            account_id=account_id
        )

        # 状态过滤
        if status:
            orders = [o for o in orders if o.status.value == status.upper()]

        # 限制返回数量
        orders = orders[:limit]

        return {
            "orders": [
                {
                    "order_id": o.order_id,
                    "status": o.status.value,
                    "symbol": o.symbol,
                    "side": o.side.value,
                    "order_type": o.order_type.value,
                    "quantity": o.quantity,
                    "filled_quantity": o.filled_quantity,
                    "price": o.price,
                    "avg_fill_price": o.avg_fill_price,
                    "created_at": o.created_time.isoformat()
                }
                for o in orders
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询订单列表失败: {str(e)}")


@router.put("/orders/{order_id}")
async def modify_order(
    order_id: str,
    request: OrderUpdateRequest,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """修改订单（仅支持PENDING状态的订单）"""
    try:
        service = get_trading_service()
        order = service.get_order(order_id)

        if not order:
            raise HTTPException(status_code=404, detail="订单不存在")

        # 验证权限
        account = service.account_mgr.get_account(int(order.account_id), current_user.id)
        if not account:
            raise HTTPException(status_code=403, detail="无权修改此订单")

        result = service.modify_order(order_id, request.quantity, request.price)
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"修改订单失败: {str(e)}")


@router.delete("/orders/{order_id}")
async def cancel_order(
    order_id: str,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """取消订单"""
    try:
        service = get_trading_service()
        result = service.cancel_order(order_id)
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取消订单失败: {str(e)}")


# ==================== 账户管理 ====================

@router.post("/accounts")
async def create_account(
    request: CreateAccountRequest,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """创建模拟账户"""
    try:
        service = get_trading_service()
        result = service.create_account(
            user_id=current_user.id,
            name=request.name,
            initial_balance=request.initial_balance
        )
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建账户失败: {str(e)}")


@router.get("/accounts")
async def list_accounts(
    current_user: UserInDB = Depends(get_current_active_user)
):
    """查询用户的所有账户"""
    try:
        service = get_trading_service()
        accounts = service.list_user_accounts(user_id=current_user.id)
        return {"accounts": accounts}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询账户列表失败: {str(e)}")


@router.get("/accounts/{account_id}")
async def get_account_detail(
    account_id: int,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """查询账户详情（含持仓、历史）"""
    try:
        service = get_trading_service()

        if not service.account_mgr.account_exists(account_id, current_user.id):
            raise HTTPException(status_code=404, detail="账户不存在或无权访问")

        account = service.account_mgr.get_account(account_id, current_user.id)
        positions = service.get_positions(current_user.id, account_id, refresh_prices=False)
        portfolio = service.get_portfolio(current_user.id, account_id, refresh_prices=False)
        trade_history = service.account_mgr.get_trade_history(account_id, limit=100)

        return {
            "account_id": account_id,
            "account_name": _normalize_account_name(account.account_name if account else ""),
            "portfolio": portfolio,
            "positions": positions,
            "trade_history": trade_history,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询账户详情失败: {str(e)}")


@router.post("/accounts/{account_id}/reset")
async def reset_account(
    account_id: int,
    request: ResetAccountRequest,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """重置模拟账户为初始现金状态。"""
    try:
        service = get_trading_service()

        if not service.account_mgr.account_exists(account_id, current_user.id):
            raise HTTPException(status_code=404, detail="账户不存在或无权访问")

        return service.reset_account(
            user_id=current_user.id,
            account_id=account_id,
            initial_balance=request.initial_balance,
            account_name=request.account_name,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置账户失败: {str(e)}")


@router.get("/auto/status")
async def get_auto_trading_status(current_user: UserInDB = Depends(require_admin)):
    """获取自动模拟交易配置、状态与当前账户快照。"""
    del current_user
    try:
        config = load_daemon_config()
        trading_cfg = dict(config.get("trading", {}))
        service = get_trading_service()
        return _build_auto_trading_payload(service, trading_cfg)
    except Exception as e:
        logger.error(f"读取自动交易状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"读取自动交易状态失败: {str(e)}")


@router.put("/auto/config")
async def update_auto_trading_config(
    request: AutoTradingConfigUpdateRequest,
    current_user: UserInDB = Depends(require_admin),
):
    """更新自动模拟交易配置。"""
    del current_user
    try:
        config = load_daemon_config()
        trading_cfg = dict(config.get("trading", {}))

        available_ids = {item["id"] for item in list_backtestable_strategies()}
        available_universe_modes = {
            UNIVERSE_MODE_MANUAL,
            UNIVERSE_MODE_ASSET_POOL,
            UNIVERSE_MODE_CN_A_SHARE,
        }
        patch = request.model_dump(exclude_none=True)

        if "strategy_ids" in patch:
            strategy_ids = _normalize_symbol_list(patch["strategy_ids"], uppercase=False)
            if not strategy_ids:
                raise HTTPException(status_code=400, detail="至少保留一个自动交易策略")
            invalid_ids = sorted(set(strategy_ids) - available_ids)
            if invalid_ids:
                raise HTTPException(status_code=400, detail=f"未知策略: {', '.join(invalid_ids)}")
            patch["strategy_ids"] = strategy_ids

        if "universe_mode" in patch:
            universe_mode = str(patch["universe_mode"] or "").strip().lower()
            if universe_mode not in available_universe_modes:
                raise HTTPException(
                    status_code=400,
                    detail=f"未知标的范围模式: {universe_mode or 'empty'}",
                )
            patch["universe_mode"] = universe_mode

        if "universe" in patch:
            universe = _normalize_symbol_list(patch["universe"])
            effective_mode = str(
                patch.get("universe_mode")
                or trading_cfg.get("universe_mode")
                or UNIVERSE_MODE_MANUAL
            ).strip().lower()
            if effective_mode == UNIVERSE_MODE_MANUAL and not universe:
                raise HTTPException(status_code=400, detail="至少保留一个交易标的")
            patch["universe"] = universe

        effective_mode = str(
            patch.get("universe_mode")
            or trading_cfg.get("universe_mode")
            or UNIVERSE_MODE_MANUAL
        ).strip().lower()
        if effective_mode == UNIVERSE_MODE_MANUAL and not (
            patch.get("universe") or trading_cfg.get("universe")
        ):
            raise HTTPException(status_code=400, detail="手动标的池模式至少保留一个交易标的")

        for key, value in patch.items():
            trading_cfg[key] = value

        config["trading"] = trading_cfg
        save_daemon_config(config)
        save_daemon_status(
            {
                "config_trading_enabled": bool(trading_cfg.get("enabled", False)),
                "config_trading_interval_minutes": int(trading_cfg.get("interval_minutes", 0) or 0),
            }
        )

        service = get_trading_service()
        return _build_auto_trading_payload(service, trading_cfg)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新自动交易配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新自动交易配置失败: {str(e)}")


@router.post("/auto/run-now")
async def run_auto_trading_now(
    request: AutoTradingRunRequest,
    current_user: UserInDB = Depends(require_admin),
):
    """立即执行一次自动模拟交易。"""
    del current_user
    try:
        config = load_daemon_config()
        trading_cfg = dict(config.get("trading", {}))
        service = get_trading_service()
        if not _AUTO_TRADING_RUN_LOCK.acquire(blocking=False):
            response = _build_auto_trading_payload(service, trading_cfg)
            response["run_request_status"] = "already_running"
            response["message"] = "已有一轮自动交易正在后台执行，请稍后刷新结果。"
            return jsonable_encoder(response)

        requested_at = local_now_str()
        save_daemon_status(
            {
                "trading_run_state": "running",
                "last_trading_requested_at": requested_at,
                "last_trading_error": None,
                "last_manual_test": "running",
            }
        )

        worker = threading.Thread(
            target=_run_auto_trading_cycle_in_background,
            kwargs={
                "config": config,
                "reset_account": request.reset_account,
                "initial_balance": request.initial_balance,
            },
            name="auto-trading-run-now",
            daemon=True,
        )
        worker.start()

        response = _build_auto_trading_payload(service, trading_cfg)
        response["run_request_status"] = "started"
        response["message"] = (
            "已受理重置并执行自动交易任务，结果将在后台生成。"
            if request.reset_account
            else "已受理自动交易任务，结果将在后台生成。"
        )
        return jsonable_encoder(response)
    except HTTPException:
        raise
    except Exception as e:
        if _AUTO_TRADING_RUN_LOCK.locked():
            _AUTO_TRADING_RUN_LOCK.release()
        logger.error(f"立即执行自动交易失败: {e}", exc_info=True)
        save_daemon_status({"last_trading_error": str(e)})
        raise HTTPException(status_code=500, detail=f"立即执行自动交易失败: {str(e)}")


@router.delete("/accounts/{account_id}")
async def close_account(
    account_id: int,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """关闭账户（需无持仓）"""
    try:
        service = get_trading_service()

        if not service.account_mgr.account_exists(account_id, current_user.id):
            raise HTTPException(status_code=404, detail="账户不存在或无权访问")

        # 检查是否有持仓
        positions = service.get_positions(current_user.id, account_id, refresh_prices=False)
        if positions:
            raise HTTPException(status_code=400, detail="账户仍有持仓，无法关闭")

        success = service.account_mgr.close_account(account_id, current_user.id)
        if success:
            return {"success": True, "message": "账户已关闭"}
        else:
            raise HTTPException(status_code=500, detail="关闭账户失败")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"关闭账户失败: {str(e)}")


# ==================== 持仓管理 ====================

@router.get("/accounts/{account_id}/positions")
async def get_positions(
    account_id: int,
    refresh: bool = Query(default=True, description="是否刷新最新价格"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """查询持仓列表"""
    try:
        service = get_trading_service()

        if not service.account_mgr.account_exists(account_id, current_user.id):
            raise HTTPException(status_code=404, detail="账户不存在或无权访问")

        positions = service.get_positions(current_user.id, account_id, refresh_prices=refresh)
        return {"positions": positions}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询持仓失败: {str(e)}")


@router.get("/accounts/{account_id}/portfolio")
async def get_portfolio(
    account_id: int,
    refresh: bool = Query(default=True, description="是否刷新最新持仓市值"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """查询账户投资组合"""
    try:
        service = get_trading_service()

        if not service.account_mgr.account_exists(account_id, current_user.id):
            raise HTTPException(status_code=404, detail="账户不存在或无权访问")

        portfolio = service.get_portfolio(current_user.id, account_id, refresh_prices=refresh)
        return portfolio

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询投资组合失败: {str(e)}")


# ==================== 止损止盈 ====================

@router.post("/accounts/{account_id}/stop-loss")
async def set_stop_loss(
    account_id: int,
    symbol: str,
    stop_type: str = Query(default="percentage", description="止损类型: fixed/trailing/percentage"),
    stop_percentage: float = Query(default=0.05, description="止损百分比"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """设置止损规则"""
    try:
        service = get_trading_service()

        if not service.account_mgr.account_exists(account_id, current_user.id):
            raise HTTPException(status_code=404, detail="账户不存在或无权访问")

        result = service.set_stop_loss(
            user_id=current_user.id,
            account_id=account_id,
            symbol=symbol,
            stop_type=stop_type,
            stop_percentage=stop_percentage
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"设置止损失败: {str(e)}")


@router.delete("/accounts/{account_id}/stop-loss/{symbol}")
async def remove_stop_loss(
    account_id: int,
    symbol: str,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """移除止损规则"""
    try:
        service = get_trading_service()

        if not service.account_mgr.account_exists(account_id, current_user.id):
            raise HTTPException(status_code=404, detail="账户不存在或无权访问")

        service.order_mgr.remove_stop_loss(account_id, symbol)
        return {"success": True, "message": f"止损规则已移除: {symbol}"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"移除止损失败: {str(e)}")


@router.post("/accounts/{account_id}/take-profit")
async def set_take_profit(
    account_id: int,
    symbol: str,
    take_profit_percentage: float = Query(default=0.10, description="止盈百分比"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """设置止盈规则"""
    try:
        service = get_trading_service()

        if not service.account_mgr.account_exists(account_id, current_user.id):
            raise HTTPException(status_code=404, detail="账户不存在或无权访问")

        result = service.set_take_profit(
            user_id=current_user.id,
            account_id=account_id,
            symbol=symbol,
            take_profit_percentage=take_profit_percentage
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"设置止盈失败: {str(e)}")


# ==================== 风控相关 ====================

@router.post("/risk/check")
async def check_order_risk(
    account_id: int,
    symbol: str,
    side: str,
    order_type: str,
    quantity: int,
    price: Optional[float] = Query(default=None),
    stop_price: Optional[float] = Query(default=None),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """预检查订单风险（提交前）"""
    try:
        service = get_trading_service()

        if not service.account_mgr.account_exists(account_id, current_user.id):
            raise HTTPException(status_code=404, detail="账户不存在或无权访问")

        result = service.check_order_risk(
            user_id=current_user.id,
            account_id=account_id,
            symbol=symbol,
            side=OrderSide(side.upper()),
            order_type=OrderType(order_type.upper()),
            quantity=quantity,
            price=price,
            stop_price=stop_price
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"风控检查失败: {str(e)}")


@router.get("/risk/events")
async def get_risk_events(
    account_id: Optional[int] = Query(default=None),
    limit: int = Query(default=50),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """获取风险事件记录"""
    try:
        service = get_trading_service()
        risk_monitor = service.risk_monitor

        if account_id and not service.account_mgr.account_exists(account_id, current_user.id):
            raise HTTPException(status_code=403, detail="无权访问此账户")

        events = risk_monitor.get_risk_events(account_id=account_id, limit=limit)
        return {"events": events}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取风险事件失败: {str(e)}")


# ==================== 绩效分析与权益曲线 ====================

@router.get("/accounts/{account_id}/performance")
async def get_account_performance(
    account_id: int,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    获取账户绩效指标

    返回：
    - 总收益率
    - 年化收益率
    - 夏普比率
    - 最大回撤
    - 胜率
    """
    try:
        service = get_trading_service()

        if not service.account_mgr.account_exists(account_id, current_user.id):
            raise HTTPException(status_code=404, detail="账户不存在或无权访问")

        # 获取账户信息
        account = service.account_mgr.get_account(account_id, current_user.id)
        if not account:
            raise HTTPException(status_code=404, detail="账户不存在")

        # 获取最新投资组合快照
        portfolio = service.get_portfolio(current_user.id, account_id, refresh_prices=False)
        total_market_value = float(portfolio.get("position_value", 0.0) or 0.0)
        total_assets = float(portfolio.get("total_assets", account.balance) or 0.0)

        # 计算总收益率
        initial_capital = _safe_float(account.initial_capital, 0.0) or 0.0
        total_return_pct = ((total_assets - initial_capital) / initial_capital * 100) if initial_capital > 0 else 0

        # 获取交易历史计算胜率和夏普比率
        trade_history = service.account_mgr.get_trade_history(account_id, limit=500)

        # 计算胜率
        profitable_trades = 0
        total_closed_trades = 0
        # 简化计算：基于已实现盈亏
        realized_pnl_list = []
        for trade in trade_history:
            realized_pnl = _safe_float(trade.get("realized_pnl", trade.get("pnl")), None)
            if realized_pnl is not None:
                realized_pnl_list.append(realized_pnl)
                total_closed_trades += 1
                if realized_pnl > 0:
                    profitable_trades += 1

        win_rate = (profitable_trades / total_closed_trades * 100) if total_closed_trades > 0 else 0

        # 计算简化夏普比率（基于日收益）
        # 获取权益历史
        equity_history = service.account_mgr.get_equity_history(account_id, days=90)
        sharpe_ratio = 0.0
        max_drawdown = 0.0
        equity_values = [
            value
            for value in (_safe_float(entry.get("equity"), None) for entry in equity_history)
            if value is not None and value > 0
        ]

        if len(equity_values) >= 10:
            # 计算日收益率
            returns = []
            for i in range(1, len(equity_values)):
                if equity_values[i-1] > 0:
                    daily_return = (equity_values[i] - equity_values[i-1]) / equity_values[i-1]
                    returns.append(daily_return)

            if returns:
                import numpy as np
                avg_return = np.mean(returns)
                std_return = np.std(returns)
                if std_return > 0:
                    # 年化夏普比率 (假设无风险利率为2%)
                    sharpe_ratio = ((avg_return * 252) - 0.02) / (std_return * np.sqrt(252))

            # 计算最大回撤
            peak = equity_values[0]
            for equity in equity_values:
                if equity > peak:
                    peak = equity
                drawdown = (peak - equity) / peak if peak > 0 else 0
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

        # 计算年化收益率（简化：基于创建时间）
        from datetime import datetime
        created_at = account.created_at if account.created_at else datetime.now()
        days_active = (datetime.now() - created_at).days if isinstance(created_at, datetime) else 30
        if days_active < 1:
            days_active = 1

        growth_base = 1 + total_return_pct / 100
        annual_return_pct = 0.0
        if total_return_pct != 0 and growth_base > 0:
            annual_return_pct = ((growth_base) ** (365 / days_active) - 1) * 100

        return {
            "account_id": account_id,
            "initial_capital": initial_capital,
            "total_assets": total_assets,
            "cash": float(portfolio.get("cash", account.balance) or 0.0),
            "market_value": total_market_value,
            "total_return_pct": round(total_return_pct, 2),
            "annual_return_pct": round(annual_return_pct, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "max_drawdown_pct": round(max_drawdown * 100, 2),
            "win_rate_pct": round(win_rate, 2),
            "total_trades": total_closed_trades,
            "profitable_trades": profitable_trades,
            "days_active": days_active,
            "timestamp": local_now_iso()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取绩效指标失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取绩效指标失败: {str(e)}")


@router.get("/accounts/{account_id}/equity-curve")
async def get_equity_curve(
    account_id: int,
    days: int = Query(default=30, ge=7, le=365),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    获取账户权益曲线数据

    Args:
        days: 返回天数（7-365）

    返回时间序列数据用于图表展示
    """
    try:
        service = get_trading_service()

        if not service.account_mgr.account_exists(account_id, current_user.id):
            raise HTTPException(status_code=404, detail="账户不存在或无权访问")

        # 获取权益历史
        equity_history = service.account_mgr.get_equity_history(account_id, days=days)

        # 如果没有历史记录，生成基于当前持仓的实时数据
        if not equity_history:
            account = service.account_mgr.get_account(account_id, current_user.id)
            positions = service.get_positions(current_user.id, account_id, refresh_prices=False)
            total_market_value = sum(float(p.get("market_value", 0.0) or 0.0) for p in positions)
            current_equity = account.balance + account.frozen + total_market_value

            # 返回单点数据
            from datetime import datetime
            equity_history = [{
                "date": local_today_str(),
                "equity": current_equity,
                "cash": account.balance,
                "market_value": total_market_value
            }]

        return {
            "account_id": account_id,
            "days": days,
            "data": equity_history,
            "count": len(equity_history)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取权益曲线失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取权益曲线失败: {str(e)}")


# ==================== 辅助函数 ====================

def get_trading_service() -> TradingService:
    """获取TradingService实例（单例）"""
    from core.database import _db_instance

    db = get_database()

    if not hasattr(get_trading_service, '_instance'):
        from core.account_manager import AccountManager
        from core.order_manager import OrderManager
        from core.risk_monitor import RiskMonitor
        from core.brokers.paper_broker import PaperBrokerAdapter

        account_mgr = AccountManager(db)
        order_mgr = OrderManager(db)
        risk_monitor = RiskMonitor()
        broker = PaperBrokerAdapter(risk_monitor=risk_monitor)

        get_trading_service._instance = TradingService(account_mgr, order_mgr, risk_monitor, broker, db)

    return get_trading_service._instance
