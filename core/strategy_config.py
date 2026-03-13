"""策略配置管理

职责：
- 策略参数管理
- 策略启用/禁用
- 策略权重配置

v1.1.0 新增：策略配置管理
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import logging

from core.database import Database

logger = logging.getLogger(__name__)


@dataclass
class StrategyConfig:
    """策略配置"""
    id: Optional[int] = None
    user_id: int = 1
    strategy_name: str = ""
    config_json: str = "{}"
    is_active: bool = True
    weight: float = 1.0
    created_at: str = ""
    updated_at: str = ""


class StrategyConfigManager:
    """策略配置管理器"""

    def __init__(self, db: Optional[Database] = None):
        """
        初始化管理器

        Args:
            db: 数据库实例
        """
        self.db = db or Database()
        self._ensure_tables()

    def _ensure_tables(self):
        """确保表存在"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategy_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                strategy_name TEXT NOT NULL,
                config_json TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                weight REAL DEFAULT 1.0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, strategy_name)
            )
        """)
        self.db.conn.commit()
        logger.info("策略配置表已创建")

    def save_config(self, config: StrategyConfig) -> bool:
        """
        保存策略配置

        Args:
            config: 策略配置对象

        Returns:
            是否成功
        """
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("""
                INSERT INTO strategy_config
                (user_id, strategy_name, config_json, is_active, weight)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, strategy_name) DO UPDATE SET
                    config_json = excluded.config_json,
                    is_active = excluded.is_active,
                    weight = excluded.weight,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                config.user_id,
                config.strategy_name,
                config.config_json,
                1 if config.is_active else 0,
                config.weight
            ))
            self.db.conn.commit()
            return True
        except Exception as e:
            logger.error(f"保存策略配置失败: {e}")
            return False

    def get_config(self, user_id: int, strategy_name: str) -> Optional[StrategyConfig]:
        """
        获取策略配置

        Args:
            user_id: 用户ID
            strategy_name: 策略名称

        Returns:
            策略配置对象
        """
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT id, user_id, strategy_name, config_json, is_active, weight, created_at, updated_at
                FROM strategy_config
                WHERE user_id = ? AND strategy_name = ?
            """, (user_id, strategy_name))
            row = cursor.fetchone()

            if row:
                return StrategyConfig(
                    id=row[0],
                    user_id=row[1],
                    strategy_name=row[2],
                    config_json=row[3],
                    is_active=bool(row[4]),
                    weight=row[5] or 1.0,
                    created_at=row[6],
                    updated_at=row[7]
                )
            return None
        except Exception as e:
            logger.error(f"获取策略配置失败: {e}")
            return None

    def get_all_configs(self, user_id: int) -> List[StrategyConfig]:
        """
        获取所有策略配置

        Args:
            user_id: 用户ID

        Returns:
            策略配置列表
        """
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT id, user_id, strategy_name, config_json, is_active, weight, created_at, updated_at
                FROM strategy_config
                WHERE user_id = ?
                ORDER BY strategy_name
            """, (user_id,))
            rows = cursor.fetchall()

            configs = []
            for row in rows:
                configs.append(StrategyConfig(
                    id=row[0],
                    user_id=row[1],
                    strategy_name=row[2],
                    config_json=row[3],
                    is_active=bool(row[4]),
                    weight=row[5] or 1.0,
                    created_at=row[6],
                    updated_at=row[7]
                ))
            return configs
        except Exception as e:
            logger.error(f"获取策略配置列表失败: {e}")
            return []

    def delete_config(self, user_id: int, strategy_name: str) -> bool:
        """
        删除策略配置

        Args:
            user_id: 用户ID
            strategy_name: 策略名称

        Returns:
            是否成功
        """
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("""
                DELETE FROM strategy_config
                WHERE user_id = ? AND strategy_name = ?
            """, (user_id, strategy_name))
            self.db.conn.commit()
            return True
        except Exception as e:
            logger.error(f"删除策略配置失败: {e}")
            return False

    def get_active_strategies(self, user_id: int) -> List[StrategyConfig]:
        """
        获取启用的策略列表

        Args:
            user_id: 用户ID

        Returns:
            启用的策略配置列表
        """
        configs = self.get_all_configs(user_id)
        return [c for c in configs if c.is_active]


# 预设策略配置
DEFAULT_STRATEGY_CONFIGS = {
    'ma': {
        'name': 'ma',
        'display_name': 'MA金叉策略',
        'description': '短期均线上穿长期均线买入',
        'default_config': {
            'short_period': 20,
            'long_period': 50
        },
        'enabled': True,
        'weight': 1.0
    },
    'rsi': {
        'name': 'rsi',
        'display_name': 'RSI超卖策略',
        'description': 'RSI低于30买入',
        'default_config': {
            'period': 14,
            'oversold': 30,
            'overbought': 70
        },
        'enabled': True,
        'weight': 1.0
    },
    'trend': {
        'name': 'trend',
        'display_name': '多头趋势策略',
        'description': '连续上涨趋势买入',
        'default_config': {
            'min_days': 5,
            'min_gain': 0.05
        },
        'enabled': True,
        'weight': 1.5
    },
    'breakout': {
        'name': 'breakout',
        'display_name': '突破策略',
        'description': '价格突破20日高点买入',
        'default_config': {
            'period': 20
        },
        'enabled': True,
        'weight': 1.0
    },
    'value': {
        'name': 'value',
        'display_name': '价值策略',
        'description': '低估值价值股',
        'default_config': {
            'max_pe': 30,
            'max_pb': 2.0
        },
        'enabled': True,
        'weight': 1.2
    }
}


def get_default_strategy_config(strategy_name: str) -> Dict:
    """
    获取策略默认配置

    Args:
        strategy_name: 策略名称

    Returns:
        配置字典
    """
    if strategy_name in DEFAULT_STRATEGY_CONFIGS:
        return DEFAULT_STRATEGY_CONFIGS[strategy_name]['default_config']
    return {}


def get_strategy_display_name(strategy_name: str) -> str:
    """
    获取策略显示名称

    Args:
        strategy_name: 策略名称

    Returns:
        显示名称
    """
    if strategy_name in DEFAULT_STRATEGY_CONFIGS:
        return DEFAULT_STRATEGY_CONFIGS[strategy_name]['display_name']
    return strategy_name


def get_all_strategy_names() -> List[str]:
    """
    获取所有策略名称

    Returns:
        策略名称列表
    """
    return list(DEFAULT_STRATEGY_CONFIGS.keys())


# 全局实例
_strategy_config_manager: Optional[StrategyConfigManager] = None


def get_strategy_config_manager(db: Optional[Database] = None) -> StrategyConfigManager:
    """
    获取策略配置管理器（单例模式）

    Args:
        db: 数据库实例

    Returns:
        策略配置管理器
    """
    global _strategy_config_manager
    if _strategy_config_manager is None:
        _strategy_config_manager = StrategyConfigManager(db)
    return _strategy_config_manager
