"""账户管理器单元测试"""

import pytest
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.account_manager import AccountManager, Account, Position, InsufficientFundsError, InsufficientSharesError
from core.database import get_database


@pytest.fixture(scope="module")
def db():
    """获取测试数据库"""
    return get_database(":memory:")


@pytest.fixture
def account_manager(db):
    """获取账户管理器"""
    return AccountManager(db)


class TestAccountManager:
    """账户管理器测试类"""

    def test_create_account(self, account_manager):
        """测试创建账户"""
        account_id = account_manager.create_account(
            user_id=1,
            name="测试账户",
            initial_balance=100000.0
        )

        assert account_id is not None

        account = account_manager.get_account(account_id, 1)
        assert account is not None
        assert account.account_name == "测试账户"
        assert account.balance == 100000.0
        assert account.initial_capital == 100000.0

    def test_get_user_accounts(self, account_manager):
        """测试获取用户账户列表"""
        # 创建多个账户
        account_manager.create_account(1, "账户1", 100000)
        account_manager.create_account(1, "账户2", 200000)
        account_manager.create_account(1, "账户3", 300000)

        accounts = account_manager.get_user_accounts(1)
        assert len(accounts) >= 3

    def test_get_nonexistent_account(self, account_manager):
        """测试获取不存在的账户"""
        account = account_manager.get_account(999999, 1)
        assert account is None

    def test_account_exists(self, account_manager):
        """测试账户存在检查"""
        account_id = account_manager.create_account(
            user_id=1,
            name="测试账户",
            initial_balance=100000.0
        )

        assert account_manager.account_exists(account_id, 1) is True
        assert account_manager.account_exists(account_id, 2) is False
        assert account_manager.account_exists(999999, 1) is False


class TestPositionManagement:
    """持仓管理测试"""

    def test_update_position_buy(self, account_manager):
        """测试更新买入持仓"""
        account_id = account_manager.create_account(
            user_id=1,
            name="测试账户",
            initial_balance=100000.0
        )

        # 第一次买入
        account_manager.update_position_buy(
            account_id=account_id,
            ticker="600000",
            quantity=100,
            cost=1000.0  # 10元 * 100股
        )

        position = account_manager.get_position(account_id, "600000")
        assert position is not None
        assert position.shares == 100
        assert position.avg_cost == 10.0

        # 追加买入
        account_manager.update_position_buy(
            account_id=account_id,
            ticker="600000",
            quantity=100,
            cost=1100.0  # 11元 * 100股
        )

        position = account_manager.get_position(account_id, "600000")
        assert position.shares == 200
        # 加权平均成本 = (100*10 + 100*11) / 200 = 10.5
        assert position.avg_cost == 10.5

    def test_update_position_sell(self, account_manager):
        """测试更新卖出持仓"""
        account_id = account_manager.create_account(
            user_id=1,
            name="测试账户",
            initial_balance=100000.0
        )

        # 先买入
        account_manager.update_position_buy(
            account_id=account_id,
            ticker="600000",
            quantity=200,
            cost=2000.0
        )

        # 卖出部分
        account_manager.update_position_sell(
            account_id=account_id,
            ticker="600000",
            quantity=100
        )

        position = account_manager.get_position(account_id, "600000")
        assert position.shares == 100

        # 全部卖出
        account_manager.update_position_sell(
            account_id=account_id,
            ticker="600000",
            quantity=100
        )

        position = account_manager.get_position(account_id, "600000")
        assert position is None

    def test_freeze_unfreeze_funds(self, account_manager):
        """测试资金冻结/解冻"""
        account_id = account_manager.create_account(
            user_id=1,
            name="测试账户",
            initial_balance=100000.0
        )

        # 冻结资金
        account_manager.freeze_funds(account_id, 5000.0)

        account = account_manager.get_account(account_id, 1)
        assert account.balance == 95000.0
        assert account.frozen == 5000.0

        # 解冻资金
        account_manager.unfreeze_funds(account_id, 5000.0)

        account = account_manager.get_account(account_id, 1)
        assert account.balance == 100000.0
        assert account.frozen == 0.0

    def test_insufficient_funds(self, account_manager):
        """测试资金不足异常"""
        account_id = account_manager.create_account(
            user_id=1,
            name="测试账户",
            initial_balance=1000.0
        )

        with pytest.raises(InsufficientFundsError):
            account_manager.freeze_funds(account_id, 5000.0)

    def test_freeze_unfreeze_shares(self, account_manager):
        """测试持仓冻结/解冻"""
        account_id = account_manager.create_account(
            user_id=1,
            name="测试账户",
            initial_balance=100000.0
        )

        # 先买入
        account_manager.update_position_buy(
            account_id=account_id,
            ticker="600000",
            quantity=200,
            cost=2000.0
        )

        # 冻结持仓
        account_manager.freeze_shares(account_id, "600000", 100)

        position = account_manager.get_position(account_id, "600000")
        assert position.available_shares == 100

        # 解冻持仓
        account_manager.unfreeze_shares(account_id, "600000", 100)

        position = account_manager.get_position(account_id, "600000")
        assert position.available_shares == 200

    def test_insufficient_shares(self, account_manager):
        """测试持仓不足异常"""
        account_id = account_manager.create_account(
            user_id=1,
            name="测试账户",
            initial_balance=100000.0
        )

        with pytest.raises(InsufficientSharesError):
            account_manager.freeze_shares(account_id, "600000", 100)


class TestPortfolio:
    """投资组合测试"""

    def test_portfolio_total_equity(self):
        """测试投资组合总资产计算"""
        from core.account_manager import Account, Portfolio

        account = Account(
            id=1,
            user_id=1,
            account_name="测试账户",
            balance=50000.0,
            frozen=0.0,
            initial_capital=100000.0
        )

        positions = [
            Position(
                account_id=1,
                ticker="600000",
                shares=100,
                available_shares=100,
                avg_cost=10.0,
                market_value=1200.0,
                unrealized_pnl=200.0
            ),
            Position(
                account_id=1,
                ticker="000001",
                shares=200,
                available_shares=200,
                avg_cost=20.0,
                market_value=4400.0,
                unrealized_pnl=400.0
            )
        ]

        portfolio = Portfolio(account, positions)
        assert portfolio.total_equity == 55600.0  # 50000 + 1200 + 4400
        assert portfolio.position_value == 5600.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
