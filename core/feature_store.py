"""
特征仓库模块（阶段一：基础设施升级）

职责：
- 统一管理特征计算与持久化
- 特征版本化管理
- 为训练和预测提供一致的特征接口
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from .advanced_forecasting import FeatureEngineer
from .data_store import BASE_DIR, classify_market

FEATURES_DIR = os.path.join(BASE_DIR, "features")
FEATURES_DAILY_DIR = os.path.join(FEATURES_DIR, "daily")
FEATURE_META_FILE = os.path.join(FEATURES_DIR, "feature_meta.json")

# 当前特征版本
CURRENT_FEATURE_VERSION = "v1.0"


def _ensure_dirs() -> None:
    """确保特征目录存在"""
    os.makedirs(FEATURES_DIR, exist_ok=True)
    os.makedirs(FEATURES_DAILY_DIR, exist_ok=True)


def get_feature_file_path(ticker: str) -> str:
    """获取某个标的的特征文件路径"""
    safe_ticker = ticker.replace("/", "_").replace("\\", "_").replace(":", "_")
    market = classify_market(ticker)
    # 统一归类到A股目录（与价格数据保持一致）
    if market == "基金":
        market = "A股"
    market_dir = os.path.join(FEATURES_DAILY_DIR, market)
    os.makedirs(market_dir, exist_ok=True)
    return os.path.join(market_dir, f"{safe_ticker}.parquet")


def load_feature_meta() -> Dict:
    """加载特征元数据"""
    if not os.path.exists(FEATURE_META_FILE):
        return {
            "version": CURRENT_FEATURE_VERSION,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "feature_list": [],
            "lookback_windows": [5, 10, 20, 60],
        }
    try:
        with open(FEATURE_META_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "version": CURRENT_FEATURE_VERSION,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "feature_list": [],
            "lookback_windows": [5, 10, 20, 60],
        }


def save_feature_meta(meta: Dict) -> None:
    """保存特征元数据"""
    _ensure_dirs()
    meta["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(FEATURE_META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


class FeatureStore:
    """特征仓库管理器"""

    def __init__(self):
        self.feature_engineer = FeatureEngineer()
        self.meta = load_feature_meta()

    def compute_features(
        self,
        price_series: pd.Series,
        lookback_windows: Optional[List[int]] = None,
        use_enhanced_features: bool = True,
    ) -> pd.DataFrame:
        """
        计算特征（不持久化）

        参数:
            price_series: 价格序列
            lookback_windows: 回看窗口列表
            use_enhanced_features: 是否使用增强特征

        返回:
            特征DataFrame
        """
        if lookback_windows is None:
            lookback_windows = self.meta.get("lookback_windows", [5, 10, 20, 60])

        # 基础特征
        df = self.feature_engineer.create_price_features(price_series, lookback_windows)

        # 滞后特征
        df = self.feature_engineer.create_lag_features(df, "return_1d", lags=[1, 2, 3, 5, 10])

        # 增强特征（可选）
        if use_enhanced_features:
            df = self.feature_engineer.add_enhanced_features(df, price_series)

        return df

    def save_features(self, ticker: str, features_df: pd.DataFrame) -> bool:
        """
        保存特征到本地仓库

        参数:
            ticker: 标的代码
            features_df: 特征DataFrame

        返回:
            是否成功
        """
        if features_df is None or features_df.empty:
            return False

        try:
            _ensure_dirs()
            path = get_feature_file_path(ticker)
            features_df = features_df.copy()
            if not isinstance(features_df.index, pd.DatetimeIndex):
                features_df.index = pd.to_datetime(features_df.index)
            features_df = features_df.sort_index()

            # 保存特征文件
            features_df.to_parquet(path)

            # 更新元数据中的特征列表（去重）
            feature_list = self.meta.get("feature_list", [])
            for col in features_df.columns:
                if col not in feature_list:
                    feature_list.append(col)
            self.meta["feature_list"] = sorted(feature_list)
            save_feature_meta(self.meta)

            return True
        except Exception as e:
            print(f"保存特征失败 ({ticker}): {e}")
            return False

    def load_features(
        self, ticker: str, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        从本地仓库加载特征

        参数:
            ticker: 标的代码
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）

        返回:
            特征DataFrame，不存在则返回None
        """
        path = get_feature_file_path(ticker)
        if not os.path.exists(path):
            return None

        try:
            df = pd.read_parquet(path)
            if df.empty:
                return None

            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            df = df.sort_index()

            # 日期过滤
            if start_date:
                df = df[df.index >= pd.to_datetime(start_date)]
            if end_date:
                df = df[df.index <= pd.to_datetime(end_date)]

            return df
        except Exception as e:
            print(f"加载特征失败 ({ticker}): {e}")
            return None

    def get_latest_features(self, ticker: str, n_days: int = 1) -> Optional[pd.DataFrame]:
        """
        获取最新N天的特征

        参数:
            ticker: 标的代码
            n_days: 天数

        返回:
            特征DataFrame
        """
        features = self.load_features(ticker)
        if features is None or features.empty:
            return None
        return features.tail(n_days)

    def update_features_for_ticker(
        self,
        ticker: str,
        price_series: pd.Series,
        use_enhanced_features: bool = True,
    ) -> bool:
        """
        为某个标的更新特征（计算并保存）

        参数:
            ticker: 标的代码
            price_series: 价格序列
            use_enhanced_features: 是否使用增强特征

        返回:
            是否成功
        """
        if price_series is None or price_series.empty:
            return False

        # 计算特征
        features_df = self.compute_features(
            price_series, use_enhanced_features=use_enhanced_features
        )

        # 保存特征
        return self.save_features(ticker, features_df)

    def feature_exists(self, ticker: str) -> bool:
        """检查某个标的的特征是否存在"""
        path = get_feature_file_path(ticker)
        return os.path.exists(path)

    def get_feature_version(self) -> str:
        """获取当前特征版本"""
        return self.meta.get("version", CURRENT_FEATURE_VERSION)


# 全局单例
_feature_store_instance: Optional[FeatureStore] = None


def get_feature_store() -> FeatureStore:
    """获取特征仓库单例"""
    global _feature_store_instance
    if _feature_store_instance is None:
        _feature_store_instance = FeatureStore()
    return _feature_store_instance

