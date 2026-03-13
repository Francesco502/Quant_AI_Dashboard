"""自动交易执行器

职责：
- 将选股结果一键生成调仓计划
- 支持定时自动执行（如每日收盘前）
- 策略-交易联动

v1.1.0 新增：独立自动交易模块
"""

from __future__ import annotations

import pandas as pd
from typing import Dict, List, Optional, Callable
from datetime import datetime, time
import logging

from core.paper_account import PaperAccount
from core.scanner.strategies import StockSelector, StrategySignal
from core.data_service import load_price_data

logger = logging.getLogger(__name__)


class AutoTrader:
    """自动交易执行器"""

    def __init__(
        self,
        user_id: int,
        account: Optional[PaperAccount] = None,
        date_time_provider: Optional[Callable] = None
    ):
        """
        初始化自动交易器

        Args:
            user_id: 用户ID
            account: PaperAccount实例，若为None则创建新的
            date_time_provider: 时间提供函数（用于测试）
        """
        self.user_id = user_id
        self.account = account or PaperAccount(user_id=user_id)
        self.date_time_provider = date_time_provider or datetime.now

        # 加载默认账户
        if not self.account.account_id:
            self.account.load_default_account()

        # 交易开关
        self.enabled = True
        self.market_closed = False

        # 执行配置
        self.config = {
            'max_positions': 20,          # 最大持仓数量
            'position_percent': 0.05,     # 每只股票仓位比例（5%）
            'min_investment': 1000,       # 最小投资金额
            'rebalance_threshold': 0.15,  # 再平衡阈值（持仓偏离15%时调仓）
        }

        # 交易记录缓存
        self.pending_orders: List[Dict] = []
        self.executed_trades: List[Dict] = []

    def set_config(self, **kwargs):
        """设置执行配置"""
        self.config.update(kwargs)
        logger.info(f"AutoTrader 配置更新: {kwargs}")

    def generate_rebalance_plan(
        self,
        target_stocks: List[Dict],
        current_holdings: List[Dict],
        total_value: float
    ) -> List[Dict]:
        """
        生成调仓计划

        Args:
            target_stocks: 目标持仓列表 [{ticker, weight, action, score}]
            current_holdings: 当前持仓列表 [{ticker, shares, cost_price, current_price}]
            total_value: 账户总价值

        Returns:
            调仓计划 [{ticker, action, shares, reason, target_weight}]
        """
        # 构建当前持仓字典
        current_holdings_dict = {h['ticker']: h for h in current_holdings}

        # 计算目标持仓
        target_holdings = {}
        for stock in target_stocks:
            ticker = stock['ticker']
            # 根据评分确定权重（评分越高，权重越大）
            score = stock.get('score', 50)
            weight = min(score / 100, 1.0)  # 归一化到0-1
            target_holdings[ticker] = {
                'ticker': ticker,
                'weight': weight,
                'action': stock.get('action', '买入'),
                'score': score
            }

        # 生成调仓计划
        plan = []
        total_weight = sum(h['weight'] for h in target_holdings.values())

        # 处理目标持仓
        for ticker, target in target_holdings.items():
            if total_weight > 0:
                target_weight = target['weight'] / total_weight
            else:
                target_weight = 0

            current = current_holdings_dict.get(ticker)

            if target['action'] in ['买入', '加仓']:
                if current is None:
                    # 新建持仓
                    target_shares = self._calculate_shares(ticker, total_value, target_weight)
                    if target_shares > 0:
                        plan.append({
                            'ticker': ticker,
                            'action': 'BUY',
                            'shares': target_shares,
                            'reason': f'新建持仓，目标权重 {target_weight*100:.1f}%',
                            'target_weight': target_weight,
                            'score': target['score']
                        })
                else:
                    # 检查是否需要调仓
                    current_weight = (current['shares'] * current.get('current_price', 0)) / total_value
                    if abs(current_weight - target_weight) > self.config['rebalance_threshold']:
                        target_shares = int(total_value * target_weight / current.get('current_price', 1))
                        plan.append({
                            'ticker': ticker,
                            'action': 'ADJUST',
                            'shares': target_shares,
                            'reason': f'调整持仓，目标权重 {target_weight*100:.1f}%',
                            'target_weight': target_weight,
                            'current_weight': current_weight
                        })

            elif target['action'] == '卖出':
                if current is not None:
                    # 清仓
                    plan.append({
                        'ticker': ticker,
                        'action': 'SELL',
                        'shares': current['shares'],
                        'reason': f'清仓卖出，评分 {target["score"]}',
                        'target_weight': 0,
                        'current_weight': (current['shares'] * current.get('current_price', 0)) / total_value
                    })

        # 处理需要清仓的持仓
        for ticker, current in current_holdings_dict.items():
            if ticker not in target_holdings:
                # 不在目标列表中，清仓
                if current['shares'] > 0:
                    plan.append({
                        'ticker': ticker,
                        'action': 'SELL',
                        'shares': current['shares'],
                        'reason': '移除持仓，不在目标列表中',
                        'target_weight': 0,
                        'current_weight': (current['shares'] * current.get('current_price', 0)) / total_value
                    })

        return plan

    def _calculate_shares(self, ticker: str, total_value: float, weight: float) -> int:
        """计算目标股数"""
        if weight <= 0:
            return 0

        # 加载当前价格
        try:
            price_df = load_price_data([ticker], days=1)
            if price_df.empty:
                return 0
            current_price = price_df[ticker].iloc[-1]
        except Exception:
            current_price = 10  # 降级默认价格

        target_value = total_value * weight
        shares = int(target_value / current_price)

        # 确保最小投资金额
        if shares * current_price < self.config['min_investment']:
            return 0

        return shares

    def execute_plan(self, plan: List[Dict]) -> List[Dict]:
        """
        执行调仓计划

        Args:
            plan: 调仓计划

        Returns:
            执行结果列表
        """
        if not self.enabled:
            logger.warning("AutoTrader 已禁用，跳过执行")
            return []

        results = []
        for order in plan:
            result = self._execute_order(order)
            if result:
                results.append(result)
                self.executed_trades.append(result)

        logger.info(f"执行调仓计划完成: {len(results)} 笔交易")
        return results

    def _execute_order(self, order: Dict) -> Optional[Dict]:
        """执行单笔订单"""
        ticker = order['ticker']
        action = order['action']
        shares = order['shares']

        try:
            # 加载实时价格
            price_df = load_price_data([ticker], days=1)
            if price_df.empty:
                logger.warning(f"无法获取 {ticker} 的价格数据")
                return None

            current_price = price_df[ticker].iloc[-1]

            # 模拟交易执行
            if action == 'BUY':
                result = self._buy(ticker, current_price, shares)
            elif action == 'SELL':
                result = self._sell(ticker, current_price, shares)
            elif action == 'ADJUST':
                result = self._adjust(ticker, current_price, shares)
            else:
                logger.warning(f"未知订单类型: {action}")
                return None

            if result:
                logger.info(f"订单执行成功: {action} {shares} 股 {ticker} @ {current_price:.2f}")

            return result

        except Exception as e:
            logger.error(f"订单执行失败 {ticker}: {e}")
            return None

    def _buy(self, ticker: str, price: float, shares: int) -> Optional[Dict]:
        """买入"""
        account_info = self._get_account_info()
        cost = price * shares

        if cost > account_info['available_cash']:
            # 买不起，减少份额
            shares = int(account_info['available_cash'] / price)
            if shares <= 0:
                return None
            cost = price * shares

        # 模拟买入（实际应调用交易接口）
        # 这里返回订单信息，实际执行需要对接 real broker
        return {
            'ticker': ticker,
            'action': 'BUY',
            'shares': shares,
            'price': price,
            'cost': cost,
            'timestamp': self.date_time_provider().isoformat(),
            'status': 'pending'  # 实际应为 'filled' 或 'pending'
        }

    def _sell(self, ticker: str, price: float, shares: int) -> Optional[Dict]:
        """卖出"""
        account_info = self._get_account_info()
        current_position = account_info.get('positions', {}).get(ticker, 0)

        if shares > current_position:
            shares = current_position

        if shares <= 0:
            return None

        proceeds = price * shares
        return {
            'ticker': ticker,
            'action': 'SELL',
            'shares': shares,
            'price': price,
            'proceeds': proceeds,
            'timestamp': self.date_time_provider().isoformat(),
            'status': 'pending'
        }

    def _adjust(self, ticker: str, price: float, target_shares: int) -> Optional[Dict]:
        """调整持仓"""
        account_info = self._get_account_info()
        current_position = account_info.get('positions', {}).get(ticker, 0)

        if current_position == target_shares:
            return None

        if target_shares > current_position:
            # 加仓
            return self._buy(ticker, price, target_shares - current_position)
        else:
            # 减仓
            return self._sell(ticker, price, current_position - target_shares)

    def _get_account_info(self) -> Dict:
        """获取账户信息"""
        # 这里应该调用真实的账户查询接口
        # 简化实现：返回模拟数据
        return {
            'total_value': getattr(self.account, 'balance', 100000),
            'available_cash': getattr(self.account, 'balance', 100000) * 0.5,
            'positions': {},
            'Frozen': 0
        }

    def scan_and_rebalance(self, strategy: str = 'all') -> Dict:
        """
        扫描并调仓（一键功能）

        Args:
            strategy: 策略名称

        Returns:
            执行结果
        """
        # 1. 获取当前持仓
        current_holdings = self._get_current_holdings()

        # 2. 执行选股
        try:
            selector = StockSelector()
            price_df = load_price_data([h['ticker'] for h in current_holdings], days=365)

            # 添加一些候选股票
            candidates = ['600519', '000001', '601318', '600276', '600809']
            for t in candidates:
                if t not in price_df.columns:
                    try:
                        df = load_price_data([t], days=365)
                        if not df.empty:
                            price_df[t] = df[t]
                    except Exception:
                        pass

            if price_df.empty:
                return {'error': '无法获取价格数据'}

            top_stocks = selector.select_stocks(price_df, top_n=20)

        except Exception as e:
            logger.error(f"选股失败: {e}")
            top_stocks = pd.DataFrame()

        # 3. 生成调仓计划
        total_value = self._get_account_info()['total_value']
        plan = self.generate_rebalance_plan(
            top_stocks.to_dict('records'),
            current_holdings,
            total_value
        )

        # 4. 执行计划
        results = self.execute_plan(plan)

        return {
            'status': 'success',
            'total_stocks_selected': len(top_stocks),
            'rebalance_plan': plan,
            'executed_trades': results,
            'trading_count': len(results)
        }

    def _get_current_holdings(self) -> List[Dict]:
        """获取当前持仓"""
        # 这里应该调用真实的持仓查询接口
        # 简化实现：从账户信息获取
        return getattr(self.account, 'holdings', [])

    def is_market_hours(self) -> bool:
        """检查是否为交易时间（A股 9:30-15:00）"""
        now = self.date_time_provider()
        current_time = now.time()

        market_open = time(9, 30)
        market_close = time(15, 0)

        # 工作日检查
        if now.weekday() >= 5:  # 周末
            return False

        return market_open <= current_time <= market_close

    def schedule_rebalance(self, schedule_time: str = "14:30") -> Dict:
        """
        安排定时调仓

        Args:
            schedule_time: 调仓时间（HH:MM格式）

        Returns:
            调度结果
        """
        now = self.date_time_provider()

        # 解析目标时间
        target_hour, target_minute = map(int, schedule_time.split(':'))

        # 计算下次执行时间
        next_run = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        if next_run <= now:
            from datetime import timedelta
            next_run = next_run + timedelta(days=1)

        return {
            'status': 'scheduled',
            'next_run': next_run.isoformat(),
            'schedule_time': schedule_time,
            'weekday': next_run.strftime('%A')
        }


# 全局实例
_auto_traders: Dict[int, AutoTrader] = {}


def get_auto_trader(user_id: int) -> AutoTrader:
    """
    获取AutoTrader实例（单例模式）

    Args:
        user_id: 用户ID

    Returns:
        AutoTrader实例
    """
    if user_id not in _auto_traders:
        _auto_traders[user_id] = AutoTrader(user_id=user_id)
    return _auto_traders[user_id]
