"""
数据迁移脚本 - 从旧系统到新系统
用于平滑过渡到重构后的交易系统

执行方式:
    python scripts/migrate_trading_system.py
"""

import sys
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import Database, get_database
from core.paper_account import PaperAccount
from core.order_types import OrderSide, OrderType, OrderStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradingSystemMigrator:
    """交易系统数据迁移器"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()
        self.migrated_orders = 0
        self.migrated_positions = 0
        self.migrated_trades = 0

    def migrate_paper_accounts(self):
        """迁移PaperAccount数据到新的accounts表"""
        logger.info("开始迁移 PaperAccount 数据...")

        try:
            # 尝试加载默认账户
            account = PaperAccount(user_id=1)
            if not account.load_default_account():
                logger.info("未找到默认账户，跳过迁移")
                return

            account_data = account._load_account_data()
            if not account_data:
                logger.info("账户数据为空，跳过迁移")
                return

            # 插入或更新 accounts 表
            with self.db.conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO accounts (user_id, account_name, balance, initial_capital, currency, status)
                    VALUES (?, '默认账户', ?, ?, 'CNY', 'active')
                    ON CONFLICT(user_id) DO UPDATE SET
                        balance = excluded.balance,
                        initial_capital = excluded.initial_capital,
                        updated_at = CURRENT_TIMESTAMP
                """, (1, account_data.get('balance', 0), account_data.get('total_assets', 0)))

            self.db.conn.commit()
            logger.info(f"账户迁移完成")

            # 迁移持仓
            self._migrate_positions(account_data)

            # 迁移交易历史
            self._migrate_trade_history(account_data)

        except Exception as e:
            logger.error(f"账户迁移失败: {e}", exc_info=True)

    def _migrate_positions(self, account_data: Dict):
        """迁移持仓数据"""
        try:
            positions = account_data.get('positions', [])
            account_id = self._get_account_id(1)

            if not account_id:
                logger.warning("未找到账户ID，跳过持仓迁移")
                return

            with self.db.conn.cursor() as cursor:
                for pos in positions:
                    ticker = pos.get('ticker', '')
                    shares = int(pos.get('shares', 0))
                    avg_cost = float(pos.get('avg_cost', 0))

                    cursor.execute("""
                        INSERT INTO positions (account_id, ticker, shares, available_shares, avg_cost)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(account_id, ticker) DO UPDATE SET
                            shares = excluded.shares,
                            avg_cost = excluded.avg_cost,
                            updated_at = CURRENT_TIMESTAMP
                    """, (account_id, ticker, shares, shares, avg_cost))

            self.db.conn.commit()
            self.migrated_positions = len(positions)
            logger.info(f"持仓迁移完成: {len(positions)} 条")

        except Exception as e:
            logger.error(f"持仓迁移失败: {e}", exc_info=True)

    def _migrate_trade_history(self, account_data: Dict):
        """迁移交易历史"""
        try:
            trades = account_data.get('trade_log', [])
            account_id = self._get_account_id(1)

            if not account_id:
                logger.warning("未找到账户ID，跳过交易历史迁移")
                return

            with self.db.conn.cursor() as cursor:
                for trade in trades:
                    ticker = trade.get('ticker', '')
                    action = trade.get('action', '')
                    price = float(trade.get('price', 0))
                    shares = int(trade.get('shares', 0))
                    fee = float(trade.get('fee', 0))
                    trade_time = trade.get('date', '')

                    cursor.execute("""
                        INSERT INTO trade_history (account_id, ticker, action, price, shares, fee, trade_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (account_id, ticker, action, price, shares, fee, trade_time))

            self.db.conn.commit()
            self.migrated_trades = len(trades)
            logger.info(f"交易历史迁移完成: {len(trades)} 条")

        except Exception as e:
            logger.error(f"交易历史迁移失败: {e}", exc_info=True)

    def _get_account_id(self, user_id: int) -> Optional[int]:
        """根据user_id获取account_id"""
        with self.db.conn.cursor() as cursor:
            cursor.execute("SELECT id FROM accounts WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return row['id'] if row else None

    def migrate_paper_trading_orders(self):
        """迁移旧订单文件到orders表（如果有）"""
        logger.info("检查订单文件迁移...")

        # 查找旧的订单文件
        data_dir = Path("data")
        orders_file = data_dir / "orders.json"

        if not orders_file.exists():
            logger.info("未找到 orders.json 文件，跳过迁移")
            return

        try:
            with open(orders_file, 'r', encoding='utf-8') as f:
                orders = json.load(f)

            account_id = self._get_account_id(1)

            if not orders or not account_id:
                logger.info("订单数据为空或未找到账户ID，跳过迁移")
                return

            with self.db.conn.cursor() as cursor:
                for order in orders:
                    order_id = order.get('order_id', '')
                    if not order_id:
                        continue

                    cursor.execute("""
                        INSERT INTO orders (
                            order_id, account_id, symbol, side, order_type,
                            quantity, price, stop_price, status, filled_quantity,
                            avg_fill_price, time_in_force, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        order_id,
                        account_id,
                        order.get('ticker', ''),
                        order.get('action', ''),
                        'MARKET',  # 旧系统只有市价单
                        order.get('shares', 0),
                        order.get('price'),
                        None,
                        self._map_status(order.get('status', '')),
                        order.get('filled_quantity', 0),
                        order.get('avg_price', 0),
                        'DAY',
                        order.get('created_at', ''),
                        order.get('updated_at', '')
                    ))

            self.db.conn.commit()
            self.migrated_orders = len(orders)
            logger.info(f"订单迁移完成: {len(orders)} 条")

        except Exception as e:
            logger.error(f"订单迁移失败: {e}", exc_info=True)

    def _map_status(self, old_status: str) -> str:
        """映射旧系统状态到新系统"""
        status_map = {
            'pending': 'PENDING',
            'submitted': 'SUBMITTED',
            'filled': 'FILLED',
            'cancelled': 'CANCELLED',
            'rejected': 'REJECTED',
            'expired': 'EXPIRED',
            'failed': 'FAILED'
        }
        return status_map.get(old_status.lower(), 'PENDING')


def dry_run_migration():
    """模拟迁移（不实际执行）"""
    logger.info("=== 模拟迁移 ===")
    logger.info("将执行以下操作:")
    logger.info("1. 创建/更新 accounts 表")
    logger.info("2. 迁移 positions 数据")
    logger.info("3. 迁移 trade_history 数据")
    logger.info("4. 迁移 orders 数据（如有）")


def main():
    """主函数"""
    logger.info("开始交易系统数据迁移...")

    # 干运行
    dry_run_migration()

    # 确认执行
    response = input("\n是否继续执行迁移? (yes/no): ")
    if response.lower() != 'yes':
        logger.info("迁移已取消")
        return

    # 执行迁移
    migrator = TradingSystemMigrator()
    migrator.migrate_paper_accounts()
    migrator.migrate_paper_trading_orders()

    # 输出统计
    logger.info("=== 迁移完成 ===")
    logger.info(f"账户: 1")
    logger.info(f"持仓: {migrator.migrated_positions}")
    logger.info(f"交易历史: {migrator.migrated_trades}")
    logger.info(f"订单: {migrator.migrated_orders}")

    print(f"\n迁移完成！统计:")
    print(f"  - 持仓: {migrator.migrated_positions} 条")
    print(f"  - 交易历史: {migrator.migrated_trades} 条")
    print(f"  - 订单: {migrator.migrated_orders} 条")


if __name__ == "__main__":
    main()
