"""Stock scanner routes."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.data_service import load_price_data
from core.data_store import BASE_DIR
from core.market_scanner import MarketScanner
from core.scanner.scanner_engine import get_scanner_engine
from core.scanner.strategies import list_strategies


logger = logging.getLogger(__name__)
router = APIRouter()


class StockSelectorRequest(BaseModel):
    tickers: Optional[List[str]] = None
    strategy: Optional[str] = "all"
    top_n: int = 20
    min_score: int = 60


class StockSelectorResponse(BaseModel):
    stocks: List[Dict]
    total_count: int
    timestamp: str


def _resolve_strategy_name(strategy_key: Optional[str]) -> Optional[str]:
    if not strategy_key:
        return None
    key = strategy_key.strip().lower()
    if key in {"all", "*"}:
        return None

    available = list_strategies()
    if not available:
        return None

    # Exact match by registered name.
    for item in available:
        name = str(item.get("name", ""))
        if key == name.lower():
            return name

    # Common frontend aliases.
    alias_keywords = {
        "ma": ["ma"],
        "rsi": ["rsi"],
        "trend": ["trend"],
        "breakout": ["break", "突破"],
        "value": ["value", "价值"],
    }
    keywords = alias_keywords.get(key, [key])
    for item in available:
        name = str(item.get("name", ""))
        lower_name = name.lower()
        if any(k in lower_name for k in keywords):
            return name

    return None


def _load_default_universe(limit: int = 500) -> List[str]:
    # 1) Try dynamic market universe from market scanner.
    try:
        rows = MarketScanner().get_market_tickers(market="CN")
        tickers = [str(r.get("ticker", "")).strip() for r in rows if r.get("ticker")]
        tickers = [t for t in tickers if t]
        if tickers:
            return tickers[:limit]
    except Exception:
        pass

    # 2) Fallback to local parquet repository.
    try:
        prices_dir = Path(BASE_DIR) / "prices"
        tickers: List[str] = []
        for fp in prices_dir.rglob("*.parquet"):
            code = fp.stem.strip().upper()
            if code.isdigit() and len(code) == 6:
                tickers.append(code)
        tickers = sorted(set(tickers))
        return tickers[:limit]
    except Exception:
        return []


@router.post("/select", response_model=StockSelectorResponse)
async def select_stocks(request: StockSelectorRequest):
    try:
        scan_top_n = max(1, int(request.top_n))
        scan_min_score = max(0, int(request.min_score))

        tickers = request.tickers or _load_default_universe(limit=max(scan_top_n * 20, 300))
        if not tickers:
            raise HTTPException(status_code=404, detail="No tickers available for scanning")

        price_df = load_price_data(tickers, days=365)
        if price_df.empty:
            raise HTTPException(status_code=404, detail="Unable to load price data")

        engine = get_scanner_engine()
        strategy_name = _resolve_strategy_name(request.strategy)

        if strategy_name:
            df = engine.scan_single_strategy(
                price_df,
                strategy_name=strategy_name,
                top_n=scan_top_n,
                min_score=scan_min_score,
            )
        else:
            df = engine.scan(
                price_df,
                top_n=scan_top_n,
                min_score=scan_min_score,
            )

        if df.empty:
            return StockSelectorResponse(
                stocks=[],
                total_count=0,
                timestamp=datetime.utcnow().isoformat(),
            )

        return StockSelectorResponse(
            stocks=df.to_dict("records"),
            total_count=int(len(df)),
            timestamp=datetime.utcnow().isoformat(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Stock scan failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies")
async def get_strategies():
    try:
        dynamic = list_strategies()
        normalized = []
        for item in dynamic:
            name = str(item.get("name", ""))
            normalized.append(
                {
                    "name": name,
                    "display_name": name,
                    "description": str(item.get("description", "")),
                }
            )
        if normalized:
            return {"strategies": normalized}
    except Exception:
        pass

    # Fallback static list.
    return {
        "strategies": [
            {"name": "all", "display_name": "综合策略", "description": "组合多策略扫描"},
            {"name": "ma", "display_name": "MA金叉", "description": "均线交叉趋势"},
            {"name": "rsi", "display_name": "RSI超卖", "description": "超卖反弹机会"},
            {"name": "trend", "display_name": "多头趋势", "description": "趋势延续"},
            {"name": "breakout", "display_name": "突破策略", "description": "价格突破关键位"},
            {"name": "value", "display_name": "价值策略", "description": "价值因子筛选"},
        ]
    }


@router.get("/hot")
async def get_hot_stocks(limit: int = 10):
    try:
        tickers = _load_default_universe(limit=max(30, limit * 3))
        if not tickers:
            return {"stocks": []}

        price_df = load_price_data(tickers, days=90)
        if price_df.empty:
            return {"stocks": []}

        returns = price_df.pct_change().dropna()
        if returns.empty:
            return {"stocks": []}

        cumulative = (1 + returns).cumprod()
        scores = (cumulative.iloc[-1] - 1) * 100

        stocks = []
        for ticker in scores.index:
            score = float(scores[ticker])
            stocks.append(
                {
                    "ticker": ticker,
                    "score": score,
                    "action": "买入" if score > 20 else ("观望" if score > 0 else "卖出"),
                }
            )

        stocks.sort(key=lambda x: x["score"], reverse=True)
        return {"stocks": stocks[:limit]}
    except Exception as e:
        logger.error("Failed to fetch hot stocks: %s", e)
        return {"stocks": []}
