"""User-specific watchlist, strategy config, and preference storage."""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional

from core.database import get_database


logger = logging.getLogger(__name__)


@dataclass
class WatchItem:
    user_id: int
    ticker: str
    added_at: str
    note: Optional[str] = None


@dataclass
class StrategyConfig:
    user_id: int
    strategy_name: str
    config_json: str
    created_at: str


@dataclass
class UserPreferences:
    user_id: int
    default_strategy: str = "all"
    risk_tolerance: str = "moderate"
    notification_enabled: bool = True
    preferences_json: str = ""


class UserConfigManager:
    _init_lock = threading.Lock()

    def __init__(self):
        self.db = get_database()
        self._db_lock = threading.Lock()
        self._tables_ready = False

    def _cursor(self):
        if not self.db.conn:
            raise RuntimeError("Database connection is not initialized")
        return self.db.conn.cursor()

    def _ensure_tables(self) -> None:
        if self._tables_ready:
            return

        with self._init_lock:
            if self._tables_ready:
                return

            with self._db_lock:
                cursor = self._cursor()

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_watchlist (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        ticker TEXT NOT NULL,
                        added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        note TEXT,
                        UNIQUE(user_id, ticker)
                    )
                    """
                )

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_strategy_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        strategy_name TEXT NOT NULL,
                        config_json TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                # One-time dedupe for legacy rows before unique index enforcement.
                cursor.execute(
                    """
                    DELETE FROM user_strategy_config
                    WHERE id NOT IN (
                        SELECT MAX(id)
                        FROM user_strategy_config
                        GROUP BY user_id, strategy_name
                    )
                    """
                )

                cursor.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_user_strategy_config_user_strategy
                    ON user_strategy_config(user_id, strategy_name)
                    """
                )

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_preferences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER UNIQUE NOT NULL,
                        default_strategy TEXT DEFAULT 'all',
                        risk_tolerance TEXT DEFAULT 'moderate',
                        notification_enabled INTEGER DEFAULT 1,
                        preferences_json TEXT,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                self.db.conn.commit()

            self._tables_ready = True
            logger.info("User config tables are ready")

    def add_watchlist(self, user_id: int, ticker: str, note: Optional[str] = None) -> bool:
        self._ensure_tables()
        try:
            with self._db_lock:
                cursor = self._cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO user_watchlist (user_id, ticker, note) VALUES (?, ?, ?)",
                    (user_id, ticker, note),
                )
                self.db.conn.commit()
            return True
        except Exception as e:
            logger.error("Failed to add watchlist item: %s", e)
            return False

    def remove_watchlist(self, user_id: int, ticker: str) -> bool:
        self._ensure_tables()
        try:
            with self._db_lock:
                cursor = self._cursor()
                cursor.execute(
                    "DELETE FROM user_watchlist WHERE user_id = ? AND ticker = ?",
                    (user_id, ticker),
                )
                self.db.conn.commit()
            return True
        except Exception as e:
            logger.error("Failed to remove watchlist item: %s", e)
            return False

    def get_watchlist(self, user_id: int) -> List[str]:
        self._ensure_tables()
        try:
            with self._db_lock:
                cursor = self._cursor()
                cursor.execute("SELECT ticker FROM user_watchlist WHERE user_id = ?", (user_id,))
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error("Failed to load watchlist: %s", e)
            return []

    def add_strategy_config(self, user_id: int, strategy_name: str, config: Dict) -> bool:
        self._ensure_tables()
        try:
            config_json = json.dumps(config, ensure_ascii=False)
            with self._db_lock:
                cursor = self._cursor()
                cursor.execute(
                    """
                    INSERT INTO user_strategy_config (user_id, strategy_name, config_json)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id, strategy_name) DO UPDATE SET
                        config_json = excluded.config_json,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (user_id, strategy_name, config_json),
                )
                self.db.conn.commit()
            return True
        except Exception as e:
            logger.error("Failed to save strategy config: %s", e)
            return False

    def get_strategy_config(self, user_id: int, strategy_name: str) -> Optional[Dict]:
        self._ensure_tables()
        try:
            with self._db_lock:
                cursor = self._cursor()
                cursor.execute(
                    "SELECT config_json FROM user_strategy_config WHERE user_id = ? AND strategy_name = ?",
                    (user_id, strategy_name),
                )
                row = cursor.fetchone()
                return json.loads(row[0]) if row else None
        except Exception as e:
            logger.error("Failed to load strategy config: %s", e)
            return None

    def save_preferences(self, preferences: UserPreferences) -> bool:
        self._ensure_tables()
        try:
            with self._db_lock:
                cursor = self._cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO user_preferences
                    (user_id, default_strategy, risk_tolerance, notification_enabled, preferences_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        preferences.user_id,
                        preferences.default_strategy,
                        preferences.risk_tolerance,
                        1 if preferences.notification_enabled else 0,
                        preferences.preferences_json,
                    ),
                )
                self.db.conn.commit()
            return True
        except Exception as e:
            logger.error("Failed to save preferences: %s", e)
            return False

    def get_preferences(self, user_id: int) -> Optional[UserPreferences]:
        self._ensure_tables()
        try:
            with self._db_lock:
                cursor = self._cursor()
                cursor.execute(
                    """
                    SELECT user_id, default_strategy, risk_tolerance, notification_enabled, preferences_json
                    FROM user_preferences
                    WHERE user_id = ?
                    """,
                    (user_id,),
                )
                row = cursor.fetchone()

                if not row:
                    return None

                return UserPreferences(
                    user_id=int(row["user_id"]),
                    default_strategy=row["default_strategy"] or "all",
                    risk_tolerance=row["risk_tolerance"] or "moderate",
                    notification_enabled=bool(row["notification_enabled"]),
                    preferences_json=row["preferences_json"] or "",
                )
        except Exception as e:
            logger.error("Failed to load preferences: %s", e)
            return None


_user_config_manager: Optional[UserConfigManager] = None


def get_user_config_manager() -> UserConfigManager:
    global _user_config_manager
    if _user_config_manager is None:
        _user_config_manager = UserConfigManager()
    return _user_config_manager
