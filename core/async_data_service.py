"""异步数据服务

职责：
- 使用异步IO提升并发性能
- 并发获取多个标的的数据
- 支持异步HTTP请求
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

import pandas as pd

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    yf = None


logger = logging.getLogger(__name__)


class AsyncDataService:
    """异步数据服务"""
    
    def __init__(self, timeout: int = 30):
        """
        初始化异步数据服务

        Args:
            timeout: 请求超时时间（秒）
        """
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        if AIOHTTP_AVAILABLE:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    async def fetch_multiple_tickers(
        self,
        tickers: List[str],
        days: int = 365,
        data_source: str = "yfinance"
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """
        并发获取多个标的的数据

        Args:
            tickers: 标的代码列表
            days: 获取天数
            data_source: 数据源（目前支持yfinance）

        Returns:
            标的数据字典 {ticker: DataFrame}
        """
        if not tickers:
            return {}
        
        if data_source == "yfinance" and YFINANCE_AVAILABLE:
            return await self._fetch_yfinance_multiple(tickers, days)
        else:
            # 回退到同步方式
            logger.warning(f"数据源 {data_source} 不支持异步，回退到同步方式")
            return self._fetch_sync_fallback(tickers, days, data_source)
    
    async def _fetch_yfinance_multiple(
        self,
        tickers: List[str],
        days: int
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """使用yfinance并发获取数据"""
        # yfinance本身不支持异步，但可以在事件循环中并发执行
        loop = asyncio.get_event_loop()
        
        # 创建任务列表
        tasks = [
            loop.run_in_executor(None, self._fetch_yfinance_single, ticker, days)
            for ticker in tickers
        ]
        
        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        data_dict = {}
        for ticker, result in zip(tickers, results):
            if isinstance(result, Exception):
                logger.error(f"获取数据失败: {ticker} - {result}")
                data_dict[ticker] = None
            else:
                data_dict[ticker] = result
        
        return data_dict
    
    def _fetch_yfinance_single(
        self,
        ticker: str,
        days: int
    ) -> Optional[pd.DataFrame]:
        """同步获取单个标的的数据（用于executor）"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            ticker_obj = yf.Ticker(ticker)
            df = ticker_obj.history(start=start_date, end=end_date)
            
            if df.empty:
                return None
            
            # 标准化列名
            df.columns = [col.lower() for col in df.columns]
            
            # 重命名列
            rename_map = {
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
            }
            
            # 只保留需要的列
            available_cols = [col for col in rename_map.keys() if col in df.columns]
            df = df[available_cols]
            
            return df
            
        except Exception as e:
            logger.error(f"获取yfinance数据失败: {ticker} - {e}")
            return None
    
    async def fetch_http_data(
        self,
        url: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        异步HTTP请求

        Args:
            url: 请求URL
            params: 请求参数
            headers: 请求头

        Returns:
            响应数据（JSON格式）
        """
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp未安装，无法使用异步HTTP请求")
            return None
        
        if not self.session:
            async with aiohttp.ClientSession() as session:
                return await self._fetch_http(session, url, params, headers)
        else:
            return await self._fetch_http(self.session, url, params, headers)
    
    async def _fetch_http(
        self,
        session: aiohttp.ClientSession,
        url: str,
        params: Optional[Dict],
        headers: Optional[Dict]
    ) -> Optional[Dict]:
        """执行HTTP请求"""
        try:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"HTTP请求失败: {url} - 状态码: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"HTTP请求异常: {url} - {e}")
            return None
    
    def _fetch_sync_fallback(
        self,
        tickers: List[str],
        days: int,
        data_source: str
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """同步回退方法"""
        from .data_service import _load_price_data_remote
        
        # 使用现有的同步方法
        df = _load_price_data_remote(
            tickers=tickers,
            days=days,
            data_sources=[data_source] if data_source else None
        )
        
        if df is None or df.empty:
            return {ticker: None for ticker in tickers}
        
        # 转换为字典格式
        result = {}
        for ticker in tickers:
            if ticker in df.columns:
                result[ticker] = pd.DataFrame({ticker: df[ticker]})
            else:
                result[ticker] = None
        
        return result


async def fetch_multiple_tickers_async(
    tickers: List[str],
    days: int = 365,
    data_source: str = "yfinance"
) -> Dict[str, Optional[pd.DataFrame]]:
    """
    便捷函数：并发获取多个标的的数据

    Args:
        tickers: 标的代码列表
        days: 获取天数
        data_source: 数据源

    Returns:
        标的数据字典
    """
    async with AsyncDataService() as service:
        return await service.fetch_multiple_tickers(tickers, days, data_source)


def fetch_multiple_tickers_sync(
    tickers: List[str],
    days: int = 365,
    data_source: str = "yfinance"
) -> Dict[str, Optional[pd.DataFrame]]:
    """
    同步包装函数：使用异步服务但以同步方式调用

    Args:
        tickers: 标的代码列表
        days: 获取天数
        data_source: 数据源

    Returns:
        标的数据字典
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            fetch_multiple_tickers_async(tickers, days, data_source)
        )
    finally:
        loop.close()

