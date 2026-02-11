"""全市场扫描器模块

职责：
- 获取全市场（A股/港股）股票列表
- 分批次执行选股策略
- 汇总选股结果
"""

from __future__ import annotations

import logging
import time
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np

try:
    import akshare as ak
except ImportError:
    ak = None

from core.data_service import load_price_data, load_ohlcv_data
from core.technical_indicators import calculate_all_indicators, get_trading_signals
# from core.stocktradebyz.Selector import BBIKDJSelector # 动态导入以避免循环依赖

logger = logging.getLogger(__name__)

class MarketScanner:
    """全市场扫描器"""
    
    def __init__(self):
        self.market_cache = {} # {market_type: dataframe}
        self.last_update = {} # {market_type: timestamp}

    def get_market_tickers(self, market: str = "CN") -> List[Dict]:
        """
        获取全市场代码列表
        
        Args:
            market: 'CN' (A股), 'HK' (港股)
            
        Returns:
            List[{"ticker": str, "name": str}]
        """
        # 简单缓存机制 (1小时有效)
        if market in self.market_cache and time.time() - self.last_update.get(market, 0) < 3600:
            return self.market_cache[market]

        tickers = []
        try:
            if market == "CN":
                if ak:
                    # 获取 A 股实时行情作为基础列表 (包含 代码, 名称, 最新价等)
                    df = ak.stock_zh_a_spot_em()
                    # 筛选列
                    if not df.empty:
                        # 转换代码格式: 600000 -> 600000 (AkShare usually returns 6 digits)
                        # We need to adapt to our system's ticker format (usually 6 digits for A-share)
                        
                        # Filter out some garbage or delisted
                        df = df[df["最新价"] > 0] 
                        
                        for _, row in df.iterrows():
                            code = str(row["代码"])
                            name = str(row["名称"])
                            tickers.append({"ticker": code, "name": name})
            
            elif market == "HK":
                if ak:
                    df = ak.stock_hk_spot_em()
                    if not df.empty:
                        for _, row in df.iterrows():
                            code = str(row["代码"]) # usually 5 digits like 00700
                            name = str(row["名称"])
                            tickers.append({"ticker": code, "name": name})

        except Exception as e:
            logger.error(f"获取市场列表失败 ({market}): {e}")
            
        if tickers:
            self.market_cache[market] = tickers
            self.last_update[market] = time.time()
            
        return tickers

    def scan_market(
        self, 
        strategy_config: Dict, 
        market: str = "CN", 
        batch_size: int = 50,
        max_workers: int = 4,
        limit: int = 200 # 限制扫描总数，防止演示时过慢
    ) -> List[Dict]:
        """
        执行扫描
        
        Args:
            strategy_config: 策略配置 (e.g. {"name": "BBI_KDJ", "params": {...}})
            market: "CN" or "HK"
            batch_size: 每批次获取数据的股票数量
            limit: 最大扫描数量 (Debug用)
            
        Returns:
            符合条件的股票列表
        """
        all_tickers = self.get_market_tickers(market)
        if not all_tickers:
            return []
            
        # 仅取前 limit 个用于演示/测试
        target_tickers = [t["ticker"] for t in all_tickers[:limit]]
        
        results = []
        
        # 分批处理
        total_batches = (len(target_tickers) + batch_size - 1) // batch_size
        
        logger.info(f"开始扫描市场 {market}, 总数: {len(target_tickers)}, 批次: {total_batches}")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_batch = {}
            
            for i in range(0, len(target_tickers), batch_size):
                batch = target_tickers[i : i + batch_size]
                future = executor.submit(self._process_batch, batch, strategy_config)
                future_to_batch[future] = i // batch_size
                
            for future in as_completed(future_to_batch):
                batch_idx = future_to_batch[future]
                try:
                    batch_results = future.result()
                    if batch_results:
                        results.extend(batch_results)
                    logger.info(f"批次 {batch_idx + 1}/{total_batches} 完成, 发现 {len(batch_results)} 个目标")
                except Exception as e:
                    logger.error(f"批次 {batch_idx + 1} 失败: {e}")
                    
        return results

    def _process_batch(self, tickers: List[str], strategy_config: Dict) -> List[Dict]:
        """处理单个批次"""
        batch_results = []
        try:
            # 1. 批量加载数据 (Need enough history for indicators)
            # Default to 120 days
            
            # 使用 load_ohlcv_data 获取完整的 OHLCV 数据，而非仅 Close
            ohlcv_map = load_ohlcv_data(tickers, days=120)
            
            if not ohlcv_map:
                return []
                
            # 2. 对每个 ticker 计算指标并筛选
            # 动态导入策略类
            from core.stocktradebyz.Selector import BBIKDJSelector
            
            # 解析策略配置
            strategy_name = strategy_config.get("name", "BBI_KDJ")
            params = strategy_config.get("params", {})
            
            selector = None
            if strategy_name == "BBI_KDJ":
                selector = BBIKDJSelector(**params)
            
            if not selector:
                return []
            
            # 遍历该批次的所有股票
            for ticker, df in ohlcv_map.items():
                if df is None or df.empty:
                    continue
                    
                if len(df) < 60: # 数据过短
                    continue
                
                try:
                    # 使用 selector._passes_filters 判断是否符合策略
                    # 注意：_passes_filters 内部会计算指标
                    if selector._passes_filters(df):
                        # 获取最新价格和变动幅度供前端展示
                        latest = df.iloc[-1]
                        prev = df.iloc[-2] if len(df) > 1 else latest
                        
                        price = float(latest["close"])
                        prev_price = float(prev["close"])
                        change = (price - prev_price) / prev_price if prev_price > 0 else 0
                        
                        batch_results.append({
                            "ticker": ticker,
                            "price": price,
                            "change": change,
                            "volume": float(latest["volume"]) if "volume" in latest else 0,
                            "strategy": strategy_name,
                            "signal_date": str(latest.name.date()) if hasattr(latest.name, "date") else str(latest.name)
                        })
                except Exception as e:
                    # 单个股票计算失败不影响整体
                    logger.debug(f"Ticker {ticker} scan failed: {e}")
                    continue
            
            return batch_results
            
        except Exception as e:
            logger.error(f"批次处理失败: {e}")
            return []

    def _fetch_ohlcv_single(self, ticker: str) -> Optional[pd.DataFrame]:
        """获取单只股票的 OHLCV 数据"""
        # 简单封装，复用 data_service 逻辑有点复杂，这里快速实现一个
        # 仅支持 A 股
        try:
            if ak:
                # 区分 A 股和 港股
                if len(ticker) == 6 and ticker.isdigit():
                    df = ak.stock_zh_a_hist(symbol=ticker, period="daily", start_date="20230101", adjust="qfq")
                    if not df.empty:
                        df.rename(columns={
                            "日期": "date", "开盘": "open", "收盘": "close", 
                            "最高": "high", "最低": "low", "成交量": "volume"
                        }, inplace=True)
                        df["date"] = pd.to_datetime(df["date"])
                        df.set_index("date", inplace=True)
                        return df
                elif len(ticker) == 5 and ticker.isdigit():
                     # HK
                     df = ak.stock_hk_hist(symbol=ticker, period="daily", start_date="20230101", adjust="qfq")
                     if not df.empty:
                        df.rename(columns={
                            "日期": "date", "开盘": "open", "收盘": "close", 
                            "最高": "high", "最低": "low", "成交量": "volume"
                        }, inplace=True)
                        df["date"] = pd.to_datetime(df["date"])
                        df.set_index("date", inplace=True)
                        return df
        except Exception:
            pass
        return None
