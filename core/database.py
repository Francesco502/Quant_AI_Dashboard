"""SQLite数据库接口

职责：
- 提供SQLite数据库接口，替代文件系统存储
- 支持批量插入和查询优化
- 兼容现有data_store接口
"""

from __future__ import annotations

import sqlite3
import os
import logging
from typing import Optional, Dict, List
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np


logger = logging.getLogger(__name__)


class Database:
    """SQLite数据库接口"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化数据库连接

        Args:
            db_path: 数据库文件路径（可选，默认使用data/quant.db）
        """
        if db_path is None:
            from .data_store import BASE_DIR
            db_path = os.path.join(BASE_DIR, "quant.db")
        
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        
        # 确保目录存在
        dir_name = os.path.dirname(db_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        
        # 初始化数据库
        self._init_database()
        
        logger.info(f"数据库初始化完成: {self.db_path}")
    
    def _init_database(self):
        """初始化数据库表结构"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        cursor = self.conn.cursor()
        
        # 创建价格数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                date DATE NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL NOT NULL,
                volume REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ticker, date)
            )
        """)
        
        # 创建索引以优化查询
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ticker_date 
            ON price_data(ticker, date)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ticker 
            ON price_data(ticker)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_date 
            ON price_data(date)
        """)

        # --------------------
        # 用户系统表
        # --------------------

        # 1. Users 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. User Assets 表 (替代 user_state.json 中的 assets)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                asset_type TEXT DEFAULT 'stock', -- stock, fund, gold
                alias TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id),
                UNIQUE(user_id, ticker)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_assets_user_id 
            ON user_assets(user_id)
        """)

        # 3. User Strategies 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                strategy_name TEXT NOT NULL,
                config TEXT, -- JSON format
                is_active BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)

        # --------------------
        # 模拟交易系统表
        # --------------------

        # 4. Accounts 表 (模拟账户资金)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                account_name TEXT NOT NULL,
                balance REAL DEFAULT 100000.0,
                frozen REAL DEFAULT 0.0,
                currency TEXT DEFAULT 'CNY',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)

        # 添加初始资本和状态字段（用于兼容老数据）
        try:
            cursor.execute("ALTER TABLE accounts ADD COLUMN initial_capital REAL")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE accounts ADD COLUMN status TEXT DEFAULT 'active'")
        except sqlite3.OperationalError:
            pass

        # 5. Positions 表 (持仓)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                shares INTEGER DEFAULT 0,
                avg_cost REAL DEFAULT 0.0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(account_id) REFERENCES accounts(id),
                UNIQUE(account_id, ticker)
            )
        """)

        # 添加 available_shares 字段（用于T+1考虑）
        try:
            cursor.execute("ALTER TABLE positions ADD COLUMN available_shares INTEGER")
        except sqlite3.OperationalError:
            pass

        # 6. Trade History 表 (交易记录)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                action TEXT NOT NULL, -- BUY, SELL
                price REAL NOT NULL,
                shares INTEGER NOT NULL,
                fee REAL DEFAULT 0.0,
                trade_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(account_id) REFERENCES accounts(id)
            )
        """)

        # 7. Equity History 表 (每日权益快照，用于绘制权益曲线)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS equity_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                date DATE NOT NULL,
                equity REAL NOT NULL,
                cash REAL NOT NULL,
                position_value REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(account_id) REFERENCES accounts(id),
                UNIQUE(account_id, date)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_equity_history_account_date
            ON equity_history(account_id, date)
        """)

        # --------------------
        # 订单与交易系统表 (新增)
        # --------------------

        # 8. Orders 表 (订单持久化)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE NOT NULL,
                account_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                order_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL,
                stop_price REAL,
                status TEXT DEFAULT 'PENDING',
                filled_quantity INTEGER DEFAULT 0,
                avg_fill_price REAL DEFAULT 0.0,
                time_in_force TEXT DEFAULT 'DAY',
                strategy_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY(account_id) REFERENCES accounts(id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_account ON orders(account_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol)
        """)

        # 9. Fills 表 (成交记录)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fill_id TEXT UNIQUE NOT NULL,
                order_id TEXT NOT NULL,
                account_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                commission REAL DEFAULT 0.0,
                slippage REAL DEFAULT 0.0,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(order_id) REFERENCES orders(order_id),
                FOREIGN KEY(account_id) REFERENCES accounts(id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fills_order ON fills(order_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fills_account ON fills(account_id)
        """)

        # 10. Stop Loss Rules 表 (止损止盈规则)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stop_loss_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                rule_type TEXT NOT NULL,
                stop_type TEXT NOT NULL,
                trigger_price REAL NOT NULL,
                quantity INTEGER,
                enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(account_id) REFERENCES accounts(id),
                UNIQUE(account_id, symbol, rule_type)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stop_loss_rules_account ON stop_loss_rules(account_id)
        """)

        # 11. Stop Loss Rules 表添加 last_triggered_at 字段（用于防止重复触发）
        try:
            cursor.execute("""
                ALTER TABLE stop_loss_rules ADD COLUMN last_triggered_at TIMESTAMP
            """)
        except sqlite3.OperationalError:
            pass  # 字段已存在

        # 12. Risk Events 表 (风险事件记录)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS risk_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                symbol TEXT,
                order_id TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_risk_events_account ON risk_events(account_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_risk_events_severity ON risk_events(severity)
        """)

        # 更新 stop_loss_rules 表，添加最小触发时间间隔字段（默认60秒）
        try:
            cursor.execute("""
                ALTER TABLE stop_loss_rules ADD COLUMN cooldown_seconds INTEGER DEFAULT 60
            """)
        except sqlite3.OperationalError:
            pass  # 字段已存在

        # 更新 trade_history 表，添加 order_id 和 pnl 字段
        try:
            cursor.execute("""
                ALTER TABLE trade_history ADD COLUMN order_id TEXT
            """)
        except sqlite3.OperationalError:
            pass  # 字段已存在

        try:
            cursor.execute("""
                ALTER TABLE trade_history ADD COLUMN pnl REAL
            """)
        except sqlite3.OperationalError:
            pass  # 字段已存在

        # 13. Strategy Templates 表 (策略模板库)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategy_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                template_name TEXT NOT NULL,
                strategy_id TEXT NOT NULL,
                strategy_type TEXT NOT NULL,
                description TEXT,
                params TEXT NOT NULL,
                is_public BOOLEAN DEFAULT 0,
                is_favorite BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_strategy_templates_user
            ON strategy_templates(user_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_strategy_templates_strategy
            ON strategy_templates(strategy_id)
        """)

        # 14. Backtest History 表 (回测历史记录)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backtest_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                template_id INTEGER,
                strategy_id TEXT NOT NULL,
                strategy_params TEXT,
                tickers TEXT NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE,
                initial_capital REAL NOT NULL,
                metrics TEXT,
                equity_curve TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(template_id) REFERENCES strategy_templates(id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_backtest_history_user
            ON backtest_history(user_id)
        """)

        self.conn.commit()

    def save_price_data(
        self,
        ticker: str,
        data: pd.DataFrame | pd.Series,
        replace: bool = True
    ) -> bool:
        """
        保存价格数据

        Args:
            ticker: 标的代码
            data: 价格数据（DataFrame或Series）
            replace: 是否替换已存在的数据

        Returns:
            是否成功
        """
        if data is None or data.empty:
            return False

        try:
            # 转换为DataFrame
            if isinstance(data, pd.Series):
                df = pd.DataFrame({"close": data})
            else:
                df = data.copy()

            # 确保有日期索引
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)

            # 准备数据
            records = []
            for date, row in df.iterrows():
                record = {
                    "ticker": ticker,
                    "date": date.strftime("%Y-%m-%d"),
                    "close": float(row.get("close", 0)),
                }

                # 添加OHLCV列（如果存在）
                for col in ["open", "high", "low", "volume"]:
                    if col in row:
                        value = row[col]
                        if pd.notna(value):
                            record[col] = float(value)
                        else:
                            record[col] = None
                    else:
                        record[col] = None

                records.append(record)

            if not records:
                return False

            # 批量插入，使用事务和分批提交
            cursor = self.conn.cursor()

            # 使用事务包裹整个操作
            cursor.execute("BEGIN TRANSACTION")

            try:
                if replace:
                    # 先删除该标的的所有旧数据
                    cursor.execute("DELETE FROM price_data WHERE ticker = ?", (ticker,))

                    # 分批插入新数据（每1000条一批）
                    batch_size = 1000
                    for i in range(0, len(records), batch_size):
                        batch = records[i:i + batch_size]
                        cursor.executemany("""
                            INSERT INTO price_data
                            (ticker, date, open, high, low, close, volume, updated_at)
                            VALUES (:ticker, :date, :open, :high, :low, :close, :volume, CURRENT_TIMESTAMP)
                        """, batch)
                else:
                    # 使用INSERT OR IGNORE（跳过已存在的数据，分批）
                    batch_size = 1000
                    for i in range(0, len(records), batch_size):
                        batch = records[i:i + batch_size]
                        cursor.executemany("""
                            INSERT OR IGNORE INTO price_data
                            (ticker, date, open, high, low, close, volume)
                            VALUES (:ticker, :date, :open, :high, :low, :close, :volume)
                        """, batch)

                cursor.execute("COMMIT")
            except Exception as e:
                cursor.execute("ROLLBACK")
                raise

            logger.debug(f"保存价格数据: {ticker} - {len(records)} 条记录")
            return True

        except Exception as e:
            logger.error(f"保存价格数据失败: {ticker} - {e}")
            try:
                self.conn.rollback()
            except Exception:
                pass
            return False
            
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def query_price_data(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        查询价格数据

        Args:
            ticker: 标的代码
            start_date: 起始日期（可选，格式：YYYY-MM-DD）
            end_date: 结束日期（可选，格式：YYYY-MM-DD）

        Returns:
            价格数据DataFrame（如果不存在返回None）
        """
        try:
            query = """
                SELECT date, open, high, low, close, volume
                FROM price_data
                WHERE ticker = ?
            """
            params = [ticker]
            
            if start_date:
                query += " AND date >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND date <= ?"
                params.append(end_date)
            
            query += " ORDER BY date"
            
            df = pd.read_sql_query(query, self.conn, params=params, parse_dates=["date"])
            
            if df.empty:
                return None
            
            # 设置日期为索引
            df.set_index("date", inplace=True)
            
            # 确保列顺序
            columns = []
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df.columns:
                    columns.append(col)
            df = df[columns]
            
            return df
            
        except Exception as e:
            logger.error(f"查询价格数据失败: {ticker} - {e}")
            return None
    
    def query_price_series(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[pd.Series]:
        """
        查询价格序列（仅close列）

        Args:
            ticker: 标的代码
            start_date: 起始日期（可选）
            end_date: 结束日期（可选）

        Returns:
            价格序列（如果不存在返回None）
        """
        df = self.query_price_data(ticker, start_date, end_date)
        
        if df is None or df.empty:
            return None
        
        if "close" in df.columns:
            return df["close"]
        else:
            return None
    
    def get_tickers(self) -> List[str]:
        """获取所有标的代码列表"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT DISTINCT ticker FROM price_data ORDER BY ticker")
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取标的列表失败: {e}")
            return []
    
    def get_date_range(self, ticker: str) -> Optional[Dict[str, str]]:
        """获取标的的日期范围"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT MIN(date) as start_date, MAX(date) as end_date
                FROM price_data
                WHERE ticker = ?
            """, (ticker,))
            
            row = cursor.fetchone()
            if row and row[0]:
                return {
                    "start_date": row[0],
                    "end_date": row[1],
                }
            return None
        except Exception as e:
            logger.error(f"获取日期范围失败: {ticker} - {e}")
            return None
    
    def delete_ticker(self, ticker: str) -> bool:
        """删除标的的所有数据"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM price_data WHERE ticker = ?", (ticker,))
            self.conn.commit()
            
            deleted_count = cursor.rowcount
            logger.info(f"删除标的数据: {ticker} - {deleted_count} 条记录")
            return True
        except Exception as e:
            logger.error(f"删除标的数据失败: {ticker} - {e}")
            if self.conn:
                self.conn.rollback()
            return False
    
    def get_statistics(self) -> Dict:
        """获取数据库统计信息"""
        try:
            cursor = self.conn.cursor()
            
            # 标的数量
            cursor.execute("SELECT COUNT(DISTINCT ticker) FROM price_data")
            ticker_count = cursor.fetchone()[0]
            
            # 总记录数
            cursor.execute("SELECT COUNT(*) FROM price_data")
            record_count = cursor.fetchone()[0]
            
            # 日期范围
            cursor.execute("SELECT MIN(date), MAX(date) FROM price_data")
            date_range = cursor.fetchone()
            
            return {
                "ticker_count": ticker_count,
                "record_count": record_count,
                "start_date": date_range[0] if date_range[0] else None,
                "end_date": date_range[1] if date_range[1] else None,
                "db_path": self.db_path,
                "db_size_mb": os.path.getsize(self.db_path) / (1024 * 1024) if os.path.exists(self.db_path) else 0,
            }
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()


# 全局数据库实例（延迟初始化）
_db_instance: Optional[Database] = None


def get_database(db_path: Optional[str] = None) -> Database:
    """
    获取数据库实例（单例模式）

    Args:
        db_path: 数据库文件路径（可选）

    Returns:
        数据库实例
    """
    global _db_instance
    
    if _db_instance is None:
        _db_instance = Database(db_path)
    
    return _db_instance

