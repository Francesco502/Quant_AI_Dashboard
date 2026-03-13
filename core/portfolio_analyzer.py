"""Portfolio analysis utilities."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from core.data_service import load_price_data
from core.risk_analysis import (
    calculate_correlation_matrix,
    calculate_max_drawdown,
    calculate_portfolio_risk_metrics,
    find_highly_correlated_pairs,
)
from core.strategy_engine import generate_multi_asset_signals


class PortfolioAnalyzer:
    """Analyze multi-asset portfolio risk/return and diversification."""

    def __init__(
        self,
        tickers: List[str],
        weights: Optional[List[float]] = None,
        position_shares: Optional[Dict[str, float]] = None,
    ):
        self.requested_tickers = [str(t).strip().upper() for t in tickers if str(t).strip()]
        # Backward compatibility for existing callers/tests.
        self.tickers = list(self.requested_tickers)
        self.requested_weights = list(weights) if weights else None
        self.requested_shares = {
            str(k).strip().upper(): max(0.0, float(v))
            for k, v in (position_shares or {}).items()
            if str(k).strip()
        }

    @staticmethod
    def _resolve_weights(count: int, raw_weights: Optional[List[float]]) -> np.ndarray:
        if count <= 0:
            return np.array([])

        if not raw_weights or len(raw_weights) != count:
            return np.ones(count, dtype=float) / count

        arr = np.array(raw_weights, dtype=float)
        arr[arr < 0] = 0
        total = float(arr.sum())
        if total <= 0:
            return np.ones(count, dtype=float) / count
        return arr / total

    @staticmethod
    def _safe_return_pct(series: pd.Series) -> float:
        series = series.dropna()
        if series.empty:
            return 0.0
        first = float(series.iloc[0])
        last = float(series.iloc[-1])
        if first == 0:
            return 0.0
        return (last / first - 1.0) * 100.0

    @staticmethod
    def _ewma_covariance(returns_df: pd.DataFrame, decay: float = 0.94) -> pd.DataFrame:
        if returns_df.empty:
            return pd.DataFrame()
        cov = returns_df.cov().copy()
        for _, row in returns_df.iterrows():
            vec = row.values.astype(float).reshape(-1, 1)
            outer = np.matmul(vec, vec.T)
            cov = decay * cov + (1.0 - decay) * pd.DataFrame(
                outer, index=returns_df.columns, columns=returns_df.columns
            )
        return cov

    @staticmethod
    def _shrink_covariance(cov: pd.DataFrame, shrinkage: float = 0.15) -> pd.DataFrame:
        if cov.empty:
            return cov
        diag = np.diag(np.diag(cov.values))
        shrunk = (1.0 - shrinkage) * cov.values + shrinkage * diag
        return pd.DataFrame(shrunk, index=cov.index, columns=cov.columns)

    @staticmethod
    def _risk_contributions(cov: pd.DataFrame, weights: np.ndarray) -> List[Dict[str, float]]:
        if cov.empty or len(weights) == 0:
            return []
        cov_matrix = cov.values.astype(float)
        w = weights.astype(float).reshape(-1, 1)
        port_var = float(np.matmul(np.matmul(w.T, cov_matrix), w).item())
        if port_var <= 0:
            return []
        marginal = np.matmul(cov_matrix, w) / np.sqrt(port_var)
        component = (w * marginal).reshape(-1)
        total = float(component.sum())
        if total == 0:
            return []
        rc_ratio = component / total
        out: List[Dict[str, float]] = []
        for idx, ticker in enumerate(cov.index.tolist()):
            out.append(
                {
                    "ticker": str(ticker),
                    "marginal_risk": float(marginal[idx][0]),
                    "component_risk": float(component[idx]),
                    "risk_contribution": float(rc_ratio[idx]),
                }
            )
        return out

    @staticmethod
    def _factor_exposures(returns_df: pd.DataFrame) -> List[Dict[str, float]]:
        if returns_df.empty:
            return []
        market_factor = returns_df.mean(axis=1)
        momentum_factor = market_factor.rolling(20).mean().fillna(0.0)
        market_var = float(np.var(market_factor.values)) or 1e-9
        momentum_var = float(np.var(momentum_factor.values)) or 1e-9
        exposures: List[Dict[str, float]] = []
        for ticker in returns_df.columns:
            asset_ret = returns_df[ticker].values
            beta_market = float(np.cov(asset_ret, market_factor.values)[0, 1] / market_var)
            beta_momentum = float(np.cov(asset_ret, momentum_factor.values)[0, 1] / momentum_var)
            exposures.append(
                {
                    "ticker": str(ticker),
                    "beta_market": beta_market,
                    "beta_momentum": beta_momentum,
                }
            )
        return exposures

    @staticmethod
    def _benchmark_attribution(returns_df: pd.DataFrame, weights: np.ndarray) -> Dict[str, float]:
        if returns_df.empty or len(weights) == 0:
            return {
                "benchmark_return": 0.0,
                "portfolio_return": 0.0,
                "active_return": 0.0,
                "allocation_effect": 0.0,
            }
        benchmark_weights = np.ones(len(weights), dtype=float) / len(weights)
        annual_asset_returns = returns_df.mean(axis=0).values * 252.0
        portfolio_return = float(np.dot(weights, annual_asset_returns))
        benchmark_return = float(np.dot(benchmark_weights, annual_asset_returns))
        active = portfolio_return - benchmark_return
        allocation_effect = float(np.dot(weights - benchmark_weights, annual_asset_returns))
        return {
            "benchmark_return": benchmark_return,
            "portfolio_return": portfolio_return,
            "active_return": active,
            "allocation_effect": allocation_effect,
        }

    def _resolve_market_value_weights(
        self,
        effective_tickers: List[str],
        price_df: pd.DataFrame,
    ) -> Optional[np.ndarray]:
        if not effective_tickers or not self.requested_shares:
            return None

        market_values: List[float] = []
        for ticker in effective_tickers:
            shares = float(self.requested_shares.get(ticker, 0.0))
            if shares <= 0:
                market_values.append(0.0)
                continue

            series = price_df[ticker].dropna() if ticker in price_df.columns else pd.Series(dtype=float)
            last_price = float(series.iloc[-1]) if not series.empty else 0.0
            market_values.append(shares * max(last_price, 0.0))

        values = np.array(market_values, dtype=float)
        total = float(values.sum())
        if total <= 0:
            return None
        return values / total

    def analyze(self, days: int = 365, risk_free_rate: float = 0.02) -> Dict:
        price_df = load_price_data(self.requested_tickers, days=days)
        if price_df.empty:
            return {"error": "无法获取价格数据"}

        effective_tickers = [t for t in self.requested_tickers if t in price_df.columns]
        if not effective_tickers:
            return {"error": "None of the requested tickers has available data"}

        price_df = price_df[effective_tickers].dropna(how="all")
        if price_df.empty:
            return {"error": "Price data is empty after filtering"}

        returns_df = price_df.pct_change().dropna(how="all").fillna(0.0)
        if returns_df.empty:
            return {"error": "Insufficient return data"}

        # Prefer real holdings market-value weights over static target allocation.
        weights: Optional[np.ndarray] = self._resolve_market_value_weights(effective_tickers, price_df)
        if weights is None and self.requested_weights and len(self.requested_weights) == len(effective_tickers):
            weights = self._resolve_weights(len(effective_tickers), self.requested_weights)
        if weights is None:
            weights = self._resolve_weights(len(effective_tickers), None)
        portfolio_returns = (returns_df * weights).sum(axis=1)
        portfolio_price = (1 + portfolio_returns).cumprod()

        risk_metrics = calculate_portfolio_risk_metrics(returns_df, weights, risk_free_rate)
        ewma_cov = self._ewma_covariance(returns_df)
        shrunk_cov = self._shrink_covariance(ewma_cov, shrinkage=0.15)
        risk_contributions = self._risk_contributions(shrunk_cov, weights)
        factor_exposures = self._factor_exposures(returns_df)
        benchmark_attribution = self._benchmark_attribution(returns_df, weights)

        asset_metrics: List[Dict] = []
        contributions: List[Dict] = []

        for idx, ticker in enumerate(effective_tickers):
            series = price_df[ticker].dropna()
            returns = series.pct_change().dropna()
            annual_vol = float(returns.std() * np.sqrt(252)) if not returns.empty else 0.0
            max_dd = float(calculate_max_drawdown(series)[0]) if len(series) > 1 else 0.0
            sharpe = (
                float((returns.mean() * 252 - risk_free_rate) / (returns.std() * np.sqrt(252)))
                if (not returns.empty and float(returns.std()) > 0)
                else 0.0
            )

            weight = float(weights[idx])
            return_pct = self._safe_return_pct(series)
            contribution_pct = return_pct * weight

            asset_metrics.append(
                {
                    "ticker": ticker,
                    "last_price": float(series.iloc[-1]) if not series.empty else 0.0,
                    "annual_volatility": round(annual_vol, 4),
                    "max_drawdown": round(max_dd, 4),
                    "sharpe_ratio": round(sharpe, 4),
                    "weight": round(weight, 6),
                }
            )

            contributions.append(
                {
                    "ticker": ticker,
                    "return_pct": round(return_pct, 4),
                    "contribution_pct": round(contribution_pct, 4),
                    "weight": round(weight, 6),
                }
            )

        corr_df = calculate_correlation_matrix(returns_df)
        if corr_df is None or corr_df.empty:
            corr_df = pd.DataFrame(np.eye(len(effective_tickers)), index=effective_tickers, columns=effective_tickers)
        else:
            corr_df = corr_df.reindex(index=effective_tickers, columns=effective_tickers).fillna(0.0)

        correlations = corr_df.round(4).values.tolist()
        highly_correlated = find_highly_correlated_pairs(corr_df, threshold=0.7)

        technical_signals = generate_multi_asset_signals(price_df, min_history=60)

        total_return = float(portfolio_price.iloc[-1] - 1.0) if not portfolio_price.empty else 0.0
        annual_return = float(portfolio_returns.mean() * 252) if not portfolio_returns.empty else 0.0
        max_dd = float(calculate_max_drawdown(portfolio_price)[0]) if len(portfolio_price) > 1 else 0.0
        return_attribution = {
            "asset_contributions": contributions,
            "portfolio_return_pct": round(annual_return * 100.0, 4),
        }

        return {
            "summary": {
                "total_return": round(total_return, 4),
                "annual_return": round(annual_return, 4),
                "annual_volatility": round(float(risk_metrics.get("annual_volatility", 0.0)), 4),
                "sharpe_ratio": round(float(risk_metrics.get("sharpe_ratio", 0.0)), 4),
                "sortino_ratio": round(float(risk_metrics.get("sortino_ratio", 0.0)), 4),
                "max_drawdown": round(max_dd, 4),
                "var_95": round(float(risk_metrics.get("var_95", 0.0)), 4),
                "cvar_95": round(float(risk_metrics.get("cvar_95", 0.0)), 4),
            },
            "asset_metrics": asset_metrics,
            "weights": dict(zip(effective_tickers, [round(float(w), 6) for w in weights])),
            "correlation_matrix": corr_df.to_dict(),
            "correlations": correlations,
            "covariance_matrix_ewma_shrunk": shrunk_cov.round(8).to_dict() if not shrunk_cov.empty else {},
            "highly_correlated_pairs": highly_correlated.to_dict("records") if not highly_correlated.empty else [],
            "contributions": sorted(contributions, key=lambda x: abs(float(x["contribution_pct"])), reverse=True),
            "return_attribution": return_attribution,
            "risk_contributions": sorted(
                risk_contributions,
                key=lambda x: abs(float(x.get("risk_contribution", 0.0))),
                reverse=True,
            ),
            "factor_exposures": factor_exposures,
            "benchmark_attribution": benchmark_attribution,
            "technical_signals": (
                technical_signals.to_dict("records")
                if technical_signals is not None and not technical_signals.empty
                else []
            ),
            "timestamp": datetime.utcnow().isoformat(),
        }
