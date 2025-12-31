"""pytest配置和共享fixtures"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tempfile
import os


@pytest.fixture
def sample_price_data():
    """创建示例价格数据"""
    dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
    prices = np.random.uniform(100, 200, 100)
    return pd.Series(prices, index=dates, name="close")


@pytest.fixture
def sample_ohlcv_data():
    """创建示例OHLCV数据"""
    dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
    data = {
        "open": np.random.uniform(100, 200, 100),
        "high": np.random.uniform(200, 300, 100),
        "low": np.random.uniform(50, 100, 100),
        "close": np.random.uniform(100, 200, 100),
        "volume": np.random.uniform(1000000, 5000000, 100),
    }
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def sample_returns():
    """创建示例收益率数据"""
    dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
    returns = np.random.normal(0.001, 0.02, 100)  # 均值0.1%，标准差2%
    return pd.Series(returns, index=dates)


@pytest.fixture
def sample_account():
    """创建示例账户数据"""
    return {
        "cash": 1000000.0,
        "positions": {
            "AAPL": 100,
            "TSLA": 50,
        },
        "equity_history": [],
        "trade_log": [],
    }


@pytest.fixture
def temp_dir():
    """创建临时目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

