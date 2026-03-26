"""外部数据加载器

统一的外部数据加载接口，提供宏观经济数据、行业轮动数据、
市场情绪数据和资金流向数据的加载、融合和特征工程功能。
"""

from __future__ import annotations

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass

import pandas as pd
import numpy as np

from .economic import EconomicDataLoader
from .industry import IndustryDataLoader
from .sentiment import SentimentDataLoader
from .flow import FlowDataLoader


@dataclass
class ExternalDataConfig:
    """外部数据配置"""
    data_dir: str = "data/external"
    economic_config: Dict[str, Any] = None
    industry_config: Dict[str, Any] = None
    sentiment_config: Dict[str, Any] = None
    flow_config: Dict[str, Any] = None

    def __post_init__(self):
        self.economic_config = self.economic_config or {}
        self.industry_config = self.industry_config or {}
        self.sentiment_config = self.sentiment_config or {}
        self.flow_config = self.flow_config or {}


class ExternalDataLoader:
    """外部数据加载器（统一入口）

    功能：
    - 统一加载各类外部数据
    - 数据融合（外部数据 + 价格数据）
    - 特征工程（整体流程）
    - 数据缓存
    """

    def __init__(self, data_dir: str = "data/external"):
        """初始化外部数据加载器

        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 初始化各类数据加载器
        self.economic_loader = EconomicDataLoader(data_dir=str(self.data_dir))
        self.industry_loader = IndustryDataLoader(data_dir=str(self.data_dir))
        self.sentiment_loader = SentimentDataLoader(data_dir=str(self.data_dir))
        self.flow_loader = FlowDataLoader(data_dir=str(self.data_dir))

        # 缓存目录
        self.cache_dir = self.data_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 数据文件路径
        self.merged_file = self.data_dir / "external_merged.parquet"
        self.features_file = self.data_dir / "external_features.parquet"

    def load_all_external_data(self, start_date: str = "2010-01-01", end_date: str = None) -> Dict[str, pd.DataFrame]:
        """加载所有外部数据

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            包含各类型外部数据的字典
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        external_data = {
            "economic": self.economic_loader.get_all_data(start_date, end_date),
            "industry": self.industry_loader.get_industry_rotation(start_date, end_date),
            "sentiment": self.sentiment_loader.get_market_sentiment(start_date, end_date),
            "flow": self.flow_loader.get_flow_data(start_date, end_date),
        }

        return external_data

    def merge_price_with_external(self, price_df: pd.DataFrame, external_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """将价格数据与外部数据合并

        Args:
            price_df: 价格数据DataFrame
            external_data: 外部数据字典

        Returns:
            合并后的DataFrame
        """
        if price_df.empty:
            return price_df

        result = price_df.copy()

        # 1. 合并宏观经济数据
        if "economic" in external_data:
            for data_type, df in external_data["economic"].items():
                if df.empty:
                    continue

                # 重采样宏观经济数据以匹配价格数据频率
                if data_type == "gdp":
                    # GDP是季度数据，需要线性插值
                    df_temp = df.set_index("date")
                    df_resampled = df_temp.resample("D").interpolate()
                    df_resampled = df_resampled.reset_index()
                    result = self._join_by_date(result, df_resampled, prefix="gdp_")
                else:
                    # 月度或其他频率的数据
                    df_temp = df.set_index("date")
                    df_resampled = df_temp.resample("D").ffill()
                    df_resampled = df_resampled.reset_index()
                    result = self._join_by_date(result, df_resampled, prefix=f"{data_type}_")

        # 2. 合并行业数据
        if "industry" in external_data:
            industry_df = external_data["industry"]
            if not industry_df.empty:
                # 计算行业相对强度
                industry_df = self.industry_loader.calculate_relative_strength(industry_df)
                result = self._join_by_date(result, industry_df, prefix="industry_")

        # 3. 合并情绪数据
        if "sentiment" in external_data:
            sentiment_df = external_data["sentiment"]
            if not sentiment_df.empty:
                result = self._join_by_date(result, sentiment_df, prefix="sentiment_")

        # 4. 合并资金流向数据
        if "flow" in external_data:
            flow_df = external_data["flow"]
            if not flow_df.empty:
                result = self._join_by_date(result, flow_df, prefix="flow_")

        return result

    def _join_by_date(self, price_df: pd.DataFrame, external_df: pd.DataFrame, prefix: str = "") -> pd.DataFrame:
        """按日期合并价格和外部数据

        Args:
            price_df: 价格数据
            external_df: 外部数据
            prefix: 列名前缀

        Returns:
            合并后的DataFrame
        """
        if price_df.empty or external_df.empty:
            return price_df

        result = price_df.copy()

        # 确保date列为datetime
        if not isinstance(result.index, pd.DatetimeIndex):
            if "date" in result.columns:
                result["date"] = pd.to_datetime(result["date"])
                result = result.set_index("date")

        # 处理外部数据
        external_temp = external_df.copy()
        if "date" in external_temp.columns:
            external_temp["date"] = pd.to_datetime(external_temp["date"])
            external_temp = external_temp.set_index("date")

        # 重命名列添加前缀
        rename_cols = {}
        for col in external_temp.columns:
            if col != "date" and col not in result.columns:
                rename_cols[col] = f"{prefix}{col}" if prefix else col

        external_temp = external_temp.rename(columns=rename_cols)

        # 合并
        result = result.join(external_temp, how="left")

        # 前向填充外部数据
        external_cols = [col for col in result.columns if prefix in col]
        for col in external_cols:
            result[col] = result[col].fillna(method="ffill")

        result = result.reset_index()

        return result

    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """提取外部数据特征

        功能：
        - 时间特征（月份、季度、星期等）
        - 统计特征（Z-score、百分位数、滚动统计等）
        - 交叉特征（外部数据之间的交互）

        Args:
            df: 原始数据

        Returns:
            添加特征后的数据
        """
        if df.empty:
            return df

        df_features = df.copy()

        # 1. 时间特征
        if "date" in df_features.columns:
            df_features["date"] = pd.to_datetime(df_features["date"])
            df_features["year"] = df_features["date"].dt.year
            df_features["month"] = df_features["date"].dt.month
            df_features["quarter"] = df_features["date"].dt.quarter
            df_features["day_of_week"] = df_features["date"].dt.dayofweek
            df_features["day_of_year"] = df_features["date"].dt.dayofyear

        # 2. 宏观经济特征
        macro_features = [
            ("gdp", ["gdp_percentile", "gdp_zscore", "gdp_yoy_momentum"]),
            ("cpi", ["cpi_percentile", "cpi_zscore", "cpi_mom"]),
            ("pmi", ["pmi_percentile", "pmi_zscore", "pmi_gap_50", "pmi_momentum"]),
        ]

        for data_type, features in macro_features:
            for feature in features:
                if feature in df_features.columns:
                    df_features[f"{data_type}_{feature}"] = df_features[feature]

        # 3. 情绪特征
        sentiment_features = [
            "sentiment_index",
            "sentiment_heat",
            "fear_index",
            "sentiment_state",
            "zhangdie_ratio",
            "turnover_ratio",
        ]

        for feature in sentiment_features:
            if feature in df_features.columns:
                df_features[f"sent_{feature}"] = df_features[feature]

        # 4. 资金流向特征
        flow_features = [
            "north_flow",
            "main_flow",
            "total_flow",
            "flow_type",
            "flow_sentiment",
            "north_momentum_1d",
        ]

        for feature in flow_features:
            if feature in df_features.columns:
                df_features[f"flow_{feature}"] = df_features[feature]

        # 5. 行业特征（聚合）
        industry_cols = [col for col in df_features.columns if "industry_" in col]
        if industry_cols:
            # 计算行业 vibe（行业数据的综合指标）
            numeric_industry_cols = df_features[industry_cols].select_dtypes(include=[np.number]).columns
            if len(numeric_industry_cols) > 0:
                df_features["industry_vibe"] = df_features[numeric_industry_cols].mean(axis=1)

        # 6. 统计特征（Z-score）
        for col in df_features.select_dtypes(include=[np.number]).columns:
            if col in ["year", "month", "quarter", "day_of_week", "day_of_year"]:
                continue

            mean_val = df_features[col].mean()
            std_val = df_features[col].std()
            if std_val > 0:
                df_features[f"{col}_zscore"] = (df_features[col] - mean_val) / std_val
                df_features[f"{col}_percentile"] = df_features[col].rank(pct=True)

        # 7. 滚动统计特征
        for col in df_features.select_dtypes(include=[np.number]).columns:
            if col.endswith("_zscore") or col.endswith("_percentile"):
                continue

            rolling_windows = [5, 10, 20]
            for window in rolling_windows:
                if len(df_features) >= window:
                    df_features[f"{col}_ma{window}"] = df_features[col].rolling(window).mean()
                    df_features[f"{col}_std{window}"] = df_features[col].rolling(window).std()

        return df_features

    def get_full_pipeline(self, price_df: pd.DataFrame, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """完整的外部数据特征工程管道

        流程：
        1. 加载外部数据
        2. 数据合并
        3. 特征提取

        Args:
            price_df: 价格数据
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            包含所有特征的DataFrame
        """
        if price_df.empty:
            return price_df

        # 1. 确定日期范围
        if start_date is None:
            start_date = price_df["date"].min() if "date" in price_df.columns else "2010-01-01"
        if end_date is None:
            end_date = price_df["date"].max() if "date" in price_df.columns else datetime.now().strftime("%Y-%m-%d")

        # 2. 加载外部数据
        external_data = self.load_all_external_data(start_date, end_date)

        # 3. 合并数据
        merged_df = self.merge_price_with_external(price_df, external_data)

        # 4. 提取特征
        features_df = self.extract_features(merged_df)

        return features_df

    def save_merged_data(self, df: pd.DataFrame, filename: str = None) -> bool:
        """保存合并后的数据

        Args:
            df: 数据DataFrame
            filename: 文件名

        Returns:
            是否成功
        """
        if filename is None:
            filename = "external_merged.parquet"

        filepath = self.data_dir / filename

        try:
            df.to_parquet(filepath, index=False)
            return True
        except Exception as e:
            print(f"保存合并数据失败: {e}")
            return False

    def save_features(self, df: pd.DataFrame, filename: str = None) -> bool:
        """保存特征数据

        Args:
            df: 数据DataFrame
            filename: 文件名

        Returns:
            是否成功
        """
        if filename is None:
            filename = "external_features.parquet"

        filepath = self.data_dir / filename

        try:
            df.to_parquet(filepath, index=False)
            return True
        except Exception as e:
            print(f"保存特征数据失败: {e}")
            return False

    def load_merged_data(self, filename: str = None) -> pd.DataFrame:
        """加载合并后的数据

        Args:
            filename: 文件名

        Returns:
            DataFrame数据
        """
        if filename is None:
            filename = "external_merged.parquet"

        filepath = self.data_dir / filename

        if filepath.exists():
            try:
                return pd.read_parquet(filepath)
            except Exception:
                pass

        return pd.DataFrame()

    def load_features(self, filename: str = None) -> pd.DataFrame:
        """加载特征数据

        Args:
            filename: 文件名

        Returns:
            DataFrame数据
        """
        if filename is None:
            filename = "external_features.parquet"

        filepath = self.data_dir / filename

        if filepath.exists():
            try:
                return pd.read_parquet(filepath)
            except Exception:
                pass

        return pd.DataFrame()

    def get_economic_summary(self, start_date: str = "2010-01-01", end_date: str = None) -> Dict[str, Any]:
        """获取宏观经济摘要

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            宏观经济摘要字典
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        all_data = self.economic_loader.get_all_data(start_date, end_date)
        combined = self.economic_loader.combine_dataframes(all_data)

        summary = {
            "last_update": datetime.now().strftime("%Y-%m-%d"),
            "data_types": list(all_data.keys()),
            "date_range": {
                "start": start_date,
                "end": end_date,
            },
            "recent_values": {},
        }

        # 获取最新值
        for data_type, df in all_data.items():
            if not df.empty:
                latest = df.iloc[-1] if isinstance(df, pd.DataFrame) else df
                summary["recent_values"][data_type] = latest.to_dict() if isinstance(latest, pd.Series) else latest

        return summary

    def get_industry_summary(self, start_date: str = "2010-01-01", end_date: str = None) -> Dict[str, Any]:
        """获取行业轮动摘要

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            行业轮动摘要字典
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        df = self.industry_loader.get_industry_rotation(start_date, end_date)
        summary = self.industry_loader.get_industry_summary(df, end_date)

        return summary

    def get_sentiment_summary(self, start_date: str = "2010-01-01", end_date: str = None) -> Dict[str, Any]:
        """获取市场情绪摘要

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            市场情绪摘要字典
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        df = self.sentiment_loader.get_market_sentiment(start_date, end_date)
        summary = self.sentiment_loader.get_sentiment_summary(df, end_date)

        return summary

    def get_flow_summary(self, start_date: str = "2010-01-01", end_date: str = None) -> Dict[str, Any]:
        """获取资金流向摘要

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            资金流向摘要字典
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        df = self.flow_loader.get_flow_data(start_date, end_date)
        summary = self.flow_loader.get_flow_summary(df, end_date)

        return summary
