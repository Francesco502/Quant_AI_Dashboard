from __future__ import annotations

from core.order_types import OrderSide


COMMISSION_RATE = 0.0003
SELL_STAMP_DUTY_RATE = 0.001
MIN_COMMISSION = 5.0


def estimate_trade_fee(side: OrderSide | str, price: float, quantity: int) -> float:
    side_value = side.value if isinstance(side, OrderSide) else str(side).upper()
    safe_price = float(max(price, 0.0))
    safe_quantity = int(max(quantity, 0))
    notional = safe_price * safe_quantity

    if notional <= 0:
        return 0.0

    commission = max(MIN_COMMISSION, notional * COMMISSION_RATE)
    if side_value == OrderSide.SELL.value:
        return round(float(commission + notional * SELL_STAMP_DUTY_RATE), 4)
    return round(float(commission), 4)


def estimate_buy_total_cost(price: float, quantity: int) -> float:
    safe_price = float(max(price, 0.0))
    safe_quantity = int(max(quantity, 0))
    total = safe_price * safe_quantity + estimate_trade_fee(OrderSide.BUY, safe_price, safe_quantity)
    return round(float(total), 4)
