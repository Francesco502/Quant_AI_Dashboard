"""Shared pytest fixtures for unit, integration, and e2e tests."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tempfile
import os
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from api.main import app
from api.auth import create_access_token, get_user_by_username, create_user


# --------------------------------------------------------------------------
# 鍏变韩fixtures
# --------------------------------------------------------------------------

# Fallback benchmark fixture for environments without pytest-benchmark.
try:
    import pytest_benchmark.plugin  # type: ignore  # noqa: F401
except Exception:
    @pytest.fixture
    def benchmark():
        def _run(func, *args, **kwargs):
            return func(*args, **kwargs)
        return _run

@pytest.fixture
def sample_price_data():
    """鍒涘缓绀轰緥浠锋牸鏁版嵁"""
    dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
    prices = np.random.uniform(100, 200, 100)
    return pd.Series(prices, index=dates, name="close")


@pytest.fixture
def sample_ohlcv_data():
    """鍒涘缓绀轰緥OHLCV鏁版嵁"""
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
    """鍒涘缓绀轰緥鏀剁泭鐜囨暟鎹?"""
    dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
    returns = np.random.normal(0.001, 0.02, 100)  # 鍧囧€?.1%锛屾爣鍑嗗樊2%
    return pd.Series(returns, index=dates)


@pytest.fixture
def sample_account():
    """鍒涘缓绀轰緥璐︽埛鏁版嵁"""
    return {
        "cash": 1000000.0,
        "positions": {
            "AAPL": 100,
            "TSLA": 50,
        },
        "equity_history": [],
        "trade_log": [],
    }


@pytest.fixture(scope="session")
def auth_token():
    """Create a reusable API token for authenticated integration tests."""
    username = "admin"
    if not get_user_by_username(username):
        create_user(username=username, password="admin123", role="admin")
    return create_access_token({"sub": username, "role": "admin"})


@pytest.fixture(scope="session")
def auth_headers(auth_token):
    """Authorization header used by protected API endpoints."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def auth_client(auth_headers):
    """FastAPI test client with default Authorization header."""
    with TestClient(app) as client:
        client.headers.update(auth_headers)
        yield client


@pytest.fixture
def temp_dir():
    """鍒涘缓涓存椂鐩綍"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


# --------------------------------------------------------------------------
# Mock fixtures - 鐢ㄤ簬鍑忓皯澶栭儴渚濊禆
# --------------------------------------------------------------------------

@pytest.fixture
def mock_akshare():
    """Mock akshare妯″潡"""
    with patch('core.market_scanner.ak') as mock_ak:
        yield mock_ak


@pytest.fixture
def mock_load_price_data():
    """Mock load_price_data鍑芥暟"""
    with patch('core.data_service.load_price_data') as mock:
        yield mock


@pytest.fixture
def mock_load_ohlcv_data():
    """Mock load_ohlcv_data鍑芥暟"""
    with patch('core.data_service.load_ohlcv_data') as mock:
        yield mock


@pytest.fixture
def mock_load_local_price_history():
    """Mock load_local_price_history鍑芥暟"""
    with patch('core.data_store.load_local_price_history') as mock:
        yield mock


@pytest.fixture
def mock_save_local_price_history():
    """Mock save_local_price_history鍑芥暟"""
    with patch('core.data_store.save_local_price_history') as mock:
        yield mock


@pytest.fixture
def mock_load_local_ohlcv_history():
    """Mock load_local_ohlcv_history鍑芥暟"""
    with patch('core.data_store.load_local_ohlcv_history') as mock:
        yield mock


@pytest.fixture
def mock_save_local_ohlcv_history():
    """Mock save_local_ohlcv_history鍑芥暟"""
    with patch('core.data_store.save_local_ohlcv_history') as mock:
        yield mock


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI瀹㈡埛绔?"""
    with patch('core.llm_client.OpenAI') as mock:
        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Test response"))]
        )
        mock.return_value = client_mock
        yield client_mock


@pytest.fixture
def mock_llm_client():
    """Mock LLM瀹㈡埛绔?"""
    with patch('core.llm_client.LLMClient') as mock:
        client_mock = MagicMock()
        client_mock.generate.return_value = "Test response"
        client_mock.chat.return_value = "Test chat response"
        mock.return_value = client_mock
        yield client_mock


@pytest.fixture
def mock_database():
    """Mock Database"""
    with patch('core.database.Database') as mock:
        db_mock = MagicMock()
        db_mock.conn = MagicMock()
        db_mock.cursor = MagicMock()
        mock.return_value = db_mock
        yield db_mock


@pytest.fixture
def mock_position_manager():
    """Mock PositionManager"""
    with patch('core.risk_monitor.PositionManager') as mock:
        pm_mock = MagicMock()
        pm_mock.check_position_limit.return_value = (True, "")
        mock.return_value = pm_mock
        yield pm_mock


@pytest.fixture
def mock_stock_selector():
    """Mock StockSelector"""
    with patch('core.scanner.strategies.StockSelector') as mock:
        selector_mock = MagicMock()
        selector_mock.select_stocks.return_value = pd.DataFrame({
            'ticker': ['600519'],
            'score': [80],
        })
        mock.return_value = selector_mock
        yield selector_mock


@pytest.fixture
def mock_execution_algorithm():
    """Mock ExecutionAlgorithm"""
    with patch('core.execution_algorithms.ExecutionAlgorithm') as mock:
        algo_mock = MagicMock()
        algo_mock.execute.return_value = []
        mock.return_value = algo_mock
        yield algo_mock


@pytest.fixture
def mock_slippage_model():
    """Mock SlippageModel"""
    with patch('core.slippage_model.SlippageModel') as mock:
        model_mock = MagicMock()
        model_mock.apply_slippage.return_value = 100.0
        mock.return_value = model_mock
        yield model_mock


@pytest.fixture
def mock_broker_adapter():
    """Mock BrokerAdapter"""
    with patch('core.interfaces.broker_adapter.BrokerAdapter') as mock:
        broker_mock = MagicMock()
        broker_mock.get_positions.return_value = []
        broker_mock.get_account_info.return_value = {
            "cash": 1000000.0,
            "total_assets": 1000000.0
        }
        broker_mock.place_order.return_value = MagicMock(
            status=MagicMock(value="FILLED")
        )
        mock.return_value = broker_mock
        yield broker_mock


# --------------------------------------------------------------------------
# 鏃堕棿鐩稿叧fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def current_market_time():
    """鎻愪緵褰撳墠甯傚満鏃堕棿锛堜氦鏄撴椂闂村唴锛?"""
    # 宸ヤ綔鏃?10:00
    return datetime(2025, 3, 3, 10, 0, 0)


@pytest.fixture
def after_market_time():
    """鎻愪緵闈炰氦鏄撴椂闂达紙鐩樺悗锛?"""
    # 20:00
    return datetime(2025, 3, 3, 20, 0, 0)


@pytest.fixture
def weekend_time():
    """鎻愪緵鍛ㄦ湯鏃堕棿"""
    # 鍛ㄥ叚
    return datetime(2025, 3, 8, 10, 0, 0)


@pytest.fixture
def trading_time_provider(current_market_time):
    """鎻愪緵浜ゆ槗鏃堕棿鐨凾imeProvider鍑芥暟"""
    return lambda: current_market_time


@pytest.fixture
def non_trading_time_provider(after_market_time):
    """鎻愪緵闈炰氦鏄撴椂闂寸殑TimeProvider鍑芥暟"""
    return lambda: after_market_time


# --------------------------------------------------------------------------
# 浠锋牸鏁版嵁fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def trending_price_data():
    """鍒涘缓鏈夎秼鍔跨殑浠锋牸鏁版嵁锛堜笂鍗囪秼鍔匡級"""
    dates = pd.date_range(start="2025-01-01", periods=252, freq="B")
    prices = 100 + np.arange(252) * 0.5 + np.random.normal(0, 2, 252)
    return pd.DataFrame({
        "open": prices - 1,
        "high": prices + 1,
        "low": prices - 2,
        "close": prices,
        "volume": np.random.randint(1000000, 5000000, 252),
    }, index=dates)


@pytest.fixture
def volatile_price_data():
    """鍒涘缓楂樻尝鍔ㄤ环鏍兼暟鎹?"""
    dates = pd.date_range(start="2025-01-01", periods=252, freq="B")
    prices = 100 + np.cumsum(np.random.normal(0, 5, 252))
    return pd.DataFrame({
        "open": prices - 3,
        "high": prices + 3,
        "low": prices - 5,
        "close": prices,
        "volume": np.random.randint(5000000, 20000000, 252),
    }, index=dates)


@pytest.fixture
def flat_price_data():
    """鍒涘缓绋冲畾浠锋牸鏁版嵁锛堜綆娉㈠姩锛?"""
    dates = pd.date_range(start="2025-01-01", periods=252, freq="B")
    prices = 100 + np.random.normal(0, 0.5, 252)
    return pd.DataFrame({
        "open": prices - 0.2,
        "high": prices + 0.2,
        "low": prices - 0.3,
        "close": prices,
        "volume": np.random.randint(100000, 500000, 252),
    }, index=dates)


# --------------------------------------------------------------------------
# 璐︽埛鐩稿叧fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def profit_account():
    """鍒涘缓鐩堝埄璐︽埛"""
    return {
        "cash": 1100000.0,
        "positions": {
            "AAPL": 100,
            "TSLA": 50,
        },
        "initial_capital": 1000000.0,
        "equity_history": [],
        "trade_log": [],
    }


@pytest.fixture
def loss_account():
    """鍒涘缓浜忔崯璐︽埛"""
    return {
        "cash": 800000.0,
        "positions": {
            "AAPL": 100,
            "TSLA": 50,
        },
        "initial_capital": 1000000.0,
        "equity_history": [],
        "trade_log": [],
    }


@pytest.fixture
def empty_account():
    """鍒涘缓绌鸿处鎴凤紙鏃犳寔浠擄級"""
    return {
        "cash": 1000000.0,
        "positions": {},
        "initial_capital": 1000000.0,
        "equity_history": [],
        "trade_log": [],
    }


@pytest.fixture
def leveraged_account():
    """鍒涘缓鏉犳潌璐︽埛锛堝崠绌猴級"""
    return {
        "cash": 1500000.0,
        "positions": {
            "AAPL": -100,  # 鍗栫┖
            "TSLA": 50,
        },
        "initial_capital": 1000000.0,
        "equity_history": [],
        "trade_log": [],
    }


# --------------------------------------------------------------------------
# 绛栫暐閰嶇疆fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def ma_strategy_config():
    """鍒涘缓MA绛栫暐閰嶇疆"""
    return {
        "name": "ma",
        "display_name": "MA閲戝弶绛栫暐",
        "params": {
            "short_period": 5,
            "long_period": 20
        },
        "weight": 1.0
    }


@pytest.fixture
def rsi_strategy_config():
    """鍒涘缓RSI绛栫暐閰嶇疆"""
    return {
        "name": "rsi",
        "display_name": "RSI瓒呭崠绛栫暐",
        "params": {
            "period": 14,
            "oversold": 30,
            "overbought": 70
        },
        "weight": 1.0
    }


@pytest.fixture
def trend_strategy_config():
    """鍒涘缓瓒嬪娍绛栫暐閰嶇疆"""
    return {
        "name": "trend",
        "display_name": "澶氬ご瓒嬪娍绛栫暐",
        "params": {
            "min_days": 5,
            "min_gain": 0.05
        },
        "weight": 1.5
    }


# --------------------------------------------------------------------------
# 淇″彿鏁版嵁fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def bullish_signals():
    """鍒涘缓鐪嬫定淇″彿鏁版嵁"""
    return pd.DataFrame({
        "ticker": ["600519", "000001", "601318"],
        "action": ["涔板叆", "涔板叆", "涔板叆"],
        "combined_signal": [0.85, 0.75, 0.65],
        "last_price": [1780.0, 35.0, 50.0],
    })


@pytest.fixture
def bearish_signals():
    """鍒涘缓鐪嬭穼淇″彿鏁版嵁"""
    return pd.DataFrame({
        "ticker": ["600519", "000001", "601318"],
        "action": ["鍗栧嚭", "鍗栧嚭", "瑙傛湜"],
        "combined_signal": [0.35, 0.45, 0.55],
        "last_price": [1780.0, 35.0, 50.0],
    })


@pytest.fixture
def mixed_signals():
    """鍒涘缓娣峰悎淇″彿鏁版嵁"""
    return pd.DataFrame({
        "ticker": ["600519", "000001", "601318"],
        "action": ["涔板叆", "鍗栧嚭", "瑙傛湜"],
        "combined_signal": [0.8, 0.2, 0.5],
        "last_price": [1780.0, 35.0, 50.0],
    })


# --------------------------------------------------------------------------
# 璁㈠崟鏁版嵁fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def buy_orders():
    """鍒涘缓涔板叆璁㈠崟"""
    return [
        {
            "order_id": "ORD_001",
            "symbol": "600519",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 100,
            "price": 1780.0,
        }
    ]


@pytest.fixture
def sell_orders():
    """鍒涘缓鍗栧嚭璁㈠崟"""
    return [
        {
            "order_id": "ORD_001",
            "symbol": "600519",
            "side": "SELL",
            "order_type": "MARKET",
            "quantity": 100,
            "price": 1780.0,
        }
    ]


@pytest.fixture
def limit_orders():
    """鍒涘缓闄愪环璁㈠崟"""
    return [
        {
            "order_id": "ORD_001",
            "symbol": "600519",
            "side": "BUY",
            "order_type": "LIMIT",
            "quantity": 100,
            "price": 1750.0,
        }
    ]


# --------------------------------------------------------------------------
# 椋庨櫓鐩稿叧fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def conservative_limits():
    """鍒涘缓淇濆畧椋庨櫓闄愬埗"""
    from core.risk_types import RiskLimits
    return RiskLimits(
        max_position_size=0.05,
        max_total_exposure=0.5,
        max_sector_exposure=0.2,
        max_single_stock=0.02,
        max_daily_loss=0.03,
        max_total_loss=0.1,
        stop_loss_threshold=0.05,
        max_correlation=0.6,
        min_liquidity_ratio=0.2
    )


@pytest.fixture
def aggressive_limits():
    """鍒涘缓婵€杩涢闄╅檺鍒?"""
    from core.risk_types import RiskLimits
    return RiskLimits(
        max_position_size=0.2,
        max_total_exposure=0.95,
        max_sector_exposure=0.5,
        max_single_stock=0.1,
        max_daily_loss=0.1,
        max_total_loss=0.3,
        stop_loss_threshold=0.1,
        max_correlation=0.9,
        min_liquidity_ratio=0.05
    )


# --------------------------------------------------------------------------
# 鏁版嵁楠岃瘉fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def clean_data():
    """鍒涘缓骞插噣鐨勬暟鎹?"""
    dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
    return pd.DataFrame({
        "open": np.random.uniform(100, 200, 100),
        "high": np.random.uniform(200, 300, 100),
        "low": np.random.uniform(50, 100, 100),
        "close": np.random.uniform(100, 200, 100),
        "volume": np.random.randint(1000000, 5000000, 100),
    }, index=dates)


@pytest.fixture
def data_with_nan():
    """鍒涘缓鍖呭惈NaN鐨勬暟鎹?"""
    dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
    data = pd.DataFrame({
        "close": np.random.uniform(100, 200, 100),
        "volume": np.random.randint(1000000, 5000000, 100),
    }, index=dates)
    data.iloc[10:15, 0] = np.nan
    return data


@pytest.fixture
def data_with_outliers():
    """鍒涘缓鍖呭惈寮傚父鍊肩殑鏁版嵁"""
    dates = pd.date_range(start="2025-01-01", periods=100, freq="D")
    data = pd.DataFrame({
        "close": np.random.uniform(100, 200, 100),
        "volume": np.random.randint(1000000, 5000000, 100),
    }, index=dates)
    data.iloc[50, 0] = -1000  # Negative outlier
    data.iloc[60, 1] = 100000000  # Large outlier
    return data


# --------------------------------------------------------------------------
# 缁勫悎鍒嗘瀽fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def correlated_assets():
    """鍒涘缓楂樺害鐩稿叧鐨勮祫浜ф暟鎹?"""
    dates = pd.date_range(start="2025-01-01", periods=252, freq="B")
    base_returns = np.random.normal(0.001, 0.02, 252)

    return pd.DataFrame(
        {
            "AAPL": 100 * (1 + pd.Series(base_returns)).cumprod(),
            "MSFT": 100 * (1 + pd.Series(base_returns * 0.9)).cumprod(),  # Highly correlated
        },
        index=dates,
    )


@pytest.fixture
def uncorrelated_assets():
    """鍒涘缓涓嶇浉鍏宠祫浜ф暟鎹?"""
    dates = pd.date_range(start="2025-01-01", periods=252, freq="B")

    return pd.DataFrame({
        "AAPL": 100 * (1 + pd.Series(np.random.normal(0.001, 0.02, 252))).cumprod(),
        "TSLA": 100 * (1 + pd.Series(np.random.normal(0.002, 0.03, 252))).cumprod(),
        "GOOGL": 100 * (1 + pd.Series(np.random.normal(-0.0005, 0.015, 252))).cumprod(),
    }, index=dates)


# --------------------------------------------------------------------------
# 鍥炴祴缁撴灉fixtures
# --------------------------------------------------------------------------

@pytest.fixture
def backtest_results():
    """鍒涘缓鍥炴祴缁撴灉鏁版嵁"""
    return {
        "portfolio": {
            "metrics": {
                "total_return": 0.15,
                "annual_return": 0.15,
                "max_drawdown": -0.10,
                "sharpe_ratio": 1.2,
                "sortino_ratio": 1.5,
                "calmar_ratio": 1.5,
            },
            "equity_curve": [
                {"date": "2025-01-01", "equity": 100000},
                {"date": "2025-12-31", "equity": 115000},
            ],
            "weights": [
                {"date": "2025-01-01", "AAPL": 0.5, "TSLA": 0.5}
            ]
        },
        "individual": {},
        "trade_history": [
            {"date": "2025-01-05", "ticker": "AAPL", "action": "buy", "shares": 100, "price": 150.0},
        ]
    }


@pytest.fixture
def equity_curve():
    """鍒涘缓鏉冪泭鏇茬嚎鏁版嵁"""
    return [
        {"date": "2025-01-01", "equity": 100000},
        {"date": "2025-02-01", "equity": 105000},
        {"date": "2025-03-01", "equity": 110000},
        {"date": "2025-04-01", "equity": 108000},
        {"date": "2025-05-01", "equity": 115000},
        {"date": "2025-06-01", "equity": 120000},
    ]

