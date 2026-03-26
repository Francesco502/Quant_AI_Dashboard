"""账户管理器 - 支持多用户多账户，SQLite持久化

职责：
- 管理模拟账户的创建、查询、更新
- 支持多用户隔离
- 持久化账户状态到SQLite
- 资金冻结/解冻管理
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import pandas as pd
from core.database import Database, get_database
from core.data_service import load_price_data

logger = logging.getLogger(__name__)


class Account:
    """账户数据类"""

    def __init__(
        self,
        id: int,
        user_id: int,
        account_name: str,
        balance: float,
        frozen: float,
        initial_capital: float,
        currency: str = "CNY",
        status: str = "active",
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        self.id = id
        self.user_id = user_id
        self.account_name = account_name
        self.balance = balance
        self.frozen = frozen
        self.initial_capital = initial_capital
        self.currency = currency
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at

    @property
    def total_assets(self) -> float:
        """总资产 = 可用余额 + 冻结资金"""
        return self.balance + self.frozen

    @property
    def available_balance(self) -> float:
        """可用余额"""
        return self.balance

    @classmethod
    def from_row(cls, row) -> Account:
        """从数据库行创建Account对象"""
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            account_name=row["account_name"],
            balance=row["balance"],
            frozen=row["frozen"],
            initial_capital=row["initial_capital"] if "initial_capital" in row.keys() else row["balance"],
            currency=row["currency"] if "currency" in row.keys() else "CNY",
            status=row["status"] if "status" in row.keys() else "active",
            created_at=row["created_at"] if "created_at" in row.keys() else None,
            updated_at=row["updated_at"] if "updated_at" in row.keys() else None
        )


class Position:
    """持仓数据类"""

    def __init__(
        self,
        account_id: int,
        ticker: str,
        shares: int,
        available_shares: int,
        avg_cost: float,
        market_value: float = 0.0,
        unrealized_pnl: float = 0.0,
        updated_at: Optional[datetime] = None
    ):
        self.account_id = account_id
        self.ticker = ticker
        self.shares = shares
        self.available_shares = available_shares
        self.avg_cost = avg_cost
        self.market_value = market_value
        self.unrealized_pnl = unrealized_pnl
        self.updated_at = updated_at

    @property
    def unrealized_return_pct(self) -> float:
        """持仓收益率"""
        if self.avg_cost <= 0 or self.shares <= 0:
            return 0.0
        # 使用 market_value = shares * current_price，避免直接计算
        if self.market_value <= 0:
            return 0.0
        return ((self.market_value / (self.shares * self.avg_cost)) - 1) * 100

    @classmethod
    def from_row(cls, row) -> Position:
        """从数据库行创建Position对象"""
        return cls(
            account_id=row["account_id"],
            ticker=row["ticker"],
            shares=row["shares"],
            available_shares=row["available_shares"] if "available_shares" in row.keys() else row["shares"],
            avg_cost=row["avg_cost"],
            market_value=row["market_value"] if "market_value" in row.keys() else 0,
            unrealized_pnl=row["unrealized_pnl"] if "unrealized_pnl" in row.keys() else 0,
            updated_at=row["updated_at"] if "updated_at" in row.keys() else None
        )


class InsufficientFundsError(Exception):
    """资金不足异常"""
    pass


class InsufficientSharesError(Exception):
    """持仓不足异常"""
    pass


class AccountManager:
    """账户管理器 - 支持多用户多账户"""

    def __init__(self, db: Database):
        self.db = db

    def create_account(
        self,
        user_id: int,
        name: str,
        initial_balance: float
    ) -> int:
        """创建新账户"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT INTO accounts
            (user_id, account_name, balance, frozen, initial_capital, currency, status)
            VALUES (?, ?, ?, ?, ?, 'CNY', 'active')
        """, (user_id, name, initial_balance, 0.0, initial_balance))
        self.db.conn.commit()
        return cursor.lastrowid

    def get_account(self, account_id: int, user_id: int) -> Optional[Account]:
        """获取账户（验证用户权限）"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT * FROM accounts
            WHERE id = ? AND user_id = ? AND status = 'active'
        """, (account_id, user_id))
        row = cursor.fetchone()
        return Account.from_row(row) if row else None

    def get_account_by_id(self, account_id: int) -> Optional[Account]:
        """仅通过ID获取账户（不验证用户）"""
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        return Account.from_row(row) if row else None

    def get_user_accounts(self, user_id: int) -> List[Account]:
        """获取用户的所有账户"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT * FROM accounts
            WHERE user_id = ? AND status = 'active'
            ORDER BY id
        """, (user_id,))
        return [Account.from_row(row) for row in cursor.fetchall()]

    def list_accounts_with_positions(self, user_id: int) -> List[Dict]:
        """获取用户账户列表及持仓信息"""
        accounts = self.get_user_accounts(user_id)
        result = []

        for account in accounts:
            positions = self.get_positions(account.id)
            total_position_value = sum(p.market_value for p in positions)

            result.append({
                "account_id": account.id,
                "account_name": account.account_name,
                "balance": account.balance,
                "frozen": account.frozen,
                "initial_capital": account.initial_capital,
                "total_assets": account.total_assets + total_position_value,
                "available_balance": account.available_balance,
                "total_position_value": total_position_value,
                "positions": positions
            })

        return result

    def get_positions(
        self,
        account_id: int,
        refresh_prices: bool = True,
        remote_cache_days: Optional[int] = 30,
    ) -> List[Position]:
        """获取账户持仓列表"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT * FROM positions
            WHERE account_id = ? AND shares > 0
        """, (account_id,))
        rows = cursor.fetchall()

        positions = [Position.from_row(row) for row in rows]

        if refresh_prices and positions:
            tickers = [p.ticker for p in positions]
            try:
                price_df = load_price_data(
                    tickers,
                    days=5,
                    remote_cache_days=max(5, int(remote_cache_days or 30)),
                )
                if not price_df.empty:
                    for p in positions:
                        if p.ticker in price_df.columns:
                            valid_prices = price_df[p.ticker].dropna()
                            if not valid_prices.empty:
                                current_price = float(valid_prices.iloc[-1])
                                # 验证价格有效性
                                if current_price and current_price > 0:
                                    p.market_value = current_price * p.shares
                                    p.unrealized_pnl = (current_price - p.avg_cost) * p.shares
            except Exception as e:
                logger.error(f"获取价格失败: {e}")

        return positions

    def get_position(self, account_id: int, ticker: str) -> Optional[Position]:
        """获取单个持仓"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT * FROM positions
            WHERE account_id = ? AND ticker = ? AND shares > 0
        """, (account_id, ticker))
        row = cursor.fetchone()
        return Position.from_row(row) if row else None

    def freeze_funds(self, account_id: int, amount: float):
        """冻结资金（买入订单）"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            UPDATE accounts
            SET balance = balance - ?,
                frozen = frozen + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND balance >= ?
        """, (amount, amount, account_id, amount))

        if cursor.rowcount == 0:
            raise InsufficientFundsError("余额不足")

    def unfreeze_funds(self, account_id: int, amount: float):
        """解冻资金（订单取消或平仓）"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            UPDATE accounts
            SET balance = balance + ?,
                frozen = frozen - ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND frozen >= ?
        """, (amount, amount, account_id, amount))

    def freeze_shares(self, account_id: int, ticker: str, quantity: int):
        """冻结持仓（卖出订单）"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            UPDATE positions
            SET available_shares = available_shares - ?
            WHERE account_id = ? AND ticker = ? AND available_shares >= ?
        """, (quantity, account_id, ticker, quantity))

        if cursor.rowcount == 0:
            raise InsufficientSharesError("可用持仓不足")

    def unfreeze_shares(self, account_id: int, ticker: str, quantity: int):
        """解冻持仓（订单取消）"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            UPDATE positions
            SET available_shares = available_shares + ?
            WHERE account_id = ? AND ticker = ?
        """, (quantity, account_id, ticker))

    def update_position_buy(
        self,
        account_id: int,
        ticker: str,
        quantity: int,
        cost: float
    ):
        """更新买入持仓（加权平均成本）"""
        cursor = self.db.conn.cursor()
        try:
            cursor.execute("""
                SELECT shares, avg_cost FROM positions
                WHERE account_id = ? AND ticker = ?
            """, (account_id, ticker))
            row = cursor.fetchone()

            if row:
                old_shares = row["shares"]
                old_cost = row["avg_cost"]
                new_shares = old_shares + quantity
                new_cost = ((old_shares * old_cost) + cost) / new_shares

                cursor.execute("""
                    UPDATE positions
                    SET shares = ?, avg_cost = ?, available_shares = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE account_id = ? AND ticker = ?
                """, (new_shares, new_cost, new_shares, account_id, ticker))
            else:
                avg_cost = cost / quantity
                cursor.execute("""
                    INSERT INTO positions
                    (account_id, ticker, shares, available_shares, avg_cost)
                    VALUES (?, ?, ?, ?, ?)
                """, (account_id, ticker, quantity, quantity, avg_cost))
        except Exception as e:
            logger.error(f"update_position_buy 失败: account_id={account_id}, ticker={ticker}, quantity={quantity}, cost={cost}, error={e}")
            raise

    def update_position_sell(
        self,
        account_id: int,
        ticker: str,
        quantity: int
    ):
        """更新卖出持仓"""
        cursor = self.db.conn.cursor()
        try:
            cursor.execute("""
                SELECT shares, avg_cost FROM positions
                WHERE account_id = ? AND ticker = ?
            """, (account_id, ticker))
            row = cursor.fetchone()

            if row:
                new_shares = row["shares"] - quantity

                if new_shares <= 0:
                    cursor.execute("""
                        DELETE FROM positions
                        WHERE account_id = ? AND ticker = ?
                    """, (account_id, ticker))
                else:
                    cursor.execute("""
                        UPDATE positions
                        SET shares = ?, available_shares = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE account_id = ? AND ticker = ?
                    """, (new_shares, new_shares, account_id, ticker))
        except Exception as e:
            logger.error(f"update_position_sell 失败: account_id={account_id}, ticker={ticker}, quantity={quantity}, error={e}")
            raise

    def apply_fill(
        self,
        account_id: int,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        commission: float
    ):
        """应用成交到账户"""
        cursor = self.db.conn.cursor()

        try:
            if side == "BUY":
                cost = round(quantity * price + commission, 4)
                cursor.execute("""
                    UPDATE accounts
                    SET frozen = frozen - ?
                    WHERE id = ? AND frozen >= ?
                """, (cost, account_id, cost))

                if cursor.rowcount == 0:
                    raise InsufficientFundsError("冻结资金不足")

                self.update_position_buy(account_id, symbol, quantity, cost)

            else:
                income = round(quantity * price - commission, 4)
                cursor.execute("""
                    UPDATE accounts
                    SET balance = balance + ?
                    WHERE id = ?
                """, (income, account_id))

                self.update_position_sell(account_id, symbol, quantity)

            self.db.conn.commit()
        except Exception as e:
            logger.error(f"apply_fill 失败: account_id={account_id}, symbol={symbol}, side={side}, error={e}")
            self.db.conn.rollback()
            raise

    def add_trade_history(
        self,
        account_id: int,
        ticker: str,
        action: str,
        price: float,
        shares: int,
        fee: float,
        order_id: Optional[str] = None,
        pnl: Optional[float] = None
    ):
        """添加交易历史记录"""
        cursor = self.db.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO trade_history
                (account_id, ticker, action, price, shares, fee, order_id, pnl)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (account_id, ticker, action, price, shares, fee, order_id, pnl))
        except Exception as e:
            logger.error(f"add_trade_history 失败: account_id={account_id}, ticker={ticker}, action={action}, error={e}")
            raise

    def get_trade_history(self, account_id: int, limit: int = 100) -> List[Dict]:
        """获取交易历史"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT * FROM trade_history
            WHERE account_id = ?
            ORDER BY trade_time DESC
            LIMIT ?
        """, (account_id, limit))
        return [dict(row) for row in cursor.fetchall()]

    def get_order_trades(self, account_id: int, order_id: str) -> List[Dict]:
        """获取订单的所有成交记录"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT * FROM fills
            WHERE account_id = ? AND order_id = ?
            ORDER BY executed_at
        """, (account_id, order_id))
        return [dict(row) for row in cursor.fetchall()]

    def update_position_market_value(self, account_id: int):
        """更新所有持仓的市值"""
        positions = self.get_positions(account_id, refresh_prices=True)
        if not positions:
            return

        # 使用 executemany 批量更新，提升性能
        cursor = self.db.conn.cursor()
        data = [(p.market_value, p.unrealized_pnl, account_id, p.ticker) for p in positions]
        cursor.executemany("""
            UPDATE positions
            SET market_value = ?, unrealized_pnl = ?, updated_at = CURRENT_TIMESTAMP
            WHERE account_id = ? AND ticker = ?
        """, data)
        self.db.conn.commit()

    def close_account(self, account_id: int, user_id: int) -> bool:
        """关闭账户（标记为已关闭，保留历史数据）"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT shares FROM positions
            WHERE account_id = ? AND shares > 0
        """, (account_id,))
        if cursor.fetchone():
            return False

        cursor.execute("""
            UPDATE accounts
            SET status = 'closed', updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
        """, (account_id, user_id))
        self.db.conn.commit()
        return cursor.rowcount > 0

    def get_account_by_name(self, user_id: int, account_name: str) -> Optional[Account]:
        """Return an active account by name."""
        cursor = self.db.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM accounts
            WHERE user_id = ? AND account_name = ? AND status = 'active'
            ORDER BY id
            LIMIT 1
            """,
            (user_id, account_name),
        )
        row = cursor.fetchone()
        return Account.from_row(row) if row else None

    def get_or_create_account(self, user_id: int, name: str, initial_balance: float) -> Account:
        """Return a named account or create it when absent."""
        account = self.get_account_by_name(user_id, name)
        if account:
            return account

        account_id = self.create_account(user_id=user_id, name=name, initial_balance=initial_balance)
        created = self.get_account(account_id, user_id)
        if not created:
            raise ValueError(f"Failed to create account {name!r} for user {user_id}")
        return created

    def reset_account(
        self,
        account_id: int,
        user_id: int,
        initial_balance: float,
        account_name: Optional[str] = None,
    ) -> Account:
        """Reset the selected account back to clean cash-only state."""
        cursor = self.db.conn.cursor()
        cursor.execute(
            """
            SELECT 1 FROM accounts
            WHERE id = ? AND user_id = ? AND status = 'active'
            """,
            (account_id, user_id),
        )
        if cursor.fetchone() is None:
            raise ValueError("Account does not exist or access is denied")

        try:
            self.db.conn.execute("BEGIN")
            cursor.execute("DELETE FROM fills WHERE account_id = ?", (account_id,))
            cursor.execute("DELETE FROM orders WHERE account_id = ?", (account_id,))
            cursor.execute("DELETE FROM positions WHERE account_id = ?", (account_id,))
            cursor.execute("DELETE FROM trade_history WHERE account_id = ?", (account_id,))
            cursor.execute("DELETE FROM equity_history WHERE account_id = ?", (account_id,))
            cursor.execute("DELETE FROM stop_loss_rules WHERE account_id = ?", (account_id,))
            cursor.execute("DELETE FROM risk_events WHERE account_id = ?", (account_id,))

            set_clauses = [
                "balance = ?",
                "frozen = 0.0",
                "initial_capital = ?",
                "status = 'active'",
                "updated_at = CURRENT_TIMESTAMP",
            ]
            params: List[object] = [initial_balance, initial_balance]
            if account_name:
                set_clauses.insert(0, "account_name = ?")
                params.insert(0, account_name)
            params.extend([account_id, user_id])

            cursor.execute(
                f"""
                UPDATE accounts
                SET {", ".join(set_clauses)}
                WHERE id = ? AND user_id = ?
                """,
                tuple(params),
            )
            self.db.conn.commit()
        except Exception:
            self.db.conn.rollback()
            raise

        account = self.get_account(account_id, user_id)
        if not account:
            raise ValueError("Failed to reload account after reset")
        return account

    def account_exists(self, account_id: int, user_id: int) -> bool:
        """检查账户是否存在且属于用户"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT 1 FROM accounts
            WHERE id = ? AND user_id = ? AND status = 'active'
        """, (account_id, user_id))
        return cursor.fetchone() is not None

    def get_equity_history(self, account_id: int, days: int = 30) -> List[Dict]:
        """
        获取账户权益历史

        Args:
            account_id: 账户ID
            days: 获取天数

        Returns:
            权益历史列表，每项包含 date, equity, cash, market_value
        """
        cursor = self.db.conn.cursor()
        from datetime import datetime, timedelta

        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        cursor.execute("""
            SELECT date, equity, cash, position_value as market_value
            FROM equity_history
            WHERE account_id = ? AND date >= ?
            ORDER BY date ASC
        """, (account_id, start_date))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def save_equity_snapshot(self, account_id: int, equity: float, cash: float, position_value: float):
        """
        保存每日权益快照

        Args:
            account_id: 账户ID
            equity: 总权益
            cash: 现金
            position_value: 持仓市值
        """
        cursor = self.db.conn.cursor()
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO equity_history
                (account_id, date, equity, cash, position_value)
                VALUES (?, ?, ?, ?, ?)
            """, (account_id, today, equity, cash, position_value))
            self.db.conn.commit()
        except Exception as e:
            logger.error(f"保存权益快照失败: account_id={account_id}, error={e}")
            self.db.conn.rollback()
            raise


class Portfolio:
    """投资组合数据类"""

    def __init__(self, account: Account, positions: List[Position]):
        self.account = account
        self.positions = positions

    @property
    def total_equity(self) -> float:
        """总资产 = 现金 + 持仓市值"""
        position_value = sum(p.market_value for p in self.positions)
        return self.account.balance + position_value

    @property
    def cash(self) -> float:
        """可用现金"""
        return self.account.balance

    @property
    def position_value(self) -> float:
        """持仓市值"""
        return sum(p.market_value for p in self.positions)

    @property
    def position_weight(self) -> Dict[str, float]:
        """各持仓权重"""
        total = self.total_equity
        if total == 0:
            return {}

        weights = {}
        for p in self.positions:
            weights[p.ticker] = p.market_value / total
        return weights

    def get_position(self, symbol: str) -> int:
        """获取指定标的的持仓数量"""
        for p in self.positions:
            if p.ticker == symbol:
                return p.shares
        return 0
