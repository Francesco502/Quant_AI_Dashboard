"""将决策仪表盘、大盘复盘等结构化内容格式化为 Markdown 文本，供各渠道推送。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Tuple


def format_dashboard_report(content: Dict[str, Any]) -> Tuple[str, str]:
    """格式化决策仪表盘报告：标题 + Markdown 正文。

    content 预期结构：{"results": [...], "summary": {...}?}
    每项 result 含：ticker, name, decision (conclusion, action, score, buy_price, stop_loss, target_price, checklist, highlights, risks), meta
    """
    results: List[Dict[str, Any]] = content.get("results") or []
    date_str = datetime.now().strftime("%Y-%m-%d")

    title = f"🎯 {date_str} 决策仪表盘"
    lines = [f"## {title}", ""]
    lines.append(f"共分析 {len(results)} 只标的")
    lines.append("")

    buy_c = sum(1 for r in results if (r.get("decision") or {}).get("action") == "买入")
    watch_c = sum(1 for r in results if (r.get("decision") or {}).get("action") == "观望")
    sell_c = sum(1 for r in results if (r.get("decision") or {}).get("action") == "卖出")
    lines.append(f"🟢 买入: {buy_c}  🟡 观望: {watch_c}  🔴 卖出: {sell_c}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for r in results:
        ticker = r.get("ticker", "")
        name = r.get("name") or ticker
        dec = r.get("decision") or {}
        action = dec.get("action", "观望")
        score = dec.get("score", 0)
        conclusion = dec.get("conclusion", "")

        lines.append(f"### {name} ({ticker})")
        lines.append(f"**结论** {conclusion}")
        lines.append(f"**操作** {action} | **评分** {score}")
        buy_price = dec.get("buy_price")
        stop_loss = dec.get("stop_loss")
        target_price = dec.get("target_price")
        if buy_price is not None or stop_loss is not None or target_price is not None:
            lines.append(f"- 买入价: {buy_price} | 止损: {stop_loss} | 目标: {target_price}")
        checklist = dec.get("checklist") or []
        if checklist:
            lines.append("- 检查清单:")
            for item in checklist:
                it = item if isinstance(item, dict) else {}
                lines.append(f"  - {it.get('item', item)}: {it.get('status', '')}")
        highlights = dec.get("highlights") or []
        if highlights:
            lines.append("- 利好: " + "; ".join(highlights[:3]))
        risks = dec.get("risks") or []
        if risks:
            lines.append("- 风险: " + "; ".join(risks[:3]))
        lines.append("")

    lines.append("---")
    lines.append(f"*生成时间: {datetime.now().strftime('%H:%M')}*")
    return title, "\n".join(lines)


def format_market_review_report(content: Dict[str, Any]) -> Tuple[str, str]:
    """格式化大盘复盘报告：标题 + Markdown 正文。

    content 预期结构：date, market, indices[], overview, sectors{gain, loss}, northbound
    """
    date_str = content.get("date") or datetime.now().date().isoformat()
    market = content.get("market", "cn")
    title = f"🎯 {date_str} 大盘复盘 ({market})"
    lines = [f"## {title}", ""]

    indices = content.get("indices") or []
    if indices:
        lines.append("### 主要指数")
        for idx in indices:
            name = idx.get("name", "")
            value = idx.get("value", 0)
            pct = idx.get("pct_change", 0)
            sign = "🟢" if pct >= 0 else "🔴"
            lines.append(f"- {name}: {value:.2f} ({sign}{pct:+.2f}%)")
        lines.append("")

    overview = content.get("overview") or {}
    if overview.get("up") is not None:
        lines.append("### 市场概况")
        lines.append(
            f"上涨: {overview.get('up', 0)} | 下跌: {overview.get('down', 0)} | "
            f"涨停: {overview.get('limit_up', 0)} | 跌停: {overview.get('limit_down', 0)}"
        )
        lines.append("")

    sectors = content.get("sectors") or {}
    gain = sectors.get("gain") or []
    loss = sectors.get("loss") or []
    if gain or loss:
        lines.append("### 板块表现")
        if gain:
            lines.append("领涨: " + "、".join(gain[:5]))
        if loss:
            lines.append("领跌: " + "、".join(loss[:5]))
        lines.append("")

    northbound = content.get("northbound") or {}
    if northbound.get("description"):
        lines.append("### 北向资金")
        lines.append(northbound.get("description", ""))
        lines.append("")

    lines.append("---")
    lines.append(f"*生成时间: {datetime.now().strftime('%H:%M')}*")
    return title, "\n".join(lines)
