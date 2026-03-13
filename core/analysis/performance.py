"""Performance Analysis Module for Backtest Results

功能：
- 总收益率计算
- 最大回撤计算
- 夏普比率
- 索提诺比率
- 信息比率
- Beta和Alpha
- 回撤分析
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class DrawdownDetail:
    """回撤详情数据类"""
    start_date: str
    end_date: str
    duration: int  # 天数
    peak_value: float
    trough_value: float
    depth: float  # 回撤深度
    recovery_date: Optional[str] = None
    recovered: bool = False


class PerformanceAnalyzer:
    """绩效分析器"""

    @staticmethod
    def calculate_metrics(equity_curve: List[Dict]) -> Dict[str, float]:
        """计算绩效指标

        Args:
            equity_curve: 权益曲线，格式：[{"date": "2025-01-01", "equity": 100000}, ...]

        Returns:
            包含各项指标的字典
        """
        if not equity_curve:
            return {
                "total_return": 0.0,
                "annual_return": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
            }

        df = pd.DataFrame(equity_curve)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        # 总收益率
        initial_equity = df.iloc[0]["equity"]
        final_equity = df.iloc[-1]["equity"]
        total_return = (final_equity - initial_equity) / initial_equity

        # 计算收益序列
        df["returns"] = df["equity"].pct_change().fillna(0)

        # 年化收益率
        days = (df["date"].iloc[-1] - df["date"].iloc[0]).days
        if days > 0:
            annual_return = (1 + total_return) ** (365 / days) - 1
        else:
            annual_return = 0.0

        # 最大回撤
        df["cummax"] = df["equity"].cummax()
        df["drawdown"] = (df["equity"] - df["cummax"]) / df["cummax"]
        max_drawdown = df["drawdown"].min()

        # 夏普比率
        returns = df["returns"]
        if len(returns) > 1 and returns.std() > 0:
            avg_return = returns.mean()
            std_return = returns.std()
            sharpe_ratio = np.sqrt(252) * avg_return / std_return if std_return > 0 else 0
        else:
            sharpe_ratio = 0.0

        # 索提诺比率
        negative_returns = returns[returns < 0]
        if len(negative_returns) > 0:
            downside_std = negative_returns.std()
            if downside_std > 0:
                sortino_ratio = np.sqrt(252) * avg_return / downside_std
            else:
                sortino_ratio = 0.0
        else:
            sortino_ratio = 0.0

        return {
            "total_return": round(total_return, 4),
            "annual_return": round(annual_return, 4),
            "max_drawdown": round(float(-max_drawdown), 4),  # 返回正值
            "sharpe_ratio": round(sharpe_ratio, 4),
            "sortino_ratio": round(sortino_ratio, 4),
        }

    @staticmethod
    def calculate_sharpe_ratio(returns: pd.Series, periods: int = 252, risk_free_rate: float = 0.0) -> float:
        """计算夏普比率

        Args:
            returns: 收益率序列
            periods: 年化.periods (日度数据=252, 月度数据=12)
            risk_free_rate: 无风险利率

        Returns:
            夏普比率
        """
        if len(returns) < 2:
            return 0.0

        excess_returns = returns - risk_free_rate / periods
        if excess_returns.std() == 0:
            return 0.0

        sharpe = np.sqrt(periods) * excess_returns.mean() / excess_returns.std()
        return float(sharpe)

    @staticmethod
    def calculate_sortino_ratio(returns: pd.Series, periods: int = 252, risk_free_rate: float = 0.0) -> float:
        """计算索提诺比率

        Args:
            returns: 收益率序列
            periods: 年化.periods
            risk_free_rate: 无风险利率

        Returns:
            索提诺比率
        """
        if len(returns) < 2:
            return 0.0

        excess_returns = returns - risk_free_rate / periods
        negative_returns = excess_returns[excess_returns < 0]

        if len(negative_returns) == 0 or negative_returns.std() == 0:
            return 0.0

        downside_std = negative_returns.std()
        sortino = np.sqrt(periods) * excess_returns.mean() / downside_std
        return float(sortino)

    @staticmethod
    def calculate_information_ratio(
        strategy_returns: pd.Series, benchmark_returns: pd.Series, periods: int = 252
    ) -> float:
        """计算信息比率

        Args:
            strategy_returns: 策略收益率序列
            benchmark_returns: 基准收益率序列
            periods: 年化.periods

        Returns:
            信息比率
        """
        if len(strategy_returns) < 2 or len(benchmark_returns) < 2:
            return 0.0

        excess_returns = strategy_returns - benchmark_returns
        if excess_returns.std() == 0:
            return 0.0

        ir = np.sqrt(periods) * excess_returns.mean() / excess_returns.std()
        return float(ir)

    @staticmethod
    def calculate_beta(
        strategy_returns: pd.Series, benchmark_returns: pd.Series
    ) -> float:
        """计算Beta值

        Args:
            strategy_returns: 策略收益率序列
            benchmark_returns: 基准收益率序列

        Returns:
            Beta值
        """
        if len(strategy_returns) < 2 or len(benchmark_returns) < 2:
            return 0.0

        # 计算协方差和方差
        covariance = np.cov(strategy_returns, benchmark_returns)[0, 1]
        benchmark_variance = np.var(benchmark_returns)

        if benchmark_variance == 0:
            return 0.0

        beta = covariance / benchmark_variance
        return float(beta)

    @staticmethod
    def calculate_alpha(
        strategy_returns: pd.Series,
        benchmark_returns: pd.Series,
        periods: int = 252,
        risk_free_rate: float = 0.0,
    ) -> float:
        """计算Alpha值

        Args:
            strategy_returns: 策略收益率序列
            benchmark_returns: 基准收益率序列
            periods: 年化.periods
            risk_free_rate: 无风险利率

        Returns:
            Alpha值（年化）
        """
        if len(strategy_returns) < 2 or len(benchmark_returns) < 2:
            return 0.0

        beta = PerformanceAnalyzer.calculate_beta(strategy_returns, benchmark_returns)

        # 计算年化收益率
        strategy_annual = (1 + strategy_returns.mean()) ** periods - 1
        benchmark_annual = (1 + benchmark_returns.mean()) ** periods - 1

        alpha = strategy_annual - (risk_free_rate + beta * (benchmark_annual - risk_free_rate))
        return float(alpha)

    @staticmethod
    def analyze_drawdowns(equity_curve: List[Dict]) -> Dict[str, Any]:
        """详细回撤分析

        Args:
            equity_curve: 权益曲线

        Returns:
            回撤分析结果
        """
        if not equity_curve:
            return {
                "max_drawdown": 0.0,
                "drawdown_duration": 0,
                "drawdown_details": [],
            }

        df = pd.DataFrame(equity_curve)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        # 计算累计最大值和回撤
        df["cummax"] = df["equity"].cummax()
        df["drawdown"] = (df["equity"] - df["cummax"]) / df["cummax"]

        # 找出回撤开始和结束点
        in_drawdown = False
        drawdown_details = []

        peak_idx = 0
        for i in range(len(df)):
            if df.iloc[i]["drawdown"] < 0:
                if not in_drawdown:
                    # 开始新的回撤
                    in_drawdown = True
                    peak_idx = i
                    peak_value = df.iloc[peak_idx]["equity"]
            else:
                if in_drawdown:
                    # 回撤结束
                    in_drawdown = False
                    trough_idx = i - 1
                    trough_value = df.iloc[trough_idx]["equity"]
                    duration = (df.iloc[i]["date"] - df.iloc[peak_idx]["date"]).days

                    # 计算恢复日期
                    recovery_date = None
                    recovered = False
                    for j in range(i, len(df)):
                        if df.iloc[j]["equity"] >= peak_value:
                            recovery_date = str(df.iloc[j]["date"]).split()[0]
                            recovered = True
                            break

                    depth = float(df.iloc[trough_idx]["drawdown"])

                    drawdown_details.append({
                        "start_date": str(df.iloc[peak_idx]["date"]).split()[0],
                        "end_date": str(df.iloc[trough_idx]["date"]).split()[0],
                        "recovery_date": recovery_date,
                        "duration": duration,
                        "peak_value": float(peak_value),
                        "trough_value": float(trough_value),
                        "depth": depth,
                        "recovered": recovered,
                    })

        # 如果仍在回撤中
        if in_drawdown:
            trough_idx = len(df) - 1
            trough_value = df.iloc[trough_idx]["equity"]
            duration = (df.iloc[trough_idx]["date"] - df.iloc[peak_idx]["date"]).days

            drawdown_details.append({
                "start_date": str(df.iloc[peak_idx]["date"]).split()[0],
                "end_date": str(df.iloc[trough_idx]["date"]).split()[0],
                "recovery_date": None,
                "duration": duration,
                "peak_value": float(peak_value),
                "trough_value": float(trough_value),
                "depth": float(df.iloc[trough_idx]["drawdown"]),
                "recovered": False,
            })

        max_drawdown = float(-df["drawdown"].min()) if len(df) > 0 else 0.0  # 返回正值

        return {
            "max_drawdown": round(max_drawdown, 4),
            "drawdown_duration": len(drawdown_details),
            "drawdown_details": drawdown_details,
        }
