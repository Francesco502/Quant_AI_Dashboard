"""数据存储适配器

职责：
- 提供统一的数据存储接口
- 支持SQLite和文件系统两种存储方式
- 自动选择最优存储方式
"""

from __future__ import annotations

import logging
from typing import Optional
import pandas as pd

from .database import Database, get_database
from . import data_store


logger = logging.getLogger(__name__)


class DataStoreAdapter:
    """数据存储适配器（统一接口）"""
    
    def __init__(self, use_database: bool = True, use_filesystem: bool = True):
        """
        初始化数据存储适配器

        Args:
            use_database: 是否使用SQLite数据库
            use_filesystem: 是否使用文件系统（Parquet）
        """
        self.use_database = use_database
        self.use_filesystem = use_filesystem
        
        if use_database:
            try:
                self.db = get_database()
                logger.info("数据存储适配器：启用SQLite数据库")
            except Exception as e:
                logger.warning(f"数据库初始化失败，回退到文件系统: {e}")
                self.use_database = False
                self.db = None
        else:
            self.db = None
    
    def load_price_history(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[pd.Series]:
        """
        加载价格历史（优先从数据库，回退到文件系统）

        Args:
            ticker: 标的代码
            start_date: 起始日期（可选）
            end_date: 结束日期（可选）

        Returns:
            价格序列
        """
        # 优先从数据库读取
        if self.use_database and self.db:
            try:
                series = self.db.query_price_series(ticker, start_date, end_date)
                if series is not None and not series.empty:
                    return series
            except Exception as e:
                logger.warning(f"从数据库读取失败，回退到文件系统: {ticker} - {e}")
        
        # 回退到文件系统
        if self.use_filesystem:
            series = data_store.load_local_price_history(ticker)
            if series is not None and not series.empty:
                # 如果数据库可用，同步到数据库
                if self.use_database and self.db:
                    try:
                        self.db.save_price_data(ticker, series, replace=False)
                    except Exception as e:
                        logger.warning(f"同步到数据库失败: {ticker} - {e}")
                return series
        
        return None
    
    def load_ohlcv_history(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        加载OHLCV历史

        Args:
            ticker: 标的代码
            start_date: 起始日期（可选）
            end_date: 结束日期（可选）

        Returns:
            OHLCV DataFrame
        """
        # 优先从数据库读取
        if self.use_database and self.db:
            try:
                df = self.db.query_price_data(ticker, start_date, end_date)
                if df is not None and not df.empty:
                    return df
            except Exception as e:
                logger.warning(f"从数据库读取失败，回退到文件系统: {ticker} - {e}")
        
        # 回退到文件系统
        if self.use_filesystem:
            df = data_store.load_local_ohlcv_history(ticker)
            if df is not None and not df.empty:
                # 如果数据库可用，同步到数据库
                if self.use_database and self.db:
                    try:
                        self.db.save_price_data(ticker, df, replace=False)
                    except Exception as e:
                        logger.warning(f"同步到数据库失败: {ticker} - {e}")
                return df
        
        return None
    
    def save_price_history(self, ticker: str, series: pd.Series) -> bool:
        """
        保存价格历史（同时保存到数据库和文件系统）

        Args:
            ticker: 标的代码
            series: 价格序列

        Returns:
            是否成功
        """
        success = True
        
        # 保存到数据库
        if self.use_database and self.db:
            try:
                self.db.save_price_data(ticker, series, replace=True)
            except Exception as e:
                logger.error(f"保存到数据库失败: {ticker} - {e}")
                success = False
        
        # 保存到文件系统
        if self.use_filesystem:
            try:
                data_store.save_local_price_history(ticker, series)
            except Exception as e:
                logger.error(f"保存到文件系统失败: {ticker} - {e}")
                success = False
        
        return success
    
    def save_ohlcv_history(self, ticker: str, df: pd.DataFrame) -> bool:
        """
        保存OHLCV历史

        Args:
            ticker: 标的代码
            df: OHLCV DataFrame

        Returns:
            是否成功
        """
        success = True
        
        # 保存到数据库
        if self.use_database and self.db:
            try:
                self.db.save_price_data(ticker, df, replace=True)
            except Exception as e:
                logger.error(f"保存到数据库失败: {ticker} - {e}")
                success = False
        
        # 保存到文件系统
        if self.use_filesystem:
            try:
                data_store.save_local_ohlcv_history(ticker, df)
            except Exception as e:
                logger.error(f"保存到文件系统失败: {ticker} - {e}")
                success = False
        
        return success


# 全局适配器实例（延迟初始化）
_adapter_instance: Optional[DataStoreAdapter] = None


def get_data_store_adapter(
    use_database: bool = True,
    use_filesystem: bool = True
) -> DataStoreAdapter:
    """
    获取数据存储适配器实例

    Args:
        use_database: 是否使用数据库
        use_filesystem: 是否使用文件系统

    Returns:
        数据存储适配器实例
    """
    global _adapter_instance
    
    if _adapter_instance is None:
        _adapter_instance = DataStoreAdapter(use_database, use_filesystem)
    
    return _adapter_instance

