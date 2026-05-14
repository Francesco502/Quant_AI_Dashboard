"""Daily decision workbench aggregation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from .data_freshness import get_price_freshness_batch
from .user_assets import get_user_asset_service


def get_trading_service():
    from api.routers.trading import get_trading_service as _get_trading_service

    return _get_trading_service()


def _safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _asset_tickers(assets: List[Dict[str, Any]]) -> List[str]:
    tickers: List[str] = []
    for asset in assets:
        ticker = str(asset.get("ticker") or "").strip().upper()
        if ticker:
            tickers.append(ticker)
    return tickers


def _build_next_actions(*, stale_count: int, asset_count: int, account_found: bool) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    if stale_count:
        actions.append({
            "kind": "data",
            "title": "先更新过期数据",
            "description": f"有 {stale_count} 个标的数据过期，建议更新后再扫描或回测。",
            "href": "/settings",
            "priority": "high",
        })
    actions.append({
        "kind": "scan",
        "title": "运行市场扫描",
        "description": "用资产池或全市场扫描找到今天值得继续研究的候选标的。",
        "href": "/market-scanner",
        "priority": "medium" if asset_count else "high",
    })
    actions.append({
        "kind": "decision",
        "title": "生成 AI 决策",
        "description": "对候选标的生成结构化结论，再决定是否进入回测或纸面交易。",
        "href": "/dashboard-llm",
        "priority": "medium",
    })
    actions.append({
        "kind": "trade",
        "title": "检查纸面账户",
        "description": "确认现金、持仓和最近订单，避免回测结果和纸面执行脱节。",
        "href": "/trading",
        "priority": "medium" if account_found else "high",
    })
    return actions


def build_daily_workbench_snapshot(user_id: int, *, max_age_days: int = 5) -> Dict[str, Any]:
    asset_overview = get_user_asset_service().get_overview(user_id, sync_dca=False)
    assets = asset_overview.get("assets") or []
    tickers = _asset_tickers(assets)
    freshness = get_price_freshness_batch(tickers, max_age_days=max_age_days)
    stale_items = [item for item in freshness.values() if item.get("is_stale")]

    trading_service = get_trading_service()
    list_accounts = getattr(trading_service.account_mgr, "get_user_accounts", None)
    if list_accounts is None:
        list_accounts = getattr(trading_service.account_mgr, "list_accounts", None)
    accounts = list_accounts(user_id) if callable(list_accounts) else []
    primary_account = accounts[0] if accounts else None
    paper_account: Dict[str, Any]
    if primary_account is not None:
        portfolio = trading_service.get_portfolio(user_id, int(primary_account.id), refresh_prices=False)
        orders = trading_service.get_orders_by_account(user_id, int(primary_account.id))[:5]
        trades = trading_service.account_mgr.get_trade_history(int(primary_account.id), limit=5)
        paper_account = {
            "found": True,
            "account_id": int(primary_account.id),
            "account_name": getattr(primary_account, "account_name", None) or getattr(primary_account, "name", "模拟账户"),
            "total_assets": _safe_float(portfolio.get("total_assets")),
            "cash": _safe_float(portfolio.get("cash")),
            "position_value": _safe_float(portfolio.get("position_value", portfolio.get("market_value"))),
            "recent_order_count": len(orders),
            "recent_trade_count": len(trades),
        }
    else:
        paper_account = {
            "found": False,
            "account_id": None,
            "account_name": None,
            "total_assets": 0.0,
            "cash": 0.0,
            "position_value": 0.0,
            "recent_order_count": 0,
            "recent_trade_count": 0,
        }

    return {
        "as_of": datetime.now().isoformat(timespec="seconds"),
        "asset_summary": {
            "asset_count": len(assets),
            "total_market_value": _safe_float((asset_overview.get("summary") or {}).get("total_market_value")),
            "tickers": tickers,
        },
        "data_freshness": {
            "stale_count": len(stale_items),
            "items": list(freshness.values()),
        },
        "paper_account": paper_account,
        "market_review": {
            "href": "/market-review",
            "status": "ready",
            "description": "查看市场广度、主线结构与情绪节奏。",
        },
        "scan_summary": {
            "href": "/market-scanner",
            "status": "ready",
            "description": "运行扫描后，从候选标的进入预测、回测或纸面交易。",
        },
        "backtest_summary": {
            "href": "/backtest",
            "status": "ready",
            "description": "验证候选标的和策略参数，避免直接依据扫描结果行动。",
        },
        "next_actions": _build_next_actions(
            stale_count=len(stale_items),
            asset_count=len(assets),
            account_found=bool(paper_account["found"]),
        ),
    }
