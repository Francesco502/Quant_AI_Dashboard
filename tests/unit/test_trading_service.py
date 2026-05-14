"""Unit tests for core.trading_service — the central trading orchestration module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.trading_service import (
    InsufficientFundsError,
    InsufficientSharesError,
    TradingError,
    TradingService,
)
from core.order_types import OrderSide, OrderType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.cursor = MagicMock()
    db.conn = MagicMock()
    return db


@pytest.fixture
def service(mock_db):
    with (
        patch("core.trading_service.get_database", return_value=mock_db),
        patch("core.trading_service.PaperAccountManager") as mock_pm,
        patch("core.trading_service.OrderManager") as mock_om,
        patch("core.trading_service.PositionManager") as mock_pos,
    ):
        svc = TradingService()
        svc._paper_account_mgr = mock_pm.return_value
        svc._order_mgr = mock_om.return_value
        svc._position_mgr = mock_pos.return_value
        yield svc


# ---------------------------------------------------------------------------
# Error classes
# ---------------------------------------------------------------------------

class TestTradingErrors:
    def test_trading_error_is_exception(self):
        assert issubclass(TradingError, Exception)

    def test_insufficient_funds(self):
        err = InsufficientFundsError("余额不足")
        assert "余额不足" in str(err)
        assert isinstance(err, TradingError)

    def test_insufficient_shares(self):
        err = InsufficientSharesError("持仓不足")
        assert isinstance(err, TradingError)


# ---------------------------------------------------------------------------
# TradingService initialization
# ---------------------------------------------------------------------------

class TestTradingServiceInit:
    def test_create_service(self, mock_db):
        with (
            patch("core.trading_service.get_database", return_value=mock_db),
            patch("core.trading_service.PaperAccountManager"),
            patch("core.trading_service.OrderManager"),
            patch("core.trading_service.PositionManager"),
        ):
            svc = TradingService()
            assert svc is not None

    def test_create_account(self, service):
        service._paper_account_mgr.create_account.return_value = {"account_id": 1}
        result = service.create_account(user_id=7, name="Test", initial_balance=50000)
        service._paper_account_mgr.create_account.assert_called_once()
        assert result is not None

    def test_list_user_accounts(self, service):
        service._paper_account_mgr.list_accounts.return_value = [
            {"account_id": 1, "name": "Acc1"},
            {"account_id": 2, "name": "Acc2"},
        ]
        result = service.list_user_accounts(user_id=7)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Order submission
# ---------------------------------------------------------------------------

class TestOrderSubmission:
    def test_submit_market_buy(self, service):
        service._order_mgr.create_order.return_value = MagicMock(
            order_id="ORD-1", symbol="600519", side=OrderSide.BUY,
            order_type=OrderType.MARKET, quantity=100, status=MagicMock(value="PENDING"),
        )
        service._paper_account_mgr.get_account.return_value = {
            "account_id": 1, "user_id": 7,
            "portfolio": {"cash": 500000, "total_assets": 500000},
        }

        result = service.submit_order(
            user_id=7, account_id=1, symbol="600519",
            side=OrderSide.BUY, order_type=OrderType.MARKET, quantity=100,
        )
        assert result is not None

    def test_submit_order_checks_account_ownership(self, service):
        service._paper_account_mgr.get_account.return_value = None

        with pytest.raises(TradingError, match="账户"):
            service.submit_order(
                user_id=7, account_id=999, symbol="600519",
                side=OrderSide.BUY, order_type=OrderType.MARKET, quantity=100,
            )


# ---------------------------------------------------------------------------
# Order queries
# ---------------------------------------------------------------------------

class TestOrderQueries:
    def test_get_order_by_id(self, service):
        mock_order = MagicMock()
        mock_order.order_id = "ORD-X"
        service._order_mgr.get_order.return_value = mock_order

        result = service.get_order("ORD-X")
        assert result is not None
        assert result.order_id == "ORD-X"

    def test_get_nonexistent_order(self, service):
        service._order_mgr.get_order.return_value = None
        result = service.get_order("NONEXISTENT")
        assert result is None

    def test_get_orders_by_account(self, service):
        service._order_mgr.list_orders.return_value = [MagicMock(), MagicMock()]
        result = service.get_orders_by_account(user_id=7, account_id=1)
        assert len(result) == 2

    def test_get_active_orders(self, service):
        service._order_mgr.list_orders.return_value = [MagicMock()]
        result = service.get_active_orders(user_id=7)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Positions and portfolio
# ---------------------------------------------------------------------------

class TestPositionsAndPortfolio:
    def test_get_positions(self, service):
        service._paper_account_mgr.get_account.return_value = {
            "account_id": 1, "user_id": 7,
            "portfolio": {"cash": 100000, "positions": []},
        }
        service._position_mgr.get_positions.return_value = []
        result = service.get_positions(user_id=7, account_id=1)
        assert isinstance(result, list)

    def test_get_portfolio(self, service):
        service._paper_account_mgr.get_account.return_value = {
            "account_id": 1, "user_id": 7,
            "portfolio": {"cash": 100000, "total_assets": 150000, "positions": []},
        }
        service._position_mgr.get_positions.return_value = []
        result = service.get_portfolio(user_id=7, account_id=1, refresh_prices=False)
        assert "portfolio" in result


# ---------------------------------------------------------------------------
# Cancel order
# ---------------------------------------------------------------------------

class TestCancelOrder:
    def test_cancel_pending_order(self, service):
        mock_order = MagicMock()
        mock_order.status = MagicMock(value="PENDING")
        mock_order.account_id = 1
        service._order_mgr.get_order.return_value = mock_order
        service._paper_account_mgr.get_account.return_value = {
            "account_id": 1, "user_id": 7,
        }
        service._order_mgr.cancel_order.return_value = True

        result = service.cancel_order("ORD-1")
        assert result is not None

    def test_cancel_filled_order_fails(self, service):
        mock_order = MagicMock()
        mock_order.status = MagicMock(value="FILLED")
        service._order_mgr.get_order.return_value = mock_order

        with pytest.raises(TradingError, match="已成交"):
            service.cancel_order("ORD-1")
