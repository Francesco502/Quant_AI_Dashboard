from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import pandas as pd
import logging
from datetime import datetime

from core.backtest_engine import BacktestEngine
from core.data_service import load_price_data
from core.stocktradebyz_adapter import get_default_selector_configs

router = APIRouter()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  内置经典策略（适用于回测引擎的仓位管理型策略）
# ---------------------------------------------------------------------------

def sma_strategy(history: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, int]:
    """SMA 金叉策略"""
    short_window = int(params.get("short_window", 10))
    long_window = int(params.get("long_window", 30))
    positions = {}
    for ticker in history.columns:
        if len(history) < long_window:
            continue
        prices = history[ticker]
        short_ma = prices.tail(short_window).mean()
        long_ma = prices.tail(long_window).mean()
        positions[ticker] = 100 if short_ma > long_ma else 0
    return positions

def mean_reversion_strategy(history: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, int]:
    """布林带均值回归策略"""
    window = int(params.get("window", 20))
    std_dev = float(params.get("std_dev", 2.0))
    positions = {}
    for ticker in history.columns:
        if len(history) < window:
            continue
        prices = history[ticker]
        sma = prices.tail(window).mean()
        std = prices.tail(window).std()
        upper = sma + std_dev * std
        lower = sma - std_dev * std
        current = prices.iloc[-1]
        if current < lower:
            positions[ticker] = 100
        elif current > upper:
            positions[ticker] = 0
    return positions

# 经典策略注册表
BUILTIN_STRATEGIES: Dict[str, Dict[str, Any]] = {
    "sma_crossover": {
        "func": sma_strategy,
        "name": "SMA 金叉策略",
        "description": "短期均线上穿长期均线时买入，下穿时卖出。",
        "category": "classic",
        "default_params": {"short_window": 10, "long_window": 30}
    },
    "mean_reversion": {
        "func": mean_reversion_strategy,
        "name": "布林带均值回归",
        "description": "价格触及布林下轨时买入，触及上轨时卖出。",
        "category": "classic",
        "default_params": {"window": 20, "std_dev": 2.0}
    }
}

# ---------------------------------------------------------------------------
#  统一策略列表（经典 + Z哥战法）
# ---------------------------------------------------------------------------

def _build_unified_strategy_list() -> List[Dict[str, Any]]:
    """
    合并经典策略与 STZ 战法策略，返回统一格式列表。
    所有页面（回测、扫描、信号）共享同一份策略列表。
    """
    result: List[Dict[str, Any]] = []

    # 1. 内置经典策略
    for sid, conf in BUILTIN_STRATEGIES.items():
        result.append({
            "id": sid,
            "name": conf["name"],
            "description": conf["description"],
            "category": "classic",
            "default_params": conf["default_params"],
            "class_name": sid,
            "alias": conf["name"],
            "activate": True,
        })

    # 2. STZ 战法策略（来源: core/stocktradebyz/configs.json）
    try:
        stz_configs = get_default_selector_configs()
        for cfg in stz_configs:
            # cfg 是 SelectorConfig dataclass，用属性访问
            result.append({
                "id": f"stz_{cfg.class_name}",
                "name": cfg.alias,
                "description": f"Z哥战法 — {cfg.alias}（{cfg.class_name}）",
                "category": "stz",
                "default_params": cfg.params or {},
                "class_name": cfg.class_name,
                "alias": cfg.alias,
                "activate": cfg.activate,
            })
    except Exception as e:
        logger.warning(f"加载 STZ 策略失败: {e}", exc_info=True)

    return result


# --- API Models ---

class BacktestRequest(BaseModel):
    strategy_id: str
    tickers: List[str]
    start_date: str
    end_date: Optional[str] = None
    initial_capital: float = 100000.0
    params: Dict[str, Any] = {}

class BacktestResponse(BaseModel):
    metrics: Dict[str, Any]
    equity_curve: List[Dict[str, Any]]
    trades: List[Dict[str, Any]]

# --- Endpoints ---

@router.get("/strategies")
async def list_strategies():
    """
    统一策略列表端点 —— 返回所有可用策略（经典 + Z哥战法）。
    前端所有页面（回测、交易中心、量化战法）通过此端点获取策略清单。
    """
    return _build_unified_strategy_list()


@router.post("/run", response_model=BacktestResponse)
async def run_backtest(request: BacktestRequest):
    """Run a backtest"""
    # 检查是否为内置经典策略
    if request.strategy_id not in BUILTIN_STRATEGIES:
        raise HTTPException(status_code=404, detail="Strategy not found (仅支持经典策略回测)")

    strategy_conf = BUILTIN_STRATEGIES[request.strategy_id]
    strategy_func = strategy_conf["func"]

    try:
        start_dt = datetime.strptime(request.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(request.end_date, "%Y-%m-%d") if request.end_date else datetime.now()
        days = (end_dt - start_dt).days + 100

        price_data = load_price_data(request.tickers, days=days)

        price_data = price_data[price_data.index >= request.start_date]
        if request.end_date:
            price_data = price_data[price_data.index <= request.end_date]

        if price_data.empty:
            raise HTTPException(status_code=400, detail="指定日期范围内无数据")

        engine = BacktestEngine(initial_capital=request.initial_capital)
        results = engine.run(price_data, strategy_func, request.params)

        equity_curve_list = []
        if "equity_curve" in results and not results["equity_curve"].empty:
            df = results["equity_curve"].reset_index()
            df["date"] = df["date"].dt.strftime("%Y-%m-%d")
            equity_curve_list = df.to_dict(orient="records")

        metrics = {
            "total_return": results.get("total_return", 0),
            "sharpe_ratio": results.get("sharpe_ratio", 0),
            "max_drawdown": results.get("max_drawdown", 0),
            "volatility": results.get("volatility", 0),
        }

        trades = results.get("trade_history", [])

        return {
            "metrics": metrics,
            "equity_curve": equity_curve_list,
            "trades": trades
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
