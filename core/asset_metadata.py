from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from time import time
from typing import Any, Dict, List, Optional
import json

try:
    import akshare as ak

    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    ak = None


USER_STATE_FILE = Path("data") / "user_state.json"
_CATALOG_LOCK = Lock()
_CATALOG_CACHE: Dict[str, Any] = {"loaded_at": 0.0, "items": []}
_CATALOG_TTL_SECONDS = 6 * 60 * 60
_EXCLUDED_EQUITY_PREFIXES = ("ST", "*ST", "S*ST", "SST")

_FUND_KEYWORDS = (
    "基金",
    "联接",
    "债",
    "债券",
    "货币",
    "滚动持有",
    "中短债",
    "理财",
)


@dataclass(frozen=True)
class AssetCatalogEntry:
    ticker: str
    name: str
    asset_type: str
    market: str
    source: str
    category: Optional[str] = None
    pinyin: str = ""


def normalize_asset_type(value: Any) -> Optional[str]:
    raw = str(value or "").strip().lower()
    if not raw:
        return None

    alias_map = {
        "fund": "fund",
        "mutual_fund": "fund",
        "otc_fund": "fund",
        "基金": "fund",
        "场外基金": "fund",
        "etf": "etf",
        "lof": "etf",
        "exchange_fund": "etf",
        "场内etf": "etf",
        "场内基金": "etf",
        "stock": "stock",
        "equity": "stock",
        "股票": "stock",
        "other": "other",
        "其他": "other",
    }
    return alias_map.get(raw)


def resolve_asset_type(
    ticker: str,
    *,
    asset_name: Optional[str] = None,
    asset_type: Optional[str] = None,
) -> str:
    normalized = normalize_asset_type(asset_type)
    code = str(ticker or "").strip().upper()
    name = str(asset_name or "")
    upper_name = name.upper()

    if normalized:
        return normalized

    if code.endswith(".OF"):
        return "fund"

    if "ETF" in upper_name or "LOF" in upper_name:
        if "联接" in name:
            return "fund"
        return "etf"

    if any(keyword in name for keyword in _FUND_KEYWORDS):
        return "fund"

    digits = "".join(ch for ch in code if ch.isdigit())
    if len(digits) == 6 and digits.startswith(("15", "50", "51", "56", "58")):
        return "etf"

    if code.endswith(".HK") or code.endswith(".US"):
        return "stock"

    if code.isalpha():
        return "stock"

    if len(digits) == 6:
        return "stock"

    return "other"


def supports_realtime_quote(
    ticker: str,
    *,
    asset_name: Optional[str] = None,
    asset_type: Optional[str] = None,
) -> bool:
    code = str(ticker or "").strip().upper()
    digits = "".join(ch for ch in code if ch.isdigit())
    if len(digits) != 6:
        return False

    resolved = resolve_asset_type(code, asset_name=asset_name, asset_type=asset_type)
    if resolved == "fund":
        return False
    if digits.startswith(("15", "50", "51", "56", "58")):
        return True
    return resolved in {"stock", "etf"}


def should_prefer_fund_nav(
    ticker: str,
    *,
    asset_name: Optional[str] = None,
    asset_type: Optional[str] = None,
) -> bool:
    return resolve_asset_type(
        ticker,
        asset_name=asset_name,
        asset_type=asset_type,
    ) == "fund" and not supports_realtime_quote(
        ticker,
        asset_name=asset_name,
        asset_type=asset_type,
    )


def _read_user_state() -> Dict[str, Any]:
    if not USER_STATE_FILE.exists():
        return {}
    try:
        with USER_STATE_FILE.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def _is_excluded_equity_name(name: str) -> bool:
    text = str(name or "").strip()
    upper_text = text.upper()
    return upper_text.startswith(_EXCLUDED_EQUITY_PREFIXES) or "退" in text


def get_asset_hint(ticker: str) -> Dict[str, Any]:
    code = str(ticker or "").strip().upper()
    digits = "".join(ch for ch in code if ch.isdigit())
    selected = _read_user_state().get("selected_tickers", [])
    if not isinstance(selected, list):
        return {}

    for item in selected:
        if not isinstance(item, dict):
            continue
        raw_ticker = str(item.get("ticker") or "").strip().upper()
        raw_digits = "".join(ch for ch in raw_ticker if ch.isdigit())
        if raw_ticker == code or (digits and raw_digits == digits):
            return {
                "ticker": raw_ticker or code,
                "name": item.get("name") or "",
                "asset_type": item.get("asset_type"),
                "market": item.get("market") or "CN",
            }
    return {}


def get_asset_pool_tickers(limit: Optional[int] = None) -> List[str]:
    selected = _read_user_state().get("selected_tickers", [])
    if not isinstance(selected, list):
        return []

    tickers: List[str] = []
    for item in selected:
        if isinstance(item, dict):
            ticker = str(item.get("ticker") or "").strip().upper()
        else:
            ticker = str(item or "").strip().upper()
        if not ticker or ticker in tickers:
            continue
        tickers.append(ticker)

    if limit and limit > 0:
        return tickers[: int(limit)]
    return tickers


def _load_fund_catalog() -> List[AssetCatalogEntry]:
    if not AKSHARE_AVAILABLE or ak is None:
        return []
    df = ak.fund_name_em()
    if df is None or df.empty:
        return []

    code_col = df.columns[0]
    pinyin_col = df.columns[1] if len(df.columns) > 1 else None
    name_col = df.columns[2] if len(df.columns) > 2 else df.columns[0]
    category_col = df.columns[3] if len(df.columns) > 3 else None

    items: List[AssetCatalogEntry] = []
    for _, row in df.iterrows():
        ticker = str(row.get(code_col) or "").strip()
        name = str(row.get(name_col) or "").strip()
        if not ticker or not name or _is_excluded_equity_name(name):
            continue
        category = str(row.get(category_col) or "").strip() if category_col else ""
        pinyin = str(row.get(pinyin_col) or "").strip().upper() if pinyin_col else ""
        items.append(
            AssetCatalogEntry(
                ticker=ticker,
                name=name,
                asset_type=resolve_asset_type(ticker, asset_name=name, asset_type="fund"),
                market="CN",
                source="fund_name_em",
                category=category or None,
                pinyin=pinyin,
            )
        )
    return items


def _load_stock_catalog() -> List[AssetCatalogEntry]:
    if not AKSHARE_AVAILABLE or ak is None:
        return []
    df = ak.stock_info_a_code_name()
    if df is None or df.empty:
        return []

    code_col = df.columns[0]
    name_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]

    items: List[AssetCatalogEntry] = []
    for _, row in df.iterrows():
        ticker = str(row.get(code_col) or "").strip()
        name = str(row.get(name_col) or "").strip()
        if not ticker or not name:
            continue
        items.append(
            AssetCatalogEntry(
                ticker=ticker,
                name=name,
                asset_type="stock",
                market="CN",
                source="stock_info_a_code_name",
                category="A股",
            )
        )
    return items


def _load_catalog_items() -> List[AssetCatalogEntry]:
    with _CATALOG_LOCK:
        now = time()
        cached_items = _CATALOG_CACHE.get("items")
        loaded_at = float(_CATALOG_CACHE.get("loaded_at") or 0.0)
        if cached_items and now - loaded_at < _CATALOG_TTL_SECONDS:
            return list(cached_items)

        items = _load_fund_catalog() + _load_stock_catalog()
        deduped: Dict[tuple[str, str, str], AssetCatalogEntry] = {}
        for item in items:
            deduped[(item.ticker, item.name, item.asset_type)] = item

        merged = list(deduped.values())
        _CATALOG_CACHE["loaded_at"] = now
        _CATALOG_CACHE["items"] = merged
        return list(merged)


def search_assets(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    text = str(query or "").strip()
    if not text:
        return []

    normalized = text.upper()
    digits = "".join(ch for ch in normalized if ch.isdigit())
    results: List[tuple[int, AssetCatalogEntry]] = []

    for item in _load_catalog_items():
        code = item.ticker.upper()
        name = item.name.upper()
        pinyin = item.pinyin.upper()

        score = 0
        if digits and code == digits:
            score = 140
        elif code == normalized:
            score = 138
        elif digits and code.startswith(digits):
            score = 124
        elif code.startswith(normalized):
            score = 120
        elif digits and digits in code:
            score = 108
        elif normalized == name:
            score = 112
        elif normalized in name:
            score = 96 if name.startswith(normalized) else 84
        elif pinyin and normalized in pinyin:
            score = 72 if pinyin.startswith(normalized) else 60

        if score <= 0:
            continue

        if item.asset_type == "fund":
            score += 2
        elif item.asset_type == "etf":
            score += 1
        results.append((score, item))

    results.sort(key=lambda pair: (-pair[0], pair[1].ticker, pair[1].name))
    top_items = results[: max(1, min(int(limit), 50))]

    return [
        {
            "ticker": item.ticker,
            "name": item.name,
            "asset_type": item.asset_type,
            "market": item.market,
            "source": item.source,
            "category": item.category,
            "score": score,
        }
        for score, item in top_items
    ]


def list_cn_a_share_tickers(limit: Optional[int] = None) -> List[str]:
    tickers: List[str] = []

    try:
        from core.tushare_provider import list_active_a_share_tickers

        for item in list_active_a_share_tickers(limit=limit):
            ticker = str(item.get("ticker") or "").strip().upper()
            if ticker and ticker not in tickers:
                tickers.append(ticker)
    except Exception:
        pass

    if not tickers:
        for item in _load_stock_catalog():
            ticker = str(item.ticker or "").strip().upper()
            if not ticker or ticker in tickers or _is_excluded_equity_name(item.name):
                continue
            tickers.append(ticker)

    if limit and limit > 0:
        return tickers[: int(limit)]
    return tickers
