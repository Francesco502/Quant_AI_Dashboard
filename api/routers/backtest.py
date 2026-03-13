from fastapi import APIRouter, HTTPException, Body, Query
from pydantic import BaseModel, Field, field_validator, ValidationInfo
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta

from core.backtest_engine import BacktestEngine
from core.data_service import load_price_data
from core.stocktradebyz_adapter import get_default_selector_configs
from core.analysis.performance_extended import (
    ExtendedPerformanceAnalyzer,
    compare_multiple_strategies,
    generate_backtest_report
)

router = APIRouter()
logger = logging.getLogger(__name__)

# --- API Models ---

class BacktestRequest(BaseModel):
    strategy_id: str
    tickers: List[str]
    start_date: str
    end_date: Optional[str] = None
    initial_capital: float = 100000.0
    params: Dict[str, Any] = {}

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date_format(cls, v: str, info: ValidationInfo) -> str:
        if v is None:
            return v
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError(f'Date {v} does not match format YYYY-MM-DD')


class BacktestResponse(BaseModel):
    metrics: Dict[str, Any]
    equity_curve: List[Dict[str, Any]]
    trades: List[Dict[str, Any]]


class MultiStrategyBacktestRequest(BaseModel):
    strategies: Dict[str, Dict[str, Any]]  # {strategy_id: {weight, params}}
    tickers: List[str]
    start_date: str
    end_date: Optional[str] = None
    initial_capital: float = 100000.0


class OptimizeRequest(BaseModel):
    strategy_id: str
    tickers: List[str]
    param_grid: Dict[str, List[Any]]
    start_date: str
    end_date: Optional[str] = None
    initial_capital: float = 100000.0
    objective: str = "trading_objective"


class ExportBacktestRequest(BaseModel):
    """导出回测报告请求"""
    report_type: str = "html"  # html, pdf, json
    include_charts: bool = True
    format: str = "A4"  # A4, letter
    initial_capital: float = 100000.0  # 初始资本（用于计算收益）


class CompareStrategiesRequest(BaseModel):
    strategy_results: List[Dict[str, Any]]  # [{"name", "metrics", "equity_curve"}]
    benchmark_code: Optional[str] = None


# ---------------------------------------------------------------------------
#  内置经典策略
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


# -------------------------------------------------------------------
# v1.2.0 - 新 API Models
# -------------------------------------------------------------------

class MultiStrategyRequest(BaseModel):
    """多策略组合回测请求"""
    strategies: Dict[str, Dict[str, Any]] = Field(
        ...,
        description="策略字典 {id: {weights: float, params: dict}}"
    )
    tickers: List[str] = Field(..., description="标的列表")
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="结束日期 YYYY-MM-DD")
    initial_capital: float = Field(100000.0, description="初始资本")
    benchmark_ticker: Optional[str] = Field("000300.SH", description="基准指数代码")

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date_format(cls, v: str, info: ValidationInfo) -> str:
        if v is None:
            return v
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError(f'Date {v} does not match format YYYY-MM-DD')


class ParameterOptimizationRequest(BaseModel):
    """参数优化请求"""
    strategy_id: str = Field(..., description="策略ID")
    tickers: List[str] = Field(..., description="标的列表")
    param_grid: Dict[str, List[Any]] = Field(
        ...,
        description="参数网格 {param_name: [values]}"
    )
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="结束日期")
    initial_capital: float = Field(100000.0, description="初始资本")
    objective: str = Field("trading_objective", description="优化目标")
    cv_days: int = Field(60, description="交叉验证天数")

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date_format(cls, v: str, info: ValidationInfo) -> str:
        if v is None:
            return v
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError(f'Date {v} does not match format YYYY-MM-DD')


class ExportBacktestRequest(BaseModel):
    """导出回测报告请求"""
    equity_curve: List[Dict[str, Any]]  # 权益曲线数据
    trades: List[Dict[str, Any]]  # 交易记录
    metrics: Dict[str, Any]  # 指标字典
    report_type: str = Field("html", description="导出格式: html, pdf, csv")
    include_charts: bool = Field(True, description="是否包含图表")
    format: str = Field("A4", description="报告格式: A4, letter")
    initial_capital: float = Field(100000.0, description="初始资本")


# --- Endpoints ---

@router.get("/strategies")
async def list_strategies():
    """
    统一策略列表端点 —— 返回所有可用策略（经典 + Z哥战法）。
    """
    return _build_unified_strategy_list()


@router.post("/run", response_model=Dict[str, Any])
async def run_backtest(request: BacktestRequest):
    """Run a backtest"""
    if request.strategy_id not in BUILTIN_STRATEGIES:
        raise HTTPException(status_code=404, detail="Strategy not found")

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


# --------------------------------------------------------------------------
# v1.2.0 - 新增 API 端点
# --------------------------------------------------------------------------

@router.post("/run-multi", response_model=Dict[str, Any])
async def run_multi_strategy_backtest(request: MultiStrategyRequest):
    """
    多策略组合回测 - v1.2.0 新增

    支持同时运行多个策略并对比结果，计算组合收益。
    """
    try:
        # 解析策略
        strategies = {}
        weights = {}
        strategy_params = {}

        for sid, conf in request.strategies.items():
            if sid not in BUILTIN_STRATEGIES:
                continue

            strategies[sid] = (
                BUILTIN_STRATEGIES[sid]["func"],
                conf.get("params", {})
            )
            weights[sid] = conf.get("weight", 1.0 / len(request.strategies))

        start_dt = datetime.strptime(request.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(request.end_date, "%Y-%m-%d") if request.end_date else datetime.now()
        days = (end_dt - start_dt).days + 100

        price_data = load_price_data(request.tickers, days=days)
        price_data = price_data[price_data.index >= request.start_date]
        if request.end_date:
            price_data = price_data[price_data.index <= request.end_date]

        if price_data.empty:
            raise HTTPException(status_code=400, detail="指定日期范围内无数据")

        # 加载基准数据（如果指定）
        benchmark_data = None
        if request.benchmark_ticker and request.benchmark_ticker not in request.tickers:
            try:
                bench_days = days + 30  # 额外数据用于对齐
                benchmark_data = load_price_data([request.benchmark_ticker], days=bench_days)
                benchmark_data = benchmark_data[benchmark_data.index >= request.start_date]
                if request.end_date:
                    benchmark_data = benchmark_data[benchmark_data.index <= request.end_date]
            except Exception as e:
                logger.warning(f"加载基准数据失败: {e}")

        # 运行多策略回测
        engine = BacktestEngine(initial_capital=request.initial_capital)
        results = engine.run_multi_strategy(
            price_data,
            strategies,
            weights,
            request.benchmark_ticker,
            benchmark_data
        )

        # 检查是否有错误（空策略等）
        if "error" in results:
            raise HTTPException(status_code=500, detail=results["error"])

        # 整理组合结果
        port_result = results.get("portfolio", {})
        port_curve = []
        if "equity_curve" in port_result and not port_result["equity_curve"].empty:
            df = port_result["equity_curve"].reset_index()
            df["date"] = df["date"].dt.strftime("%Y-%m-%d")
            port_curve = df.to_dict(orient="records")

        # 整理 individual 结果
        individual_results = {}
        for sid, result in results.get("individual", {}).items():
            ind_curve = []
            if "equity_curve" in result and not result["equity_curve"].empty:
                df = result["equity_curve"].reset_index()
                df["date"] = df["date"].dt.strftime("%Y-%m-%d")
                ind_curve = df.to_dict(orient="records")

            individual_results[sid] = {
                "metrics": {
                    "total_return": result.get("total_return", 0),
                    "sharpe_ratio": result.get("sharpe_ratio", 0),
                    "max_drawdown": result.get("max_drawdown", 0),
                    "volatility": result.get("volatility", 0),
                },
                "equity_curve": ind_curve,
                "weight": weights.get(sid, 0)
            }

        return {
            "portfolio": {
                "metrics": {
                    "total_return": port_result.get("total_return", 0),
                    "sharpe_ratio": port_result.get("sharpe_ratio", 0),
                    "max_drawdown": port_result.get("max_drawdown", 0),
                    "volatility": port_result.get("volatility", 0),
                    **port_result.get("benchmark_comparison", {})
                },
                "equity_curve": port_curve,
                "weights": port_result.get("weights", {}),
                "benchmark_comparison": port_result.get("benchmark_comparison", {})
            },
            "individual": individual_results
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Multi-strategy backtest failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize", response_model=Dict[str, Any])
async def optimize_parameters(request: ParameterOptimizationRequest):
    """
    参数优化 - v1.2.0 新增

    使用网格搜索优化策略参数。
    """
    if request.strategy_id not in BUILTIN_STRATEGIES:
        raise HTTPException(status_code=404, detail="Strategy not found")

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

        # 运行参数优化
        engine = BacktestEngine(initial_capital=request.initial_capital)
        results = engine.optimize_parameters(
            price_data,
            strategy_func,
            request.param_grid,
            request.objective,
            request.cv_days,
            parallel=True
        )

        # 格式化结果
        all_results_formatted = []
        for item in results.get("all_results", []):
            params_str = ", ".join(f"{k}={v}" for k, v in item["params"].items())
            all_results_formatted.append({
                "params": params_str,
                "params_dict": item["params"],
                "score": item["score"]
            })

        # 获取最优参数的详细回测结果
        best_params = results.get("best_params", {})
        if best_params:
            best_engine = BacktestEngine(initial_capital=request.initial_capital)
            best_result = best_engine.run(price_data, strategy_func, best_params)

            best_curve = []
            if "equity_curve" in best_result and not best_result["equity_curve"].empty:
                df = best_result["equity_curve"].reset_index()
                df["date"] = df["date"].dt.strftime("%Y-%m-%d")
                best_curve = df.to_dict(orient="records")

            return {
                "best_params": best_params,
                "best_score": results.get("best_score", 0),
                "objective": request.objective,
                "all_results": all_results_formatted,
                "best_result": {
                    "metrics": {
                        "total_return": best_result.get("total_return", 0),
                        "sharpe_ratio": best_result.get("sharpe_ratio", 0),
                        "max_drawdown": best_result.get("max_drawdown", 0),
                        "volatility": best_result.get("volatility", 0),
                    },
                    "equity_curve": best_curve
                }
            }

        return {
            "best_params": {},
            "best_score": results.get("best_score", 0),
            "objective": request.objective,
            "all_results": all_results_formatted,
            "best_result": None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Parameter optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extended-analysis", response_model=Dict[str, Any])
async def extended_analysis(
    equity_curve: List[Dict[str, Any]],
    trades: List[Dict[str, Any]],
    initial_capital: float = 100000,
    benchmark_ticker: Optional[str] = None
):
    """
    扩展绩效分析 - v1.2.0 新增

    计算信息比率、滚动夏普、交易分析、月度收益等详细指标。
    """
    try:
        analyzer = ExtendedPerformanceAnalyzer(initial_capital)

        for point in equity_curve:
            analyzer.add_equity_point(
                point["date"],
                point["equity"],
                point.get("cash", 0)
            )

        for trade in trades:
            analyzer.add_trade(
                trade["date"],
                trade["ticker"],
                trade["action"],
                trade["shares"],
                trade["price"],
                trade.get("cost", 0)
            )

        # 加载基准数据
        benchmark_series = None
        if benchmark_ticker:
            try:
                # 简化处理：在这里需要实际加载数据
                # 为简化API，暂时返回占位符
                pass
            except Exception as e:
                logger.warning(f"加载基准数据失败: {e}")

        metrics = analyzer.calculate_extended_metrics(benchmark_series)

        # 构建响应
        drawdown_details = [
            {
                "start_date": dd.start_date,
                "end_date": dd.end_date,
                "duration": dd.duration,
                "depth": dd.depth
            }
            for dd in metrics.drawdown_details
        ]

        monthly_returns = [
            {
                "year": mr.year,
                "month": mr.month,
                "return_rate": mr.return_rate,
                "is_positive": mr.is_positive
            }
            for mr in metrics.monthly_returns
        ]

        return {
            "metrics": {
                "total_return": metrics.total_return,
                "annual_return": metrics.annual_return,
                "annual_volatility": metrics.annual_volatility,
                "sharpe_ratio": metrics.sharpe_ratio,
                "information_ratio": metrics.information_ratio,
                "max_drawdown": metrics.max_drawdown,
                "sortino_ratio": metrics.sortino_ratio,
                "calmar_ratio": metrics.calmar_ratio,
                "beta": metrics.beta,
                "alpha": metrics.alpha,
                "r_squared": metrics.r_squared,
                "tracking_error": metrics.tracking_error
            },
            "drawdown_analysis": {
                "details": drawdown_details,
                "summary": {
                    "max_drawdown": f"{metrics.max_drawdown * 100:.2f}%",
                    "avg_drawdown": f"{metrics.avg_drawdown * 100:.2f}%",
                    "max_drawdown_duration": f"{metrics.drawdown_duration}天"
                }
            },
            "trade_analysis": {
                "total_trades": metrics.trade_analysis.total_trades,
                "win_rate": metrics.trade_analysis.win_rate,
                "profit_factor": metrics.trade_analysis.profit_factor,
                "avg_win": metrics.trade_analysis.avg_win,
                "avg_loss": metrics.trade_analysis.avg_loss,
                "frequency": metrics.trade_analysis.trade_frequency
            },
            "monthly_returns": monthly_returns,
            "best_month": {
                "year": metrics.best_month.year,
                "month": metrics.best_month.month,
                "return_rate": metrics.best_month.return_rate
            } if metrics.best_month else None,
            "worst_month": {
                "year": metrics.worst_month.year,
                "month": metrics.worst_month.month,
                "return_rate": metrics.worst_month.return_rate
            } if metrics.worst_month else None,
            "position_concentration": {
                "top_5_weight": metrics.top_5_weight,
                "top_10_weight": metrics.top_10_weight,
                "description": metrics.position_concentration.get("description", "N/A")
            }
        }

    except Exception as e:
        logger.error(f"Extended analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export", response_model=Dict[str, Any])
async def export_backtest(request: ExportBacktestRequest):
    """
    导出回测报告 - v1.2.0 新增

    支持导出为 HTML/ZendRPT/CSV 格式。
    """
    from datetime import datetime as dt

    try:
        # 生成扩展分析
        analyzer = ExtendedPerformanceAnalyzer(request.initial_capital)

        for point in request.equity_curve:
            # 转换日期字符串为 datetime
            date_value = point["date"]
            if isinstance(date_value, str):
                date_value = dt.strptime(date_value, "%Y-%m-%d")

            analyzer.add_equity_point(
                date_value,
                point["equity"],
                point.get("cash", 0)
            )

        for trade in request.trades:
            # 转换日期字符串为 datetime
            date_value = trade["date"]
            if isinstance(date_value, str):
                date_value = dt.strptime(date_value, "%Y-%m-%d")

            analyzer.add_trade(
                date_value,
                trade["ticker"],
                trade["action"],
                trade["shares"],
                trade["price"],
                trade.get("cost", 0)
            )

        metrics = analyzer.calculate_extended_metrics()

        report = generate_backtest_report(
            request.equity_curve,
            request.trades,
            request.initial_capital
        )

        # HTML 报告模板
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>回测报告 - {datetime.now().strftime("%Y-%m-%d")}</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        h1 {{ color: #1a1a1a; border-bottom: 2px solid #3b82f6; padding-bottom: 16px; }}
        h2 {{ color: #333; margin-top: 32px; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 24px 0; }}
        .metric-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #3b82f6; }}
        .metric-label {{ color: #666; font-size: 12px; text-transform: uppercase; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #1a1a1a; margin-top: 8px; }}
        .positive {{ color: #10b981; }}
        .negative {{ color: #ef4444; }}
        table {{ width: 100%; border-collapse: collapse; margin: 24px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; font-weight: 600; color: #333; }}
        .tr-buy {{ color: #ef4444; }}
        .tr-sell {{ color: #10b981; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 回测报告</h1>
        <p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>

        <h2>核心指标</h2>
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">总收益率</div>
                <div class="metric-value {'positive' if metrics.total_return >= 0 else 'negative'}">
                    {metrics.total_return * 100:.2f}%
                </div>
            </div>
            <div class="metric-card">
                <div class="metric-label">年化收益</div>
                <div class="metric-value {'positive' if metrics.annual_return >= 0 else 'negative'}">
                    {metrics.annual_return * 100:.2f}%
                </div>
            </div>
            <div class="metric-card">
                <div class="metric-label">夏普比率</div>
                <div class="metric-value">{metrics.sharpe_ratio:.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">最大回撤</div>
                <div class="metric-value negative">{metrics.max_drawdown * 100:.2f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">信息比率</div>
                <div class="metric-value">{metrics.information_ratio:.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">胜率</div>
                <div class="metric-value {'positive' if metrics.trade_analysis.win_rate >= 0.5 else 'negative'}">
                    {metrics.trade_analysis.win_rate * 100:.2f}%
                </div>
            </div>
        </div>

        <h2>交易分析</h2>
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">总交易次数</div>
                <div class="metric-value">{metrics.trade_analysis.total_trades}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">盈亏比</div>
                <div class="metric-value">{metrics.trade_analysis.profit_factor:.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">平均盈利</div>
                <div class="metric-value positive">+{metrics.trade_analysis.avg_win:.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">平均亏损</div>
                <div class="metric-value negative">-{metrics.trade_analysis.avg_loss:.2f}</div>
            </div>
        </div>

        <h2>月度收益</h2>
        <table>
            <tr>
                <th>年份</th>
                <th>月份</th>
                <th>收益率</th>
                <th>涨跌</th>
            </tr>
            {"".join(f"<tr><td>{mr['year']}</td><td>{mr['month']:02d}</td><td>{mr['return']}</td><td class='{'positive' if mr['positive'] else 'negative'}'>{mr['return']}</td></tr>" for mr in report["monthly_returns"][:12])}
        </table>

        <h2>回撤分析</h2>
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">最大回撤</div>
                <div class="metric-value negative">{report["drawdown_analysis"]["summary"]["最大回撤"]}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">平均回撤</div>
                <div class="metric-value">{report["drawdown_analysis"]["summary"]["平均回撤"]}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">最长回撤期</div>
                <div class="metric-value">{report["drawdown_analysis"]["summary"]["最长回撤期"]}</div>
            </div>
        </div>

        <p style="margin-top: 40px; color: #999; font-size: 12px; text-align: center;">
            本报告由 Quant-AI Dashboard 生成
        </p>
    </div>
</body>
</html>
"""

        return {
            "format": request.format,
            "data": report,
            "html": html_content,
            "exported_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/benchmarks", response_model=Dict[str, List[Dict[str, Any]]])
async def list_benchmarks():
    """
    获取可用基准指数列表 - v1.2.0 新增
    支持全市场、大盘、中盘、小盘、行业、商品等类别
    """
    # 支持的基准指数池（全收益指数支持）
    benchmarks = [
        # 全市场
        {"code": "000001.SH", "name": "上证指数", "type": "composite", "category": "全市场", "description": "上海证券综合指数", "is_total_return": False},
        {"code": "399001.SZ", "name": "深证成指", "type": "composite", "category": "全市场", "description": "深圳证券成分指数", "is_total_return": False},
        {"code": "000852.CSI", "name": "中证全指", "type": "composite", "category": "全市场", "description": "中证全指指数", "is_total_return": True},
        {"code": "000985.CSI", "name": "中证全指(全收益)", "type": "composite", "category": "全市场", "description": "中证全指指数(全收益)", "is_total_return": True},
        # 大盘
        {"code": "000300.SH", "name": "沪深300", "type": "large_cap", "category": "大盘", "description": "沪深300指数", "is_total_return": True},
        {"code": "000016.SH", "name": "上证50", "type": "blue_chip", "category": "大盘", "description": "上证50指数", "is_total_return": True},
        {"code": "000905.SH", "name": "中证500", "type": "mid_cap", "category": "大盘", "description": "中证500指数", "is_total_return": True},
        # 中盘
        {"code": "000906.SH", "name": "中证800", "type": "large_mid", "category": "中盘", "description": "中证800指数", "is_total_return": True},
        # 小盘
        {"code": "000852.SH", "name": "中证1000", "type": "small_cap", "category": "小盘", "description": "中证1000指数", "is_total_return": True},
        {"code": "399376.SZ", "name": "国证2000", "type": "small_cap", "category": "小盘", "description": "国证2000指数", "is_total_return": True},
        # 行业
        {"code": "H11023.CSI", "name": "中证医药", "type": "sector", "category": "行业", "description": "中证医药卫生指数", "is_total_return": True},
        {"code": "930604.CSI", "name": "中证TMT", "type": "sector", "category": "行业", "description": "中证TMT产业指数", "is_total_return": True},
        {"code": "H10121.CSI", "name": "中证消费", "type": "sector", "category": "行业", "description": "中证主要消费指数", "is_total_return": True},
        {"code": "H10521.CSI", "name": "中证金融", "type": "sector", "category": "行业", "description": "中证主要金融指数", "is_total_return": True},
        {"code": "H10221.CSI", "name": "中证能源", "type": "sector", "category": "行业", "description": "中证能源指数", "is_total_return": True},
        {"code": "H10321.CSI", "name": "中证工业", "type": "sector", "category": "行业", "description": "中证工业指数", "is_total_return": True},
        {"code": "H10421.CSI", "name": "中证原材料", "type": "sector", "category": "行业", "description": "中证原材料指数", "is_total_return": True},
        # 商品
        {"code": "N0000001.NH", "name": "南华商品", "type": "commodity", "category": "商品", "description": "南华商品指数", "is_total_return": False},
    ]

    return {"benchmarks": benchmarks}


@router.post("/compare-strategies", response_model=Dict[str, Any])
async def compare_strategies(
    equity_curves: Dict[str, List[Dict[str, Any]]],
    trades: Dict[str, List[Dict[str, Any]]],
    initial_capital: float = 100000
):
    """
    多策略对比分析 - v1.2.0 新增

    对多个策略的回测结果进行对比分析。
    """
    try:
        # 构建策略结果字典
        strategy_results = {}
        for name, curve in equity_curves.items():
            if name in trades:
                strategy_results[name] = {
                    "equity_curve": curve,
                    "trades": trades[name]
                }

        # 使用扩展分析器进行对比
        df = compare_multiple_strategies(strategy_results, initial_capital)

        # 计算相对指标
        metrics = df.to_dict(orient="records")

        return {
            "comparison_table": metrics,
            "summary": {
                "best_sharpe": max(m["sharpe_ratio"] for m in metrics if m["sharpe_ratio"]),
                "best_return": max(m["total_return"] for m in metrics if m["total_return"]),
                "lowest_drawdown": min(m["max_drawdown"] for m in metrics if m["max_drawdown"])
            }
        }

    except Exception as e:
        logger.error(f"Strategy comparison failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
