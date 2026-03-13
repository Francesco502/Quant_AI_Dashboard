"""新闻 / 舆情搜索服务（Phase 2）

优先使用 Tavily，其他数据源（SerpAPI / Bocha / Brave）预留扩展点。

【扩展约定】
- 接口签名固定：search_news(query, max_age_days=3, limit=10) -> List[Dict]
- 返回列表项统一字段：title, url, snippet, source, date（可选）
- 新增数据源时在 search_news() 内调用 _xxx_search()，结果 extend 到 results，最后统一去重、截断
- 环境变量约定：TAVILY_API_KEYS（逗号分隔）、SERPAPI_API_KEYS、BOCHA_API_KEYS、BRAVE_API_KEYS
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import os
import logging

logger = logging.getLogger(__name__)


def _get_env_keys(name: str) -> List[str]:
    """从逗号分隔的 KEY 列表环境变量中取出 key 集合"""
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def _tavily_search(query: str, max_age_days: int, limit: int) -> List[Dict[str, Any]]:
    """使用 Tavily 进行新闻搜索"""
    keys = _get_env_keys("TAVILY_API_KEYS")
    if not keys:
        return []
    api_key = keys[0]

    try:
        from tavily import TavilyClient  # type: ignore[import]
    except Exception as e:  # pragma: no cover - 环境未安装 tavily-python
        logger.warning("tavily-python 未安装，跳过 Tavily 搜索: %s", e)
        return []

    client = TavilyClient(api_key=api_key)

    # time_period 语义由 Tavily 决定，这里用简单的 \"Xd\" 表示最近 X 天
    time_period = f"{max_age_days}d"

    try:
        resp = client.search(  # type: ignore[attr-defined]
            query=query,
            search_depth="basic",
            max_results=limit,
            include_answer=False,
            time_period=time_period,
        )
    except Exception as e:
        logger.warning("Tavily 搜索失败: %s", e)
        return []

    items: List[Dict[str, Any]] = []
    for r in resp.get("results", []):
        items.append(
            {
                "title": r.get("title") or "",
                "url": r.get("url") or "",
                "snippet": r.get("content") or r.get("snippet") or "",
                "source": "tavily",
                "date": r.get("published_date") or None,
            }
        )
    return items


def search_news(query: str, max_age_days: int = 3, limit: int = 10) -> List[Dict[str, Any]]:
    """统一新闻/舆情搜索入口

    当前实现：
      - 优先使用 Tavily；
      - 其他数据源（SerpAPI / Bocha / Brave）留作后续扩展；
      - 未配置任何 KEY 时返回空列表。
    """
    results: List[Dict[str, Any]] = []

    # 1. Tavily
    try:
        results.extend(_tavily_search(query, max_age_days=max_age_days, limit=limit))
    except Exception as e:  # pragma: no cover
        logger.warning("Tavily 搜索异常: %s", e)

    # TODO: 2. SerpAPI / Bocha / Brave 可在此处按需扩展

    # 简单去重（按 url）
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for item in results:
        url = item.get("url") or ""
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(item)

    return deduped[:limit]

