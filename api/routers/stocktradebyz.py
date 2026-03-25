"""
StockTradebyZ 战法与资产池管理 API
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Dict, Optional, Any
from pydantic import BaseModel
import pandas as pd
import json
import os
from pathlib import Path
from datetime import datetime
from time import time
import logging

from core.stocktradebyz_adapter import (
    get_default_selector_configs,
    run_selectors_for_universe,
    run_selectors_for_market,
    STZ_DIR,
    STZ_CONFIG_PATH
)
from core.data_store import BASE_DIR
from core.app_utils import save_selector_results
from core.asset_metadata import (
    get_asset_hint,
    resolve_asset_type,
    search_assets,
    should_prefer_fund_nav,
    supports_realtime_quote,
)
from core.data_service import (
    get_active_data_sources,
    get_api_key_status,
    load_cn_realtime_quotes_sina,
    load_price_data,
)
from core.market_scanner import MarketScanner

router = APIRouter()
logger = logging.getLogger(__name__)
_ASSET_POOL_CACHE_TTL_SECONDS = 180
_ASSET_POOL_RESPONSE_CACHE: Dict[str, Any] = {
    "signature": "",
    "loaded_at": 0.0,
    "items": [],
}

# 全局扫描器实例
market_scanner = MarketScanner()

# 用户状态文件路径 (兼容 Streamlit)
USER_STATE_FILE = os.path.join("data", "user_state.json")

# ----------------------------------------------------------------------
#  数据模型
# ----------------------------------------------------------------------

class ScanMarketRequest(BaseModel):
    market: str = "CN" # CN / HK
    strategy_config: Dict[str, Any]
    limit: int = 100

class SelectorConfigModel(BaseModel):
    class_name: str
    alias: str
    activate: bool
    params: Dict[str, Any]

class RunStrategyRequest(BaseModel):
    trade_date: str
    mode: str = "universe"  # universe (资产池) 或 market (全市场)
    market: str = "CN"  # CN / HK
    selector_names: Optional[List[str]] = None
    selector_params: Optional[Dict[str, Dict[str, Any]]] = None
    tickers: Optional[List[str]] = None # 仅当 mode=universe 时使用
    min_score: float = 60.0
    top_n: int = 20

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    ak = None

class Asset(BaseModel):
    ticker: str
    name: Optional[str] = ""
    alias: Optional[str] = ""
    last_price: Optional[float] = None
    asset_type: Optional[str] = None
    last_price_date: Optional[str] = None
    price_source: Optional[str] = None

class AssetPoolRequest(BaseModel):
    tickers: List[Any] # Can be str (legacy) or Dict/Asset

class SingleAssetRequest(BaseModel):
    ticker: str
    asset_name: Optional[str] = ""
    asset_type: Optional[str] = None
    alias: Optional[str] = ""


class AssetSearchResult(BaseModel):
    ticker: str
    name: str
    asset_type: str
    market: str = "CN"
    source: Optional[str] = None
    category: Optional[str] = None
    score: Optional[int] = None

class AliasUpdateRequest(BaseModel):
    ticker: str
    alias: str

class DataSourceRequest(BaseModel):
    sources: List[str]
    api_keys: Optional[Dict[str, str]] = None


def _post_process_selector_results(
    result_df: pd.DataFrame,
    *,
    min_score: float,
    top_n: int,
) -> pd.DataFrame:
    """Normalize selector output to ticker-level rows with score/action/topN filtering."""
    if result_df is None or result_df.empty:
        return pd.DataFrame()

    df = result_df.copy()
    if "ticker" not in df.columns:
        return pd.DataFrame()

    if "score" not in df.columns:
        selector_col = "selector_class" if "selector_class" in df.columns else None
        if selector_col:
            count_df = (
                df.groupby("ticker")[selector_col]
                .nunique()
                .reset_index(name="selector_hits")
            )
        else:
            count_df = (
                df.groupby("ticker")
                .size()
                .reset_index(name="selector_hits")
            )
        df = df.merge(count_df, on="ticker", how="left")
        max_hits = float(df["selector_hits"].max() or 1.0)
        # Convert "number of triggered selectors" to 0-100 score.
        df["score"] = (df["selector_hits"] / max_hits * 100.0).round(2)

    agg_map: Dict[str, Any] = {"score": "max"}
    if "name" in df.columns:
        agg_map["name"] = "first"
    if "last_close" in df.columns:
        agg_map["last_close"] = "last"
    if "trade_date" in df.columns:
        agg_map["trade_date"] = "last"
    if "selector_alias" in df.columns:
        agg_map["selector_alias"] = lambda s: ", ".join(
            sorted({str(v).strip() for v in s if str(v).strip()})
        )
    if "selector_class" in df.columns:
        agg_map["selector_class"] = lambda s: ", ".join(
            sorted({str(v).strip() for v in s if str(v).strip()})
        )

    grouped = df.groupby("ticker", as_index=False).agg(agg_map)
    grouped["score"] = pd.to_numeric(grouped["score"], errors="coerce").fillna(0.0)
    grouped = grouped[grouped["score"] >= float(min_score)]
    grouped = grouped.sort_values("score", ascending=False)
    if top_n > 0:
        grouped = grouped.head(int(top_n))

    if "action" not in grouped.columns:
        grouped["action"] = grouped["score"].apply(
            lambda s: "强烈买入" if s >= 85 else ("买入" if s >= 60 else "观察")
        )

    return grouped.reset_index(drop=True)

# ----------------------------------------------------------------------
#  路由实现
# ----------------------------------------------------------------------

@router.post("/scan/market")
async def scan_market(request: ScanMarketRequest):
    """
    全市场扫描
    """
    try:
        results = market_scanner.scan_market(
            strategy_config=request.strategy_config,
            market=request.market,
            limit=request.limit
        )
        return {"status": "success", "count": len(results), "results": results}
    except Exception as e:
        logger.error(f"扫描失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/data-sources")
async def get_data_sources():
    """获取当前数据源配置。统一由服务端环境变量控制。"""
    try:
        return {
            "sources": get_active_data_sources(),
            "api_key_status": get_api_key_status(),
            "configuration_mode": "env_locked",
        }
    except Exception as e:
        logger.error(f"获取数据源失败: {e}")
        return {
            "sources": ["AkShare", "Binance"],
            "api_key_status": {"Tushare": False, "AlphaVantage": False},
            "configuration_mode": "env_locked",
        }

@router.post("/data-sources")
async def update_data_sources(request: DataSourceRequest):
    """禁止在前端修改数据源配置。"""
    raise HTTPException(
        status_code=403,
        detail="数据源和 API Key 由服务器环境变量统一管理，前端不允许修改。",
    )

@router.get("/strategies", response_model=List[SelectorConfigModel])
async def list_strategies():
    """获取所有可用战法配置"""
    try:
        configs = get_default_selector_configs()
        return [
            SelectorConfigModel(
                class_name=cfg.class_name,
                alias=cfg.alias,
                activate=cfg.activate,
                params=cfg.params
            )
            for cfg in configs
        ]
    except Exception as e:
        logger.error(f"获取战法列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取战法列表失败: {str(e)}")

@router.post("/run")
async def run_strategy(request: RunStrategyRequest):
    """运行战法选股"""
    try:
        trade_date = pd.to_datetime(request.trade_date)
        
        result_df = None
        if request.mode == "universe":
            if not request.tickers:
                # 尝试从资产池加载
                pool_tickers = _normalize_ticker_list(_load_asset_pool())
                if not pool_tickers:
                     raise HTTPException(status_code=400, detail="资产池为空，请先添加资产或指定 tickers")
                request.tickers = pool_tickers

            result_df = run_selectors_for_universe(
                tickers=_normalize_ticker_list(request.tickers),
                trade_date=trade_date,
                selector_names=request.selector_names,
                selector_params=request.selector_params
            )
        elif request.mode == "market":
            # 全市场扫描
            def _progress_callback(p, msg):
                logger.info(f"Progress: {p:.2f} - {msg}")

            result_df = run_selectors_for_market(
                trade_date=trade_date,
                market=request.market,
                selector_names=request.selector_names,
                selector_params=request.selector_params,
                progress_callback=_progress_callback
            )
        else:
            raise HTTPException(status_code=400, detail=f"未知的运行模式: {request.mode}")

        result_df = _post_process_selector_results(
            result_df,
            min_score=request.min_score,
            top_n=request.top_n,
        )

        if result_df is None or result_df.empty:
            return {"status": "success", "count": 0, "data": [], "message": "未找到符合条件的标的"}

        # 保存结果
        save_success = save_selector_results(result_df, request.trade_date)
        
        # 转换结果用于返回
        # 处理 NaN 值以避免 JSON 序列化错误
        result_df = result_df.fillna("")
        records = result_df.to_dict("records")
        
        return {
            "status": "success", 
            "count": len(records), 
            "data": records,
            "saved": save_success,
            "message": "选股完成"
        }

    except Exception as e:
        logger.error(f"运行战法失败: {e}")
        raise HTTPException(status_code=500, detail=f"运行战法失败: {str(e)}")

@router.get("/asset-pool", response_model=List[Asset])
async def get_asset_pool(force_refresh: bool = Query(False)):
    """获取当前资产池并附带按资产类型路由后的最新价格。"""
    try:
        return _build_asset_pool_response(_load_asset_pool_as_dicts(), force_refresh=force_refresh)
    except Exception as e:
        logger.error(f"获取资产池失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取资产池失败: {str(e)}")


@router.get("/asset-search", response_model=List[AssetSearchResult])
async def search_asset_candidates(
    q: str = Query(..., min_length=1, description="资产代码或名称关键字"),
    limit: int = Query(12, ge=1, le=30),
):
    """按代码或名称搜索资产，让用户确认后再添加。"""
    try:
        return search_assets(q, limit=limit)
    except Exception as e:
        logger.error(f"搜索资产失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索资产失败: {str(e)}")

@router.post("/asset-pool")
async def update_asset_pool(request: AssetPoolRequest):
    """更新资产池"""
    try:
        new_pool = _dedupe_pool_assets([_normalize_pool_asset_entry(item) for item in request.tickers])
        _save_asset_pool(new_pool)
        return {"status": "success", "count": len(new_pool)}
    except Exception as e:
        logger.error(f"更新资产池失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新资产池失败: {str(e)}")

@router.post("/asset-pool/add")
async def add_asset_to_pool(request: SingleAssetRequest):
    """添加单个资产到资产池"""
    try:
        current_pool = _load_asset_pool_as_dicts()
        new_asset = _normalize_pool_asset_entry(
            {
                "ticker": request.ticker,
                "name": request.asset_name,
                "asset_type": request.asset_type,
                "alias": request.alias,
            }
        )

        exists = any(asset["ticker"] == new_asset["ticker"] for asset in current_pool)

        if not exists:
            current_pool.append(new_asset)
            current_pool = _dedupe_pool_assets(current_pool)
            _save_asset_pool(current_pool)
            return {
                "status": "success",
                "message": f"已添加 {new_asset['ticker']}",
                "pool": _build_asset_pool_response(current_pool),
            }

        return {
            "status": "success",
            "message": f"{new_asset['ticker']} 已存在",
            "pool": _build_asset_pool_response(current_pool),
        }
    except Exception as e:
        logger.error(f"添加资产失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加资产失败: {str(e)}")

@router.post("/asset-pool/delete")
async def delete_asset_from_pool(request: SingleAssetRequest):
    """从资产池移除单个资产"""
    try:
        current_pool = _load_asset_pool_as_dicts()
        ticker = request.ticker.strip().upper()
        
        new_pool = [a for a in current_pool if a["ticker"] != ticker]
        
        if len(new_pool) < len(current_pool):
            _save_asset_pool(new_pool)
            return {"status": "success", "message": f"已移除 {ticker}", "pool": _build_asset_pool_response(new_pool)}
        else:
            return {"status": "success", "message": f"{ticker} 不在资产池中", "pool": _build_asset_pool_response(new_pool)}
    except Exception as e:
        logger.error(f"移除资产失败: {e}")
        raise HTTPException(status_code=500, detail=f"移除资产失败: {str(e)}")

@router.post("/asset-pool/update-alias")
async def update_asset_alias(request: AliasUpdateRequest):
    """更新资产别名"""
    try:
        current_pool = _load_asset_pool_as_dicts()
        ticker = request.ticker.strip().upper()
        
        updated = False
        for asset in current_pool:
            if asset["ticker"] == ticker:
                asset["alias"] = request.alias
                updated = True
                break
        
        if updated:
            _save_asset_pool(current_pool)
            return {"status": "success", "message": f"已更新 {ticker} 别名", "pool": _build_asset_pool_response(current_pool)}
        else:
            raise HTTPException(status_code=404, detail="资产不存在")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新别名失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新别名失败: {str(e)}")

@router.get("/history")
async def list_history():
    """获取历史选股记录列表"""
    try:
        base_path = Path(BASE_DIR)
        signals_dir = base_path / "signals" / "z_selectors"
        if not signals_dir.exists():
            return []
        
        files = sorted(signals_dir.glob("*.csv"), reverse=True)
        history = []
        for f in files:
            try:
                # 文件名即日期
                date_str = f.stem
                # 读取行数作为简单统计
                df = pd.read_csv(f)
                count = len(df)
                history.append({
                    "date": date_str,
                    "count": count,
                    "file": f.name
                })
            except Exception:
                continue
        return history
    except Exception as e:
        logger.error(f"获取历史记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取历史记录失败: {str(e)}")

@router.get("/history/{date_str}")
async def get_history_detail(date_str: str):
    """获取指定日期的选股详情"""
    try:
        base_path = Path(BASE_DIR)
        signals_dir = base_path / "signals" / "z_selectors"
        file_path = signals_dir / f"{date_str}.csv"
        
        if not file_path.exists():
             raise HTTPException(status_code=404, detail="未找到该日期的选股记录")
        
        df = pd.read_csv(file_path)
        df = df.fillna("")
        return df.to_dict("records")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取历史详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取历史详情失败: {str(e)}")


# ----------------------------------------------------------------------
#  辅助函数
# ----------------------------------------------------------------------

LEGACY_TICKER_MAP = {
    "016858": "006195",
}


def _lookup_catalog_asset(ticker: str) -> Dict[str, Any]:
    normalized = str(ticker or "").strip().upper()
    digits = "".join(ch for ch in normalized if ch.isdigit())
    query = digits or normalized
    if not query:
        return {}

    for item in search_assets(query, limit=8):
        item_ticker = str(item.get("ticker") or "").strip().upper()
        item_digits = "".join(ch for ch in item_ticker if ch.isdigit())
        if item_ticker == normalized or (digits and item_digits == digits):
            return item
    return {}


def _normalize_pool_ticker(raw_ticker: Any) -> str:
    ticker = str(raw_ticker or "").strip().upper()
    digits = "".join(ch for ch in ticker if ch.isdigit())
    if digits and digits in LEGACY_TICKER_MAP:
        mapped = LEGACY_TICKER_MAP[digits]
        if ticker == digits:
            return mapped
        return ticker.replace(digits, mapped)
    return ticker


def _normalize_pool_asset_entry(item: Any) -> Dict[str, Any]:
    raw: Dict[str, Any]
    if isinstance(item, Asset):
        raw = item.dict()
    elif isinstance(item, dict):
        raw = dict(item)
    else:
        raw = {"ticker": item}

    ticker = _normalize_pool_ticker(raw.get("ticker"))
    if not ticker:
        raise ValueError("Asset pool entry is missing ticker")

    hint = get_asset_hint(ticker)
    raw_name = str(raw.get("name") or raw.get("asset_name") or "").strip()
    raw_type = raw.get("asset_type")
    catalog_item: Dict[str, Any] = {}
    if not raw_name or not (raw_type or hint.get("asset_type")):
        catalog_item = _lookup_catalog_asset(ticker)

    name = str(raw_name or hint.get("name") or catalog_item.get("name") or "").strip()
    alias = str(raw.get("alias") or "").strip()
    asset_type = resolve_asset_type(
        ticker,
        asset_name=name,
        asset_type=raw_type or hint.get("asset_type") or catalog_item.get("asset_type"),
    )

    return {
        "ticker": ticker,
        "name": name,
        "alias": alias,
        "asset_type": asset_type,
    }


def _dedupe_pool_assets(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for item in items:
        normalized = _normalize_pool_asset_entry(item)
        ticker = normalized["ticker"]
        if ticker in seen:
            continue
        seen.add(ticker)
        deduped.append(normalized)
    return deduped


def _load_asset_pool_as_dicts() -> List[Dict[str, Any]]:
    """加载资产池并确保为统一结构。"""
    raw_pool = _load_asset_pool()
    normalized = _dedupe_pool_assets(raw_pool)
    if raw_pool != normalized:
        _save_asset_pool(normalized)
    return normalized


def _normalize_ticker_list(items: Optional[List[Any]]) -> List[str]:
    normalized: List[str] = []
    seen: set[str] = set()

    for item in items or []:
        ticker = ""
        if isinstance(item, str):
            ticker = item
        elif isinstance(item, dict):
            ticker = str(item.get("ticker", ""))
        elif hasattr(item, "ticker"):
            ticker = str(getattr(item, "ticker", ""))

        clean_ticker = _normalize_pool_ticker(ticker.strip().upper())
        if not clean_ticker or clean_ticker in seen:
            continue

        seen.add(clean_ticker)
        normalized.append(clean_ticker)

    return normalized

# 首次部署时的默认资产池（种子数据）
DEFAULT_ASSET_POOL = [
    {"ticker": "013281", "name": "国泰海通30天滚动持有中短债债券A", "alias": "", "asset_type": "fund"},
    {"ticker": "002611", "name": "博时黄金ETF联接C", "alias": "", "asset_type": "fund"},
    {"ticker": "160615", "name": "鹏华沪深300ETF联接(LOF)A", "alias": "", "asset_type": "fund"},
    {"ticker": "006195", "name": "国金量化多因子股票A", "alias": "", "asset_type": "fund"},
    {"ticker": "159755", "name": "广发国证新能源车电池ETF", "alias": "", "asset_type": "etf"},
    {"ticker": "006810", "name": "泰康港股通中证香港银行投资指数C", "alias": "", "asset_type": "fund"},
]


def _load_asset_pool() -> List[Any]:
    """从 user_state.json 加载资产池，首次部署自动种子化默认资产。"""
    if not os.path.exists(USER_STATE_FILE):
        _save_asset_pool(DEFAULT_ASSET_POOL)
        return list(DEFAULT_ASSET_POOL)
    try:
        with open(USER_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            pool = data.get("selected_tickers", [])
            if not pool:
                _save_asset_pool(DEFAULT_ASSET_POOL)
                return list(DEFAULT_ASSET_POOL)
            return pool
    except Exception:
        return list(DEFAULT_ASSET_POOL)


def _extract_latest_price(series: Optional[pd.Series]) -> Optional[tuple[float, str]]:
    if series is None:
        return None
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return None
    latest_idx = pd.to_datetime(clean.index[-1])
    return float(clean.iloc[-1]), latest_idx.strftime("%Y-%m-%d")


def _pool_cache_signature(pool_items: List[Dict[str, Any]]) -> str:
    return json.dumps(pool_items, ensure_ascii=False, sort_keys=True)


def _invalidate_asset_pool_response_cache() -> None:
    _ASSET_POOL_RESPONSE_CACHE["signature"] = ""
    _ASSET_POOL_RESPONSE_CACHE["loaded_at"] = 0.0
    _ASSET_POOL_RESPONSE_CACHE["items"] = []


def _restore_cached_asset_pool_response(signature: str) -> Optional[List[Asset]]:
    if _ASSET_POOL_RESPONSE_CACHE.get("signature") != signature:
        return None
    loaded_at = float(_ASSET_POOL_RESPONSE_CACHE.get("loaded_at") or 0.0)
    if time() - loaded_at > _ASSET_POOL_CACHE_TTL_SECONDS:
        return None

    cached_items = _ASSET_POOL_RESPONSE_CACHE.get("items") or []
    return [Asset(**item) for item in cached_items]


def _store_cached_asset_pool_response(signature: str, items: List[Asset]) -> None:
    _ASSET_POOL_RESPONSE_CACHE["signature"] = signature
    _ASSET_POOL_RESPONSE_CACHE["loaded_at"] = time()
    _ASSET_POOL_RESPONSE_CACHE["items"] = [item.dict() for item in items]


def _build_asset_pool_response(pool_items: List[Dict[str, Any]], *, force_refresh: bool = False) -> List[Asset]:
    assets = [Asset(**_normalize_pool_asset_entry(item)) for item in pool_items]
    if not assets:
        return []

    signature = _pool_cache_signature([asset.dict() for asset in assets])
    if not force_refresh:
        cached = _restore_cached_asset_pool_response(signature)
        if cached is not None:
            return cached

    tickers = [asset.ticker for asset in assets]
    price_df = pd.DataFrame()
    try:
        price_df = load_price_data(tickers, days=70, refresh_stale=force_refresh)
    except Exception as exc:
        logger.warning("读取资产池通用价格失败: %s", exc)

    realtime_candidates = [
        asset.ticker
        for asset in assets
        if supports_realtime_quote(
            asset.ticker,
            asset_name=asset.name,
            asset_type=asset.asset_type,
        )
    ]
    realtime_quotes: Dict[str, Dict[str, object]] = {}
    if realtime_candidates:
        try:
            realtime_quotes = load_cn_realtime_quotes_sina(realtime_candidates)
        except Exception as exc:
            logger.warning("读取资产池实时行情失败: %s", exc)

    for asset in assets:
        latest_price: Optional[float] = None
        latest_date: Optional[str] = None
        price_source: Optional[str] = None

        if not price_df.empty and asset.ticker in price_df.columns:
            latest = _extract_latest_price(price_df[asset.ticker])
            if latest:
                latest_price, latest_date = latest
                price_source = "fund_nav" if should_prefer_fund_nav(
                    asset.ticker,
                    asset_name=asset.name,
                    asset_type=asset.asset_type,
                ) else "price_history"

        quote = realtime_quotes.get(asset.ticker)
        if quote:
            quote_price = quote.get("price")
            if isinstance(quote_price, (int, float)) and float(quote_price) > 0:
                latest_price = float(quote_price)
                latest_date = str(quote.get("trade_date") or latest_date or "")
                price_source = "sina_realtime"

        asset.last_price = latest_price
        asset.last_price_date = latest_date
        asset.price_source = price_source

    _store_cached_asset_pool_response(signature, assets)
    return assets


def _save_asset_pool(tickers: List[Any]) -> None:
    """保存资产池到 user_state.json。"""
    os.makedirs(os.path.dirname(USER_STATE_FILE), exist_ok=True)

    current_data = {}
    if os.path.exists(USER_STATE_FILE):
        try:
            with open(USER_STATE_FILE, "r", encoding="utf-8") as f:
                current_data = json.load(f)
        except Exception:
            pass

    current_data["selected_tickers"] = _dedupe_pool_assets([_normalize_pool_asset_entry(item) for item in tickers])

    with open(USER_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(current_data, f, ensure_ascii=False, indent=2)
    _invalidate_asset_pool_response_cache()
