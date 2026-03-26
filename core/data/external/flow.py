"""资金流向数据加载器

提供资金流向数据的获取、清洗和特征提取功能。

数据源：
- 北向资金（沪深港通）
- 主力资金流向
- 散户资金流向
- 行业资金流向

存储格式：
- data/external/flow.csv
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
class FlowDataConfig:
    """资金流向数据配置"""
    data_dir: str = "data/external"
    sources: List[str] = None

    def __post_init__(self):
        if self.sources is None:
            self.sources = ["akshare", "local"]


class FlowDataLoader:
    """资金流向数据加载器

    功能：
    - 获取北向资金数据
    - 获取主力资金流向数据
    - 计算资金流向指标
    """

    def __init__(self, data_dir: str = "data/external"):
        """初始化资金流向数据加载器

        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config = FlowDataConfig(data_dir=str(self.data_dir))

        # 缓存目录
        self.cache_dir = self.data_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 数据文件路径
        self.flow_file = self.data_dir / "flow.csv"

        # 北向资金代码
        self.hk_flow_codes = {
            "north_money": "800001",  # 北向资金
            "south_money": "800002",  # 南向资金
        }

    def fetch_north_money_akshare(self, start_date: str, end_date: str) -> pd.DataFrame:
        """使用AkShare获取北向资金数据

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame格式的北向资金数据
        """
        if not AKSHARE_AVAILABLE:
            print("AkShare未安装，请运行: pip install akshare")
            return pd.DataFrame()

        try:
            # 获取每日北向资金数据
            df = ak.stock_hk_daily(symbol="00931.HK", start_date=start_date.replace("-", ""), end_date=end_date.replace("-", ""))

            if df is not None and not df.empty:
                df = df.rename(columns={
                    "date": "date",
                    "close": "north_money",
                })

                df["date"] = pd.to_datetime(df["date"])
                df["flow_type"] = "north"

                # 累计净流入（模拟）
                df["net_flows"] = df["north_money"].diff()
                df["net_flows"] = df["net_flows"].fillna(0)

                # 过滤日期范围
                df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]

                return df

        except Exception as e:
            print(f"获取北向资金数据失败: {e}")

        return pd.DataFrame()

    def fetch主力资金_akshare(self, start_date: str, end_date: str) -> pd.DataFrame:
        """使用AkShare获取主力资金流向数据

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame格式的主力资金数据
        """
        if not AKSHARE_AVAILABLE:
            return pd.DataFrame()

        try:
            # 获取主力资金流向数据
            df = ak.stock_zh_a_sgfl()

            if df is not None and not df.empty:
                df["date"] = pd.to_datetime(df["交易日期"])
                df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
                return df

        except Exception as e:
            print(f"获取主力资金数据失败: {e}")

        return pd.DataFrame()

    def fetch_flow_data_local(self, start_date: str, end_date: str) -> pd.DataFrame:
        """从本地文件加载资金流向数据

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame格式的资金流向数据
        """
        if self.flow_file.exists():
            try:
                df = pd.read_csv(self.flow_file, parse_dates=["date"])

                # 过滤日期范围
                df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
                return df
            except Exception:
                pass

        return pd.DataFrame()

    def fetch_flow_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """获取资金流向数据（主入口）

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame格式的资金流向数据
        """
        # 按优先级尝试数据源
        for source in self.config.sources:
            if source == "akshare":
                df_north = self.fetch_north_money_akshare(start_date, end_date)
                df_main = self.fetch主力资金_akshare(start_date, end_date)

                if not df_north.empty or not df_main.empty:
                    return self._merge_flow_data(df_north, df_main)

            elif source == "local":
                df = self.fetch_flow_data_local(start_date, end_date)
                if not df.empty:
                    return df

        # 所有数据源失败，使用合成数据
        return self._generate_synthetic_flow_data(start_date, end_date)

    def _merge_flow_data(self, df_north: pd.DataFrame, df_main: pd.DataFrame) -> pd.DataFrame:
        """合并北向资金和主力资金数据

        Args:
            df_north: 北向资金数据
            df_main: 主力资金数据

        Returns:
            合并后的DataFrame
        """
        result = pd.DataFrame()

        if df_north.empty and df_main.empty:
            return result

        if not df_north.empty:
            result = df_north.copy()
            if "main_flow" not in result.columns:
                result["main_flow"] = np.nan
            if "small_flow" not in result.columns:
                result["small_flow"] = np.nan

        if not df_main.empty and not result.empty:
            # 按日期合并
            if "date" in df_main.columns:
                result = result.merge(df_main[["date", "主力净额", "主力净占比"]], on="date", how="left")
                result = result.rename(columns={
                    "主力净额": "main_flow",
                    "主力净占比": "main_flow_pct",
                })

        elif not df_main.empty:
            result = df_main.copy()
            result = result.rename(columns={
                "主力净额": "main_flow",
                "主力净占比": "main_flow_pct",
            })
            if "north_flow" not in result.columns:
                result["north_flow"] = np.nan

        return result

    def _generate_synthetic_flow_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """生成模拟资金流向数据（降级方案）

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame格式的模拟数据
        """
        dates = pd.date_range(start=start_date, end=end_date, freq="D")

        np.random.seed(42)
        rows = []

        north_base = 50  # 北向资金基础值（亿元）
        main_base = 30  # 主力资金基础值（亿元）

        for date in dates:
            # 北向资金（亿人民币）
            north_flow = north_base + np.random.uniform(-20, 30)
            north_cumulative = 2000 + sum([r[1] for r in rows]) if rows else north_flow

            # 主力资金（亿人民币）
            main_flow = main_base + np.random.uniform(-30, 40)
            main_cumulative = 1500 + sum([r[1] for r in rows]) if rows else main_flow

            # 散户资金（主力的反向）
            small_flow = -main_flow * 0.3

            # 行业资金流向（模拟）
            industry_flows = {
                "医药生物": np.random.uniform(-5, 10),
                "电子": np.random.uniform(-8, 12),
                "计算机": np.random.uniform(-10, 8),
                "新能源": np.random.uniform(-15, 15),
                "金融": np.random.uniform(-10, 5),
                "消费": np.random.uniform(-5, 8),
            }

            # 资金净流入总额
            total_flow = north_flow + main_flow + small_flow

            # 资金流向指标
            if total_flow != 0:
                north_ratio = north_flow / total_flow
                main_ratio = main_flow / total_flow
            else:
                north_ratio = 0
                main_ratio = 0

            rows.append({
                "date": date,
                "north_flow": round(north_flow, 2),
                "north_cumulative": round(north_cumulative, 2),
                "main_flow": round(main_flow, 2),
                "main_cumulative": round(main_cumulative, 2),
                "small_flow": round(small_flow, 2),
                "total_flow": round(total_flow, 2),
                "north_ratio": round(north_ratio, 3),
                "main_ratio": round(main_ratio, 3),
                "industry_flows": json.dumps(industry_flows),
            })

        df = pd.DataFrame(rows)

        # 计算动量
        df["north_momentum_1d"] = df["north_flow"].pct_change(1)
        df["north_momentum_3d"] = df["north_flow"].pct_change(3)
        df["north_momentum_5d"] = df["north_flow"].pct_change(5)

        return df.sort_values("date").reset_index(drop=True)

    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗资金流向数据

        Args:
            df: 原始数据

        Returns:
            清洗后的数据
        """
        if df.empty:
            return df

        df_clean = df.copy()

        # 1. 处理缺失值
        numeric_cols = [
            "north_flow", "north_cumulative", "main_flow", "main_cumulative",
            "small_flow", "total_flow", "north_ratio", "main_ratio",
            "north_momentum_1d", "north_momentum_3d", "north_momentum_5d"
        ]
        for col in numeric_cols:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].fillna(method="ffill").fillna(method="bfill")
                df_clean[col] = df_clean[col].fillna(0)

        # 2. 处理异常值
        for col in ["north_flow", "main_flow", "total_flow"]:
            if col in df_clean.columns:
                median_val = df_clean[col].median()
                iqr = df_clean[col].quantile(0.75) - df_clean[col].quantile(0.25)
                lower = median_val - 5 * iqr
                upper = median_val + 5 * iqr
                df_clean[col] = df_clean[col].clip(lower=lower, upper=upper)

        return df_clean.sort_values("date").reset_index(drop=True)

    def calculate_flow_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算资金流向指标

        功能：
        - 资金动量
        - 资金流向强度
        - 行业资金分布
        - 资金流向情绪

        Args:
            df: 原始数据

        Returns:
            添加指标后的数据
        """
        if df.empty:
            return df

        df_indicators = df.copy()

        # 1. 计算资金动量
        for col in ["north_flow", "main_flow", "total_flow"]:
            if col in df_indicators.columns:
                df_indicators[f"{col}_ma5"] = df_indicators[col].rolling(5).mean()
                df_indicators[f"{col}_ma20"] = df_indicators[col].rolling(20).mean()
                df_indicators[f"{col}_ratio_ma5"] = df_indicators[col] / df_indicators[f"{col}_ma5"]

        # 2. 计算资金流向强度（相对于历史分位数）
        for col in ["north_flow", "main_flow", "total_flow"]:
            if col in df_indicators.columns:
                df_indicators[f"{col}_percentile"] = df_indicators[col].rank(pct=True)

        # 3. 资金流向分类
        def classify_flow(row):
            total = row.get("total_flow", 0)
            north = row.get("north_flow", 0)
            main = row.get("main_flow", 0)

            if total > 0 and north > 0 and main > 0:
                return "all_inflow"  # 全部资金流入
            elif total < 0 and north < 0 and main < 0:
                return "all_outflow"  # 全部资金流出
            elif north > 0 and main < 0:
                return "north_in_main_out"  # 北向流入，主力流出
            elif north < 0 and main > 0:
                return "north_out_main_in"  # 北向流出，主力流入
            else:
                return "mixed"  # 混合

        df_indicators["flow_type"] = df_indicators.apply(classify_flow, axis=1)

        # 4. 资金流向情绪指数（0-100）
        if "total_flow" in df_indicators.columns:
            # 基于净流入金额的情感指数
            max_flow = df_indicators["total_flow"].abs().max()
            df_indicators["flow_sentiment"] = (df_indicators["total_flow"] / max_flow * 50 + 50).clip(0, 100)

        # 5. 资金流向一致性
        if all(col in df_indicators.columns for col in ["north_ratio", "main_ratio"]):
            df_indicators["flow_consistency"] = 1 - abs(df_indicators["north_ratio"] - df_indicators["main_ratio"])

        # 6. 累计资金流向变化
        if "north_cumulative" in df_indicators.columns:
            df_indicators["north_cumulative_change"] = df_indicators["north_cumulative"].diff()
            df_indicators["north_cumulative_momentum"] = df_indicators["north_cumulative"].pct_change(5)

        return df_indicators

    def get_industry_flows(self, df: pd.DataFrame) -> Dict[str, List[Dict]]:
        """获取行业资金流向数据

        Args:
            df: 资金流向数据

        Returns:
            行业资金流向字典
        """
        if df.empty or "industry_flows" not in df.columns:
            return {}

        result = {}
        industry_list = ["医药生物", "电子", "计算机", "新能源", "金融", "消费"]

        for industry in industry_list:
            flows = []
            for _, row in df.iterrows():
                try:
                    industry_flows = json.loads(row["industry_flows"])
                    flows.append({
                        "date": row["date"].strftime("%Y-%m-%d"),
                        "flow": industry_flows.get(industry, 0),
                    })
                except Exception:
                    continue

            if flows:
                result[industry] = flows

        return result

    def get_flow_summary(self, df: pd.DataFrame, date: str = None) -> Dict[str, Any]:
        """获取资金流向摘要信息

        Args:
            df: 资金流向数据
            date: 指定日期

        Returns:
            包含资金流向 summary 的字典
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
            "north_flow": float(df_temp["north_flow"].iloc[0]) if not df_temp.empty and "north_flow" in df_temp.columns else 0,
            "north_cumulative": float(df_temp["north_cumulative"].iloc[0]) if not df_temp.empty and "north_cumulative" in df_temp.columns else 0,
            "main_flow": float(df_temp["main_flow"].iloc[0]) if not df_temp.empty and "main_flow" in df_temp.columns else 0,
            "main_cumulative": float(df_temp["main_cumulative"].iloc[0]) if not df_temp.empty and "main_cumulative" in df_temp.columns else 0,
            "small_flow": float(df_temp["small_flow"].iloc[0]) if not df_temp.empty and "small_flow" in df_temp.columns else 0,
            "total_flow": float(df_temp["total_flow"].iloc[0]) if not df_temp.empty and "total_flow" in df_temp.columns else 0,
            "flow_type": df_temp["flow_type"].iloc[0] if not df_temp.empty and "flow_type" in df_temp.columns else "unknown",
            "flow_sentiment": float(df_temp["flow_sentiment"].iloc[0]) if not df_temp.empty and "flow_sentiment" in df_temp.columns else 50,
            "north_momentum_1d": float(df_temp["north_momentum_1d"].iloc[0]) if not df_temp.empty and "north_momentum_1d" in df_temp.columns else 0,
        }

        return summary

    def get_flow_trend(self, df: pd.DataFrame, window: int = 20) -> Dict[str, List[float]]:
        """获取资金流向趋势数据

        Args:
            df: 资金流向数据
            window: 窗口大小

        Returns:
            包含趋势数据的字典
        """
        if df.empty or "total_flow" not in df.columns:
            return {}

        df_temp = df.sort_values("date").copy()

        # 计算移动平均
        df_temp["total_flow_ma"] = df_temp["total_flow"].rolling(window).mean()

        # 计算趋势
        trend_data = {
            "dates": df_temp["date"].iloc[-window:].dt.strftime("%Y-%m-%d").tolist(),
            "total_flow": df_temp["total_flow"].iloc[-window:].tolist(),
            "north_flow": df_temp["north_flow"].iloc[-window:].tolist(),
            "main_flow": df_temp["main_flow"].iloc[-window:].tolist(),
            "total_flow_ma": df_temp["total_flow_ma"].iloc[-window:].tolist(),
        }

        return trend_data

    def save_data(self, df: pd.DataFrame, filename: str = None) -> bool:
        """保存资金流向数据到CSV文件

        Args:
            df: 数据DataFrame
            filename: 文件名

        Returns:
            是否成功
        """
        if filename is None:
            filename = "flow.csv"

        filepath = self.data_dir / filename

        try:
            # 确保date列为datetime
            if not isinstance(df["date"], pd.DatetimeIndex):
                df["date"] = pd.to_datetime(df["date"])

            df.to_csv(filepath, index=False)
            return True
        except Exception as e:
            print(f"保存资金流向数据失败: {e}")
            return False

    def load_data(self, filename: str = None) -> pd.DataFrame:
        """加载资金流向数据

        Args:
            filename: 文件名

        Returns:
            DataFrame数据
        """
        if filename is None:
            filename = "flow.csv"

        filepath = self.data_dir / filename

        if filepath.exists():
            try:
                df = pd.read_csv(filepath, parse_dates=["date"])
                return df
            except Exception:
                pass

        return pd.DataFrame()
