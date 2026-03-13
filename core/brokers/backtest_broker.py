from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
import logging
import math

from core.interfaces.broker_adapter import BrokerAdapter, Position
from core.order_types import Fill, Order, OrderSide, OrderStatus

logger = logging.getLogger(__name__)


class BacktestBroker(BrokerAdapter):
    """
    In-memory broker used by backtest engine.

    Realism features:
    - T+1 sell restriction for CN market.
    - Lot-size checks (CN/HK board lot).
    - Optional suspended / limit-up / limit-down guards from quote metadata.
    - Slippage linked to volume participation.
    - Partial fills based on volume capacity.
    """

    DEFAULT_MARKET_RULES: Dict[str, Dict[str, Any]] = {
        "CN": {
            "t_plus_one": True,
            "lot_size": 100,
            "stamp_duty_sell": 0.001,
        },
        "HK": {
            "t_plus_one": False,
            "lot_size": 100,
            "stamp_duty_sell": 0.0,
        },
        "US": {
            "t_plus_one": False,
            "lot_size": 1,
            "stamp_duty_sell": 0.0,
        },
    }

    def __init__(
        self,
        initial_capital: float = 100000.0,
        commission_rate: float = 0.0003,
        stamp_duty_rate: float = 0.001,
        base_slippage_bps: float = 5.0,
        impact_coefficient: float = 0.12,
        participation_rate: float = 0.1,
        market_rules: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self.initial_capital = float(initial_capital)
        self.cash = float(initial_capital)
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.fills: List[Fill] = []
        self.current_time = datetime.now()

        self.commission_rate = float(max(commission_rate, 0.0))
        self.stamp_duty_rate = float(max(stamp_duty_rate, 0.0))
        self.base_slippage_bps = float(max(base_slippage_bps, 0.0))
        self.impact_coefficient = float(max(impact_coefficient, 0.0))
        self.participation_rate = float(max(min(participation_rate, 1.0), 0.0))
        self.market_rules = dict(self.DEFAULT_MARKET_RULES)
        if market_rules:
            self.market_rules.update(market_rules)

        # Track last observed prices for mark-to-market.
        self.last_prices: Dict[str, float] = {}
        # Track same-day buys for CN T+1 checks.
        self.buy_lots_by_day: Dict[str, Dict[date, float]] = {}

    def connect(self) -> bool:
        return True

    def set_time(self, dt: datetime):
        self.current_time = dt

    def get_account_info(self) -> Dict[str, Any]:
        market_value = 0.0
        for ticker, pos in self.positions.items():
            current_price = float(self.last_prices.get(ticker, pos.avg_cost))
            pos.market_value = float(pos.shares) * current_price
            pos.unrealized_pnl = (current_price - float(pos.avg_cost)) * float(pos.shares)
            market_value += pos.market_value

        equity = self.cash + market_value
        return {
            "total_assets": equity,
            "cash": self.cash,
            "market_value": market_value,
            "equity": equity,
            "currency": "CNY",
            "buying_power": self.cash,
        }

    def get_positions(self) -> List[Position]:
        return list(self.positions.values())

    def place_order(self, order: Order) -> Order:
        order.submitted_time = self.current_time
        order.status = OrderStatus.SUBMITTED
        self.orders[order.order_id] = order
        return order

    def cancel_order(self, order_id: str) -> bool:
        if order_id in self.orders:
            self.orders[order_id].status = OrderStatus.CANCELLED
            return True
        return False

    def get_order_status(self, order_id: str) -> OrderStatus:
        if order_id in self.orders:
            return self.orders[order_id].status
        return OrderStatus.UNKNOWN

    def get_history(self, start_date: str = None, end_date: str = None) -> List[Dict]:
        return [f.to_dict() for f in self.fills]

    def _market_for_symbol(self, symbol: str) -> str:
        code = str(symbol).upper()
        if code.endswith(".HK") or code.isdigit() and len(code) == 5:
            return "HK"
        if code.endswith(".SH") or code.endswith(".SZ") or code.isdigit():
            return "CN"
        return "US"

    def _resolve_quote(self, raw: Any) -> Optional[Dict[str, Any]]:
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            price = float(raw)
            return {"price": price, "close": price}
        if isinstance(raw, dict):
            if "price" in raw and raw["price"] is not None:
                price = float(raw["price"])
            elif "close" in raw and raw["close"] is not None:
                price = float(raw["close"])
            else:
                return None
            quote = dict(raw)
            quote["price"] = price
            return quote
        return None

    def _apply_lot_size(self, quantity: float, market: str) -> int:
        rule = self.market_rules.get(market, {})
        lot_size = int(max(rule.get("lot_size", 1), 1))
        q = int(max(quantity, 0))
        if lot_size <= 1:
            return q
        return (q // lot_size) * lot_size

    def _available_to_sell(self, symbol: str, market: str) -> float:
        pos = self.positions.get(symbol)
        if pos is None:
            return 0.0

        shares = float(pos.shares)
        if not self.market_rules.get(market, {}).get("t_plus_one", False):
            return shares

        day_book = self.buy_lots_by_day.get(symbol, {})
        today_buys = float(day_book.get(self.current_time.date(), 0.0))
        return max(shares - today_buys, 0.0)

    def _record_buy(self, symbol: str, quantity: float):
        day = self.current_time.date()
        if symbol not in self.buy_lots_by_day:
            self.buy_lots_by_day[symbol] = {}
        self.buy_lots_by_day[symbol][day] = float(self.buy_lots_by_day[symbol].get(day, 0.0)) + float(quantity)

    def _calc_execution_price(
        self,
        mid_price: float,
        side: OrderSide,
        fill_qty: float,
        volume: Optional[float],
    ) -> float:
        if volume is None or volume <= 0:
            impact = 0.0
        else:
            participation = min(max(fill_qty / volume, 0.0), 1.0)
            impact = self.impact_coefficient * math.sqrt(participation)

        slippage = self.base_slippage_bps / 10000.0 + impact
        if side == OrderSide.BUY:
            return float(mid_price * (1.0 + slippage))
        return float(mid_price * (1.0 - slippage))

    def _calc_fee(self, market: str, side: OrderSide, notional: float) -> float:
        commission = notional * self.commission_rate
        sell_stamp = 0.0
        if side == OrderSide.SELL:
            sell_stamp = notional * float(self.market_rules.get(market, {}).get("stamp_duty_sell", self.stamp_duty_rate))
        return float(commission + sell_stamp)

    def _reject(self, order: Order, reason: str):
        order.status = OrderStatus.REJECTED
        order.error_message = reason
        logger.warning("Backtest order rejected %s: %s", order.order_id, reason)

    def _update_position(self, ticker: str, delta_shares: float, current_price: float):
        pos = self.positions.get(ticker)
        if not pos:
            if delta_shares > 0:
                self.positions[ticker] = Position(
                    ticker=ticker,
                    shares=delta_shares,
                    avg_cost=current_price,
                    market_value=delta_shares * current_price,
                    unrealized_pnl=0.0,
                )
            return

        new_shares = float(pos.shares) + float(delta_shares)
        if new_shares <= 0:
            del self.positions[ticker]
            return

        if delta_shares > 0:
            total_cost = float(pos.shares) * float(pos.avg_cost) + float(delta_shares) * float(current_price)
            pos.avg_cost = total_cost / new_shares

        pos.shares = new_shares
        pos.market_value = new_shares * float(current_price)
        pos.unrealized_pnl = (float(current_price) - float(pos.avg_cost)) * new_shares

    def _create_fill(self, order: Order, price: float, quantity: int, commission: float):
        fill = Fill(
            fill_id=f"FILL_{len(self.fills) + 1}",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=int(quantity),
            price=float(price),
            timestamp=self.current_time,
            commission=float(commission),
        )
        self.fills.append(fill)
        order.add_fill(fill)

    def match_orders(self, market_data: Dict[str, Any]):
        """
        Match submitted orders against current quotes.

        market_data supports either:
        - {ticker: close_price}
        - {ticker: {"price": ..., "volume": ..., "suspended": bool, "limit_up_hit": bool, "limit_down_hit": bool}}
        """
        for order in list(self.orders.values()):
            if order.status not in {OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED}:
                continue

            quote = self._resolve_quote(market_data.get(order.symbol))
            if quote is None:
                continue

            market = self._market_for_symbol(order.symbol)
            mid_price = float(quote["price"])
            self.last_prices[order.symbol] = mid_price

            if bool(quote.get("suspended", False)):
                continue
            if order.side == OrderSide.BUY and bool(quote.get("limit_up_hit", False)):
                continue
            if order.side == OrderSide.SELL and bool(quote.get("limit_down_hit", False)):
                continue

            requested_qty = int(order.remaining_quantity if order.remaining_quantity > 0 else order.quantity)
            requested_qty = self._apply_lot_size(requested_qty, market)
            if requested_qty <= 0:
                self._reject(order, "quantity below lot size")
                continue

            volume = quote.get("volume")
            volume_val = float(volume) if isinstance(volume, (int, float)) else None
            fill_qty = requested_qty
            if volume_val is not None and volume_val > 0:
                max_qty = int(volume_val * self.participation_rate)
                max_qty = self._apply_lot_size(max_qty, market)
                if max_qty <= 0:
                    continue
                fill_qty = min(fill_qty, max_qty)

            if order.side == OrderSide.SELL:
                available = self._apply_lot_size(self._available_to_sell(order.symbol, market), market)
                fill_qty = min(fill_qty, available)
                if fill_qty <= 0:
                    self._reject(order, "T+1 or insufficient shares")
                    continue

            execution_price = self._calc_execution_price(mid_price, order.side, fill_qty, volume_val)
            notional = execution_price * fill_qty
            fee = self._calc_fee(market, order.side, notional)

            if order.side == OrderSide.BUY:
                total_cost = notional + fee
                if self.cash < total_cost:
                    affordable_qty = int(
                        self.cash / max(execution_price * (1.0 + self.commission_rate), 1e-9)
                    )
                    affordable_qty = self._apply_lot_size(affordable_qty, market)
                    fill_qty = min(fill_qty, affordable_qty)
                    if fill_qty <= 0:
                        self._reject(order, "insufficient cash")
                        continue
                    notional = execution_price * fill_qty
                    fee = self._calc_fee(market, order.side, notional)
                    total_cost = notional + fee

                self.cash -= total_cost
                self._update_position(order.symbol, fill_qty, execution_price)
                self._record_buy(order.symbol, fill_qty)
            else:
                proceeds = notional - fee
                self.cash += proceeds
                self._update_position(order.symbol, -fill_qty, execution_price)

            self._create_fill(order, execution_price, int(fill_qty), fee)

            if order.remaining_quantity > 0:
                order.status = OrderStatus.PARTIALLY_FILLED
            else:
                order.status = OrderStatus.FILLED

