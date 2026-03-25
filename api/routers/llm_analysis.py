"""LLM analysis API routes."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from core import llm_client, market_review
from core.daily_analysis import run_daily_analysis, run_daily_analysis_from_env
from core.daily_analysis.backtest import backtest_ticker
from core.data_service import load_price_data


router = APIRouter()


def _llm_not_configured_message() -> str:
    status = llm_client.get_status()
    if status.get("configured") and status.get("error"):
        return (
            "LLM provider is configured but unavailable: "
            f"{status['error']}"
        )

    return (
        "LLM is not configured. Prefer setting LLM_PROVIDER=openai_compat and one of "
        "OPENAI_API_KEY, ARK_API_KEY, or VOLCENGINE_API_KEY. "
        "Gemini, Anthropic, OpenRouter, and Ollama remain available as explicit alternatives."
    )


def _build_request_config(
    provider_type: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> Optional[llm_client.LLMConfig]:
    return llm_client.build_request_config(
        provider=provider_type,
        base_url=base_url,
        model=model,
    )


def _request_not_configured_message(config_override: Optional[llm_client.LLMConfig]) -> str:
    if config_override is None:
        return _llm_not_configured_message()

    status = llm_client.get_status(config_override)
    if status.get("configured") and status.get("error"):
        return (
            "Selected LLM interface is configured but unavailable: "
            f"{status['error']}"
        )
    if status.get("provider") == "anthropic":
        return "Selected Anthropic-compatible interface is missing ANTHROPIC_API_KEY."
    return (
        "Selected OpenAI-compatible interface is missing a usable API key. "
        "Set OPENAI_API_KEY, ARK_API_KEY, or VOLCENGINE_API_KEY."
    )


def _ensure_llm_configured(config_override: Optional[llm_client.LLMConfig] = None) -> None:
    if not llm_client.is_available(config_override):
        raise HTTPException(status_code=503, detail=_request_not_configured_message(config_override))


@router.get("/config")
async def llm_config() -> Dict[str, Any]:
    """Return active provider/model settings for frontend display."""
    payload = llm_client.get_status()
    if not payload["configured"]:
        payload["message"] = _llm_not_configured_message()
    elif not payload["available"]:
        payload["message"] = _llm_not_configured_message()
    elif payload.get("selection_mode") == "explicit":
        payload["message"] = (
            "当前系统默认 LLM 已由 .env 中的 LLM_PROVIDER 显式指定。"
            "页面里的 URL 与模型只会在关闭“跟随系统默认”后作为临时覆盖。"
        )
    else:
        payload["message"] = (
            "当前系统默认 LLM 来自环境自动识别。"
            "建议在 .env 中显式设置 LLM_PROVIDER，避免多套密钥并存时默认来源不透明。"
        )
    return payload


@router.get("/health-check")
async def llm_health_check(
    model: Optional[str] = Query(None, description="Optional model override."),
    provider_type: Optional[str] = Query(None, description="Interface type: openai_compat or anthropic."),
    base_url: Optional[str] = Query(None, description="Optional runtime base URL override."),
) -> Dict[str, Any]:
    """Run a lightweight provider health check without market-data dependencies."""
    config_override = _build_request_config(provider_type=provider_type, base_url=base_url, model=model)
    _ensure_llm_configured(config_override)
    response = llm_client.chat_completion(
        [
            {"role": "system", "content": "Reply with a short plain-text health acknowledgment."},
            {"role": "user", "content": "ping"},
        ],
        model=model,
        provider_type=provider_type,
        base_url=base_url,
    ).strip()

    if not response:
        raise HTTPException(status_code=502, detail="LLM provider returned an empty response.")

    status = llm_client.get_status(config_override)
    return {
        "status": "ok",
        "provider": status["provider"],
        "model": model or status.get("model"),
        "base_url": status.get("base_url"),
        "response_preview": response[:120],
    }


class DashboardRequest(BaseModel):
    tickers: List[str] = Field(..., description="Ticker list.")
    market: str = Field("cn", description="Market: cn/hk/us")
    include_market_review: bool = Field(False, description="Attach market review in response.")
    model: Optional[str] = Field(None, description="Optional model override.")
    provider_type: Optional[str] = Field(None, description="Optional interface type override.")
    base_url: Optional[str] = Field(None, description="Optional runtime base URL override.")


@router.post("/dashboard")
async def dashboard(req: DashboardRequest) -> Dict[str, Any]:
    """Run multi-ticker decision dashboard analysis."""
    if not req.tickers:
        raise HTTPException(status_code=400, detail="tickers cannot be empty")
    config_override = _build_request_config(
        provider_type=req.provider_type,
        base_url=req.base_url,
        model=req.model,
    )
    _ensure_llm_configured(config_override)
    try:
        return run_daily_analysis(
            tickers=req.tickers,
            market=req.market,
            include_market_review=req.include_market_review,
            model=req.model,
            provider_type=req.provider_type,
            base_url=req.base_url,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Decision analysis failed: {exc}") from exc


class RunDailyRequest(BaseModel):
    tickers: Optional[List[str]] = Field(None, description="Optional ticker override list.")


@router.post("/run-daily")
async def run_daily(
    req: Optional[RunDailyRequest] = Body(None),
    push: bool = Query(True, description="Whether to send configured notifications."),
) -> Dict[str, Any]:
    """Run daily analysis once."""
    _ensure_llm_configured()
    try:
        tickers = (req.tickers if req else None) or None
        if tickers:
            return run_daily_analysis(tickers=tickers, include_market_review=True)
        return run_daily_analysis_from_env(include_market_review=True, send_push=push)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Run daily analysis failed: {exc}") from exc


@router.get("/backtest")
async def backtest(ticker: str, horizon_days: int = 5) -> Dict[str, Any]:
    """Backtest LLM decisions for one ticker."""
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker cannot be empty")
    _ensure_llm_configured()
    try:
        return backtest_ticker(ticker=ticker, horizon_days=horizon_days)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Backtest failed: {exc}") from exc


class NaturalQueryRequest(BaseModel):
    query: str = Field(..., description="Natural language question.")


def _extract_json(text: str) -> str:
    raw = text.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        return raw[start : end + 1]
    return raw


def _extract_ticker(query: str) -> str:
    patterns = [
        r"(?i)\b(?:hk)?\d{5,6}\b",
        r"(?i)\b(?:sz|sh)\d{6}\b",
        r"\b\d{6}\b",
        r"\b[A-Z]{1,5}\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, query)
        if match:
            return match.group(0).strip()
    return ""


def _guess_market(query: str, ticker: str) -> str:
    lower = query.lower()
    if "\u7f8e\u80a1" in query or re.search(r"\b(us|nyse|nasdaq)\b", lower):
        return "us"
    if "\u6e2f\u80a1" in query or ticker.lower().startswith("hk"):
        return "hk"
    return "cn"


def _parse_query_heuristically(query: str) -> Dict[str, Any]:
    lower = query.lower()
    ticker = _extract_ticker(query)
    market = _guess_market(query, ticker)

    days_match = re.search(r"(\d+)\s*(?:day|days|d|\u5929)", lower)
    days = int(days_match.group(1)) if days_match else 60

    if any(token in lower for token in ["price trend", "trend", "price", "chart"]) or any(
        token in query for token in ["\u8d70\u52bf", "\u4ef7\u683c", "\u8d8b\u52bf", "\u66f2\u7ebf"]
    ):
        intent = "price_trend"
    elif any(token in lower for token in ["market review", "market summary"]) or any(
        token in query
        for token in [
            "\u5927\u76d8",
            "\u5e02\u573a\u590d\u76d8",
            "\u590d\u76d8",
            "\u5e02\u573a\u6982\u89c8",
        ]
    ):
        intent = "market_review"
    else:
        intent = "decision"

    return {
        "ticker": ticker,
        "market": market,
        "intent": intent,
        "days": days,
    }


def _merge_parsed_query(base: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)

    ticker = str(candidate.get("ticker") or "").strip()
    if ticker:
        merged["ticker"] = ticker

    market = str(candidate.get("market") or "").strip().lower()
    if market in {"cn", "hk", "us"}:
        merged["market"] = market

    intent = str(candidate.get("intent") or "").strip().lower()
    if intent in {"decision", "analysis", "price_trend", "market_review"}:
        merged["intent"] = intent

    try:
        days = int(candidate.get("days") or merged.get("days") or 60)
        if days > 0:
            merged["days"] = days
    except Exception:
        pass

    return merged


@router.post("/natural-query")
async def natural_query(req: NaturalQueryRequest) -> Dict[str, Any]:
    """Natural language entrypoint for lightweight financial Q&A."""
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query cannot be empty")

    parsed = _parse_query_heuristically(query)
    parser = "heuristic"
    if llm_client.is_configured():
        messages = [
            {
                "role": "system",
                "content": (
                    "Convert user query into JSON with keys: ticker, market, intent, days. "
                    "intent must be one of decision, price_trend, market_review."
                ),
            },
            {"role": "user", "content": query},
        ]
        try:
            llm_parsed = json.loads(_extract_json(llm_client.chat_completion(messages)))
            if isinstance(llm_parsed, dict):
                parsed = _merge_parsed_query(parsed, llm_parsed)
                parser = "llm"
        except Exception:
            parser = "heuristic"

    intent = str(parsed.get("intent") or "decision").strip().lower()
    ticker = str(parsed.get("ticker") or "").strip()
    market = str(parsed.get("market") or "cn").strip().lower()
    try:
        days = int(parsed.get("days") or 60)
    except Exception:
        days = 60

    response: Dict[str, Any] = {
        "query": query,
        "parsed": {"ticker": ticker, "market": market, "intent": intent, "days": days},
        "parser": parser,
    }

    if intent in ("decision", "analysis"):
        if not ticker:
            raise HTTPException(status_code=400, detail="ticker is required for decision analysis")
        _ensure_llm_configured()
        try:
            response["analysis"] = run_daily_analysis(
                tickers=[ticker],
                market=market,
                include_market_review=False,
            )
        except Exception as exc:  # noqa: BLE001
            response["analysis_error"] = str(exc)
        return response

    if intent == "price_trend":
        if not ticker:
            raise HTTPException(status_code=400, detail="ticker is required for price trend")
        try:
            frame = load_price_data([ticker], days=days)
            series = frame[ticker].dropna() if ticker in frame.columns else None
            if series is not None and not series.empty:
                points = [
                    {
                        "date": idx.isoformat() if hasattr(idx, "isoformat") else str(idx),
                        "close": float(val),
                    }
                    for idx, val in series.items()
                ]
                response["price_trend"] = {
                    "last_close": float(series.iloc[-1]),
                    "start_date": points[0]["date"],
                    "end_date": points[-1]["date"],
                    "series": points,
                }
        except Exception as exc:  # noqa: BLE001
            response["price_trend_error"] = str(exc)

        if llm_client.is_configured():
            try:
                response["analysis"] = run_daily_analysis(
                    tickers=[ticker],
                    market=market,
                    include_market_review=False,
                )
            except Exception as exc:  # noqa: BLE001
                response["analysis_error"] = str(exc)

        return response

    if intent == "market_review":
        try:
            response["market_review"] = market_review.daily_review(market=market)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001
            response["market_review_error"] = str(exc)
        return response

    response["warning"] = f"Unknown intent: {intent}"
    return response
