"""Portfolio analysis API routes."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.data_service import identify_asset_type
from core.decision_dashboard import get_decision_dashboard
from core.portfolio_analyzer import PortfolioAnalyzer


logger = logging.getLogger(__name__)
router = APIRouter()


class PortfolioItem(BaseModel):
    ticker: str
    shares: int
    cost_price: Optional[float] = None


class PortfolioAnalysisRequest(BaseModel):
    holdings: List[PortfolioItem]
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
async def analyze_portfolio(request: PortfolioAnalysisRequest):
    """Analyze portfolio-level risk/return and diversification."""
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

        result = PortfolioAnalyzer(
            tickers=tickers,
            weights=weights,
            position_shares=position_shares,
        ).analyze(days=365)
        if "error" in result:
            raise HTTPException(status_code=400, detail=str(result["error"]))

        recommendations: List[Dict[str, Any]] = []
        for asset in result.get("asset_metrics", []):
            if float(asset.get("sharpe_ratio", 0.0)) < 0.5:
                recommendations.append(
                    {
                        "ticker": asset.get("ticker"),
                        "type": "risk",
                        "message": f"{asset.get('ticker')} has low Sharpe ratio; consider reducing risk exposure.",
                    }
                )

        correlated_pairs = result.get("highly_correlated_pairs", [])
        if correlated_pairs:
            recommendations.append(
                {
                    "type": "diversification",
                    "message": "Highly correlated assets detected; consider better diversification.",
                    "pairs_preview": correlated_pairs[:2],
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
            timestamp=str(result.get("timestamp") or datetime.utcnow().isoformat()),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Portfolio analysis failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/decision/{ticker}")
async def get_stock_decision(ticker: str):
    """Get single-stock decision dashboard payload."""
    try:
        return get_decision_dashboard(ticker)
    except Exception as e:
        logger.error("Decision analysis failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/asset-type/{ticker}")
async def get_asset_type(ticker: str):
    """Identify asset type and market from ticker."""
    try:
        result = identify_asset_type(ticker)
        return {"ticker": ticker, **result}
    except Exception as e:
        logger.error("Asset type detection failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
