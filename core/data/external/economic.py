"""宏观经济数据加载器

提供GDP/CPI/PMI/利率等宏观经济数据的获取、清洗和特征提取功能。

数据源：
- 国家统计局API
-_wind API (可选)
- 其他公开宏观经济数据源

存储格式：
- data/external/economic.csv
"""

from __future__ import annotations

import os
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass
from functools import lru_cache

import pandas as pd
import numpy as np
import requests

# 缓存配置
CACHE_DIR = Path("data/external/cache")
CACHE_EXPIRY_DAYS = 7  # 缓存7天

# 数据存储路径
ECONOMIC_DATA_FILE = Path("data/external/economic.csv")


@dataclass
class EconomicDataConfig:
    """宏观经济数据配置"""
    # 数据源配置
    sources: Dict[str, Dict[str, Any]] = None

    def __post_init__(self):
        self.sources = {
            "nbose": {  # 国家统计局
                "gdp": {
                    "url": "http://data.stats.gov.cn/newdata/aj query.htm",
                    "interval": "quarterly",  # 季度数据
                    "code": "gdp",
                },
                "cpi": {
                    "url": "http://data.stats.gov.cn/newdata/aj query.htm",
                    "interval": "monthly",  # 月度数据
                    "code": "cpi",
                },
                "pmi": {
                    "url": "http://data.stats.gov.cn/newdata/aj query.htm",
                    "interval": "monthly",  # 月度数据
                    "code": "pmi",
                },
            },
            "marketdocs": {  # 市场文档网（备用数据源）
                "url": "https://www.marketdocs.cn/api/economic",
                "interval": "monthly",
            },
        }


class EconomicDataLoader:
    """宏观经济数据加载器

    功能：
    - 数据获取：从国家统计局等数据源获取GDP/CPI/PMI/利率数据
    - 数据清洗：缺失值处理、异常值过滤
    - 特征提取：百分位数、动量、均线
    - 缓存机制：避免重复请求
    """

    def __init__(self, data_dir: str = "data/external"):
        """初始化宏观经济数据加载器

        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config = EconomicDataConfig()
        self.cache_dir = Path(data_dir) / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 各数据项的详细列名定义
        self.economic_columns = {
            "gdp": {
                "国内生产总值": "gdp",  # 亿元
                "国内生产总值_增长率": "gdp_yoy",  # 同比增长率
                "第一产业": "gdp_first",  # 第一产业增加值
                "第二产业": "gdp_second",  # 第二产业增加值
                "第三产业": "gdp_third",  # 第三产业增加值
            },
            "cpi": {
                "居民消费价格指数": "cpi",  # CPI指数
                "食品烟酒": "cpi_food",  # 食品烟酒类
                "衣着": "cpi_clothing",  # 衣着类
                "居住": "cpi_housing",  # 居住类
                "生活用品及服务": "cpi_living",  # 生活用品及服务
                "交通通信": "cpi_transport",  # 交通通信
                "教育文化娱乐": "cpi_education",  # 教育文化娱乐
                "医疗保健": "cpi_health",  # 医疗保健
                "其他用品及服务": "cpi_other",  # 其他
            },
            "pmi": {
                "制造业pmi": "pmi_manufacturing",  # 制造业PMI
                "制造业_pm_KeyUp": "pmi_manufacturing_ppi clue",  # 制造业PMI分项 - 采购经理人指数
                "制造业_新订单": "pmi_new_orders",  # 新订单指数
                "制造业_生产": "pmi_production",  # 生产指数
                "制造业_从业人员": "pmi_employment",  # 从业人员指数
                "非制造业pmi": "pmi_services",  # 非制造业PMI
                "综合pmi": "pmi_combined",  # 综合PMI
            },
            "interest_rate": {
                "shdr001_加权平均利率": "rate_shdr_001",  # SHDR 001
                "shibor_3个月": "rate_shibor_3m",  # SHIBOR 3M
                "国债收益率_10年": "rate_tb_10y",  # 国债收益率 10年
                "贷款基础利率": "rate_lpr",  # LPR
            },
        }

        # 数据更新频率
        self.update_freq = {
            "gdp": "quarterly",   # 季度
            "cpi": "monthly",     # 月度
            "pmi": "monthly",     # 月度
            "interest_rate": "daily",  # 日度（部分利率）
        }

        # 数据源降级顺序（优先级从高到低）
        self.source_priority = ["nbose", "marketdocs"]

    def get_cache_key(self, data_type: str, start_date: str, end_date: str) -> str:
        """生成缓存键

        Args:
            data_type: 数据类型 (gdp/cpi/pmi/interest_rate)
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            缓存键字符串
        """
        content = f"{data_type}_{start_date}_{end_date}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    @lru_cache(maxsize=100)
    def load_from_cache(self, cache_key: str) -> Optional[pd.DataFrame]:
        """从缓存加载数据

        Args:
            cache_key: 缓存键

        Returns:
            DataFrame数据或None
        """
        cache_file = self.cache_dir / f"{cache_key}.csv"
        if cache_file.exists():
            try:
                return pd.read_csv(cache_file, parse_dates=["date"])
            except Exception:
                return None
        return None

    def save_to_cache(self, cache_key: str, df: pd.DataFrame) -> None:
        """保存数据到缓存

        Args:
            cache_key: 缓存键
            df: 数据DataFrame
        """
        cache_file = self.cache_dir / f"{cache_key}.csv"
        try:
            df.to_csv(cache_file, index=False)
        except Exception:
            pass

    def fetch_from_nbose(self, data_type: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从国家统计局API获取数据（模拟接口）

        注意：实际使用时需要根据国家统计局真实API调整

        Args:
            data_type: 数据类型
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame格式的数据
        """
        # 国家统计局API URL (示例)
        base_url = "http://data.stats.gov.cn/newdata/aj query.htm"

        # 定义各数据类型的查询参数
        query_params = {
            "gdp": {"code": "gdp", "interval": "3"},
            "cpi": {"code": "cpi", "interval": "1"},
            "pmi": {"code": "pmi", "interval": "1"},
        }

        params = query_params.get(data_type, {})
        params.update({
            "startdate": start_date,
            "enddate": end_date,
            "m": "QueryData",
            "dbcode": "hgjd",
        })

        try:
            # 尝试获取数据
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            # 解析数据
            df = self._parse_nbose_data(data, data_type)

            # 过滤日期范围
            if not df.empty:
                df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]

            return df

        except Exception as e:
            print(f"从国家统计局获取 {data_type} 数据失败: {e}")
            return pd.DataFrame()

    def _parse_nbose_data(self, data: Dict, data_type: str) -> pd.DataFrame:
        """解析国家统计局返回的数据

        Args:
            data: API返回的JSON数据
            data_type: 数据类型

        Returns:
            DataFrame格式的数据
        """
        rows = []

        # 国家统计局数据格式解析（示例）
        # 实际格式可能需要根据真实API调整
        if "row" in data:
            for item in data["row"]:
                row = {"date": item.get("regDate", item.get("date", ""))}

                # 根据数据类型提取对应字段
                if data_type == "gdp":
                    row["gdp"] = item.get("ajs数值", item.get("gdp", np.nan))
                    row["gdp_yoy"] = item.get("ajs同比增长", item.get("gdp_yoy", np.nan))
                    row["gdp_first"] = item.get("第一产业", np.nan)
                    row["gdp_second"] = item.get("第二产业", np.nan)
                    row["gdp_third"] = item.get("第三产业", np.nan)

                elif data_type == "cpi":
                    row["cpi"] = item.get("居民消费价格指数", np.nan)
                    row["cpi_food"] = item.get("食品烟酒", np.nan)
                    row["cpi_clothing"] = item.get("衣着", np.nan)
                    row["cpi_housing"] = item.get("居住", np.nan)

                elif data_type == "pmi":
                    row["pmi_manufacturing"] = item.get("制造业pmi", np.nan)
                    row["pmi_new_orders"] = item.get("新订单", np.nan)
                    row["pmi_production"] = item.get("生产", np.nan)

                rows.append(row)

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").reset_index(drop=True)

    def fetch_from_marketdocs(self, data_type: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从市场文档网获取宏观经济数据（备用数据源）

        Args:
            data_type: 数据类型
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame格式的数据
        """
        # 这里使用模拟数据作为示例
        # 实际使用时需要对接真实API或使用本地数据文件
        return self._generate_synthetic_data(data_type, start_date, end_date)

    def _generate_synthetic_data(self, data_type: str, start_date: str, end_date: str) -> pd.DataFrame:
        """生成模拟数据（当数据源不可用时的降级方案）

        Args:
            data_type: 数据类型
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame格式的模拟数据
        """
        # 使用Moregenerally的起始日期
        if data_type == "gdp":
            # GDP数据（季度）
            start = pd.Timestamp("2010-01-01")
            end = pd.Timestamp(end_date)
            dates = pd.date_range(start=start, end=end, freq="Q")

            # 生成合理的GDP增长序列
            np.random.seed(42)
            base_value = 400000  # 万亿元
            growth_rates = np.random.normal(6.0, 2.0, len(dates))  # 平均6%增长

            values = []
            current = base_value
            for gr in growth_rates:
                current = current * (1 + gr / 100)
                values.append(current)

            df = pd.DataFrame({
                "date": dates,
                "gdp": values,
                "gdp_yoy": growth_rates + 6,  # 添加同比增长
                "gdp_first": [v * 0.07 for v in values],  # 第一产业占比约7%
                "gdp_second": [v * 0.37 for v in values],  # 第二产业占比约37%
                "gdp_third": [v * 0.56 for v in values],  # 第三产业占比约56%
            })

        elif data_type == "cpi":
            # CPI数据（月度）
            start = pd.Timestamp("2010-01-01")
            end = pd.Timestamp(end_date)
            dates = pd.date_range(start=start, end=end, freq="MS")

            np.random.seed(42)
            base_cpi = 100
            cpi_values = [base_cpi]
            for _ in range(len(dates) - 1):
                change = np.random.normal(0.5, 0.3)  # 平均0.5%月涨
                cpi_values.append(cpi_values[-1] * (1 + change / 100))

            df = pd.DataFrame({
                "date": dates,
                "cpi": cpi_values,
                "cpi_food": [c * 1.2 for c in cpi_values],  # 食品CPI较高
                "cpi_housing": [c * 1.1 for c in cpi_values],  # 居住CPI
                "cpi_transport": [c * 1.05 for c in cpi_values],  # 交通CPI
            })

        elif data_type == "pmi":
            # PMI数据（月度）
            start = pd.Timestamp("2010-01-01")
            end = pd.Timestamp(end_date)
            dates = pd.date_range(start=start, end=end, freq="MS")

            np.random.seed(42)
            # PMI通常在50左右波动
            pmi_values = [50 + np.random.normal(0, 3) for _ in range(len(dates))]

            df = pd.DataFrame({
                "date": dates,
                "pmi_manufacturing": pmi_values,
                "pmi_new_orders": [p + np.random.normal(1, 2) for p in pmi_values],
                "pmi_production": [p + np.random.normal(0.5, 2) for p in pmi_values],
                "pmi_employment": [p + np.random.normal(-0.5, 2) for p in pmi_values],
                "pmi_services": [p + np.random.normal(1, 3) for p in pmi_values],
            })

        else:
            # 利率数据（日度）
            start = pd.Timestamp("2010-01-01")
            end = pd.Timestamp(end_date)
            dates = pd.date_range(start=start, end=end, freq="D")

            np.random.seed(42)
            # 利率在2-8%之间波动
            rates = [2 + np.random.uniform(0, 6) for _ in range(len(dates))]

            df = pd.DataFrame({
                "date": dates,
                "rate_shibor_3m": rates,
                "rate_tb_10y": [r + 2 for r in rates],  # 国债收益率较高
                "rate_lpr": [r - 0.5 for r in rates],  # LPR相对较低
            })

        # 过滤日期范围
        df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
        return df.reset_index(drop=True)

    def fetch_economic_data(self, data_type: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取宏观经济数据（主入口）

        Args:
            data_type: 数据类型 (gdp/cpi/pmi/interest_rate)
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame格式的数据
        """
        cache_key = self.get_cache_key(data_type, start_date, end_date)

        # 1. 尝试从缓存加载
        cached = self.load_from_cache(cache_key)
        if cached is not None:
            return cached

        # 2. 尝试从优先级最高的数据源获取
        for source in self.source_priority:
            if source == "nbose":
                df = self.fetch_from_nbose(data_type, start_date, end_date)
            elif source == "marketdocs":
                df = self.fetch_from_marketdocs(data_type, start_date, end_date)
            else:
                df = pd.DataFrame()

            if not df.empty:
                self.save_to_cache(cache_key, df)
                return df

        # 3. 所有数据源失败，使用合成数据
        print(f"所有数据源不可用，使用合成数据: {data_type}")
        df = self._generate_synthetic_data(data_type, start_date, end_date)
        self.save_to_cache(cache_key, df)
        return df

    def clean_data(self, df: pd.DataFrame, data_type: str) -> pd.DataFrame:
        """清洗数据

        功能：
        - 缺失值处理
        - 异常值过滤

        Args:
            df: 原始数据
            data_type: 数据类型

        Returns:
            清洗后的数据
        """
        if df.empty:
            return df

        df_clean = df.copy()
        date_col = "date"

        # 1. 处理缺失值
        # 使用前向填充（ffill）和后向填充（bfill）
        numeric_cols = df_clean.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            # 先前向填充，再后向填充
            df_clean[col] = df_clean[col].fillna(method="ffill").fillna(method="bfill")

            # 处理剩余的NaN
            df_clean[col] = df_clean[col].fillna(0)

        # 2. 异常值过滤（使用IQR方法）
        for col in numeric_cols:
            if col == date_col:
                continue

            Q1 = df_clean[col].quantile(0.25)
            Q3 = df_clean[col].quantile(0.75)
            IQR = Q3 - Q1

            lower_bound = Q1 - 3 * IQR  # 放宽异常值标准
            upper_bound = Q3 + 3 * IQR

            # 将异常值替换为边界值
            df_clean[col] = df_clean[col].clip(lower=lower_bound, upper=upper_bound)

        # 3. 确保数据按日期排序
        if date_col in df_clean.columns:
            df_clean = df_clean.sort_values(date_col).reset_index(drop=True)

        return df_clean

    def extract_features(self, df: pd.DataFrame, data_type: str) -> pd.DataFrame:
        """提取特征

        功能：
        - 百分位数（相对位置）
        - 动量指标（同比/环比变化）
        - 均线（MA）

        Args:
            df: 原始数据
            data_type: 数据类型

        Returns:
            添加特征后的数据
        """
        if df.empty:
            return df

        df_features = df.copy()

        # 按数据类型处理不同特征
        if data_type == "gdp":
            # GDP相关特征
            # 1. 百分位数（相对于历史）
            if "gdp" in df_features.columns:
                df_features["gdp_percentile"] = df_features["gdp"].rank(pct=True)

                # 相对历史均值的偏离
                mean_gdp = df_features["gdp"].mean()
                std_gdp = df_features["gdp"].std()
                df_features["gdp_zscore"] = (df_features["gdp"] - mean_gdp) / std_gdp

            # 2. 动量（同比增长率）
            if "gdp_yoy" in df_features.columns:
                df_features["gdp_yoy_ma3"] = df_features["gdp_yoy"].rolling(3).mean()
                df_features["gdp_yoy_ma6"] = df_features["gdp_yoy"].rolling(6).mean()

                # 动量变化
                df_features["gdp_yoy_momentum"] = df_features["gdp_yoy"].diff(1)

        elif data_type == "cpi":
            # CPI相关特征
            if "cpi" in df_features.columns:
                # 百分位数
                df_features["cpi_percentile"] = df_features["cpi"].rank(pct=True)

                # Z-score
                mean_cpi = df_features["cpi"].mean()
                std_cpi = df_features["cpi"].std()
                df_features["cpi_zscore"] = (df_features["cpi"] - mean_cpi) / std_cpi

                # 均线
                df_features["cpi_ma3"] = df_features["cpi"].rolling(3).mean()
                df_features["cpi_ma6"] = df_features["cpi"].rolling(6).mean()

                # 月度变动
                df_features["cpi_mom"] = df_features["cpi"].pct_change(1)

            # 食品CPI与非食品CPI差
            if "cpi_food" in df_features.columns and "cpi" in df_features.columns:
                non_food_cpi = df_features["cpi"] * 100 - df_features["cpi_food"]
                df_features["cpi_food_diff"] = df_features["cpi_food"] - non_food_cpi

        elif data_type == "pmi":
            # PMI相关特征
            if "pmi_manufacturing" in df_features.columns:
                # 百分位数
                df_features["pmi_percentile"] = df_features["pmi_manufacturing"].rank(pct=True)

                # Z-score
                mean_pmi = df_features["pmi_manufacturing"].mean()
                std_pmi = df_features["pmi_manufacturing"].std()
                df_features["pmi_zscore"] = (df_features["pmi_manufacturing"] - mean_pmi) / std_pmi

                # 与50临界值的距离
                df_features["pmi_gap_50"] = df_features["pmi_manufacturing"] - 50

                # 均线
                df_features["pmi_ma3"] = df_features["pmi_manufacturing"].rolling(3).mean()
                df_features["pmi_ma6"] = df_features["pmi_manufacturing"].rolling(6).mean()

                # 动量
                df_features["pmi_momentum"] = df_features["pmi_manufacturing"].diff(1)

        elif data_type == "interest_rate":
            # 利率相关特征
            for col in df_features.columns:
                if col.startswith("rate_"):
                    # 百分位数
                    df_features[f"{col}_percentile"] = df_features[col].rank(pct=True)

                    # Z-score
                    mean_rate = df_features[col].mean()
                    std_rate = df_features[col].std()
                    df_features[f"{col}_zscore"] = (df_features[col] - mean_rate) / std_rate

                    # 与历史均值的差
                    df_features[f"{col}_spread"] = df_features[col] - mean_rate

                    # 均线
                    df_features[f"{col}_ma5"] = df_features[col].rolling(5).mean()
                    df_features[f"{col}_ma20"] = df_features[col].rolling(20).mean()

        return df_features

    def get_all_data(self, start_date: str = "2010-01-01", end_date: str = None) -> Dict[str, pd.DataFrame]:
        """获取所有类型的数据

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            以数据类型为键的DataFrame字典
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        data_types = ["gdp", "cpi", "pmi", "interest_rate"]
        result = {}

        for data_type in data_types:
            try:
                # 1. 获取原始数据
                df_raw = self.fetch_economic_data(data_type, start_date, end_date)

                # 2. 清洗数据
                df_clean = self.clean_data(df_raw, data_type)

                # 3. 提取特征
                df_features = self.extract_features(df_clean, data_type)

                result[data_type] = df_features

            except Exception as e:
                print(f"获取 {data_type} 数据时出错: {e}")
                result[data_type] = pd.DataFrame()

        return result

    def save_data(self, data_dict: Dict[str, pd.DataFrame], filename: str = None) -> bool:
        """保存数据到CSV文件

        Args:
            data_dict: 数据字典
            filename: 文件名

        Returns:
            是否成功
        """
        if filename is None:
            filename = "economic.csv"

        filepath = self.data_dir / filename

        try:
            # 合并所有数据
            all_data = []
            for data_type, df in data_dict.items():
                if df.empty:
                    continue

                df["data_type"] = data_type
                all_data.append(df)

            if all_data:
                combined = pd.concat(all_data, ignore_index=True)
                combined.to_csv(filepath, index=False)

                print(f"数据已保存到: {filepath}")
                return True
            else:
                print("没有数据可保存")
                return False

        except Exception as e:
            print(f"保存数据失败: {e}")
            return False

    def load_saved_data(self, filename: str = None) -> pd.DataFrame:
        """加载已保存的数据

        Args:
            filename: 文件名

        Returns:
            DataFrame数据
        """
        if filename is None:
            filename = "economic.csv"

        filepath = self.data_dir / filename

        if filepath.exists():
            try:
                df = pd.read_csv(filepath, parse_dates=["date"])
                return df
            except Exception:
                return pd.DataFrame()

        return pd.DataFrame()

    def get_economic_indicators(self, start_date: str = "2010-01-01", end_date: str = None) -> pd.DataFrame:
        """获取经济指标数据（格式化输出）

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            处理后的经济指标DataFrame
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        all_data = self.get_all_data(start_date, end_date)
        combined = self.combine_dataframes(all_data)

        return combined

    def combine_dataframes(self, data_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """合并多个DataFrame

        Args:
            data_dict: 数据字典

        Returns:
            合并后的DataFrame
        """
        if not data_dict:
            return pd.DataFrame()

        # 以gdp为基准（季度数据），其他数据进行对齐
        base_df = data_dict.get("gdp")

        if base_df is None or base_df.empty:
            # 使用其他数据作为基准
            for df in data_dict.values():
                if not df.empty:
                    base_df = df
                    break

        if base_df is None or base_df.empty:
            return pd.DataFrame()

        # 重采样其他数据以匹配基准数据的频率
        combined = base_df.set_index("date")

        for data_type, df in data_dict.items():
            if df.empty or data_type == "gdp":
                continue

            df_temp = df.set_index("date")

            # 重采样（季度数据转月度，月度数据保持）
            if data_type == "cpi" or data_type == "pmi":
                # 月度数据，重新采样到基准频率
                try:
                    df_resampled = df_temp.resample(combined.index.freq).ffill()
                    combined = combined.join(df_resampled, how="outer")
                except Exception:
                    combined = combined.join(df_temp, how="outer")

        combined = combined.reset_index()
        return combined.sort_values("date")
