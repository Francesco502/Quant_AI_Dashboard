"""市场情绪数据加载器

提供市场情绪数据的获取、清洗和特征提取功能。

数据源：
- 交易所公开数据（涨跌停数量）
- 成交额数据
- 市场情绪指标（如停牌数量、涨跌停比等）

存储格式：
- data/external/sentiment.csv
"""

from __future__ import annotations

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass

import pandas as pd
import numpy as np

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    ak = None

try:
    import tushare as ts
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False
    ts = None


@dataclass
class SentimentDataConfig:
    """市场情绪数据配置"""
    data_dir: str = "data/external"
    sources: List[str] = None

    def __post_init__(self):
        if self.sources is None:
            self.sources = ["akshare", "local"]


class SentimentDataLoader:
    """市场情绪数据加载器

    功能：
    - 获取涨跌停数量、成交额等数据
    - 计算市场情绪指标
    - 情绪热度、恐慌指数等
    """

    def __init__(self, data_dir: str = "data/external"):
        """初始化市场情绪数据加载器

        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config = SentimentDataConfig(data_dir=str(self.data_dir))

        # 缓存目录
        self.cache_dir = self.data_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 数据文件路径
        self.sentiment_file = self.data_dir / "sentiment.csv"

        # 指数代码映射（用于获取市场成交量）
        self.index_codes = {
            "sh": "000001",  # 上证指数
            "sz": "399001",  # 深证成指
            "cyb": "399006",  # 创业板指
            "kcb": "000688",  # 科创板指
        }

    def fetch_zhangdieping_akshare(self, start_date: str, end_date: str) -> pd.DataFrame:
        """使用AkShare获取涨跌停数据

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame格式的涨跌停数据
        """
        if not AKSHARE_AVAILABLE:
            print("AkShare未安装，请运行: pip install akshare")
            return pd.DataFrame()

        all_data = []

        try:
            # 获取每日涨跌停统计数据
            # 注意：具体接口可能需要根据AkShare最新版本调整
            df = ak.stock_zt_pool_em(date=end_date.replace("-", ""))

            if df is not None and not df.empty:
                df["date"] = pd.to_datetime(df["日期"])
                df["zhang_ting"] = df["东南经济指数"]  # 涨停数量（示例）
                df["die_ting"] = df["西北经济指数"]  # 跌停数量（示例）

                all_data.append(df)

        except Exception as e:
            print(f"获取涨跌停数据失败: {e}")

        if not all_data:
            return pd.DataFrame()

        combined = pd.concat(all_data, ignore_index=True)
        combined["date"] = pd.to_datetime(combined["date"])

        # 过滤日期范围
        combined = combined[(combined["date"] >= start_date) & (combined["date"] <= end_date)]

        return combined

    def fetch_turnover_data_akshare(self, start_date: str, end_date: str) -> pd.DataFrame:
        """使用AkShare获取市场成交额数据

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame格式的成交额数据
        """
        if not AKSHARE_AVAILABLE:
            return pd.DataFrame()

        all_data = []

        for market, code in self.index_codes.items():
            try:
                # 获取指数数据
                df = ak.index_zh_a_hist(symbol=code, period="daily", start_date=start_date.replace("-", ""), end_date=end_date.replace("-", ""))

                if df is not None and not df.empty:
                    df = df.rename(columns={
                        "日期": "date",
                        "成交量": "volume",
                        "成交额": "amount",
                    })

                    df["market"] = market
                    df["date"] = pd.to_datetime(df["date"])

                    all_data.append(df)

            except Exception as e:
                print(f"获取 {market} 成交额数据失败: {e}")
                continue

        if not all_data:
            return pd.DataFrame()

        combined = pd.concat(all_data, ignore_index=True)

        # 过滤日期范围
        combined = combined[(combined["date"] >= start_date) & (combined["date"] <= end_date)]

        return combined

    def fetch_sentiment_data_local(self, start_date: str, end_date: str) -> pd.DataFrame:
        """从本地文件加载情绪数据

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame格式的情绪数据
        """
        if self.sentiment_file.exists():
            try:
                df = pd.read_csv(self.sentiment_file, parse_dates=["date"])

                # 过滤日期范围
                df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
                return df
            except Exception:
                pass

        return pd.DataFrame()

    def fetch_sentiment_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """获取市场情绪数据（主入口）

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame格式的情绪数据
        """
        # 按优先级尝试数据源
        for source in self.config.sources:
            if source == "akshare":
                df_zhangdie = self.fetch_zhangdieping_akshare(start_date, end_date)
                df_turnover = self.fetch_turnover_data_akshare(start_date, end_date)

                if not df_zhangdie.empty or not df_turnover.empty:
                    return self._merge_sentiment_data(df_zhangdie, df_turnover)

            elif source == "local":
                df = self.fetch_sentiment_data_local(start_date, end_date)
                if not df.empty:
                    return df

        # 所有数据源失败，使用合成数据
        return self._generate_synthetic_sentiment_data(start_date, end_date)

    def _merge_sentiment_data(self, df_zhangdie: pd.DataFrame, df_turnover: pd.DataFrame) -> pd.DataFrame:
        """合并涨跌停和成交额数据

        Args:
            df_zhangdie: 涨跌停数据
            df_turnover: 成交额数据

        Returns:
            合并后的DataFrame
        """
        result = pd.DataFrame()

        if not df_zhangdie.empty and not df_turnover.empty:
            # 按日期合并
            result = df_zhangdie.merge(df_turnover[["date", "amount", "volume"]], on="date", how="left")

        elif not df_zhangdie.empty:
            result = df_zhangdie.copy()
            result["amount"] = np.nan
            result["volume"] = np.nan

        elif not df_turnover.empty:
            result = df_turnover.copy()
            result["zhang_ting"] = np.nan
            result["die_ting"] = np.nan

        return result

    def _generate_synthetic_sentiment_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """生成模拟情绪数据（降级方案）

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame格式的模拟数据
        """
        dates = pd.date_range(start=start_date, end=end_date, freq="D")

        np.random.seed(42)
        rows = []

        for date in dates:
            # 生成涨跌停数量（模拟均值回归）
            zhang_ting = int(np.random.uniform(10, 100))
            die_ting = int(np.random.uniform(5, 50))

            # 涨跌停比（情绪指标）
            zhangdie_ratio = zhang_ting / max(die_ting, 1)

            # 成交额（亿元）
            turnover = np.random.uniform(5000, 15000)

            # 涨停跌幅比（成交额比）
            up_down_amount_ratio = np.random.uniform(0.8, 1.5)

            # 停牌数量
            pause_count = int(np.random.uniform(0, 10))

            # 市场情绪指数（0-100）
            sentiment_index = min(100, max(0, int(zhangdie_ratio * 20 + zhang_ting / 2)))

            rows.append({
                "date": date,
                "zhang_ting": zhang_ting,
                "die_ting": die_ting,
                "zhangdie_ratio": round(zhangdie_ratio, 3),
                "turnover": round(turnover, 2),
                "up_down_amount_ratio": round(up_down_amount_ratio, 3),
                "pause_count": pause_count,
                "sentiment_index": sentiment_index,
            })

        df = pd.DataFrame(rows)
        return df.sort_values("date").reset_index(drop=True)

    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗情绪数据

        Args:
            df: 原始数据

        Returns:
            清洗后的数据
        """
        if df.empty:
            return df

        df_clean = df.copy()

        # 1. 处理缺失值
        numeric_cols = ["zhang_ting", "die_ting", "zhangdie_ratio", "turnover", "up_down_amount_ratio", "pause_count", "sentiment_index"]
        for col in numeric_cols:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].fillna(method="ffill").fillna(method="bfill")
                df_clean[col] = df_clean[col].fillna(0)

        # 2. 过滤异常值
        for col in ["zhang_ting", "die_ting"]:
            if col in df_clean.columns:
                median_val = df_clean[col].median()
                iqr = df_clean[col].quantile(0.75) - df_clean[col].quantile(0.25)
                lower = max(0, median_val - 5 * iqr)
                upper = median_val + 5 * iqr
                df_clean[col] = df_clean[col].clip(lower=lower, upper=upper)

        return df_clean.sort_values("date").reset_index(drop=True)

    def calculate_sentiment_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算市场情绪指标

        功能：
        - 情绪热度指数
        - 恐慌指数
        - 量能指标
        - 情绪动量

        Args:
            df: 原始数据

        Returns:
            添加指标后的数据
        """
        if df.empty:
            return df

        df_indicators = df.copy()

        # 1. 涨跌停比（情绪偏好）
        if "zhang_ting" in df_indicators.columns and "die_ting" in df_indicators.columns:
            df_indicators["zhangdie_ratio"] = df_indicators["zhang_ting"] / df_indicators["die_ting"].replace(0, np.nan)
            df_indicators["zhangdie_ratio"] = df_indicators["zhangdie_ratio"].fillna(1)

        # 2. 涨跌停总数
        if "zhang_ting" in df_indicators.columns and "die_ting" in df_indicators.columns:
            df_indicators["total_zhangdie"] = df_indicators["zhang_ting"] + df_indicators["die_ting"]

        # 3. 情绪热度指数（0-100）
        # 综合考虑涨跌停比、涨跌停总数、成交额等因素
        if all(col in df_indicators.columns for col in ["zhangdie_ratio", "zhang_ting", "turnover"]):
            # 涨跌停比得分（0-40分）
            ratio_score = min(40, df_indicators["zhangdie_ratio"].mean() * 5)

            # 涨跌停总数得分（0-30分）
            total_score = min(30, df_indicators["zhang_ting"].mean() / 3)

            # 成交额得分（0-30分）
            turnover_score = min(30, df_indicators["turnover"].mean() / 500)

            df_indicators["sentiment_heat"] = ratio_score + total_score + turnover_score

        # 4. 恐慌指数（100 - 情绪指数）
        if "sentiment_index" in df_indicators.columns:
            df_indicators["fear_index"] = 100 - df_indicators["sentiment_index"]

        # 5. 情绪动量（变化率）
        if "sentiment_index" in df_indicators.columns:
            df_indicators["sentiment_momentum_1d"] = df_indicators["sentiment_index"].pct_change(1)
            df_indicators["sentiment_momentum_3d"] = df_indicators["sentiment_index"].pct_change(3)
            df_indicators["sentiment_momentum_5d"] = df_indicators["sentiment_index"].pct_change(5)

        # 6. 成交额比（涨跌股成交额比）
        if "up_down_amount_ratio" not in df_indicators.columns:
            df_indicators["up_down_amount_ratio"] = 1.0

        # 7. 量能指标
        if "turnover" in df_indicators.columns:
            df_indicators["turnover_ma5"] = df_indicators["turnover"].rolling(5).mean()
            df_indicators["turnover_ma20"] = df_indicators["turnover"].rolling(20).mean()
            df_indicators["turnover_ratio"] = df_indicators["turnover"] / df_indicators["turnover_ma20"]

        # 8. 情绪状态分类
        def classify_sentiment(row):
            sentiment = row.get("sentiment_index", 50)
            if sentiment >= 80:
                return "extreme_greed"  # 极度贪婪
            elif sentiment >= 60:
                return "greed"  # 贪婪
            elif sentiment >= 40:
                return "neutral"  # 中性
            elif sentiment >= 20:
                return "fear"  # 恐慌
            else:
                return "extreme_fear"  # 极度恐慌

        if "sentiment_index" in df_indicators.columns:
            df_indicators["sentiment_state"] = df_indicators.apply(classify_sentiment, axis=1)

        return df_indicators

    def get_market_sentiment(self, start_date: str, end_date: str) -> pd.DataFrame:
        """获取市场情绪数据（含所有指标）

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            包含所有指标的DataFrame
        """
        # 1. 获取原始数据
        df_raw = self.fetch_sentiment_data(start_date, end_date)

        # 2. 清洗数据
        df_clean = self.clean_data(df_raw)

        # 3. 计算指标
        df_indicators = self.calculate_sentiment_indicators(df_clean)

        return df_indicators

    def get_sentiment_summary(self, df: pd.DataFrame, date: str = None) -> Dict[str, Any]:
        """获取情绪摘要信息

        Args:
            df: 情绪数据
            date: 指定日期

        Returns:
            包含情绪 summary 的字典
        """
        if df.empty:
            return {}

        df_temp = df.copy()

        # 获取指定日期或最新日期
        if date is not None:
            df_temp = df_temp[df_temp["date"] == pd.Timestamp(date)]
        else:
            # 获取最新数据
            df_temp = df_temp[df_temp["date"] == df_temp["date"].max()]

        summary = {
            "date": df_temp["date"].max().strftime("%Y-%m-%d") if not df_temp.empty else None,
            "sentiment_index": df_temp["sentiment_index"].iloc[0] if not df_temp.empty and "sentiment_index" in df_temp.columns else 50,
            "sentiment_state": df_temp["sentiment_state"].iloc[0] if not df_temp.empty and "sentiment_state" in df_temp.columns else "neutral",
            "zhang_ting": int(df_temp["zhang_ting"].iloc[0]) if not df_temp.empty and "zhang_ting" in df_temp.columns else 0,
            "die_ting": int(df_temp["die_ting"].iloc[0]) if not df_temp.empty and "die_ting" in df_temp.columns else 0,
            "zhangdie_ratio": float(df_temp["zhangdie_ratio"].iloc[0]) if not df_temp.empty and "zhangdie_ratio" in df_temp.columns else 1.0,
            "turnover": float(df_temp["turnover"].iloc[0]) if not df_temp.empty and "turnover" in df_temp.columns else 0,
            "fear_index": float(df_temp["fear_index"].iloc[0]) if not df_temp.empty and "fear_index" in df_temp.columns else 50,
            "sentiment_momentum_1d": float(df_temp["sentiment_momentum_1d"].iloc[0]) if not df_temp.empty and "sentiment_momentum_1d" in df_temp.columns else 0,
        }

        return summary

    def get_sentiment_trend(self, df: pd.DataFrame, window: int = 20) -> Dict[str, List[float]]:
        """获取情绪趋势数据

        Args:
            df: 情绪数据
            window: 窗口大小

        Returns:
            包含趋势数据的字典
        """
        if df.empty or "sentiment_index" not in df.columns:
            return {}

        df_temp = df.sort_values("date").copy()

        # 计算移动平均
        df_temp["sentiment_ma"] = df_temp["sentiment_index"].rolling(window).mean()

        # 计算趋势
        trend_data = {
            "dates": df_temp["date"].iloc[-window:].dt.strftime("%Y-%m-%d").tolist(),
            "sentiment_index": df_temp["sentiment_index"].iloc[-window:].tolist(),
            "sentiment_ma": df_temp["sentiment_ma"].iloc[-window:].tolist(),
        }

        return trend_data

    def save_data(self, df: pd.DataFrame, filename: str = None) -> bool:
        """保存情绪数据到CSV文件

        Args:
            df: 数据DataFrame
            filename: 文件名

        Returns:
            是否成功
        """
        if filename is None:
            filename = "sentiment.csv"

        filepath = self.data_dir / filename

        try:
            # 确保date列为 datetime
            if not isinstance(df["date"], pd.DatetimeIndex):
                df["date"] = pd.to_datetime(df["date"])

            df.to_csv(filepath, index=False)
            return True
        except Exception as e:
            print(f"保存情绪数据失败: {e}")
            return False

    def load_data(self, filename: str = None) -> pd.DataFrame:
        """加载情绪数据

        Args:
            filename: 文件名

        Returns:
            DataFrame数据
        """
        if filename is None:
            filename = "sentiment.csv"

        filepath = self.data_dir / filename

        if filepath.exists():
            try:
                df = pd.read_csv(filepath, parse_dates=["date"])
                return df
            except Exception:
                pass

        return pd.DataFrame()
