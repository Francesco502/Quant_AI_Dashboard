"""Extended Performance Analysis Module

v1.2.0 新增：更详细的回测分析指标

功能：
- 信息比率 (Information Ratio)
- 滚动夏普比率 (Rolling Sharpe)
- 交易频率统计
- 持仓集中度分析
- 最佳/最差月份收益
- 回撤详细分析
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


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


@dataclass
class TradeAnalysis:
    """交易行为分析"""
    total_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    avgtrade_duration: float  # 平均持仓天数
    longest_trade: int
    shortest_trade: int
    trade_frequency: str  # 交易频率描述


@dataclass
class MonthlyReturn:
    """月度收益数据"""
    year: int
    month: int
    return_rate: float
    is_positive: bool


@dataclass
class ExtendedMetrics:
    """扩展绩效指标"""
    # 基础指标
    total_return: float
    annual_return: float
    annual_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float

    # 信息比率相关
    information_ratio: float
    tracking_error: float
    beta: float
    alpha: float
    r_squared: float

    # 回撤分析
    drawdown_details: List[DrawdownDetail]
    avg_drawdown: float
    drawdown_duration: int

    # 交易分析
    trade_analysis: TradeAnalysis

    # 月度收益
    monthly_returns: List[MonthlyReturn]
    best_month: MonthlyReturn
    worst_month: MonthlyReturn

    # 持仓集中度
    position_concentration: Dict[str, Any]  # 各指标的集中度数据
    top_5_weight: float  # 前五大持仓权重
    top_10_weight: float  # 前十大持仓权重


class ExtendedPerformanceAnalyzer:
    """扩展绩效分析器"""

    TRADING_DAYS_PER_YEAR = 252
    TRADING_DAYS_PER_MONTH = 21

    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.equity_curve: List[Dict] = []
        self.trades: List[Dict] = []
        self.daily_returns: List[float] = []
        self.benchmark_returns: Optional[pd.Series] = None

    def add_equity_point(self, date: datetime, equity: float, cash: float = 0):
        """添加资产点数据"""
        self.equity_curve.append({
            'date': date,
            'equity': equity,
            'cash': cash
        })

    def add_trade(self, date: datetime, ticker: str, action: str,
                  shares: int, price: float, cost: float = 0):
        """添加交易记录"""
        self.trades.append({
            'date': date,
            'ticker': ticker,
            'action': action,
            'shares': shares,
            'price': price,
            'cost': cost
        })

    def set_benchmark(self, benchmark_series: pd.Series):
        """设置基准指数收益率序列"""
        self.benchmark_returns = benchmark_series

    def calculate_extended_metrics(
        self,
        benchmark_series: Optional[pd.Series] = None,
        positions_history: Optional[List[Dict]] = None
    ) -> ExtendedMetrics:
        """
        计算所有扩展绩效指标

        Args:
            benchmark_series: 基准指数收益率序列
            positions_history: 持仓历史 [{date, positions: {ticker: weight}}]

        Returns:
            ExtendedMetrics 对象
        """
        if not self.equity_curve:
            return self._default_metrics()

        # 转换为DataFrame
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df.set_index('date', inplace=True)
        equity_df.sort_index(inplace=True)

        # 计算每日收益率
        equity_df['returns'] = equity_df['equity'].pct_change().fillna(0)
        self.daily_returns = equity_df['returns'].tolist()

        # 时间范围
        start_date = equity_df.index[0]
        end_date = equity_df.index[-1]
        trading_days = (end_date - start_date).days

        # 基础收益指标
        total_return = (equity_df['equity'].iloc[-1] / self.initial_capital) - 1
        annual_return = self._annualize_return(total_return, trading_days)
        annual_volatility = equity_df['returns'].std() * np.sqrt(self.TRADING_DAYS_PER_YEAR)

        # 风险调整后收益
        sharpe_ratio = self._calculate_sharpe(equity_df['returns'])
        sortino_ratio = self._calculate_sortino(equity_df['returns'])
        max_drawdown_info = self._calculate_drawdown(equity_df['equity'])
        max_drawdown = max_drawdown_info['max_drawdown']
        calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

        # 信息比率计算
        IR, tracking_error, beta, alpha, r_squared = self._calculate_information_ratio(
            equity_df['returns'], benchmark_series
        )

        # 详细回撤分析
        drawdown_details = self._analyze_drawdowns(equity_df['equity'])
        avg_drawdown = np.mean([dd['depth'] for dd in drawdown_details]) if drawdown_details else 0

        # 交易分析
        trades_df = pd.DataFrame(self.trades) if self.trades else pd.DataFrame()
        trade_analysis = self._analyze_trades(trades_df, equity_df)

        # 月度收益分析
        monthly_returns = self._calculate_monthly_returns(equity_df)
        best_month = max(monthly_returns, key=lambda x: x.return_rate) if monthly_returns else None
        worst_month = min(monthly_returns, key=lambda x: x.return_rate) if monthly_returns else None

        # 持仓集中度分析
        concentration = self._analyze_concentration(positions_history) if positions_history else {}

        return ExtendedMetrics(
            total_return=total_return,
            annual_return=annual_return,
            annual_volatility=annual_volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            calmar_ratio=calmar_ratio,
            information_ratio=IR,
            tracking_error=tracking_error,
            beta=beta,
            alpha=alpha,
            r_squared=r_squared,
            drawdown_details=drawdown_details,
            avg_drawdown=float(avg_drawdown),
            drawdown_duration=max_drawdown_info.get('max_duration', 0),
            trade_analysis=trade_analysis,
            monthly_returns=monthly_returns,
            best_month=best_month,
            worst_month=worst_month,
            position_concentration=concentration,
            top_5_weight=concentration.get('top_5_weight', 0),
            top_10_weight=concentration.get('top_10_weight', 0)
        )

    def _annualize_return(self, total_return: float, trading_days: int) -> float:
        """年化收益率计算"""
        if trading_days <= 0:
            return 0.0
        return (1 + total_return) ** (self.TRADING_DAYS_PER_YEAR / trading_days) - 1

    def _calculate_sharpe(self, returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """计算夏普比率"""
        excess_returns = returns - risk_free_rate / self.TRADING_DAYS_PER_YEAR
        if returns.std() == 0:
            return 0.0
        return excess_returns.mean() / returns.std() * np.sqrt(self.TRADING_DAYS_PER_YEAR)

    def _calculate_sortino(self, returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """计算索提诺比率（只考虑下行风险）"""
        excess_returns = returns - risk_free_rate / self.TRADING_DAYS_PER_YEAR
        negative_returns = returns[returns < 0]
        if len(negative_returns) == 0 or negative_returns.std() == 0:
            return 0.0
        return excess_returns.mean() / negative_returns.std() * np.sqrt(self.TRADING_DAYS_PER_YEAR)

    def _calculate_drawdown(self, equity: pd.Series) -> Dict:
        """计算回撤指标"""
        cumulative = equity / self.initial_capital
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max

        max_drawdown = float(drawdown.min())

        # 计算最大回撤持续时间
        max_duration = 0
        current_duration = 0
        in_drawdown = False

        for dd in drawdown:
            if dd < 0:
                current_duration += 1
                in_drawdown = True
            else:
                if in_drawdown:
                    max_duration = max(max_duration, current_duration)
                    current_duration = 0
                    in_drawdown = False

        return {
            'max_drawdown': max_drawdown,
            'max_duration': max_duration,
            'drawdown_series': drawdown
        }

    def _calculate_information_ratio(
        self,
        strategy_returns: pd.Series,
        benchmark_series: Optional[pd.Series]
    ) -> Tuple[float, float, float, float, float]:
        """
        计算信息比率及相关指标

        Returns:
            (信息比率, 跟踪误差, Beta, Alpha, R-squared)
        """
        if benchmark_series is None or len(benchmark_series) != len(strategy_returns):
            return 0.0, 0.0, 1.0, 0.0, 0.0

        # 对齐索引
        aligned = pd.DataFrame({
            'strategy': strategy_returns.values,
            'benchmark': benchmark_series.values
        }).dropna()

        if len(aligned) < 2:
            return 0.0, 0.0, 1.0, 0.0, 0.0

        strategy = aligned['strategy']
        benchmark = aligned['benchmark']

        # 跟踪误差（超额收益的标准差）
        excess_returns = strategy - benchmark
        tracking_error = excess_returns.std() * np.sqrt(self.TRADING_DAYS_PER_YEAR)

        # 信息比率 = 超额收益均值 / 跟踪误差
        information_ratio = (excess_returns.mean() * self.TRADING_DAYS_PER_YEAR) /tracking_error if tracking_error > 0 else 0.0

        # 线性回归计算 Beta 和 Alpha
        beta, alpha, r_squared = self._regression_analysis(strategy, benchmark)

        return information_ratio, tracking_error, beta, alpha, r_squared

    def _regression_analysis(self, y: pd.Series, X: pd.Series) -> Tuple[float, float, float]:
        """简单线性回归计算 Beta, Alpha, R-squared"""
        n = len(X)
        if n < 2:
            return 1.0, 0.0, 0.0

        mean_y = y.mean()
        mean_x = X.mean()

        # Beta = Cov(Y,X) / Var(X)
        numerator = ((y - mean_y) * (X - mean_x)).sum()
        denominator = ((X - mean_x) ** 2).sum()
        beta = numerator / denominator if denominator > 0 else 1.0

        # Alpha = mean_y - beta * mean_x
        alpha = mean_y - beta * mean_x

        # R-squared
        y_pred = alpha + beta * X
        ss_res = ((y - y_pred) ** 2).sum()
        ss_tot = ((y - mean_y) ** 2).sum()
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        return beta, alpha, r_squared

    def _analyze_drawdowns(self, equity: pd.Series) -> List[Dict]:
        """详细分析每次回撤事件"""
        cumulative = equity / self.initial_capital
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max

        drawdown_events = []
        in_drawdown = False
        event_start = None
        peak_value = None
        trough_value = None
        trough_date = None

        dates = equity.index.tolist()

        for i, (date, dd) in enumerate(drawdown.items()):
            if dd < 0 and not in_drawdown:
                # 开始新回撤
                in_drawdown = True
                event_start = date
                peak_value = running_max.iloc[i]
            elif dd < 0 and in_drawdown:
                # 回撤持续中，记录最低点
                if dd < trough_value if trough_value else True:
                    trough_value = dd
                    trough_date = date
            elif dd >= 0 and in_drawdown:
                # 回撤结束
                recovery_date = date
                recovered = True
                drawdown_events.append({
                    'start_date': event_start.strftime('%Y-%m-%d'),
                    'end_date': recovery_date.strftime('%Y-%m-%d'),
                    'duration': (recovery_date - event_start).days,
                    'peak_value': float(peak_value),
                    'trough_value': float(trough_value),
                    'depth': float(trough_value),
                    'recovery_date': recovery_date.strftime('%Y-%m-%d'),
                    'recovered': recovered
                })
                in_drawdown = False
                trough_value = None

        # 处理未结束的回撤
        if in_drawdown:
            drawdown_events.append({
                'start_date': event_start.strftime('%Y-%m-%d'),
                'end_date': dates[-1].strftime('%Y-%m-%d'),
                'duration': (dates[-1] - event_start).days,
                'peak_value': float(peak_value),
                'trough_value': float(trough_value),
                'depth': float(trough_value),
                'recovery_date': None,
                'recovered': False
            })

        return drawdown_events

    def _analyze_trades(self, trades_df: pd.DataFrame, equity_df: pd.DataFrame) -> TradeAnalysis:
        """详细分析交易行为"""
        if trades_df.empty:
            return TradeAnalysis(
                total_trades=0,
                win_rate=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                profit_factor=1.0,
                avgtrade_duration=0.0,
                longest_trade=0,
                shortest_trade=0,
                trade_frequency='无交易'
            )

        # 只分析卖出交易来计算胜率
        sell_trades = trades_df[trades_df['action'] == 'sell']
        if sell_trades.empty:
            return TradeAnalysis(
                total_trades=len(trades_df),
                win_rate=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                profit_factor=1.0,
                avgtrade_duration=0.0,
                longest_trade=0,
                shortest_trade=0,
                trade_frequency='仅建仓'
            )

        # 计算每笔交易的盈亏
        buy_costs = {}
        profits = []
        trade_durations = []
        current_POSITIONS = {}

        for _, trade in trades_df.iterrows():
            date = trade['date']
            ticker = trade['ticker']
            action = trade['action']
            shares = trade['shares']
            price = trade['price']

            if action == 'buy':
                buy_costs[ticker] = price
                current_POSITIONS[ticker] = shares
            elif action == 'sell':
                if ticker in buy_costs:
                    cost_per_share = buy_costs.pop(ticker)
                    profit = (price - cost_per_share) * shares
                    profits.append(profit)

                    # 计算持有天数
                    if ticker in current_POSITIONS:
                        # 简化：假设交易日期即为持仓日期
                        pass

        win_trades = [p for p in profits if p > 0]
        loss_trades = [abs(p) for p in profits if p <= 0]

        win_rate = len(win_trades) / len(profits) if profits else 0.0
        avg_win = np.mean(win_trades) if win_trades else 0.0
        avg_loss = np.mean(loss_trades) if loss_trades else 0.0
        profit_factor = sum(win_trades) / sum(loss_trades) if loss_trades else 1.0

        # 计算交易频率
        total_trades = len(trades_df)
        trading_days = len(equity_df)
        trades_per_day = total_trades / trading_days if trading_days > 0 else 0

        if trades_per_day < 0.05:
            frequency = '极低频'
        elif trades_per_day < 0.2:
            frequency = '低频'
        elif trades_per_day < 0.5:
            frequency = '中频'
        else:
            frequency = '高频'

        return TradeAnalysis(
            total_trades=total_trades,
            win_rate=win_rate,
            avg_win=float(avg_win),
            avg_loss=float(avg_loss),
            profit_factor=float(profit_factor),
            avgtrade_duration=0.0,
            longest_trade=0,
            shortest_trade=0,
            trade_frequency=frequency
        )

    def _calculate_monthly_returns(self, equity_df: pd.DataFrame) -> List[MonthlyReturn]:
        """计算月度收益"""
        # 使用 'ME' 替代 'M' 以兼容新版本 pandas
        monthly = equity_df['equity'].resample('ME').last()
        returns = monthly.pct_change().fillna(0)

        result = []
        for date, ret in returns.items():
            if pd.isna(ret) or date <= monthly.index[0]:
                continue
            result.append(MonthlyReturn(
                year=date.year,
                month=date.month,
                return_rate=float(ret),
                is_positive=ret > 0
            ))

        return result

    def _analyze_concentration(self, positions_history: List[Dict]) -> Dict[str, Any]:
        """分析持仓集中度"""
        if not positions_history:
            return {}

        weights_by_date = []
        for entry in positions_history:
            positions = entry.get('positions', {})
            if not positions:
                continue

            weights = pd.Series(positions)
            total = weights.abs().sum()
            if total > 0:
                weights = weights / total
                weights_by_date.append(weights)

        if not weights_by_date:
            return {}

        # 合并所有日期的权重
        weights_df = pd.DataFrame(weights_by_date).fillna(0)

        # 计算平均权重
        avg_weights = weights_df.mean()

        # 排序并计算前N权重
        sorted_weights = avg_weights.abs().sort_values(ascending=False)
        top_5_weight = sorted_weights.head(5).sum() if len(sorted_weights) >= 5 else sorted_weights.sum()
        top_10_weight = sorted_weights.head(10).sum() if len(sorted_weights) >= 10 else sorted_weights.sum()

        # Gini系数（集中度指标）
        gini = self._calculate_gini(avg_weights.values)

        return {
            'unique_tickers': len(avg_weights),
            'top_5_tickers': sorted_weights.head(5).index.tolist(),
            'top_5_weight': float(top_5_weight),
            'top_10_tickers': sorted_weights.head(10).index.tolist(),
            'top_10_weight': float(top_10_weight),
            'gini_coefficient': float(gini),
            'description': '高度集中' if gini > 0.5 else '适度分散' if gini > 0.3 else '高度分散'
        }

    def _calculate_gini(self, values: np.ndarray) -> float:
        """计算Gini系数（集中度指标）"""
        values = np.abs(values)
        values = values[values > 0]
        if len(values) == 0:
            return 0.0

        values = np.sort(values)
        n = len(values)
        cumsum = np.cumsum(values)
        return (n + 1 - 2 * np.sum(cumsum) / cumsum[-1]) / n if cumsum[-1] > 0 else 0.0

    def _default_metrics(self) -> ExtendedMetrics:
        """返回默认指标"""
        return ExtendedMetrics(
            total_return=0.0,
            annual_return=0.0,
            annual_volatility=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            max_drawdown=0.0,
            calmar_ratio=0.0,
            information_ratio=0.0,
            tracking_error=0.0,
            beta=1.0,
            alpha=0.0,
            r_squared=0.0,
            drawdown_details=[],
            avg_drawdown=0.0,
            drawdown_duration=0,
            trade_analysis=TradeAnalysis(
                total_trades=0,
                win_rate=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                profit_factor=1.0,
                avgtrade_duration=0.0,
                longest_trade=0,
                shortest_trade=0,
                trade_frequency='无'
            ),
            monthly_returns=[],
            best_month=None,
            worst_month=None,
            position_concentration={},
            top_5_weight=0.0,
            top_10_weight=0.0
        )


def compare_multiple_strategies(
    strategy_results: Dict[str, Dict],
    initial_capital: float = 100000,
    benchmark_series: Optional[pd.Series] = None
) -> pd.DataFrame:
    """
    多策略绩效对比（扩展版）

    Args:
        strategy_results: {策略名: {equity_curve: [], trades: [], ...}}
        initial_capital: 初始资本
        benchmark_series: 基准指数收益率序列

    Returns:
        对比DataFrame，包含扩展指标
    """
    from datetime import datetime as dt

    comparisons = []

    for strategy_name, data in strategy_results.items():
        analyzer = ExtendedPerformanceAnalyzer(initial_capital)

        for point in data.get('equity_curve', []):
            date_value = point['date']
            if isinstance(date_value, str):
                date_value = dt.strptime(date_value, "%Y-%m-%d")
            analyzer.add_equity_point(date_value, point['equity'])

        for trade in data.get('trades', []):
            date_value = trade['date']
            if isinstance(date_value, str):
                date_value = dt.strptime(date_value, "%Y-%m-%d")
            analyzer.add_trade(
                date_value, trade['ticker'], trade['action'],
                trade['shares'], trade['price']
            )

        if benchmark_series is not None:
            analyzer.set_benchmark(benchmark_series)

        metrics = analyzer.calculate_extended_metrics(benchmark_series)

        comparisons.append({
            'strategy_name': strategy_name,
            'total_return': f"{metrics.total_return * 100:.2f}%",
            'annual_return': f"{metrics.annual_return * 100:.2f}%",
            'annual_volatility': f"{metrics.annual_volatility * 100:.2f}%",
            'sharpe_ratio': f"{metrics.sharpe_ratio:.2f}",
            'information_ratio': f"{metrics.information_ratio:.2f}",
            'max_drawdown': f"{metrics.max_drawdown * 100:.2f}%",
            'sortino_ratio': f"{metrics.sortino_ratio:.2f}",
            'win_rate': f"{metrics.trade_analysis.win_rate * 100:.2f}%",
            'total_trades': metrics.trade_analysis.total_trades,
            'beta': f"{metrics.beta:.2f}",
            'r_squared': f"{metrics.r_squared:.2f}",
            'best_month': f"{metrics.best_month.return_rate * 100:.2f}%" if metrics.best_month else "-",
            'worst_month': f"{metrics.worst_month.return_rate * 100:.2f}%" if metrics.worst_month else "-"
        })

    return pd.DataFrame(comparisons)


def generate_backtest_report(
    equity_curve: List[Dict],
    trades: List[Dict],
    initial_capital: float = 100000,
    benchmark_series: Optional[pd.Series] = None
) -> Dict:
    """
    生成完整回测报告

    Args:
        equity_curve: 资金曲线数据
        trades: 交易记录
        initial_capital: 初始资本
        benchmark_series: 基准指数收益率序列

    Returns:
        包含所有分析结果的字典
    """
    analyzer = ExtendedPerformanceAnalyzer(initial_capital)

    for point in equity_curve:
        # 转换日期字符串为 datetime
        date_value = point['date']
        if isinstance(date_value, str):
            from datetime import datetime as dt
            date_value = dt.strptime(date_value, "%Y-%m-%d")

        analyzer.add_equity_point(
            date_value,
            point['equity'],
            point.get('cash', 0)
        )

    for trade in trades:
        # 转换交易日期字符串为 datetime
        date_value = trade['date']
        if isinstance(date_value, str):
            from datetime import datetime as dt
            date_value = dt.strptime(date_value, "%Y-%m-%d")

        analyzer.add_trade(
            date_value,
            trade['ticker'],
            trade['action'],
            trade['shares'],
            trade['price'],
            trade.get('cost', 0)
        )

    if benchmark_series is not None:
        analyzer.set_benchmark(benchmark_series)

    metrics = analyzer.calculate_extended_metrics(benchmark_series)

    return {
        'metrics': {
            'total_return': metrics.total_return,
            'annual_return': metrics.annual_return,
            'annual_volatility': metrics.annual_volatility,
            'sharpe_ratio': metrics.sharpe_ratio,
            'information_ratio': metrics.information_ratio,
            'max_drawdown': metrics.max_drawdown,
            'sortino_ratio': metrics.sortino_ratio,
            'calmar_ratio': metrics.calmar_ratio,
            'beta': metrics.beta,
            'alpha': metrics.alpha,
            'r_squared': metrics.r_squared,
            'tracking_error': metrics.tracking_error
        },
        'drawdown_analysis': {
            'details': [
                {
                    'start_date': dd.start_date,
                    'end_date': dd.end_date,
                    'duration': dd.duration,
                    'depth': dd.depth
                }
                for dd in metrics.drawdown_details
            ],
            'summary': {
                '最大回撤': f"{metrics.max_drawdown * 100:.2f}%",
                '平均回撤': f"{metrics.avg_drawdown * 100:.2f}%",
                '最长回撤期': f"{metrics.drawdown_duration}天"
            }
        },
        'trade_analysis': {
            'total_trades': metrics.trade_analysis.total_trades,
            'win_rate': f"{metrics.trade_analysis.win_rate * 100:.2f}%",
            'profit_factor': f"{metrics.trade_analysis.profit_factor:.2f}",
            'avg_win': f"{metrics.trade_analysis.avg_win:.2f}",
            'avg_loss': f"{metrics.trade_analysis.avg_loss:.2f}",
            'frequency': metrics.trade_analysis.trade_frequency
        },
        'monthly_returns': [
            {
                'year': mr.year,
                'month': mr.month,
                'return': f"{mr.return_rate * 100:.2f}%",
                'positive': mr.is_positive
            }
            for mr in metrics.monthly_returns
        ],
        'concentration': {
            'top_5_weight': f"{metrics.top_5_weight * 100:.2f}%",
            'top_10_weight': f"{metrics.top_10_weight * 100:.2f}%",
            'description': metrics.position_concentration.get('description', 'N/A')
        }
    }


def export_to_csv(
    equity_curve: List[Dict],
    trades: List[Dict],
    metrics: Dict[str, Any],
    filename: str = "backtest_report.csv"
) -> str:
    """
    导出回测报告为 CSV 格式

    Args:
        equity_curve: 赢金曲线数据
        trades: 交易记录
        metrics: 回测指标
        filename: 输出文件名

    Returns:
        CSV 文件内容字符串
    """
    import io
    import csv

    output = io.StringIO()
    writer = csv.writer(output)

    # Write metrics
    writer.writerow(["指标", "值"])
    for key, value in metrics.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                writer.writerow([f"{key}_{sub_key}", sub_value])
        else:
            writer.writerow([key, value])

    writer.writerow([])  # Empty row

    # Write equity curve
    writer.writerow([" equity_curve"])
    writer.writerow(["date", "equity", "cash"])
    for point in equity_curve:
        writer.writerow([
            point.get("date", ""),
            point.get("equity", ""),
            point.get("cash", "")
        ])

    writer.writerow([])  # Empty row

    # Write trades
    writer.writerow(["交易记录"])
    if trades:
        writer.writerow(["date", "symbol", "action", "shares", "price", "cost"])
        for trade in trades:
            writer.writerow([
                trade.get("date", ""),
                trade.get("symbol", trade.get("ticker", "")),
                trade.get("action", ""),
                trade.get("shares", ""),
                trade.get("price", ""),
                trade.get("cost", "")
            ])

    return output.getvalue()


def export_to_html_report(
    equity_curve: List[Dict],
    trades: List[Dict],
    metrics: Dict[str, Any],
    initial_capital: float = 100000,
    filename: str = "backtest_report.html"
) -> str:
    """
    生成 HTML 报告
    """
    import datetime

    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>回测报告 - {date_str}</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        h1 {{ color: #1a1a1a; border-bottom: 2px solid #3b82f6; padding-bottom: 16px; }}
        h2 {{ color: #333; margin-top: 32px; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 24px 0; }}
        .metric-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #3b82f6; }}
        .metric-label {{ color: #666; font-size: 12px; text-transform: uppercase; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #1a1a1a; margin-top: 8px; }}
        .positive {{ color: #10b981; }}
        .negative {{ color: #ef4444; }}
        table {{ width: 100%; border-collapse: collapse; margin: 24px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; font-weight: 600; color: #333; }}
        .tr-buy {{ color: #ef4444; }}
        .tr-sell {{ color: #10b981; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>回测报告</h1>
        <p>生成时间: {date_str}</p>

        <h2>核心指标</h2>
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">总收益率</div>
                <div class="metric-value {'positive' if metrics.get('total_return', 0) >= 0 else 'negative'}">
                    {metrics.get('total_return', 0) * 100:.2f}%
                </div>
            </div>
            <div class="metric-card">
                <div class="metric-label">年化收益</div>
                <div class="metric-value {'positive' if metrics.get('annual_return', 0) >= 0 else 'negative'}">
                    {metrics.get('annual_return', 0) * 100:.2f}%
                </div>
            </div>
            <div class="metric-card">
                <div class="metric-label">年化波动率</div>
                <div class="metric-value">{metrics.get('annual_volatility', 0) * 100:.2f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">夏普比率</div>
                <div class="metric-value">{metrics.get('sharpe_ratio', 0):.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">信息比率</div>
                <div class="metric-value">{metrics.get('information_ratio', 0):.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">最大回撤</div>
                <div class="metric-value negative">{metrics.get('max_drawdown', 0) * 100:.2f}%</div>
            </div>
        </div>

        <h2>交易分析</h2>
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">总交易次数</div>
                <div class="metric-value">{metrics.get('trade_analysis', {{}}).get('total_trades', 0)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">胜率</div>
                <div class="metric-value {'positive' if metrics.get('trade_analysis', {{}}).get('win_rate', 0) >= 0.5 else 'negative'}">
                    {metrics.get('trade_analysis', {{}}).get('win_rate', 0) * 100:.2f}%
                </div>
            </div>
            <div class="metric-card">
                <div class="metric-label">盈亏比</div>
                <div class="metric-value">{metrics.get('trade_analysis', {{}}).get('profit_factor', 1.0):.2f}</div>
            </div>
        </div>

        <p style="margin-top: 40px; color: #999; font-size: 12px; text-align: center;">
            本报告由 Quant-AI Dashboard 生成
        </p>
    </div>
</body>
</html>
"""
    return html_content
