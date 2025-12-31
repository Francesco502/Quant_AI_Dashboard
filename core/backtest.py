"""回测模块"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from datetime import datetime


class SimpleBacktest:
    """简单回测引擎"""
    
    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.positions = {}  # {ticker: shares}
        self.cash = initial_capital
        self.equity_curve = []
        self.trades = []
    
    def run_backtest(
        self,
        price_data: pd.DataFrame,
        signals: pd.DataFrame,
        commission: float = 0.001  # 0.1% 手续费
    ) -> Dict:
        """
        运行回测
        
        参数:
            price_data: 价格数据（列为资产代码）
            signals: 交易信号（1=买入, -1=卖出, 0=持有）
            commission: 手续费率
        """
        dates = price_data.index
        tickers = price_data.columns.tolist()
        
        for date in dates:
            portfolio_value = self.cash
            for ticker in tickers:
                if ticker in self.positions:
                    portfolio_value += self.positions[ticker] * price_data.loc[date, ticker]
            
            self.equity_curve.append({
                'date': date,
                'equity': portfolio_value,
                'cash': self.cash,
                'positions_value': portfolio_value - self.cash
            })
            
            # 执行交易信号
            for ticker in tickers:
                if ticker not in signals.columns:
                    continue
                
                signal = signals.loc[date, ticker] if date in signals.index else 0
                current_price = price_data.loc[date, ticker]
                
                if signal == 1:  # 买入信号
                    self._buy(ticker, current_price, commission, date)
                elif signal == -1:  # 卖出信号
                    self._sell(ticker, current_price, commission, date)
        
        return self._calculate_performance()
    
    def _buy(self, ticker: str, price: float, commission: float, date: datetime):
        """买入"""
        # 简单策略：用50%的现金买入
        target_value = self.cash * 0.5
        shares = int(target_value / (price * (1 + commission)))
        cost = shares * price * (1 + commission)
        
        if cost <= self.cash:
            if ticker not in self.positions:
                self.positions[ticker] = 0
            self.positions[ticker] += shares
            self.cash -= cost
            
            self.trades.append({
                'date': date,
                'ticker': ticker,
                'action': 'buy',
                'shares': shares,
                'price': price,
                'cost': cost
            })
    
    def _sell(self, ticker: str, price: float, commission: float, date: datetime):
        """卖出"""
        if ticker in self.positions and self.positions[ticker] > 0:
            shares = self.positions[ticker]
            proceeds = shares * price * (1 - commission)
            
            self.positions[ticker] = 0
            self.cash += proceeds
            
            self.trades.append({
                'date': date,
                'ticker': ticker,
                'action': 'sell',
                'shares': shares,
                'price': price,
                'proceeds': proceeds
            })
    
    def _calculate_performance(self) -> Dict:
        """计算回测性能指标"""
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df.set_index('date', inplace=True)
        
        # 计算收益率
        equity_df['returns'] = equity_df['equity'].pct_change()
        equity_df['cumulative_returns'] = (1 + equity_df['returns']).cumprod() - 1
        
        # 总收益率
        total_return = (equity_df['equity'].iloc[-1] / self.initial_capital) - 1
        
        # 年化收益率（假设252个交易日）
        days = (equity_df.index[-1] - equity_df.index[0]).days
        annual_return = (1 + total_return) ** (252 / days) - 1 if days > 0 else 0
        
        # 年化波动率
        annual_vol = equity_df['returns'].std() * np.sqrt(252)
        
        # 夏普比率
        sharpe = annual_return / annual_vol if annual_vol > 0 else 0
        
        # 最大回撤
        cumulative = equity_df['equity'] / self.initial_capital
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # 胜率（如果有交易）
        if len(self.trades) > 0:
            trades_df = pd.DataFrame(self.trades)
            # 简化：假设卖出时盈利为正
            # 实际应该计算每笔交易的盈亏
            win_rate = 0.5  # 占位符
        else:
            win_rate = 0
        
        return {
            'equity_curve': equity_df,
            'total_return': total_return,
            'annual_return': annual_return,
            'annual_volatility': annual_vol,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'total_trades': len(self.trades),
            'final_equity': equity_df['equity'].iloc[-1]
        }


def simple_ma_strategy(price_data: pd.Series, short_window: int = 20, long_window: int = 50) -> pd.Series:
    """
    简单移动平均交叉策略
    
    返回:
        交易信号（1=买入, -1=卖出, 0=持有）
    """
    short_ma = price_data.rolling(window=short_window).mean()
    long_ma = price_data.rolling(window=long_window).mean()
    
    signals = pd.Series(0, index=price_data.index)
    signals[short_ma > long_ma] = 1  # 金叉，买入
    signals[short_ma < long_ma] = -1  # 死叉，卖出
    
    return signals

