"""Order manager rule construction tests."""

from unittest.mock import MagicMock

import pytest

from core.order_manager import OrderManager


@pytest.fixture
def order_manager():
    return OrderManager(MagicMock())


def test_build_take_profit_rule_uses_upside_percentage(order_manager):
    rule = order_manager._build_take_profit_rule(
        account_id=1,
        symbol="600519",
        entry_price=100.0,
        take_profit_type="percentage",
        take_profit_price=None,
        take_profit_percentage=0.1,
        quantity=None,
    )

    assert rule["trigger_price"] == pytest.approx(110.0)


def test_build_stop_loss_rule_uses_downside_percentage(order_manager):
    rule = order_manager._build_stop_loss_rule(
        account_id=1,
        symbol="600519",
        entry_price=100.0,
        stop_type="percentage",
        stop_price=None,
        stop_percentage=0.05,
        quantity=None,
    )

    assert rule["trigger_price"] == pytest.approx(95.0)
