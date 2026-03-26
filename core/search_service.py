"""News and sentiment search helpers.

Current implementation prefers Tavily and keeps a stable output contract for
future providers such as SerpAPI, Bocha, or Brave.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _get_env_keys(name: str) -> List[str]:
    """Read a comma-separated API key list from the environment."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _tavily_search(query: str, max_age_days: int, limit: int) -> List[Dict[str, Any]]:
    """Search news through Tavily when keys are configured."""
    keys = _get_env_keys("TAVILY_API_KEYS")
    if not keys:
        return []
    api_key = keys[0]

    try:
        from tavily import TavilyClient  # type: ignore[import]
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning("tavily-python is not installed, skipping Tavily search: %s", exc)
        return []

    client = TavilyClient(api_key=api_key)
    time_period = f"{max_age_days}d"

    try:
        response = client.search(  # type: ignore[attr-defined]
            query=query,
            search_depth="basic",
            max_results=limit,
            include_answer=False,
            time_period=time_period,
        )
    except Exception as exc:
        logger.warning("Tavily search failed: %s", exc)
        return []

    items: List[Dict[str, Any]] = []
    for result in response.get("results", []):
        items.append(
            {
                "title": result.get("title") or "",
                "url": result.get("url") or "",
                "snippet": result.get("content") or result.get("snippet") or "",
                "source": "tavily",
                "date": result.get("published_date") or None,
            }
        )
    return items


def search_news(query: str, max_age_days: int = 3, limit: int = 10) -> List[Dict[str, Any]]:
    """Search recent news and return a normalized result list."""
    results: List[Dict[str, Any]] = []

    try:
        results.extend(_tavily_search(query, max_age_days=max_age_days, limit=limit))
    except Exception as exc:  # pragma: no cover
        logger.warning("Tavily search raised an unexpected error: %s", exc)

    # Additional providers such as SerpAPI / Bocha / Brave can be added here.

    seen = set()
    deduped: List[Dict[str, Any]] = []
    for item in results:
        url = item.get("url") or ""
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(item)

    return deduped[:limit]
