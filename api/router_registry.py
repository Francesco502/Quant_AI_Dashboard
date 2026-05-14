"""Shared API router registration.

Keep the route surface identical across app entrypoints. Optimized runtimes
should tune middleware/resources, not expose a different product API.
"""

from __future__ import annotations

from fastapi import FastAPI

from .auth import router as auth_router
from .routers import (
    accounts,
    agent,
    audit,
    backtest,
    backup,
    data,
    daily_workbench,
    data_freshness,
    external,
    forecasting,
    llm_analysis,
    market,
    models,
    monitoring,
    portfolio,
    signals,
    stocktradebyz,
    strategies,
    strategy_templates,
    trading,
    user_assets,
    user_config,
)


def register_api_routes(app: FastAPI, *, include_legacy_accounts: bool = False) -> None:
    app.include_router(auth_router, prefix="/api/auth", tags=["认证"])
    if include_legacy_accounts:
        app.include_router(accounts.router, prefix="/api/legacy/accounts", tags=["旧账户接口"])
    app.include_router(daily_workbench.router, prefix="/api", tags=["日常决策工作台"])
    app.include_router(data_freshness.router, prefix="/api", tags=["数据新鲜度"])
    app.include_router(audit.router, prefix="/api", tags=["复盘审计"])
    app.include_router(backup.router, prefix="/api", tags=["备份恢复"])
    app.include_router(strategies.router, prefix="/api/strategies", tags=["策略管理"])
    app.include_router(signals.router, prefix="/api/signals", tags=["信号管理"])
    app.include_router(data.router, prefix="/api/data", tags=["数据获取"])
    app.include_router(forecasting.router, prefix="/api/forecasting", tags=["AI预测"])
    app.include_router(trading.router, prefix="/api/trading", tags=["交易执行"])
    app.include_router(models.router, prefix="/api/models", tags=["模型管理"])
    app.include_router(stocktradebyz.router, prefix="/api/stz", tags=["战法选股"])
    app.include_router(backtest.router, prefix="/api/backtest", tags=["策略回测"])
    app.include_router(llm_analysis.router, prefix="/api/llm-analysis", tags=["LLM决策分析"])
    app.include_router(market.router, prefix="/api/market", tags=["市场概览"])
    app.include_router(agent.router, prefix="/api/agent", tags=["Agent研究"])
    app.include_router(portfolio.router, prefix="/api/portfolio", tags=["持仓分析"])
    app.include_router(user_config.router, prefix="/api/user", tags=["用户配置"])
    app.include_router(user_assets.router, prefix="/api/user", tags=["个人资产"])
    app.include_router(monitoring.router, prefix="/api", tags=["系统监控"])
    app.include_router(external.router, prefix="/api/external", tags=["外部数据源"])
    app.include_router(strategy_templates.router, prefix="/api", tags=["策略模板"])
