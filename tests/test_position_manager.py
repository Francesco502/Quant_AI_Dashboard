"""仓位管理器测试"""

import pytest
from core.position_manager import PositionManager, SectorInfo
from core.risk_types import PositionLimit


class TestPositionManager:
    """测试仓位管理器"""
    
    @pytest.fixture
    def position_manager(self):
        """创建仓位管理器实例"""
        sector_info = {
            "AAPL": SectorInfo(symbol="AAPL", sector="科技", market="美股"),
            "TSLA": SectorInfo(symbol="TSLA", sector="新能源", market="美股"),
            "159755.SZ": SectorInfo(symbol="159755.SZ", sector="新能源", market="A股"),
        }
        return PositionManager(sector_info=sector_info)
    
    @pytest.fixture
    def portfolio(self):
        """创建测试账户"""
        return {
            "initial_capital": 1_000_000.0,
            "cash": 500_000.0,
            "positions": {
                "AAPL": 100,
                "TSLA": 50
            }
        }
    
    @pytest.fixture
    def current_prices(self):
        """创建当前价格"""
        return {
            "AAPL": 150.0,
            "TSLA": 200.0,
            "159755.SZ": 1.5
        }
    
    def test_add_position_limit(self, position_manager):
        """测试添加仓位限制"""
        limit = PositionLimit(
            symbol="AAPL",
            max_position=10000,
            max_weight=0.05
        )
        position_manager.add_position_limit(limit)
        assert "AAPL" in position_manager.position_limits
    
    def test_set_sector_limit(self, position_manager):
        """测试设置行业限制"""
        position_manager.set_sector_limit("科技", max_weight=0.3)
        assert position_manager.sector_limits["科技"] == 0.3
    
    def test_set_market_limit(self, position_manager):
        """测试设置市场限制"""
        position_manager.set_market_limit("美股", max_weight=0.4)
        assert position_manager.market_limits["美股"] == 0.4
    
    def test_check_position_limit_pass(self, position_manager, portfolio, current_prices):
        """测试仓位检查通过"""
        # 设置限制
        limit = PositionLimit(symbol="159755.SZ", max_position=10000, max_weight=0.1)
        position_manager.add_position_limit(limit)
        
        # 检查小额买入
        passed, msg = position_manager.check_position_limit(
            symbol="159755.SZ",
            quantity=100,
            portfolio=portfolio,
            current_prices=current_prices
        )
        assert passed is True
    
    def test_check_position_limit_fail(self, position_manager, portfolio, current_prices):
        """测试仓位检查失败"""
        # 设置严格的限制
        limit = PositionLimit(symbol="AAPL", max_position=100, max_weight=0.01)
        position_manager.add_position_limit(limit)
        
        # 尝试大额买入
        passed, msg = position_manager.check_position_limit(
            symbol="AAPL",
            quantity=10000,
            portfolio=portfolio,
            current_prices=current_prices
        )
        assert passed is False
        assert "超过限制" in msg
    
    def test_get_available_position(self, position_manager, portfolio, current_prices):
        """测试获取可用仓位"""
        # 设置限制
        limit = PositionLimit(symbol="AAPL", max_position=10000, max_weight=0.05)
        position_manager.add_position_limit(limit)
        
        available = position_manager.get_available_position(
            symbol="AAPL",
            portfolio=portfolio,
            current_prices=current_prices
        )
        assert available >= 0
    
    def test_get_position_summary(self, position_manager, portfolio, current_prices):
        """测试获取仓位汇总"""
        summary = position_manager.get_position_summary(portfolio, current_prices)
        
        assert "total_equity" in summary
        assert "total_position_weight" in summary
        assert "symbol_weights" in summary
        assert "AAPL" in summary["symbol_weights"]
        assert "TSLA" in summary["symbol_weights"]

