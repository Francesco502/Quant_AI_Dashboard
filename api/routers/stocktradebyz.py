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
from core.data_service import get_active_data_sources, get_api_keys, load_price_data
from core.market_scanner import MarketScanner

router = APIRouter()
logger = logging.getLogger(__name__)

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
    selector_names: Optional[List[str]] = None
    selector_params: Optional[Dict[str, Dict[str, Any]]] = None
    tickers: Optional[List[str]] = None # 仅当 mode=universe 时使用

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

class AssetPoolRequest(BaseModel):
    tickers: List[Any] # Can be str (legacy) or Dict/Asset

class SingleAssetRequest(BaseModel):
    ticker: str
    alias: Optional[str] = ""

class AliasUpdateRequest(BaseModel):
    ticker: str
    alias: str

class DataSourceRequest(BaseModel):
    sources: List[str]
    api_keys: Optional[Dict[str, str]] = None

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
    """获取当前数据源配置（有序）及 API Keys"""
    try:
        return {
            "sources": get_active_data_sources(),
            "api_keys": get_api_keys()
        }
    except Exception as e:
        logger.error(f"获取数据源失败: {e}")
        return {"sources": ["AkShare", "Binance"], "api_keys": {}}

@router.post("/data-sources")
async def update_data_sources(request: DataSourceRequest):
    """更新数据源配置并触发联动"""
    try:
        old_sources = get_active_data_sources()
        _save_data_sources(request.sources, request.api_keys)
        
        # 联动逻辑：如果首选数据源改变，可能需要重新初始化连接或下载数据
        if old_sources != request.sources:
            logger.info(f"数据源配置已更新: {old_sources} -> {request.sources}")
            # TODO: 在此处触发实际的数据下载或重连逻辑
            # await data_manager.reload_sources(request.sources)
            
        return {"status": "success", "sources": request.sources}
    except Exception as e:
        logger.error(f"更新数据源失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新数据源失败: {str(e)}")

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
                pool_tickers = _load_asset_pool()
                if not pool_tickers:
                     raise HTTPException(status_code=400, detail="资产池为空，请先添加资产或指定 tickers")
                request.tickers = pool_tickers

            result_df = run_selectors_for_universe(
                tickers=request.tickers,
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
                selector_names=request.selector_names,
                selector_params=request.selector_params,
                progress_callback=_progress_callback
            )
        else:
            raise HTTPException(status_code=400, detail=f"未知的运行模式: {request.mode}")

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
async def get_asset_pool():
    """获取当前资产池（自动迁移旧格式）并附加最新价格"""
    try:
        raw_pool = _load_asset_pool()
        assets = []
        tickers_to_fetch = []
        
        # 1. 解析资产池
        for item in raw_pool:
            if isinstance(item, str):
                asset = Asset(ticker=item, name="", alias="")
                assets.append(asset)
                tickers_to_fetch.append(item)
            elif isinstance(item, dict):
                asset = Asset(**item)
                assets.append(asset)
                tickers_to_fetch.append(asset.ticker)
        
        # 2. 批量获取最新价格（尝试获取过去几天的数据以确保有数据）
        if tickers_to_fetch:
            try:
                # 使用 data_service 的统一接口
                # 注意：load_price_data 返回的是一个 DataFrame，列为 ticker，行为日期索引
                price_df = load_price_data(tickers_to_fetch, days=10)
                if price_df is not None and not price_df.empty:
                    # 统一将索引视为时间序列
                    price_df = price_df.sort_index()

                for asset in assets:
                    try:
                        if price_df is None or asset.ticker not in price_df.columns:
                            continue
                        series = price_df[asset.ticker].dropna()
                        if series.empty:
                            continue
                        # 直接取最后一个非空值作为最新价格/净值
                        asset.last_price = float(series.iloc[-1])
                    except Exception:
                        # 单个资产价格解析失败不影响整体返回
                        continue
            except Exception as e:
                logger.error(f"批量获取价格失败: {e}")
                # 不影响返回资产列表，只是没有价格
                pass

        return assets
    except Exception as e:
        logger.error(f"获取资产池失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取资产池失败: {str(e)}")

@router.post("/asset-pool")
async def update_asset_pool(request: AssetPoolRequest):
    """更新资产池"""
    try:
        # 兼容处理：如果是字符串列表，转为对象
        new_pool = []
        for item in request.tickers:
             if isinstance(item, str):
                 new_pool.append({"ticker": item, "name": "", "alias": ""})
             elif isinstance(item, dict):
                 new_pool.append(item)
             elif isinstance(item, Asset):
                 new_pool.append(item.dict())
        
        _save_asset_pool(new_pool)
        return {"status": "success", "count": len(new_pool)}
    except Exception as e:
        logger.error(f"更新资产池失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新资产池失败: {str(e)}")

def _fetch_asset_name(ticker: str) -> str:
    """尝试获取资产名称（支持A股和ETF）"""
    if not AKSHARE_AVAILABLE:
        return ""
    
    clean_ticker = ticker.replace(".SZ", "").replace(".SS", "").replace(".OF", "")
    is_otc_fund = ticker.endswith(".OF")
    
    # 0. 显式场外基金 (.OF)
    if is_otc_fund:
         try:
             # fund_em_open_fund_info 获取基金详情，包含名称
             info = ak.fund_em_open_fund_info(fund=clean_ticker, indicator="单位净值走势")
             # AkShare 接口返回格式多变，这里假设它可能失败，若失败尝试 fund_name_em 等
             # 实际上 fund_open_fund_info_em 不返回名称。
             # 使用 ak.fund_em_fund_name() 获取所有基金名称表太慢。
             # 尝试 ak.fund_individual_basic_info_xq(symbol=clean_ticker)
             pass
         except:
             pass
         
         # 尝试从 fund_em_open_fund_info 的某些字段，或者直接用 fund_name_em 搜索（如果缓存了）
         # 简单起见，尝试 fund_individual_basic_info_xq (雪球接口通常较快)
         try:
             # 注意：akshare 接口名可能变动，这里使用 fund_name_em 的搜索功能如果存在
             pass
         except:
             pass
         
         # 兜底：尝试获取净值数据，如果能获取到，暂时返回 "场外基金-代码"
         # 或者使用 fund_em_open_fund_info 返回的列名? 不行。
         return f"场外基金-{clean_ticker}"

    # 1. 尝试作为 A 股获取
    try:
        # stock_individual_info_em 有时会SSL失败，尝试更轻量的接口或忽略SSL错误
        # 这里为了稳健性，先尝试 fund_open (因为之前测试它是通的) 如果是ETF的话
        pass
    except:
        pass

    # 简单策略：优先尝试 fund_open_fund_info_em 如果看起来像基金
    if clean_ticker.isdigit() and (clean_ticker.startswith("1") or clean_ticker.startswith("5")):
         try:
             df = ak.fund_open_fund_info_em(symbol=clean_ticker, indicator="单位净值走势")
             # 这个接口不直接返回名称，需要另一个接口 fund_em_open_fund_info
             # 换用 fund_em_open_fund_info (基类信息)
             # 注意：AkShare 接口变动频繁，这里仅作尝试
             pass
         except:
             pass
    
    # 尝试 stock_individual_info_em (A股)
    try:
        # 注意：这里可能会抛出 SSL 错误，必须捕获
        info = ak.stock_individual_info_em(symbol=clean_ticker)
        # info 是 DataFrame, 包含 'item', 'value'
        if info is not None and not info.empty:
            name_row = info[info['item'] == '股票简称']
            if not name_row.empty:
                return name_row.iloc[0]['value']
    except Exception:
        pass
        
    return ""

@router.post("/asset-pool/add")
async def add_asset_to_pool(request: SingleAssetRequest):
    """添加单个资产到资产池"""
    try:
        current_pool = _load_asset_pool_as_dicts()
        ticker = request.ticker.strip().upper()
        
        # 检查是否存在
        exists = False
        for asset in current_pool:
            if asset["ticker"] == ticker:
                exists = True
                break
        
        if not exists:
            # 尝试获取名称
            name = _fetch_asset_name(ticker)
            new_asset = {
                "ticker": ticker,
                "name": name,
                "alias": request.alias or ""
            }
            current_pool.append(new_asset)
            _save_asset_pool(current_pool)
            return {"status": "success", "message": f"已添加 {ticker}", "pool": current_pool}
        else:
            return {"status": "success", "message": f"{ticker} 已存在", "pool": current_pool}
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
            return {"status": "success", "message": f"已移除 {ticker}", "pool": new_pool}
        else:
            return {"status": "success", "message": f"{ticker} 不在资产池中", "pool": new_pool}
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
            return {"status": "success", "message": f"已更新 {ticker} 别名", "pool": current_pool}
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

def _load_asset_pool_as_dicts() -> List[Dict[str, Any]]:
    """加载资产池并确保为字典列表格式"""
    raw_pool = _load_asset_pool()
    pool_dicts = []
    for item in raw_pool:
        if isinstance(item, str):
            pool_dicts.append({"ticker": item, "name": "", "alias": ""})
        elif isinstance(item, dict):
            pool_dicts.append(item)
    return pool_dicts

def _load_asset_pool() -> List[Any]:
    """从 user_state.json 加载资产池"""
    if not os.path.exists(USER_STATE_FILE):
        return []
    try:
        with open(USER_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("selected_tickers", [])
    except Exception:
        return []

def _save_asset_pool(tickers: List[Any]) -> None:
    """保存资产池到 user_state.json"""
    os.makedirs(os.path.dirname(USER_STATE_FILE), exist_ok=True)
    
    # 先读取现有数据以保留其他字段
    current_data = {}
    if os.path.exists(USER_STATE_FILE):
        try:
            with open(USER_STATE_FILE, "r", encoding="utf-8") as f:
                current_data = json.load(f)
        except Exception:
            pass
    
    current_data["selected_tickers"] = tickers
    
    with open(USER_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(current_data, f, ensure_ascii=False, indent=2)

def _save_data_sources(sources: List[str], api_keys: Optional[Dict[str, str]] = None) -> None:
    """保存数据源配置到 user_state.json"""
    os.makedirs(os.path.dirname(USER_STATE_FILE), exist_ok=True)
    
    current_data = {}
    if os.path.exists(USER_STATE_FILE):
        try:
            with open(USER_STATE_FILE, "r", encoding="utf-8") as f:
                current_data = json.load(f)
        except Exception:
            pass
    
    current_data["data_sources"] = sources
    if api_keys is not None:
        current_data["api_keys"] = api_keys
    
    with open(USER_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(current_data, f, ensure_ascii=False, indent=2)
