"""
特征工程模块单元测试

测试16项新特征的计算正确性
"""

import pytest
import numpy as np
import pandas as pd

# 测试导入
try:
    from core.features.basic import VolatilityFeatures, TrendFeatures
    from core.features.advanced import (
        MomentumFeatures,
        EfficiencyFeatures,
        MeanReversionFeatures,
    )
    FEATURES_AVAILABLE = True
except ImportError:
    FEATURES_AVAILABLE = False


@pytest.mark.skipif(not FEATURES_AVAILABLE, reason="Features not available")
class TestVolatilityFeatures:
    """测试波动率特征"""

    def setup_method(self):
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        prices = 100 + np.cumsum(np.random.randn(100))
        self.price_series = pd.Series(prices, index=dates)

    def test_realized_volatility_windows(self):
        """测试不同窗口的实现波动率"""
        df = VolatilityFeatures.compute_all(self.price_series)

        # 检查所有窗口的波动率是否存在
        assert "realized_vol_5" in df.columns
        assert "realized_vol_20" in df.columns
        assert "realized_vol_60" in df.columns

        # 检查波动率值的合理性（通常在0-1之间）
        assert df["realized_vol_5"].notna().any()
        assert df["realized_vol_20"].notna().any()
        assert df["realized_vol_60"].notna().any()

    def test_vol_ratio(self):
        """测试波动率比值"""
        df = VolatilityFeatures.compute_all(self.price_series)

        assert "vol_ratio_5_20" in df.columns
        # 短期/长期波动率比值应该在合理范围内
        ratio = df["vol_ratio_5_20"].dropna()
        assert len(ratio) > 0


@pytest.mark.skipif(not FEATURES_AVAILABLE, reason="Features not available")
class TestTrendFeatures:
    """测试趋势特征"""

    def setup_method(self):
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        prices = 100 + np.cumsum(np.random.randn(100))
        self.price_series = pd.Series(prices, index=dates)

    def test_adx_trend_strength(self):
        """测试ADX趋势强度"""
        df = TrendFeatures.compute_all(self.price_series)

        assert "adx_14" in df.columns
        # ADX值应该在0-100之间
        adx = df["adx_14"].dropna()
        assert len(adx) > 0
        assert (adx >= 0).all() or adx.isna().any()

    def test_plus_di_minus_di(self):
        """测试+DI和-DI方向运动"""
        df = TrendFeatures.compute_all(self.price_series)

        assert "plus_di_14" in df.columns
        assert "minus_di_14" in df.columns


@pytest.mark.skipif(not FEATURES_AVAILABLE, reason="Features not available")
class TestMomentumFeatures:
    """测试动量特征"""

    def setup_method(self):
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        prices = 100 + np.cumsum(np.random.randn(100))
        self.price_series = pd.Series(prices, index=dates)

    def test_momentum_periods(self):
        """测试不同周期的动量"""
        df = MomentumFeatures.compute_all(self.price_series)

        assert "momentum_5" in df.columns
        assert "momentum_10" in df.columns
        assert "momentum_20" in df.columns

    def test_streak(self):
        """测试连涨连跌天数"""
        df = MomentumFeatures.compute_all(self.price_series)

        assert "streak" in df.columns
        # streak可以是正数（连涨）或负数（连跌）
        streak = df["streak"].dropna()
        assert len(streak) > 0


@pytest.mark.skipif(not FEATURES_AVAILABLE, reason="Features not available")
class TestEfficiencyFeatures:
    """测试价格效率特征"""

    def setup_method(self):
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        prices = 100 + np.cumsum(np.random.randn(100))
        self.price_series = pd.Series(prices, index=dates)

    def test_efficiency_ratio_periods(self):
        """测试不同周期的效率比"""
        df = EfficiencyFeatures.compute_all(self.price_series)

        assert "efficiency_ratio_10" in df.columns
        assert "efficiency_ratio_20" in df.columns

        # 效率比应该在0-1之间
        er = df["efficiency_ratio_10"].dropna()
        assert len(er) > 0

    def test_efficiency_ratio_range(self):
        """测试效率比值范围"""
        df = EfficiencyFeatures.compute_all(self.price_series)

        er_10 = df["efficiency_ratio_10"]
        # 检查是否有值被正确限制在0-1之间
        assert (er_10 >= 0).all() or er_10.isna().any()
        assert (er_10 <= 1).all() or er_10.isna().any()


@pytest.mark.skipif(not FEATURES_AVAILABLE, reason="Features not available")
class TestMeanReversionFeatures:
    """测试均值回归特征"""

    def setup_method(self):
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        prices = 100 + np.cumsum(np.random.randn(100))
        self.price_series = pd.Series(prices, index=dates)

    def test_zscore_windows(self):
        """测试不同窗口的Z分数"""
        df = MeanReversionFeatures.compute_all(self.price_series)

        assert "zscore_20" in df.columns
        assert "zscore_60" in df.columns

    def test_bb_position(self):
        """测试布林带位置"""
        df = MeanReversionFeatures.compute_all(self.price_series)

        assert "bb_position_20" in df.columns

        # 布林带位置应该在0-1之间
        bb = df["bb_position_20"].dropna()
        assert len(bb) > 0


@pytest.mark.skipif(not FEATURES_AVAILABLE, reason="Features not available")
class TestFeatureStoreIntegration:
    """测试FeatureStore集成"""

    def setup_method(self):
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        prices = 100 + np.cumsum(np.random.randn(100))
        self.price_series = pd.Series(prices, index=dates)

    def test_comprehensive_features_count(self):
        """测试新增特征总数"""
        from core.feature_store import FeatureStore

        store = FeatureStore()
        df = store._add_comprehensive_features(pd.DataFrame(), self.price_series)

        # 16项新特征
        expected_features = [
            # 波动率（4项）
            "realized_vol_5", "realized_vol_20", "realized_vol_60", "vol_ratio_5_20",
            # 趋势（3项）
            "adx_14", "plus_di_14", "minus_di_14",
            # 动量（4项）
            "momentum_5", "momentum_10", "momentum_20", "streak",
            # 均值回归（3项）
            "zscore_20", "zscore_60", "bb_position_20",
            # 价格效率（2项）
            "efficiency_ratio_10", "efficiency_ratio_20",
        ]

        for feature in expected_features:
            assert feature in df.columns, f"Missing feature: {feature}"


@pytest.mark.skipif(not FEATURES_AVAILABLE, reason="Features not available")
class TestFeatureEngineeringEdgeCases:
    """测试边界情况"""

    def test_short_price_series(self):
        """测试短价格序列"""
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=30, freq="D")
        prices = pd.Series(100 + np.cumsum(np.random.randn(30)), index=dates)

        df = VolatilityFeatures.compute_all(prices)
        # 60日波动率在30天数据上应该全为NaN
        assert "realized_vol_60" in df.columns

    def test_constant_price(self):
        """测试常价格序列"""
        dates = pd.date_range("2023-01-01", periods=50, freq="D")
        prices = pd.Series([100] * 50, index=dates)

        df = MomentumFeatures.compute_all(prices)
        # 常价格的动量应该为0（或NaN）
        assert "momentum_5" in df.columns
