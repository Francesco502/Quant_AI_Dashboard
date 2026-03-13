"""全市场扫描器模块

职责：
- 获取全市场（A股/港股）股票列表
- 分批次执行选股策略
- 汇总选股结果

支持的策略：
- MA金叉策略
- RSI超卖策略
- 多头趋势策略
- 突破策略
- 价值策略
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
from core.scanner.strategies import (
    BaseStrategy,
    get_strategy,
    list_strategies,
    StrategySignal,
    StockSelector,
)

logger = logging.getLogger(__name__)


class MarketScanner:
    """全市场扫描器"""

    def __init__(self):
        self.market_cache = {}  # {market_type: dataframe}
        self.last_update = {}  # {market_type: timestamp}
        self._strategy_manager = None

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
                            code = str(row["代码"])  # usually 5 digits like 00700
                            name = str(row["名称"])
                            tickers.append({"ticker": code, "name": name})

        except Exception as e:
            logger.error(f"获取市场列表失败 ({market}): {e}")

        if tickers:
            self.market_cache[market] = tickers
            self.last_update[market] = time.time()

        return tickers

    def get_available_strategies(self) -> List[Dict]:
        """
        获取可用策略列表

        Returns:
            策略信息列表
        """
        return list_strategies()

    def scan_market(
        self,
        strategy_config: Dict,
        market: str = "CN",
        batch_size: int = 50,
        max_workers: int = 2,
        limit: int = 200,
    ) -> List[Dict]:
        """
        执行扫描

        Args:
            strategy_config: 策略配置 (e.g. {"name": "MA金叉策略", "params": {...}})
            market: "CN" or "HK"
            batch_size: 每批次获取数据的股票数量
            max_workers: 最大工作线程数
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
            # 加载OHLCV数据
            ohlcv_map = load_ohlcv_data(tickers, days=120)

            if not ohlcv_map:
                return []

            # 解析策略配置
            strategy_name = strategy_config.get("name", "MA金叉策略")
            params = strategy_config.get("params", {})

            # 创建策略实例
            try:
                strategy = get_strategy(strategy_name, **params)
            except Exception as e:
                logger.error(f"创建策略 {strategy_name} 失败: {e}")
                return []

            # 遍历该批次的所有股票
            for ticker, df in ohlcv_map.items():
                if df is None or df.empty:
                    continue

                if len(df) < 30:  # 数据过短
                    continue

                try:
                    # 计算策略评分
                    score = strategy.calculate_signal(df)

                    # 只保留有信号的股票（评分 > 50）
                    if score > 50:
                        latest = df.iloc[-1]
                        prev = df.iloc[-2] if len(df) > 1 else latest

                        price = float(latest["close"])
                        prev_price = float(prev["close"]) if "close" in prev else price
                        change = (price - prev_price) / prev_price if prev_price > 0 else 0

                        # 获取策略具体信号
                        signals = strategy.generate_signal(pd.DataFrame({'close': df['close']}))
                        signal = next((s for s in signals if s.ticker == ticker), None)

                        batch_results.append({
                            "ticker": ticker,
                            "price": price,
                            "change": change,
                            "score": score,
                            "volume": float(latest["volume"]) if "volume" in latest else 0,
                            "strategy": strategy.name() if hasattr(strategy, 'name') else strategy_name,
                            "signal_date": str(latest.name.date()) if hasattr(latest.name, "date") else str(latest.name),
                            "action": signal.action if signal else "观望",
                            "reason": signal.reason if signal else f"策略评分：{score}",
                        })
                except Exception as e:
                    logger.debug(f"Ticker {ticker} scan failed: {e}")
                    continue

            return batch_results

        except Exception as e:
            logger.error(f"批次处理失败: {e}")
            return []

    def scan_single_strategy(
        self,
        strategy_name: str,
        market: str = "CN",
        limit: int = 100,
        min_score: int = 60,
    ) -> List[Dict]:
        """
        单策略扫描

        Args:
            strategy_name: 策略名称
            market: 市场类型
            limit: 最大扫描数量
            min_score: 最低评分阈值

        Returns:
            符合条件的股票列表
        """
        strategy_config = {
            "name": strategy_name,
            "params": {}
        }

        results = self.scan_market(strategy_config, market, limit=limit)

        # 过滤最低评分
        if results:
            results = [r for r in results if r.get("score", 0) >= min_score]
            # 按评分排序
            results.sort(key=lambda x: x.get("score", 0), reverse=True)

        return results

    def scan_multi_strategies(
        self,
        strategy_configs: List[Dict],
        market: str = "CN",
        limit: int = 100,
        top_n_per_strategy: int = 10,
    ) -> Dict[str, List[Dict]]:
        """
        多策略同时扫描

        Args:
            strategy_configs: 策略配置列表
            market: 市场类型
            limit: 总股票数量限制
            top_n_per_strategy: 每个策略返回前N个

        Returns:
            按策略分组的结果字典
        """
        results = {}

        for config in strategy_configs:
            strategy_name = config.get("name", "Unknown")
            logger.info(f"开始扫描策略: {strategy_name}")
            strategy_results = self.scan_market(config, market, limit=limit)
            strategy_results = strategy_results[:top_n_per_strategy]
            results[strategy_name] = strategy_results
            logger.info(f"策略 {strategy_name} 扫描完成，发现 {len(strategy_results)} 个目标")

        return results

    def _fetch_ohlcv_single(self, ticker: str) -> Optional[pd.DataFrame]:
        """获取单只股票的 OHLCV 数据"""
        try:
            if ak:
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

    def scan_with_selector(
        self,
        price_df: pd.DataFrame,
        selector: Optional[StockSelector] = None,
        top_n: int = 20,
    ) -> pd.DataFrame:
        """
        使用选股器进行综合选股

        Args:
            price_df: 价格数据DataFrame
            selector:选股器实例
            top_n: 返回前N个

        Returns:
            选股结果DataFrame
        """
        if selector is None:
            selector = StockSelector()

        return selector.select_stocks(price_df, top_n=top_n)
