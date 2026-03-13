"""外部数据加载器测试

测试宏观经济数据、行业轮动数据、市场情绪数据和资金流向数据的加载功能。
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta

# 跳过需要真实数据源的测试
pytestmark = pytest.mark.skip(reason="需要真实数据源，暂不运行")


class TestEconomicDataLoader:
    """宏观经济数据加载器测试"""

    def test_init(self):
        """测试初始化"""
        from core.data.external.economic import EconomicDataLoader
        loader = EconomicDataLoader()
        assert loader is not None
        assert loader.config is not None

    def test_fetch_gdp_data(self):
        """测试GDP数据获取"""
        from core.data.external.economic import EconomicDataLoader
        loader = EconomicDataLoader()

        start_date = "2020-01-01"
        end_date = "2024-12-31"

        df = loader.fetch_economic_data("gdp", start_date, end_date)

        # 测试返回的数据格式
        if not df.empty:
            assert "date" in df.columns
            assert "gdp" in df.columns
            assert "gdp_yoy" in df.columns

    def test_fetch_cpi_data(self):
        """测试CPI数据获取"""
        from core.data.external.economic import EconomicDataLoader
        loader = EconomicDataLoader()

        start_date = "2020-01-01"
        end_date = "2024-12-31"

        df = loader.fetch_economic_data("cpi", start_date, end_date)

        if not df.empty:
            assert "date" in df.columns
            assert "cpi" in df.columns

    def test_clean_data(self):
        """测试数据清洗"""
        from core.data.external.economic import EconomicDataLoader
        loader = EconomicDataLoader()

        # 创建测试数据
        df = pd.DataFrame({
            "date": pd.date_range("2020-01-01", periods=10),
            "gdp": [100, 102, None, 105, 107, 109, 111, None, 115, 117],
        })

        df_clean = loader.clean_data(df, "gdp")

        # 测试缺失值已填充
        assert df_clean["gdp"].isna().sum() == 0

    def test_extract_features(self):
        """测试特征提取"""
        from core.data.external.economic import EconomicDataLoader
        loader = EconomicDataLoader()

        # 创建测试数据
        df = pd.DataFrame({
            "date": pd.date_range("2020-01-01", periods=20),
            "gdp": list(range(100, 120)),
        })

        df_features = loader.extract_features(df, "gdp")

        # 测试特征已添加
        assert "gdp_percentile" in df_features.columns
        assert "gdp_zscore" in df_features.columns


class TestIndustryDataLoader:
    """行业轮动数据加载器测试"""

    def test_init(self):
        """测试初始化"""
        from core.data.external.industry import IndustryDataLoader
        loader = IndustryDataLoader()
        assert loader is not None
        assert loader.config is not None

    def test_fetch_industry_data(self):
        """测试行业指数获取"""
        from core.data.external.industry import IndustryDataLoader
        loader = IndustryDataLoader()

        start_date = "2023-01-01"
        end_date = "2023-12-31"

        df = loader.fetch_industry_data(start_date, end_date)

        if not df.empty:
            assert "date" in df.columns
            assert "industry_code" in df.columns
            assert "industry_name" in df.columns
            assert "close" in df.columns

    def test_calculate_indicators(self):
        """测试指标计算"""
        from core.data.external.industry import IndustryDataLoader
        loader = IndustryDataLoader()

        # 创建测试数据
        dates = pd.date_range("2023-01-01", periods=100)
        rows = []
        for i, date in enumerate(dates):
            for code in ["801010", "801020"]:
                rows.append({
                    "date": date,
                    "industry_code": code,
                    "close": 3000 + i * 10,
                })
        df = pd.DataFrame(rows)

        df_indicators = loader.calculate_indicators(df)

        # 测试指标已添加
        assert "return_1d" in df_indicators.columns
        assert "return_5d" in df_indicators.columns
        assert "volatility_10" in df_indicators.columns


class TestSentimentDataLoader:
    """市场情绪数据加载器测试"""

    def test_init(self):
        """测试初始化"""
        from core.data.external.sentiment import SentimentDataLoader
        loader = SentimentDataLoader()
        assert loader is not None
        assert loader.config is not None

    def test_fetch_sentiment_data(self):
        """测试情绪数据获取"""
        from core.data.external.sentiment import SentimentDataLoader
        loader = SentimentDataLoader()

        start_date = "2023-01-01"
        end_date = "2023-12-31"

        df = loader.fetch_sentiment_data(start_date, end_date)

        if not df.empty:
            assert "date" in df.columns
            assert "zhang_ting" in df.columns
            assert "die_ting" in df.columns

    def test_calculate_sentiment_indicators(self):
        """测试情绪指标计算"""
        from core.data.external.sentiment import SentimentDataLoader
        loader = SentimentDataLoader()

        # 创建测试数据
        df = pd.DataFrame({
            "date": pd.date_range("2023-01-01", periods=20),
            "zhang_ting": [50] * 20,
            "die_ting": [20] * 20,
            "turnover": [10000] * 20,
        })

        df_indicators = loader.calculate_sentiment_indicators(df)

        # 测试指标已添加
        assert "zhangdie_ratio" in df_indicators.columns
        assert "sentiment_index" in df_indicators.columns
        assert "sentiment_heat" in df_indicators.columns


class TestFlowDataLoader:
    """资金流向数据加载器测试"""

    def test_init(self):
        """测试初始化"""
        from core.data.external.flow import FlowDataLoader
        loader = FlowDataLoader()
        assert loader is not None
        assert loader.config is not None

    def test_fetch_flow_data(self):
        """测试资金流向数据获取"""
        from core.data.external.flow import FlowDataLoader
        loader = FlowDataLoader()

        start_date = "2023-01-01"
        end_date = "2023-12-31"

        df = loader.fetch_flow_data(start_date, end_date)

        if not df.empty:
            assert "date" in df.columns
            assert "north_flow" in df.columns
            assert "main_flow" in df.columns

    def test_calculate_flow_indicators(self):
        """测试资金流向指标计算"""
        from core.data.external.flow import FlowDataLoader
        loader = FlowDataLoader()

        # 创建测试数据
        df = pd.DataFrame({
            "date": pd.date_range("2023-01-01", periods=20),
            "north_flow": [50] * 20,
            "main_flow": [30] * 20,
            "small_flow": [-24] * 20,
        })

        df_indicators = loader.calculate_flow_indicators(df)

        # 测试指标已添加
        assert "flow_type" in df_indicators.columns
        assert "flow_sentiment" in df_indicators.columns
        assert "north_momentum_1d" in df_indicators.columns


class TestExternalDataLoader:
    """统一外部数据加载器测试"""

    def test_init(self):
        """测试初始化"""
        from core.data.external.loader import ExternalDataLoader
        loader = ExternalDataLoader()
        assert loader is not None
        assert loader.economic_loader is not None
        assert loader.industry_loader is not None
        assert loader.sentiment_loader is not None
        assert loader.flow_loader is not None

    def test_load_all_external_data(self):
        """测试加载所有外部数据"""
        from core.data.external.loader import ExternalDataLoader
        loader = ExternalDataLoader()

        start_date = "2023-01-01"
        end_date = "2023-12-31"

        external_data = loader.load_all_external_data(start_date, end_date)

        assert "economic" in external_data
        assert "industry" in external_data
        assert "sentiment" in external_data
        assert "flow" in external_data

    def test_merge_price_with_external(self):
        """测试价格数据与外部数据合并"""
        from core.data.external.loader import ExternalDataLoader
        loader = ExternalDataLoader()

        # 创建测试价格数据
        price_df = pd.DataFrame({
            "date": pd.date_range("2023-01-01", periods=10),
            "AAPL": [150] * 10,
        })

        # 创建测试外部数据
        external_data = {
            "economic": {
                "cpi": pd.DataFrame({
                    "date": pd.date_range("2023-01-01", periods=10),
                    "cpi": [100] * 10,
                })
            },
            "sentiment": pd.DataFrame({
                "date": pd.date_range("2023-01-01", periods=10),
                "sentiment_index": [50] * 10,
            }),
        }

        merged_df = loader.merge_price_with_external(price_df, external_data)

        # 测试合并成功
        assert not merged_df.empty
        assert "date" in merged_df.columns

    def test_get_full_pipeline(self):
        """测试完整特征工程管道"""
        from core.data.external.loader import ExternalDataLoader
        loader = ExternalDataLoader()

        # 创建测试价格数据
        price_df = pd.DataFrame({
            "date": pd.date_range("2023-01-01", periods=20),
            "AAPL": list(range(100, 120)),
        })

        features_df = loader.get_full_pipeline(price_df, start_date="2023-01-01", end_date="2023-01-20")

        # 测试特征已添加
        assert not features_df.empty
        assert "date" in features_df.columns
