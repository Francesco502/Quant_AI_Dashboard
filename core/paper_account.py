"""模拟账户管理模块

职责：
- 管理模拟账户的资金、持仓和交易记录
- 提供买入、卖出、结算等核心功能
- 持久化数据到数据库
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Union
import sqlite3

import pandas as pd
from core.database import Database
from core.data_service import load_price_data

logger = logging.getLogger(__name__)

class InsufficientFundsError(Exception):
    pass

class InsufficientSharesError(Exception):
    pass

class PaperAccount:
    """持久化模拟账户"""

    def __init__(self, user_id: int, account_id: Optional[int] = None, db: Optional[Database] = None):
        """
        初始化模拟账户

        Args:
            user_id: 用户ID
            account_id: 账户ID（若为None，则需调用create_account或load_default_account）
            db: 数据库实例
        """
        self.user_id = user_id
        self.account_id = account_id
        self.db = db or Database()
        
        # 缓存账户状态
        self.balance = 0.0
        self.frozen = 0.0
        self.currency = "CNY"
        self.account_name = ""
        
        if account_id:
            self._load_account()

    def create_account(self, name: str = "默认模拟账户", initial_balance: float = 100000.0) -> int:
        """创建新账户"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("""
                INSERT INTO accounts (user_id, account_name, balance, frozen, currency)
                VALUES (?, ?, ?, ?, ?)
            """, (self.user_id, name, initial_balance, 0.0, "CNY"))
            self.db.conn.commit()
            
            self.account_id = cursor.lastrowid
            self.account_name = name
            self.balance = initial_balance
            self.frozen = 0.0
            
            logger.info(f"创建模拟账户成功: ID={self.account_id}, Name={name}")
            return self.account_id
        except Exception as e:
            logger.error(f"创建模拟账户失败: {e}")
            raise

    def load_default_account(self) -> bool:
        """加载用户的默认账户（第一个创建的账户）"""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT id, account_name, balance, frozen, currency
                FROM accounts
                WHERE user_id = ?
                ORDER BY id ASC
                LIMIT 1
            """, (self.user_id,))
            row = cursor.fetchone()
            
            if row:
                self.account_id = row["id"]
                self.account_name = row["account_name"]
                self.balance = row["balance"]
                self.frozen = row["frozen"]
                self.currency = row["currency"]
                return True
            return False
        except Exception as e:
            logger.error(f"加载默认账户失败: {e}")
            return False

    def _load_account(self):
        """根据 account_id 加载账户信息"""
        if not self.account_id:
            return
            
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT account_name, balance, frozen, currency
            FROM accounts
            WHERE id = ? AND user_id = ?
        """, (self.account_id, self.user_id))
        row = cursor.fetchone()
        
        if row:
            self.account_name = row["account_name"]
            self.balance = row["balance"]
            self.frozen = row["frozen"]
            self.currency = row["currency"]
        else:
            raise ValueError(f"账户不存在或无权访问: ID={self.account_id}")

    def get_positions(self) -> List[Dict]:
        """获取当前持仓列表"""
        if not self.account_id:
            return []
            
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT ticker, shares, avg_cost, updated_at
            FROM positions
            WHERE account_id = ? AND shares > 0
        """, (self.account_id,))
        
        positions = []
        for row in cursor.fetchall():
            positions.append({
                "ticker": row["ticker"],
                "shares": row["shares"],
                "avg_cost": row["avg_cost"],
                "updated_at": row["updated_at"]
            })
        return positions

    def get_trade_history(self, limit: int = 50) -> List[Dict]:
        """获取交易历史"""
        if not self.account_id:
            return []
            
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT ticker, action, price, shares, fee, trade_time
            FROM trade_history
            WHERE account_id = ?
            ORDER BY trade_time DESC
            LIMIT ?
        """, (self.account_id, limit))
        
        history = []
        for row in cursor.fetchall():
            history.append({
                "ticker": row["ticker"],
                "action": row["action"],
                "price": row["price"],
                "shares": row["shares"],
                "fee": row["fee"],
                "trade_time": row["trade_time"]
            })
        return history

    def buy(self, ticker: str, shares: int, price: Optional[float] = None) -> Dict:
        """
        买入资产
        
        Args:
            ticker: 资产代码
            shares: 买入数量
            price: 买入价格（若为None，尝试获取最新价格）
            
        Returns:
            交易结果字典
        """
        if not self.account_id:
            raise ValueError("账户未初始化")
            
        if shares <= 0:
            raise ValueError("买入数量必须大于0")
            
        # 1. 获取价格
        if price is None:
            df = load_price_data([ticker], days=5)
            if df.empty or ticker not in df.columns:
                raise ValueError(f"无法获取 {ticker} 的最新价格")
            price = float(df[ticker].iloc[-1])
            
        # 2. 计算费用 (简化版：万分之三佣金，最低5元)
        amount = price * shares
        fee = max(5.0, amount * 0.0003)
        total_cost = amount + fee
        
        # 3. 检查余额
        if self.balance < total_cost:
            raise InsufficientFundsError(f"余额不足: 需要 {total_cost:.2f}, 当前 {self.balance:.2f}")
            
        try:
            cursor = self.db.conn.cursor()
            
            # 4. 扣减余额
            new_balance = self.balance - total_cost
            cursor.execute("""
                UPDATE accounts 
                SET balance = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_balance, self.account_id))
            
            # 5. 更新持仓
            # 检查是否已有持仓
            cursor.execute("""
                SELECT shares, avg_cost FROM positions
                WHERE account_id = ? AND ticker = ?
            """, (self.account_id, ticker))
            pos_row = cursor.fetchone()
            
            if pos_row:
                old_shares = pos_row["shares"]
                old_cost = pos_row["avg_cost"]
                new_shares = old_shares + shares
                # 加权平均成本
                new_cost = ((old_shares * old_cost) + total_cost) / new_shares
                
                cursor.execute("""
                    UPDATE positions
                    SET shares = ?, avg_cost = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE account_id = ? AND ticker = ?
                """, (new_shares, new_cost, self.account_id, ticker))
            else:
                new_shares = shares
                new_cost = total_cost / shares
                cursor.execute("""
                    INSERT INTO positions (account_id, ticker, shares, avg_cost)
                    VALUES (?, ?, ?, ?)
                """, (self.account_id, ticker, shares, new_cost))
                
            # 6. 记录交易历史
            cursor.execute("""
                INSERT INTO trade_history (account_id, ticker, action, price, shares, fee)
                VALUES (?, ?, 'BUY', ?, ?, ?)
            """, (self.account_id, ticker, price, shares, fee))
            
            self.db.conn.commit()
            
            # 更新内存状态
            self.balance = new_balance
            
            logger.info(f"买入成功: {ticker} {shares}股 @ {price:.2f}")
            return {
                "success": True,
                "ticker": ticker,
                "action": "BUY",
                "price": price,
                "shares": shares,
                "cost": total_cost,
                "balance": new_balance
            }
            
        except Exception as e:
            self.db.conn.rollback()
            logger.error(f"买入失败: {e}")
            raise

    def sell(self, ticker: str, shares: int, price: Optional[float] = None) -> Dict:
        """
        卖出资产
        
        Args:
            ticker: 资产代码
            shares: 卖出数量
            price: 卖出价格
        """
        if not self.account_id:
            raise ValueError("账户未初始化")
            
        if shares <= 0:
            raise ValueError("卖出数量必须大于0")
            
        # 1. 获取持仓
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT shares, avg_cost FROM positions
            WHERE account_id = ? AND ticker = ?
        """, (self.account_id, ticker))
        pos_row = cursor.fetchone()
        
        if not pos_row or pos_row["shares"] < shares:
            current_shares = pos_row["shares"] if pos_row else 0
            raise InsufficientSharesError(f"持仓不足: 需要 {shares}, 当前 {current_shares}")
            
        # 2. 获取价格
        if price is None:
            df = load_price_data([ticker], days=5)
            if df.empty or ticker not in df.columns:
                raise ValueError(f"无法获取 {ticker} 的最新价格")
            price = float(df[ticker].iloc[-1])
            
        # 3. 计算收益与费用
        amount = price * shares
        # 卖出印花税(0.1%) + 佣金(万3)
        fee = max(5.0, amount * 0.0003) + (amount * 0.001)
        net_income = amount - fee
        
        try:
            # 4. 增加余额
            new_balance = self.balance + net_income
            cursor.execute("""
                UPDATE accounts 
                SET balance = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_balance, self.account_id))
            
            # 5. 更新持仓
            new_shares = pos_row["shares"] - shares
            if new_shares == 0:
                # 清仓，删除记录或保留为0股？这里选择保留为0股方便查看历史成本? 
                # 通常删除或置0。为了简洁，保留记录但shares=0
                cursor.execute("""
                    UPDATE positions
                    SET shares = 0, updated_at = CURRENT_TIMESTAMP
                    WHERE account_id = ? AND ticker = ?
                """, (self.account_id, ticker))
            else:
                # 卖出不改变剩余持仓的单位成本
                cursor.execute("""
                    UPDATE positions
                    SET shares = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE account_id = ? AND ticker = ?
                """, (new_shares, self.account_id, ticker))
                
            # 6. 记录交易历史
            cursor.execute("""
                INSERT INTO trade_history (account_id, ticker, action, price, shares, fee)
                VALUES (?, ?, 'SELL', ?, ?, ?)
            """, (self.account_id, ticker, price, shares, fee))
            
            self.db.conn.commit()
            
            # 更新内存状态
            self.balance = new_balance
            
            logger.info(f"卖出成功: {ticker} {shares}股 @ {price:.2f}")
            return {
                "success": True,
                "ticker": ticker,
                "action": "SELL",
                "price": price,
                "shares": shares,
                "income": net_income,
                "balance": new_balance
            }
            
        except Exception as e:
            self.db.conn.rollback()
            logger.error(f"卖出失败: {e}")
            raise

    def daily_settlement(self) -> Dict:
        """
        每日结算：计算当前持仓市值，记录权益快照到 equity_history 表。
        应在每个交易日收盘后调用一次。
        
        Returns:
            结算结果字典 {equity, cash, position_value, date}
        """
        if not self.account_id:
            raise ValueError("账户未初始化")

        # 刷新账户余额
        self._load_account()
        portfolio = self.get_portfolio_value()

        today = datetime.now().strftime("%Y-%m-%d")
        equity = portfolio["total_assets"]
        cash = portfolio["cash"]
        position_value = portfolio["market_value"]

        try:
            cursor = self.db.conn.cursor()
            # INSERT OR REPLACE：每日只保留一条快照
            cursor.execute("""
                INSERT OR REPLACE INTO equity_history (account_id, date, equity, cash, position_value)
                VALUES (?, ?, ?, ?, ?)
            """, (self.account_id, today, equity, cash, position_value))
            self.db.conn.commit()

            logger.info(f"日终结算完成: 账户={self.account_id}, 日期={today}, 权益={equity:.2f}")
            return {
                "date": today,
                "equity": equity,
                "cash": cash,
                "position_value": position_value,
            }
        except Exception as e:
            logger.error(f"日终结算失败: {e}")
            self.db.conn.rollback()
            raise

    def get_equity_history(self, days: int = 90) -> List[Dict]:
        """
        获取权益曲线历史数据
        
        Args:
            days: 查询最近多少天的数据
            
        Returns:
            权益快照列表 [{date, equity, cash, position_value}, ...]
        """
        if not self.account_id:
            return []

        try:
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT date, equity, cash, position_value
                FROM equity_history
                WHERE account_id = ?
                ORDER BY date DESC
                LIMIT ?
            """, (self.account_id, days))

            history = []
            for row in cursor.fetchall():
                history.append({
                    "date": row["date"],
                    "equity": row["equity"],
                    "cash": row["cash"],
                    "position_value": row["position_value"],
                })
            # 返回时按日期正序排列
            return list(reversed(history))
        except Exception as e:
            logger.error(f"获取权益历史失败: {e}")
            return []

    def get_portfolio_value(self) -> Dict:
        """计算账户总资产市值"""
        positions = self.get_positions()
        market_value = 0.0
        
        if positions:
            tickers = [p["ticker"] for p in positions]
            try:
                # 批量获取价格
                price_df = load_price_data(tickers, days=1)
                
                for p in positions:
                    ticker = p["ticker"]
                    shares = p["shares"]
                    price = 0.0
                    
                    # 尝试从DataFrame获取价格
                    if not price_df.empty and ticker in price_df.columns:
                        # 取最后一个有效值
                        valid_prices = price_df[ticker].dropna()
                        if not valid_prices.empty:
                            price = float(valid_prices.iloc[-1])
                    
                    # 如果批量获取失败，回退到 cost (保守估计) 或 0
                    if price == 0:
                        price = p["avg_cost"] # Fallback to cost if current price unavailable
                    
                    market_value += price * shares
                    p["current_price"] = price
                    p["market_value"] = price * shares
                    p["unrealized_pnl"] = (price - p["avg_cost"]) * shares
                    if p["avg_cost"] > 0:
                        p["return_pct"] = (price - p["avg_cost"]) / p["avg_cost"] * 100
                    else:
                        p["return_pct"] = 0.0
                        
            except Exception as e:
                logger.error(f"计算市值时获取价格失败: {e}")
                # Fallback: use cost basis
                for p in positions:
                    market_value += p["shares"] * p["avg_cost"]
                    p["current_price"] = p["avg_cost"]
                    p["market_value"] = p["shares"] * p["avg_cost"]
        
        total_assets = self.balance + market_value
        
        return {
            "total_assets": total_assets,
            "cash": self.balance,
            "market_value": market_value,
            "positions": positions
        }
