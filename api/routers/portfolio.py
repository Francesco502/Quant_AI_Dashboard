"""Portfolio analysis API routes."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from api.auth import UserInDB, require_permission
from core.rbac import Permission
from core.data_service import identify_asset_type
from core.decision_dashboard import get_decision_dashboard
from core.portfolio_analyzer import PortfolioAnalyzer


logger = logging.getLogger(__name__)
router = APIRouter()

MAX_PORTFOLIO_HOLDINGS = 80


class PortfolioItem(BaseModel):
    ticker: str
    shares: float = Field(..., gt=0)
    cost_price: Optional[float] = None


class PortfolioAnalysisRequest(BaseModel):
    holdings: List[PortfolioItem] = Field(..., min_length=1, max_length=MAX_PORTFOLIO_HOLDINGS)
    target_allocation: Optional[Dict[str, float]] = None


class ReturnContributionItem(BaseModel):
    ticker: str
    return_pct: float
    contribution_pct: float
    weight: float


class PortfolioAnalysisResponse(BaseModel):
    summary: Dict[str, Any]
    asset_metrics: List[Dict[str, Any]]
    risk_metrics: Dict[str, float]
    recommendations: List[Dict[str, Any]]
    correlations: List[List[float]]
    contributions: List[ReturnContributionItem]
    return_attribution: Dict[str, Any]
    risk_contributions: List[Dict[str, Any]]
    factor_exposures: List[Dict[str, Any]]
    benchmark_attribution: Dict[str, Any]
    highly_correlated_pairs: List[Dict[str, Any]]
    technical_signals: List[Dict[str, Any]]
    timestamp: str


@router.post("/analyze", response_model=PortfolioAnalysisResponse)
async def analyze_portfolio(
    request: PortfolioAnalysisRequest,
    current_user: UserInDB = Depends(require_permission(Permission.VIEW_DATA)),
):
    """Analyze portfolio-level risk/return and diversification."""
    del current_user
    try:
        tickers = [h.ticker for h in request.holdings]
        position_shares = {
            str(h.ticker).strip().upper(): float(h.shares)
            for h in request.holdings
            if str(h.ticker).strip() and float(h.shares) > 0
        }
        weights: Optional[List[float]] = None

        if request.target_allocation:
            total = float(sum(request.target_allocation.values()))
            if total > 0:
                weights = [float(request.target_allocation.get(t, 0.0)) / total for t in tickers]

        analyzer = PortfolioAnalyzer(
            tickers=tickers,
            weights=weights,
            position_shares=position_shares,
        )
        result = await run_in_threadpool(analyzer.analyze, days=365)
        if "error" in result:
            raise HTTPException(status_code=400, detail=str(result["error"]))

        recommendations: List[Dict[str, Any]] = []
        omitted_tickers = result.get("summary", {}).get("omitted_tickers", [])
        if omitted_tickers:
            recommendations.append(
                {
                    "type": "data_coverage",
                    "message": f"以下标的因缺少价格数据未纳入组合风险计算：{', '.join(omitted_tickers[:8])}",
                    "tickers": omitted_tickers,
                }
            )
        for asset in result.get("asset_metrics", []):
            ticker = asset.get("ticker")
            sharpe = float(asset.get("sharpe_ratio", 0.0))
            weight = float(asset.get("weight", 0.0))

            # 1. 检查年化夏普比率较低的资产
            if sharpe < 0.5:
                recommendations.append(
                    {
                        "ticker": ticker,
                        "type": "risk",
                        "message": f"标的 {ticker} 的年化夏普比率偏低 ({sharpe:.2f})，说明单位风险带来的超额收益不足，建议考虑调整该资产的持仓权重以优化组合整体风险收益比。",
                    }
                )

            # 2. 检查单一资产权重过高（集中度风险）
            if weight > 0.40:
                recommendations.append(
                    {
                        "ticker": ticker,
                        "type": "concentration",
                        "message": f"单一标的 {ticker} 在投资组合中的权重占比高达 {weight*100:.1f}%，过度集中可能会放大单一资产黑天鹅事件对组合权益的冲击，建议将单只资产权重控制在 30% 以下，以维持分散投资的优势。",
                    }
                )

        # 3. 检查高相关性资产对并给出建议
        correlated_pairs = result.get("highly_correlated_pairs", [])
        if correlated_pairs:
            pairs_desc = ", ".join([f"{p.get('ticker_1', p.get('t1'))} 与 {p.get('ticker_2', p.get('t2'))}(相关系数 {p.get('correlation', p.get('corr', 0.0)):.2f})" for p in correlated_pairs[:2]])
            recommendations.append(
                {
                    "type": "diversification",
                    "message": f"组合中检测到高相关性资产对 ({pairs_desc})。在市场大幅波动时，高相关性资产往往会同涨同跌，建议通过引入黄金、债券等低相关性资产来增强组合的抗风险能力。",
                    "pairs_preview": correlated_pairs[:2],
                }
            )

        # 4. 检查组合整体波动率
        summary = result.get("summary", {})
        ann_vol = float(summary.get("annual_volatility", 0.0))
        if ann_vol > 0.25:
            recommendations.append(
                {
                    "type": "portfolio_volatility",
                    "message": f"投资组合的整体年化波动率达到 {ann_vol*100:.1f}%，属于高风险高波动特征。建议关注当前下行风险（如 VaR 指标），或适当增配低波动理财/债券型基金进行平滑。",
                }
            )

        summary = result.get("summary", {})

        return PortfolioAnalysisResponse(
            summary=summary,
            asset_metrics=result.get("asset_metrics", []),
            risk_metrics={
                "max_drawdown": float(summary.get("max_drawdown", 0.0)),
                "var_95": float(summary.get("var_95", 0.0)),
                "cvar_95": float(summary.get("cvar_95", 0.0)),
            },
            recommendations=recommendations,
            correlations=result.get("correlations", []),
            contributions=result.get("contributions", []),
            return_attribution=result.get("return_attribution", {}),
            risk_contributions=result.get("risk_contributions", []),
            factor_exposures=result.get("factor_exposures", []),
            benchmark_attribution=result.get("benchmark_attribution", {}),
            highly_correlated_pairs=correlated_pairs,
            technical_signals=result.get("technical_signals", []),
            timestamp=str(result.get("timestamp") or datetime.now(timezone.utc).isoformat()),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Portfolio analysis failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/decision/{ticker}")
async def get_stock_decision(
    ticker: str,
    current_user: UserInDB = Depends(require_permission(Permission.VIEW_DATA)),
):
    """Get single-stock decision dashboard payload."""
    del current_user
    try:
        return await run_in_threadpool(get_decision_dashboard, ticker)
    except Exception as e:
        logger.error("Decision analysis failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/asset-type/{ticker}")
async def get_asset_type(
    ticker: str,
    current_user: UserInDB = Depends(require_permission(Permission.VIEW_DATA)),
):
    """Identify asset type and market from ticker."""
    del current_user
    try:
        result = await run_in_threadpool(identify_asset_type, ticker)
        return {"ticker": ticker, **result}
    except Exception as e:
        logger.error("Asset type detection failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
