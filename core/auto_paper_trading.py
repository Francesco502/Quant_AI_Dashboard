from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence
import logging
import math

import pandas as pd

from core.asset_metadata import get_asset_pool_tickers, list_cn_a_share_tickers
from core.backtest_engine import BacktestEngine
from core.data_service import load_price_data
from core.order_types import OrderSide, OrderType
from core.strategy_catalog import get_strategy_definition


logger = logging.getLogger(__name__)
SCREENING_BATCH_SIZE = 240
SCREENING_HISTORY_DAYS = 90
SCREENING_LIMIT_DEFAULT = 480
EVALUATION_LIMIT_DEFAULT = 120
HISTORY_BATCH_SIZE = 160
UNIVERSE_MODE_MANUAL = "manual"
UNIVERSE_MODE_ASSET_POOL = "asset_pool"
UNIVERSE_MODE_CN_A_SHARE = "cn_a_share"
AUTO_TRADING_UNIVERSE_LABELS = {
    UNIVERSE_MODE_MANUAL: "手动标的池",
    UNIVERSE_MODE_ASSET_POOL: "资产池",
    UNIVERSE_MODE_CN_A_SHARE: "A股全市场",
}


@dataclass
class StrategyEvaluation:
    strategy_id: str
    name: str
    average_total_return: float
    average_sharpe_ratio: float
    worst_drawdown: float
    score: float
    tested_tickers: List[str]
    passed: bool


@dataclass(frozen=True)
class UniverseResolution:
    mode: str
    label: str
    tickers: List[str]


def _iter_batches(items: Sequence[str], batch_size: int) -> List[List[str]]:
    effective_size = max(1, int(batch_size or 1))
    return [list(items[index : index + effective_size]) for index in range(0, len(items), effective_size)]


def _clean_price_frame(price_data: pd.DataFrame, ticker: str) -> Optional[pd.DataFrame]:
    if ticker not in price_data.columns:
        return None
    frame = price_data[[ticker]].copy()
    frame[ticker] = pd.to_numeric(frame[ticker], errors="coerce")
    frame = frame.dropna()
    if frame.empty:
        return None
    return frame


def _estimate_warmup_days(strategy_params: Dict[str, Any]) -> int:
    numeric_values = [int(value) for value in strategy_params.values() if isinstance(value, (int, float))]
    return max(numeric_values + [30]) + 20


def _round_quantity(ticker: str, raw_quantity: float) -> int:
    quantity = int(math.floor(max(raw_quantity, 0)))
    if ticker.isdigit() and len(ticker) == 6:
        return max((quantity // 100) * 100, 0)
    return quantity


def _resolve_user_id(db, username: str) -> Optional[int]:
    cursor = db.conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    return int(row["id"]) if row else None


def _ensure_account(account_mgr, user_id: int, account_name: str, initial_capital: float):
    return account_mgr.get_or_create_account(
        user_id=user_id,
        name=account_name,
        initial_balance=initial_capital,
    )


def _normalize_ticker_list(items: Sequence[Any]) -> List[str]:
    tickers: List[str] = []
    for item in items:
        ticker = str(item or "").strip().upper()
        if ticker and ticker not in tickers:
            tickers.append(ticker)
    return tickers


def _screen_ticker_scores(price_data: pd.DataFrame) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    if price_data.empty:
        return scores

    for ticker in [column for column in price_data.columns if not str(column).endswith("_volume")]:
        series = _clean_price_frame(price_data, str(ticker))
        if series is None or len(series) < 40:
            continue
        values = pd.to_numeric(series[str(ticker)], errors="coerce").dropna()
        if values.empty:
            continue
        last_price = float(values.iloc[-1])
        if last_price <= 0:
            continue

        ret_20 = (last_price / float(values.iloc[-21]) - 1.0) if len(values) > 20 else 0.0
        ret_60 = (last_price / float(values.iloc[-61]) - 1.0) if len(values) > 60 else ret_20
        volatility = float(values.pct_change().dropna().tail(60).std() or 0.0)
        stability = max(0.0, 0.25 - min(volatility, 0.25))
        liquidity_bias = 0.05 if last_price >= 2 else -0.10
        scores[str(ticker)] = (ret_60 * 0.55) + (ret_20 * 0.30) + (stability * 0.15) + liquidity_bias

    return scores


def _prefilter_universe_tickers(
    tickers: Sequence[str],
    *,
    evaluation_days: int,
    screening_limit: int,
    batch_size: int,
) -> List[str]:
    normalized = _normalize_ticker_list(tickers)
    if len(normalized) <= screening_limit:
        return normalized

    screening_days = max(SCREENING_HISTORY_DAYS, min(140, evaluation_days))
    scores: Dict[str, float] = {}
    for batch in _iter_batches(normalized, batch_size):
        try:
            frame = load_price_data(batch, days=screening_days, refresh_stale=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("auto-trading: screening batch failed: %s", exc)
            continue
        scores.update(_screen_ticker_scores(frame))

    if not scores:
        return normalized[:screening_limit]

    ranked = [ticker for ticker, _score in sorted(scores.items(), key=lambda item: item[1], reverse=True)]
    if len(ranked) < screening_limit:
        extras = [ticker for ticker in normalized if ticker not in ranked]
        ranked.extend(extras[: screening_limit - len(ranked)])
    return ranked[:screening_limit]


def _load_price_history_batched(
    tickers: Sequence[str],
    *,
    history_days: int,
    batch_size: int,
) -> pd.DataFrame:
    normalized = _normalize_ticker_list(tickers)
    if not normalized:
        return pd.DataFrame()

    frames: List[pd.DataFrame] = []
    for batch in _iter_batches(normalized, batch_size):
        try:
            frame = load_price_data(batch, days=history_days, refresh_stale=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("auto-trading: history batch failed: %s", exc)
            continue
        if not frame.empty:
            frames.append(frame)

    if not frames:
        return pd.DataFrame()

    merged = frames[0]
    for frame in frames[1:]:
        merged = merged.join(frame, how="outer")
    return merged.sort_index()


def _resolve_universe_mode(trading_cfg: Dict[str, Any]) -> str:
    mode = str(trading_cfg.get("universe_mode") or "").strip().lower()
    if mode in AUTO_TRADING_UNIVERSE_LABELS:
        return mode
    if trading_cfg.get("universe"):
        return UNIVERSE_MODE_MANUAL
    return UNIVERSE_MODE_ASSET_POOL


def resolve_auto_trading_universe(cfg: Dict[str, Any]) -> UniverseResolution:
    trading_cfg = cfg.get("trading", {})
    mode = _resolve_universe_mode(trading_cfg)
    limit = int(trading_cfg.get("universe_limit", 0) or 0)

    if mode == UNIVERSE_MODE_MANUAL:
        tickers = _normalize_ticker_list(trading_cfg.get("universe") or cfg.get("universe") or [])
    elif mode == UNIVERSE_MODE_ASSET_POOL:
        tickers = _normalize_ticker_list(get_asset_pool_tickers(limit=limit or None))
    else:
        tickers = _normalize_ticker_list(list_cn_a_share_tickers(limit=limit or None))

    return UniverseResolution(
        mode=mode,
        label=AUTO_TRADING_UNIVERSE_LABELS.get(mode, "手动标的池"),
        tickers=tickers,
    )


def evaluate_strategies(
    price_data: pd.DataFrame,
    strategy_ids: Sequence[str],
    evaluation_days: int,
    initial_capital: float,
    min_total_return: float,
    min_sharpe_ratio: float,
    max_drawdown: float,
) -> List[StrategyEvaluation]:
    evaluations: List[StrategyEvaluation] = []

    for strategy_id in strategy_ids:
        definition = get_strategy_definition(strategy_id)
        if definition is None:
            logger.warning("auto-trading: skip unknown strategy %s", strategy_id)
            continue

        warmup_days = _estimate_warmup_days(definition.default_params)
        required_rows = max(40, warmup_days + min(evaluation_days, 30))

        total_returns: List[float] = []
        sharpe_ratios: List[float] = []
        drawdowns: List[float] = []
        tested_tickers: List[str] = []

        for ticker in [column for column in price_data.columns if not str(column).endswith("_volume")]:
            ticker_frame = _clean_price_frame(price_data, str(ticker))
            if ticker_frame is None or len(ticker_frame) < required_rows:
                continue

            engine = BacktestEngine(initial_capital=initial_capital)
            result = engine.run(ticker_frame.tail(evaluation_days + warmup_days), definition.func, definition.default_params)
            total_returns.append(float(result.get("total_return", 0.0)))
            sharpe_ratios.append(float(result.get("sharpe_ratio", 0.0)))
            drawdowns.append(abs(float(result.get("max_drawdown", 0.0))))
            tested_tickers.append(str(ticker))

        if not tested_tickers:
            evaluations.append(
                StrategyEvaluation(
                    strategy_id=strategy_id,
                    name=definition.name,
                    average_total_return=0.0,
                    average_sharpe_ratio=0.0,
                    worst_drawdown=0.0,
                    score=float("-inf"),
                    tested_tickers=[],
                    passed=False,
                )
            )
            continue

        average_total_return = sum(total_returns) / len(total_returns)
        average_sharpe = sum(sharpe_ratios) / len(sharpe_ratios)
        worst_drawdown = max(drawdowns) if drawdowns else 0.0
        score = (average_total_return * 0.6) + (average_sharpe * 0.25) - (worst_drawdown * 0.15)
        passed = (
            average_total_return >= min_total_return
            and average_sharpe >= min_sharpe_ratio
            and worst_drawdown <= max_drawdown
        )
        evaluations.append(
            StrategyEvaluation(
                strategy_id=strategy_id,
                name=definition.name,
                average_total_return=average_total_return,
                average_sharpe_ratio=average_sharpe,
                worst_drawdown=worst_drawdown,
                score=score,
                tested_tickers=tested_tickers,
                passed=passed,
            )
        )

    evaluations.sort(key=lambda item: item.score, reverse=True)
    return evaluations


def _build_candidate_scores(
    price_data: pd.DataFrame,
    passed_evaluations: Sequence[StrategyEvaluation],
) -> Dict[str, float]:
    candidate_scores: Dict[str, float] = {}
    if price_data.empty:
        return candidate_scores

    for evaluation in passed_evaluations:
        definition = get_strategy_definition(evaluation.strategy_id)
        if definition is None:
            continue

        target_positions = definition.func(price_data, definition.default_params)
        for ticker, quantity in target_positions.items():
            if quantity > 0:
                candidate_scores[ticker] = candidate_scores.get(ticker, 0.0) + max(evaluation.score, 0.0) + 1.0

    return candidate_scores


def run_auto_trading_cycle(cfg: Dict[str, Any], trading_service) -> Dict[str, Any]:
    trading_cfg = cfg.get("trading", {})
    username = str(trading_cfg.get("username", "admin")).strip() or "admin"
    account_name = str(trading_cfg.get("account_name", "全市场自动模拟交易")).strip() or "全市场自动模拟交易"
    initial_capital = float(trading_cfg.get("initial_capital", 100000.0))
    max_positions = int(trading_cfg.get("max_positions", 5))
    evaluation_days = int(trading_cfg.get("evaluation_days", 180))
    min_total_return = float(trading_cfg.get("min_total_return", 0.0))
    min_sharpe_ratio = float(trading_cfg.get("min_sharpe_ratio", 0.0))
    max_drawdown = float(trading_cfg.get("max_drawdown", 0.35))
    top_n_strategies = int(trading_cfg.get("top_n_strategies", 3))
    strategy_ids = list(trading_cfg.get("strategy_ids") or [])
    universe = resolve_auto_trading_universe(cfg)
    tickers = universe.tickers

    if not strategy_ids:
        raise ValueError("No auto-trading strategies configured")
    if not tickers:
        raise ValueError(f"No trading universe configured for mode: {universe.mode}")

    user_id = _resolve_user_id(trading_service.db, username)
    if user_id is None:
        raise ValueError(f"User not found: {username}")

    account = _ensure_account(trading_service.account_mgr, user_id, account_name, initial_capital)

    screening_limit = int(trading_cfg.get("screening_limit", SCREENING_LIMIT_DEFAULT))
    screening_limit = max(top_n_strategies * max_positions * 12, screening_limit)
    screening_batch_size = int(trading_cfg.get("screening_batch_size", SCREENING_BATCH_SIZE))
    history_batch_size = int(trading_cfg.get("history_batch_size", HISTORY_BATCH_SIZE))
    evaluation_limit = int(trading_cfg.get("evaluation_limit", EVALUATION_LIMIT_DEFAULT))
    evaluation_limit = max(top_n_strategies * max_positions * 10, evaluation_limit)
    evaluation_tickers = _prefilter_universe_tickers(
        tickers,
        evaluation_days=evaluation_days,
        screening_limit=screening_limit,
        batch_size=screening_batch_size,
    )
    if len(evaluation_tickers) > evaluation_limit:
        evaluation_tickers = evaluation_tickers[:evaluation_limit]

    history_days = evaluation_days + max(120, max_positions * 10)
    price_data = _load_price_history_batched(
        evaluation_tickers,
        history_days=history_days,
        batch_size=history_batch_size,
    )
    if price_data.empty:
        raise ValueError("No market data available for auto-trading universe")

    evaluations = evaluate_strategies(
        price_data=price_data,
        strategy_ids=strategy_ids,
        evaluation_days=evaluation_days,
        initial_capital=initial_capital,
        min_total_return=min_total_return,
        min_sharpe_ratio=min_sharpe_ratio,
        max_drawdown=max_drawdown,
    )
    passed_evaluations = [item for item in evaluations if item.passed][:top_n_strategies]
    selection_mode = "validated"
    if not passed_evaluations:
        passed_evaluations = [
            item
            for item in evaluations
            if item.tested_tickers and math.isfinite(item.score)
        ][:top_n_strategies]
        selection_mode = "best_available"

    latest_prices: Dict[str, float] = {}
    for ticker in evaluation_tickers:
        series = pd.to_numeric(price_data.get(ticker), errors="coerce").dropna() if ticker in price_data.columns else pd.Series(dtype=float)
        if not series.empty:
            latest_prices[ticker] = float(series.iloc[-1])

    candidate_scores = _build_candidate_scores(price_data, passed_evaluations)
    selected_tickers = [
        ticker
        for ticker, _score in sorted(candidate_scores.items(), key=lambda item: item[1], reverse=True)
        if latest_prices.get(ticker, 0.0) > 0
    ][:max_positions]

    portfolio = trading_service.get_portfolio(user_id=user_id, account_id=account.id)
    total_equity = float(portfolio.get("total_assets", account.initial_capital))
    current_positions = {
        position.ticker: int(position.shares)
        for position in trading_service.account_mgr.get_positions(account.id, refresh_prices=False)
    }

    target_quantities: Dict[str, int] = {}
    if selected_tickers:
        max_single_weight = float(
            getattr(getattr(trading_service.risk_monitor, "risk_limits", None), "max_single_stock", 0.05)
            or 0.05
        )
        per_position_budget = min(total_equity / len(selected_tickers), total_equity * max_single_weight * 0.90)
        for ticker in selected_tickers:
            price = latest_prices.get(ticker)
            if not price or price <= 0:
                continue
            quantity = _round_quantity(ticker, per_position_budget / price)
            if quantity > 0:
                target_quantities[ticker] = quantity

    executed_orders: List[Dict[str, Any]] = []

    for ticker, current_quantity in current_positions.items():
        target_quantity = target_quantities.get(ticker, 0)
        if current_quantity > target_quantity:
            sell_quantity = current_quantity - target_quantity
            result = trading_service.submit_order(
                user_id=user_id,
                account_id=account.id,
                symbol=ticker,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=sell_quantity,
                strategy_id="auto_trading_rebalance",
            )
            executed_orders.append({"ticker": ticker, "action": "SELL", "quantity": sell_quantity, "result": result})

    refreshed_positions = {
        position.ticker: int(position.shares)
        for position in trading_service.account_mgr.get_positions(account.id, refresh_prices=False)
    }

    for ticker, target_quantity in target_quantities.items():
        current_quantity = refreshed_positions.get(ticker, 0)
        if target_quantity > current_quantity:
            buy_quantity = target_quantity - current_quantity
            result = trading_service.submit_order(
                user_id=user_id,
                account_id=account.id,
                symbol=ticker,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=buy_quantity,
                strategy_id="auto_trading_rebalance",
            )
            executed_orders.append({"ticker": ticker, "action": "BUY", "quantity": buy_quantity, "result": result})

    latest_account = trading_service.account_mgr.get_account(account.id, user_id)
    latest_positions = trading_service.account_mgr.get_positions(account.id, refresh_prices=True)
    position_value = sum(position.market_value for position in latest_positions)
    if latest_account:
        trading_service.account_mgr.save_equity_snapshot(
            account_id=account.id,
            equity=latest_account.balance + position_value,
            cash=latest_account.balance,
            position_value=position_value,
        )

    return {
        "timestamp": datetime.now().isoformat(),
        "username": username,
        "account_id": account.id,
        "universe_mode": universe.mode,
        "universe_label": universe.label,
        "universe_size": len(tickers),
        "universe_preview": tickers[:12],
        "evaluation_universe_size": len(evaluation_tickers),
        "evaluation_universe_preview": evaluation_tickers[:12],
        "selected_tickers": selected_tickers,
        "target_quantities": target_quantities,
        "evaluations": [asdict(item) for item in evaluations],
        "validated_strategies": [item.strategy_id for item in passed_evaluations],
        "selection_mode": selection_mode,
        "executed_orders": executed_orders,
    }
