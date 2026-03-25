"""每日智能分析（daily_stock_analysis 移植主入口）

对外暴露的主要函数：
- run_daily_analysis: 传入 tickers 与 market，返回决策列表与可选大盘复盘。
- run_daily_analysis_from_env: 从环境变量读取自选股并执行分析，供 daemon/Actions 使用。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from . import builder, prompts, parser, config
from core import llm_client
from core import scratchpad


@dataclass
class Decision:
    ticker: str
    name: Optional[str]
    raw_text: str
    structured: Dict[str, Any]
    meta: Dict[str, Any]


def _analyze_single(
    ticker: str,
    market: str = "cn",
    model: Optional[str] = None,
    provider_type: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Decision:
    """单标的分析主流程：构建上下文 → LLM → 解析"""
    ctx = builder.build_analysis_input(ticker=ticker, market=market)
    messages = prompts.build_messages(ctx)
    text_context = ctx.get("text_context", "") or ""

    scratchpad_path = None
    if scratchpad.is_scratchpad_enabled():
        request_id = scratchpad.generate_request_id(ticker, market)
        scratchpad_path = scratchpad.create_scratchpad(
            request_id=request_id,
            ticker=ticker,
            market=market,
            text_context_preview=text_context[:500],
        )

    t0 = time.time()
    raw = llm_client.chat_completion(
        messages,
        model=model,
        provider_type=provider_type,
        base_url=base_url,
    )
    elapsed_ms = int((time.time() - t0) * 1000)

    if scratchpad_path is not None:
        scratchpad.append_llm_call(
            scratchpad_path,
            model=model or "",
            prompt_token_estimate=min(4096, len(text_context) // 2),
            response_preview=raw[:500] if raw else "",
        )

    structured = parser.parse_decision(raw, meta=ctx.get("meta", {}))

    if scratchpad_path is not None:
        scratchpad.append_result(
            scratchpad_path,
            action=(structured.get("action") or ""),
            score=structured.get("score"),
            elapsed_ms=elapsed_ms,
        )

    return Decision(
        ticker=ticker,
        name=ctx.get("name"),
        raw_text=raw,
        structured=structured,
        meta=ctx.get("meta", {}),
    )


def run_daily_analysis(
    tickers: List[str],
    *,
    market: str = "cn",
    include_market_review: bool = False,
    model: Optional[str] = None,
    provider_type: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """运行多标的决策分析，可选附带大盘复盘。model 为空时使用服务端默认（如 .env GEMINI_MODEL）。"""
    results: List[Dict[str, Any]] = []
    for t in tickers:
        dec = _analyze_single(
            t,
            market=market,
            model=model,
            provider_type=provider_type,
            base_url=base_url,
        )
        payload = {
            "ticker": dec.ticker,
            "name": dec.name,
            "decision": dec.structured,
            "meta": dec.meta,
        }
        results.append(payload)

    # 汇总摘要信息，便于前端或推送使用
    buy_c = sum(1 for r in results if (r.get("decision") or {}).get("action") == "买入")
    watch_c = sum(1 for r in results if (r.get("decision") or {}).get("action") == "观望")
    sell_c = sum(1 for r in results if (r.get("decision") or {}).get("action") == "卖出")
    scores = [float((r.get("decision") or {}).get("score", 0)) for r in results if (r.get("decision") or {}).get("score") is not None]  # type: ignore[arg-type]
    avg_score = sum(scores) / len(scores) if scores else None

    resp: Dict[str, Any] = {
        "results": results,
        "summary": {
            "total": len(results),
            "buy": buy_c,
            "watch": watch_c,
            "sell": sell_c,
            "avg_score": avg_score,
        },
    }

    if include_market_review:
        try:
            from core import market_review

            resp["market_review"] = market_review.daily_review(market=market)
        except Exception as e:  # pragma: no cover - 容错
            resp["market_review_error"] = str(e)

    return resp


def run_daily_analysis_from_env(
    *,
    include_market_review: bool = True,
    send_push: bool = True,
) -> Dict[str, Any]:
    """从环境变量读取自选股并执行每日分析；可选推送决策与复盘到已配置渠道。"""
    tickers = config.get_default_tickers()
    market = config.get_default_market()
    result = run_daily_analysis(tickers, market=market, include_market_review=include_market_review)
    # 落盘保存决策，供后续回测使用
    try:
        from core.daily_analysis.storage import save_daily_decisions

        save_daily_decisions(result)
    except Exception as e:  # pragma: no cover
        result.setdefault("storage_error", str(e))
    if send_push:
        try:
            from core.notification import send_report

            send_report("dashboard", result)
            if result.get("market_review"):
                send_report("market_review", result["market_review"])
        except Exception as e:  # pragma: no cover
            result["notification_error"] = str(e)
    return result
