"""User asset ledger, valuation, and DCA execution service."""

from __future__ import annotations

import copy
import calendar
import datetime as dt
import hashlib
import json
import logging
import threading
import time
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from core.data_service import load_cn_realtime_quotes_sina, load_price_data, load_price_data_akshare
from core.database import get_database
from core.trading_calendar import Market, get_trading_calendar


logger = logging.getLogger(__name__)
OVERVIEW_CACHE_TTL_SECONDS = 90
SNAPSHOT_PERSIST_MIN_INTERVAL_SECONDS = 600
VALUATION_HISTORY_DAYS = 400
FUND_NAV_HISTORY_DAYS = 90

DEFAULT_ADMIN_ASSET_SEED: List[Dict[str, Any]] = [
    {
        "ticker": "013281",
        "asset_name": "国泰海通30天滚动持有中短债债券A",
        "asset_category": "现金/固收",
        "asset_style": "低风险/流动性管理/防守",
        "asset_type": "fund",
        "units": 2648.88,
        "avg_cost": 1.1326,
    },
    {
        "ticker": "002611",
        "asset_name": "博时黄金ETF联接C",
        "asset_category": "商品/避险",
        "asset_style": "抗通胀/避险/与股市低相关",
        "asset_type": "fund",
        "units": 2311.73,
        "avg_cost": 2.5308,
        "dca_rule": {
            "enabled": True,
            "frequency": "weekly",
            "weekday": 3,
            "amount": 100.0,
            "shift_to_next_trading_day": True,
        },
    },
    {
        "ticker": "160615",
        "asset_name": "鹏华沪深300ETF联接(LOF)A",
        "asset_category": "核心权益 (A股)",
        "asset_style": "大盘蓝筹/中国核心资产",
        "asset_type": "fund",
        "units": 1295.24,
        "avg_cost": 1.2088,
    },
    {
        "ticker": "159755",
        "asset_name": "电池ETF",
        "asset_category": "主题权益 (成长)",
        "asset_style": "高景气赛道/高波动/高弹性",
        "asset_type": "fund",
        "units": 6100.0,
        "avg_cost": 0.653,
    },
    {
        "ticker": "006810",
        "asset_name": "泰康港股通中证香港银行投资指数C",
        "asset_category": "境外权益 (港股)",
        "asset_style": "港股红利/低估值/高股息",
        "asset_type": "fund",
        "units": 5620.26,
        "avg_cost": 1.3523,
        "dca_rule": {
            "enabled": True,
            "frequency": "weekly",
            "weekday": 3,
            "amount": 100.0,
            "shift_to_next_trading_day": True,
        },
    },
    {
        "ticker": "006195",
        "asset_name": "国金量化多因子股票A",
        "asset_category": "增强权益 (量化)",
        "asset_style": "主动管理/量化选股/获取超额收益",
        "asset_type": "fund",
        "units": 59.89,
        "avg_cost": 3.3395,
        "dca_rule": {
            "enabled": True,
            "frequency": "weekly",
            "weekday": 3,
            "amount": 100.0,
            "shift_to_next_trading_day": True,
        },
    },
]


class UserAssetService:
    """Per-user asset ledger with valuation and DCA support."""

    _init_lock = threading.Lock()

    def __init__(self):
        self.db = get_database()
        self._db_lock = threading.Lock()
        self._cache_lock = threading.Lock()
        self._tables_ready = False
        self._overview_cache: Dict[int, Dict[str, Any]] = {}
        self._snapshot_state: Dict[int, Dict[str, Any]] = {}

    def _cursor(self):
        if not self.db.conn:
            raise RuntimeError("Database connection is not initialized")
        return self.db.conn.cursor()

    def _invalidate_user_cache(self, user_id: int) -> None:
        with self._cache_lock:
            self._overview_cache.pop(int(user_id), None)

    def invalidate_all_caches(self) -> None:
        with self._cache_lock:
            self._overview_cache.clear()

    def _get_cached_overview(self, user_id: int) -> Optional[Dict[str, Any]]:
        now = time.monotonic()
        with self._cache_lock:
            entry = self._overview_cache.get(int(user_id))
            if not entry:
                return None
            loaded_at = float(entry.get("loaded_at") or 0.0)
            if now - loaded_at > OVERVIEW_CACHE_TTL_SECONDS:
                self._overview_cache.pop(int(user_id), None)
                return None
            return copy.deepcopy(entry.get("payload"))

    def _store_cached_overview(self, user_id: int, payload: Dict[str, Any]) -> None:
        with self._cache_lock:
            self._overview_cache[int(user_id)] = {
                "loaded_at": time.monotonic(),
                "payload": copy.deepcopy(payload),
            }

    def _snapshot_signature(self, assets: List[Dict[str, Any]], summary: Dict[str, Any]) -> str:
        digest_payload = {
            "assets": [
                {
                    "ticker": asset.get("ticker"),
                    "units": round(self._to_float(asset.get("units"), 0.0), 6),
                    "current_price": round(self._to_float(asset.get("current_price"), 0.0), 6),
                    "market_value": round(self._to_float(asset.get("market_value"), 0.0), 2),
                    "total_return": round(self._to_float(asset.get("total_return"), 0.0), 2),
                }
                for asset in assets
            ],
            "summary": {
                "asset_count": int(summary.get("asset_count") or 0),
                "total_market_value": round(self._to_float(summary.get("total_market_value"), 0.0), 2),
                "total_invested_amount": round(self._to_float(summary.get("total_invested_amount"), 0.0), 2),
                "total_return": round(self._to_float(summary.get("total_return"), 0.0), 2),
            },
        }
        raw = json.dumps(digest_payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _should_persist_snapshots(
        self,
        user_id: int,
        assets: List[Dict[str, Any]],
        summary: Dict[str, Any],
        *,
        force: bool = False,
    ) -> bool:
        if not assets:
            return False

        today = dt.date.today().isoformat()
        signature = self._snapshot_signature(assets, summary)
        now = time.monotonic()

        with self._cache_lock:
            state = self._snapshot_state.get(int(user_id))
            if force or state is None:
                self._snapshot_state[int(user_id)] = {
                    "snapshot_date": today,
                    "signature": signature,
                    "persisted_at": now,
                }
                return True

            same_day = state.get("snapshot_date") == today
            same_signature = state.get("signature") == signature
            elapsed = now - float(state.get("persisted_at") or 0.0)
            if same_day and same_signature and elapsed < SNAPSHOT_PERSIST_MIN_INTERVAL_SECONDS:
                return False

            self._snapshot_state[int(user_id)] = {
                "snapshot_date": today,
                "signature": signature,
                "persisted_at": now,
            }
            return True

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
                    CREATE TABLE IF NOT EXISTS user_asset_holdings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        ticker TEXT NOT NULL,
                        asset_name TEXT,
                        asset_category TEXT,
                        asset_style TEXT,
                        asset_type TEXT,
                        notes TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, ticker)
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_asset_transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        ticker TEXT NOT NULL,
                        transaction_type TEXT NOT NULL,
                        trade_date TEXT NOT NULL,
                        quantity REAL NOT NULL DEFAULT 0,
                        price REAL NOT NULL DEFAULT 0,
                        amount REAL,
                        fee REAL NOT NULL DEFAULT 0,
                        source TEXT DEFAULT 'manual',
                        note TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_asset_dca_rules (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        ticker TEXT NOT NULL,
                        enabled INTEGER NOT NULL DEFAULT 0,
                        frequency TEXT NOT NULL DEFAULT 'weekly',
                        weekday INTEGER,
                        monthday INTEGER,
                        amount REAL NOT NULL DEFAULT 0,
                        start_date TEXT NOT NULL,
                        end_date TEXT,
                        shift_to_next_trading_day INTEGER NOT NULL DEFAULT 1,
                        last_run_date TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, ticker)
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_asset_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        snapshot_date TEXT NOT NULL,
                        ticker TEXT NOT NULL,
                        current_price REAL NOT NULL DEFAULT 0,
                        units REAL NOT NULL DEFAULT 0,
                        market_value REAL NOT NULL DEFAULT 0,
                        invested_amount REAL NOT NULL DEFAULT 0,
                        total_return REAL NOT NULL DEFAULT 0,
                        total_return_pct REAL NOT NULL DEFAULT 0,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, snapshot_date, ticker)
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_user_asset_holdings_user_ticker
                    ON user_asset_holdings(user_id, ticker)
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_user_asset_transactions_user_ticker_date
                    ON user_asset_transactions(user_id, ticker, trade_date)
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_user_asset_dca_rules_user_ticker
                    ON user_asset_dca_rules(user_id, ticker)
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_user_asset_snapshots_user_date
                    ON user_asset_snapshots(user_id, snapshot_date, ticker)
                    """
                )
                self.db.conn.commit()

            self._tables_ready = True
            logger.info("User asset tables are ready")

    @staticmethod
    def _normalize_ticker(ticker: str) -> str:
        return str(ticker or "").strip().upper()

    @staticmethod
    def _to_float(value: Any, fallback: float = 0.0) -> float:
        try:
            parsed = float(value)
            if parsed != parsed:
                return fallback
            return parsed
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _date_or_today(value: Optional[str]) -> dt.date:
        if value:
            return dt.date.fromisoformat(value)
        return dt.date.today()

    @staticmethod
    def _normalize_asset_type(value: Any) -> Optional[str]:
        raw = str(value or "").strip().lower()
        if not raw:
            return None

        alias_map = {
            "fund": "fund",
            "mutual_fund": "fund",
            "otc_fund": "fund",
            "基金": "fund",
            "场外基金": "fund",
            "鍩洪噾": "fund",
            "鍦哄鍩洪噾": "fund",
            "etf": "etf",
            "lof": "etf",
            "exchange_fund": "etf",
            "场内etf": "etf",
            "场内基金": "etf",
            "鍦哄唴etf": "etf",
            "鍦哄唴鍩洪噾": "etf",
            "stock": "stock",
            "equity": "stock",
            "股票": "stock",
            "鑲＄エ": "stock",
            "other": "other",
            "其他": "other",
            "鍏朵粬": "other",
        }
        return alias_map.get(raw)

    @staticmethod
    def _is_exchange_traded_asset(ticker: str, asset_name: Optional[str]) -> bool:
        normalized = str(ticker or "").strip().upper()
        name = str(asset_name or "").upper()
        if not normalized.isdigit() or len(normalized) != 6:
            return False
        if "联接" in name or "鑱旀帴" in name:
            return False
        if normalized.startswith(("15", "50", "51", "56", "58")):
            return True
        return "ETF" in name or "LOF" in name

    @staticmethod
    def _looks_like_fund(asset_name: Optional[str]) -> bool:
        name = str(asset_name or "")
        if not name:
            return False
        fund_keywords = (
            "基金",
            "鍩洪噾",
            "联接",
            "鑱旀帴",
            "债",
            "鍊?",
            "债券",
            "鍊哄埜",
            "货币",
            "璐у竵",
            "滚动持有",
            "婊氬姩鎸佹湁",
            "中短债",
            "涓煭鍊?",
            "理财",
            "鐞嗚储",
        )
        return any(keyword in name for keyword in fund_keywords)

    def _resolve_asset_type(
        self,
        ticker: str,
        asset_name: Optional[str] = None,
        asset_type: Optional[str] = None,
    ) -> str:
        normalized = self._normalize_asset_type(asset_type)
        normalized_ticker = self._normalize_ticker(ticker)

        if self._is_exchange_traded_asset(normalized_ticker, asset_name):
            return "etf"
        if normalized:
            return normalized
        if self._looks_like_fund(asset_name):
            return "fund"
        if normalized_ticker.endswith(".HK") or normalized_ticker.endswith(".US") or normalized_ticker.isalpha():
            return "stock"
        return "other"

    def _resolve_market(self, ticker: str) -> Market:
        normalized = self._normalize_ticker(ticker)
        if normalized.endswith(".HK"):
            return Market.HK_SHARE
        if normalized.endswith(".US") or normalized.isalpha():
            return Market.US_SHARE
        return Market.A_SHARE

    @staticmethod
    def _supports_realtime_quote(holding: Dict[str, Any]) -> bool:
        ticker = str(holding.get("ticker") or "").strip().upper()
        asset_name = str(holding.get("asset_name") or "")
        asset_type = str(holding.get("asset_type") or "").strip().lower()
        if not ticker.isdigit() or len(ticker) != 6:
            return False
        if "联接" in asset_name:
            return False
        if ticker.startswith(("15", "50", "51", "56", "58")):
            return True
        return asset_type in {"stock", "etf"}

    def _should_prefer_fund_nav(self, holding: Dict[str, Any]) -> bool:
        asset_type = str(holding.get("asset_type") or "").strip().lower()
        return asset_type == "fund" and not self._supports_realtime_quote(holding)

    def _save_holding_metadata(
        self,
        cursor,
        user_id: int,
        *,
        ticker: str,
        asset_name: Optional[str],
        asset_category: Optional[str],
        asset_style: Optional[str],
        asset_type: Optional[str],
        notes: Optional[str],
    ) -> None:
        cursor.execute(
            """
            INSERT INTO user_asset_holdings
            (user_id, ticker, asset_name, asset_category, asset_style, asset_type, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, ticker) DO UPDATE SET
                asset_name = excluded.asset_name,
                asset_category = excluded.asset_category,
                asset_style = excluded.asset_style,
                asset_type = excluded.asset_type,
                notes = excluded.notes,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                int(user_id),
                ticker,
                asset_name,
                asset_category,
                asset_style,
                asset_type,
                notes,
            ),
        )

    def _save_dca_rule(
        self,
        cursor,
        user_id: int,
        ticker: str,
        rule: Optional[Dict[str, Any]],
    ) -> None:
        if rule is None:
            return

        enabled = bool(rule.get("enabled"))
        frequency = str(rule.get("frequency") or "weekly").lower()
        weekday = rule.get("weekday")
        monthday = rule.get("monthday")
        amount = max(0.0, self._to_float(rule.get("amount"), 0.0))
        start_date = str(rule.get("start_date") or dt.date.today().isoformat())
        end_date = rule.get("end_date")
        shift = bool(rule.get("shift_to_next_trading_day", True))

        cursor.execute(
            """
            INSERT INTO user_asset_dca_rules
            (
                user_id, ticker, enabled, frequency, weekday, monthday, amount,
                start_date, end_date, shift_to_next_trading_day
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, ticker) DO UPDATE SET
                enabled = excluded.enabled,
                frequency = excluded.frequency,
                weekday = excluded.weekday,
                monthday = excluded.monthday,
                amount = excluded.amount,
                start_date = excluded.start_date,
                end_date = excluded.end_date,
                shift_to_next_trading_day = excluded.shift_to_next_trading_day,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                int(user_id),
                ticker,
                1 if enabled else 0,
                frequency,
                int(weekday) if weekday is not None else None,
                int(monthday) if monthday is not None else None,
                amount,
                start_date,
                end_date,
                1 if shift else 0,
            ),
        )

    def _insert_transaction(
        self,
        cursor,
        user_id: int,
        ticker: str,
        *,
        transaction_type: str,
        trade_date: str,
        quantity: float,
        price: float,
        amount: Optional[float],
        fee: float = 0.0,
        source: str = "manual",
        note: Optional[str] = None,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO user_asset_transactions
            (
                user_id, ticker, transaction_type, trade_date, quantity,
                price, amount, fee, source, note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(user_id),
                ticker,
                transaction_type,
                trade_date,
                float(quantity),
                float(price),
                amount,
                float(fee),
                source,
                note,
            ),
        )

    def upsert_asset(
        self,
        user_id: int,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        self._ensure_tables()

        ticker = self._normalize_ticker(payload.get("ticker", ""))
        if not ticker:
            raise ValueError("ticker is required")

        units = max(0.0, self._to_float(payload.get("units"), 0.0))
        avg_cost = max(0.0, self._to_float(payload.get("avg_cost"), 0.0))
        trade_date = str(payload.get("trade_date") or dt.date.today().isoformat())
        asset_name = payload.get("asset_name")
        resolved_asset_type = self._resolve_asset_type(
            ticker,
            asset_name=asset_name,
            asset_type=payload.get("asset_type"),
        )

        with self._db_lock:
            cursor = self._cursor()
            self._save_holding_metadata(
                cursor,
                user_id,
                ticker=ticker,
                asset_name=asset_name,
                asset_category=payload.get("asset_category"),
                asset_style=payload.get("asset_style"),
                asset_type=resolved_asset_type,
                notes=payload.get("notes"),
            )

            self._insert_transaction(
                cursor,
                user_id,
                ticker,
                transaction_type="RESET",
                trade_date=trade_date,
                quantity=units,
                price=avg_cost,
                amount=units * avg_cost,
                source="manual",
                note="Reset current holdings",
            )

            self._save_dca_rule(cursor, user_id, ticker, payload.get("dca_rule"))
            self.db.conn.commit()

        self._invalidate_user_cache(user_id)
        return self.get_overview(user_id, sync_dca=False, force_refresh=True)

    def update_asset(
        self,
        user_id: int,
        original_ticker: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        self._ensure_tables()

        normalized_original = self._normalize_ticker(original_ticker)
        ticker = self._normalize_ticker(payload.get("ticker", normalized_original))
        if not normalized_original:
            raise ValueError("original ticker is required")
        if not ticker:
            raise ValueError("ticker is required")

        units = max(0.0, self._to_float(payload.get("units"), 0.0))
        avg_cost = max(0.0, self._to_float(payload.get("avg_cost"), 0.0))
        trade_date = str(payload.get("trade_date") or dt.date.today().isoformat())

        with self._db_lock:
            cursor = self._cursor()
            cursor.execute(
                """
                SELECT asset_name, asset_type
                FROM user_asset_holdings
                WHERE user_id = ? AND ticker = ?
                LIMIT 1
                """,
                (int(user_id), normalized_original),
            )
            existing_row = cursor.fetchone()
            if existing_row is None:
                raise ValueError(f"asset {normalized_original} does not exist")
            existing = dict(existing_row)

            if ticker != normalized_original:
                cursor.execute(
                    "SELECT 1 FROM user_asset_holdings WHERE user_id = ? AND ticker = ? LIMIT 1",
                    (int(user_id), ticker),
                )
                if cursor.fetchone() is not None:
                    raise ValueError(f"asset {ticker} already exists")

                for table_name in (
                    "user_asset_holdings",
                    "user_asset_transactions",
                    "user_asset_dca_rules",
                    "user_asset_snapshots",
                ):
                    cursor.execute(
                        f"UPDATE {table_name} SET ticker = ? WHERE user_id = ? AND ticker = ?",
                        (ticker, int(user_id), normalized_original),
                    )

            asset_name = payload.get("asset_name") or existing.get("asset_name")
            resolved_asset_type = self._resolve_asset_type(
                ticker,
                asset_name=asset_name,
                asset_type=payload.get("asset_type") or existing.get("asset_type"),
            )

            self._save_holding_metadata(
                cursor,
                user_id,
                ticker=ticker,
                asset_name=asset_name,
                asset_category=payload.get("asset_category"),
                asset_style=payload.get("asset_style"),
                asset_type=resolved_asset_type,
                notes=payload.get("notes"),
            )

            self._insert_transaction(
                cursor,
                user_id,
                ticker,
                transaction_type="RESET",
                trade_date=trade_date,
                quantity=units,
                price=avg_cost,
                amount=units * avg_cost,
                source="manual",
                note="Reset current holdings",
            )

            self._save_dca_rule(cursor, user_id, ticker, payload.get("dca_rule"))
            self.db.conn.commit()

        self._invalidate_user_cache(user_id)
        return self.get_overview(user_id, sync_dca=False, force_refresh=True)

    def add_transaction(self, user_id: int, ticker: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_tables()

        normalized_ticker = self._normalize_ticker(ticker)
        transaction_type = str(payload.get("transaction_type") or "BUY").upper()
        quantity = max(0.0, self._to_float(payload.get("quantity"), 0.0))
        price = max(0.0, self._to_float(payload.get("price"), 0.0))
        amount = payload.get("amount")
        amount_value = self._to_float(amount, quantity * price) if amount is not None else quantity * price
        fee = max(0.0, self._to_float(payload.get("fee"), 0.0))
        trade_date = str(payload.get("trade_date") or dt.date.today().isoformat())

        if quantity <= 0:
            raise ValueError("quantity must be greater than 0")

        if transaction_type == "SELL":
            current = self._load_position_states(user_id).get(normalized_ticker, {})
            current_units = self._to_float(current.get("units"), 0.0)
            if quantity > current_units:
                raise ValueError("sell quantity exceeds current holdings")

        with self._db_lock:
            cursor = self._cursor()
            self._insert_transaction(
                cursor,
                user_id,
                normalized_ticker,
                transaction_type=transaction_type,
                trade_date=trade_date,
                quantity=quantity,
                price=price,
                amount=amount_value,
                fee=fee,
                source=str(payload.get("source") or "manual"),
                note=payload.get("note"),
            )
            self.db.conn.commit()

        self._invalidate_user_cache(user_id)
        return self.get_overview(user_id, sync_dca=False, force_refresh=True)

    def delete_asset(self, user_id: int, ticker: str) -> bool:
        self._ensure_tables()
        normalized_ticker = self._normalize_ticker(ticker)

        with self._db_lock:
            cursor = self._cursor()
            cursor.execute(
                "DELETE FROM user_asset_holdings WHERE user_id = ? AND ticker = ?",
                (int(user_id), normalized_ticker),
            )
            changed = cursor.rowcount > 0
            cursor.execute(
                "DELETE FROM user_asset_transactions WHERE user_id = ? AND ticker = ?",
                (int(user_id), normalized_ticker),
            )
            cursor.execute(
                "DELETE FROM user_asset_dca_rules WHERE user_id = ? AND ticker = ?",
                (int(user_id), normalized_ticker),
            )
            cursor.execute(
                "DELETE FROM user_asset_snapshots WHERE user_id = ? AND ticker = ?",
                (int(user_id), normalized_ticker),
            )
            self.db.conn.commit()
            self._invalidate_user_cache(user_id)
            return changed

    def list_transactions(self, user_id: int, ticker: Optional[str] = None) -> List[Dict[str, Any]]:
        self._ensure_tables()
        normalized_ticker = self._normalize_ticker(ticker) if ticker else None

        with self._db_lock:
            cursor = self._cursor()
            if normalized_ticker:
                cursor.execute(
                    """
                    SELECT id, ticker, transaction_type, trade_date, quantity, price,
                           amount, fee, source, note, created_at
                    FROM user_asset_transactions
                    WHERE user_id = ? AND ticker = ?
                    ORDER BY trade_date DESC, id DESC
                    """,
                    (int(user_id), normalized_ticker),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, ticker, transaction_type, trade_date, quantity, price,
                           amount, fee, source, note, created_at
                    FROM user_asset_transactions
                    WHERE user_id = ?
                    ORDER BY trade_date DESC, id DESC
                    LIMIT 200
                    """,
                    (int(user_id),),
                )
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def _transaction_date(tx: Dict[str, Any]) -> Optional[dt.date]:
        trade_date = str(tx.get("trade_date") or "").strip()
        if not trade_date:
            return None
        try:
            return dt.date.fromisoformat(trade_date[:10])
        except ValueError:
            return None

    def _calculate_position_state(
        self,
        transactions: Iterable[Dict[str, Any]],
        as_of: Optional[dt.date] = None,
    ) -> Dict[str, float]:
        units = 0.0
        cost_total = 0.0

        for tx in transactions:
            trade_date = self._transaction_date(tx)
            if as_of is not None and trade_date is not None and trade_date > as_of:
                continue

            tx_type = str(tx.get("transaction_type") or "").upper()
            quantity = max(0.0, self._to_float(tx.get("quantity"), 0.0))
            price = max(0.0, self._to_float(tx.get("price"), 0.0))
            fee = max(0.0, self._to_float(tx.get("fee"), 0.0))
            amount = self._to_float(tx.get("amount"), quantity * price)

            if tx_type == "RESET":
                units = quantity
                cost_total = quantity * price
                continue

            if tx_type in {"BUY", "ADJUSTMENT_IN"}:
                units += quantity
                cost_total += amount + fee
                continue

            if tx_type in {"SELL", "ADJUSTMENT_OUT"} and units > 0:
                sell_qty = min(quantity, units)
                avg_cost = cost_total / units if units > 0 else 0.0
                cost_total = max(0.0, cost_total - avg_cost * sell_qty)
                units = max(0.0, units - sell_qty)

        if units <= 1e-10:
            units = 0.0
            cost_total = 0.0

        avg_cost = cost_total / units if units > 0 else 0.0
        return {
            "units": round(units, 6),
            "avg_cost": avg_cost,
            "invested_amount": cost_total,
        }

    def _load_position_states(self, user_id: int) -> Dict[str, Dict[str, float]]:
        self._ensure_tables()
        with self._db_lock:
            cursor = self._cursor()
            cursor.execute(
                """
                SELECT ticker, transaction_type, trade_date, quantity, price, amount, fee, id
                FROM user_asset_transactions
                WHERE user_id = ?
                ORDER BY ticker ASC, trade_date ASC, id ASC
                """,
                (int(user_id),),
            )
            grouped: Dict[str, List[Dict[str, Any]]] = {}
            for row in cursor.fetchall():
                item = dict(row)
                grouped.setdefault(str(item["ticker"]), []).append(item)

        return {ticker: self._calculate_position_state(items) for ticker, items in grouped.items()}

    @staticmethod
    def _latest_transaction_date(transactions: Iterable[Dict[str, Any]]) -> Optional[dt.date]:
        latest: Optional[dt.date] = None
        for tx in transactions:
            trade_date = UserAssetService._transaction_date(tx)
            if trade_date is None:
                continue
            if latest is None or trade_date > latest:
                latest = trade_date
        return latest

    def _calculate_period_net_flow(
        self,
        transactions: Iterable[Dict[str, Any]],
        start_date: dt.date,
        end_date: dt.date,
    ) -> float:
        net_flow = 0.0
        for tx in transactions:
            trade_date = self._transaction_date(tx)
            if trade_date is None or trade_date <= start_date or trade_date > end_date:
                continue

            tx_type = str(tx.get("transaction_type") or "").upper()
            quantity = max(0.0, self._to_float(tx.get("quantity"), 0.0))
            price = max(0.0, self._to_float(tx.get("price"), 0.0))
            fee = max(0.0, self._to_float(tx.get("fee"), 0.0))
            amount = self._to_float(tx.get("amount"), quantity * price)

            if tx_type in {"BUY", "ADJUSTMENT_IN"}:
                net_flow += amount + fee
            elif tx_type in {"SELL", "ADJUSTMENT_OUT"}:
                net_flow -= max(0.0, amount - fee)

        return net_flow

    @staticmethod
    def _reference_price(series: pd.Series, target_date: dt.date) -> Optional[float]:
        if series.empty:
            return None
        filtered = series[series.index <= pd.Timestamp(target_date)]
        if filtered.empty:
            return None
        return float(filtered.iloc[-1])

    @staticmethod
    def _price_on_date(series: pd.Series, target_date: dt.date) -> Optional[float]:
        if series.empty:
            return None
        normalized_index = series.index.normalize()
        exact_matches = series[normalized_index == pd.Timestamp(target_date)]
        if exact_matches.empty:
            return None
        return float(exact_matches.iloc[-1])

    def _calculate_period_changes(
        self,
        user_id: int,
        ticker: str,
        series: pd.Series,
        transactions: Iterable[Dict[str, Any]],
        units: float,
        latest_price: float,
        latest_date: Optional[dt.date] = None,
        flow_end_date: Optional[dt.date] = None,
    ) -> Dict[str, float]:
        if units <= 0 or latest_price <= 0:
            return {
                "day_change": 0.0,
                "week_change": 0.0,
                "month_change": 0.0,
                "year_change": 0.0,
                "day_change_pct": 0.0,
                "week_change_pct": 0.0,
                "month_change_pct": 0.0,
                "year_change_pct": 0.0,
            }

        resolved_latest_date = latest_date
        if resolved_latest_date is None and not series.empty:
            resolved_latest_date = series.index[-1].date()
        if resolved_latest_date is None:
            return {
                "day_change": 0.0,
                "week_change": 0.0,
                "month_change": 0.0,
                "year_change": 0.0,
                "day_change_pct": 0.0,
                "week_change_pct": 0.0,
                "month_change_pct": 0.0,
                "year_change_pct": 0.0,
            }

        resolved_flow_end_date = flow_end_date or resolved_latest_date
        if resolved_flow_end_date < resolved_latest_date:
            resolved_flow_end_date = resolved_latest_date

        current_market_value = units * latest_price
        periods = {
            "day": resolved_latest_date - dt.timedelta(days=1),
            "week": resolved_latest_date - dt.timedelta(days=7),
            "month": resolved_latest_date - dt.timedelta(days=30),
            "year": resolved_latest_date - dt.timedelta(days=365),
        }
        result: Dict[str, float] = {}

        for name, ref_date in periods.items():
            net_flow = self._calculate_period_net_flow(transactions, ref_date, resolved_flow_end_date)
            ref_market_value = self._snapshot_change_value(user_id, ticker, ref_date)
            if ref_market_value is None or ref_market_value <= 0:
                ref_state = self._calculate_position_state(transactions, as_of=ref_date)
                ref_units = ref_state["units"]
                if ref_units <= 0 and abs(net_flow) <= 1e-10:
                    ref_units = units

                if ref_units > 0:
                    ref_price = self._reference_price(series, ref_date)
                    if ref_price is None or ref_price <= 0:
                        result[f"{name}_change"] = 0.0
                        result[f"{name}_change_pct"] = 0.0
                        continue
                    ref_market_value = ref_units * ref_price
                elif abs(net_flow) <= 1e-10:
                    ref_market_value = current_market_value
                else:
                    ref_market_value = 0.0

            change_value = current_market_value - ref_market_value - net_flow
            result[f"{name}_change"] = change_value
            result[f"{name}_change_pct"] = ((change_value / ref_market_value) * 100.0) if ref_market_value > 0 else 0.0

        return result

    def _snapshot_change_value(
        self,
        user_id: int,
        ticker: str,
        target_date: dt.date,
    ) -> Optional[float]:
        with self._db_lock:
            cursor = self._cursor()
            cursor.execute(
                """
                SELECT market_value
                FROM user_asset_snapshots
                WHERE user_id = ? AND ticker = ? AND snapshot_date <= ?
                ORDER BY snapshot_date DESC
                LIMIT 1
                """,
                (int(user_id), ticker, target_date.isoformat()),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._to_float(row["market_value"], 0.0)

    def _compute_due_dates(
        self,
        rule: Dict[str, Any],
        as_of: dt.date,
    ) -> List[dt.date]:
        if not rule.get("enabled"):
            return []

        start_date = self._date_or_today(rule.get("start_date"))
        end_value = rule.get("end_date")
        end_date = dt.date.fromisoformat(end_value) if end_value else as_of
        if end_date > as_of:
            end_date = as_of

        last_run_value = rule.get("last_run_date")
        if last_run_value:
            candidate_start = dt.date.fromisoformat(last_run_value) + dt.timedelta(days=1)
        else:
            candidate_start = start_date

        if candidate_start > end_date:
            return []

        frequency = str(rule.get("frequency") or "weekly").lower()
        due_dates: List[dt.date] = []

        if frequency == "monthly":
            monthday = int(rule.get("monthday") or 1)
            cursor = dt.date(candidate_start.year, candidate_start.month, 1)
            while cursor <= end_date and len(due_dates) < 120:
                last_dom = calendar.monthrange(cursor.year, cursor.month)[1]
                scheduled = dt.date(cursor.year, cursor.month, min(max(monthday, 1), last_dom))
                if candidate_start <= scheduled <= end_date:
                    due_dates.append(scheduled)
                if cursor.month == 12:
                    cursor = dt.date(cursor.year + 1, 1, 1)
                else:
                    cursor = dt.date(cursor.year, cursor.month + 1, 1)
        else:
            weekday = int(rule.get("weekday") if rule.get("weekday") is not None else 3)
            cursor = candidate_start
            while cursor <= end_date and len(due_dates) < 120:
                if cursor.weekday() == weekday:
                    due_dates.append(cursor)
                cursor += dt.timedelta(days=1)

        return due_dates

    @staticmethod
    def _next_trading_day(
        trade_date: dt.date,
        market: Market,
        calendar_service,
    ) -> dt.date:
        next_date = trade_date + dt.timedelta(days=1)
        while not calendar_service.is_trading_day(next_date, market):
            next_date += dt.timedelta(days=1)
        return next_date

    def _requires_delayed_fund_confirmation(self, rule: Dict[str, Any]) -> bool:
        asset_type = self._resolve_asset_type(
            str(rule.get("ticker") or ""),
            asset_name=rule.get("asset_name"),
            asset_type=rule.get("asset_type"),
        )
        return self._should_prefer_fund_nav(
            {
                "ticker": str(rule.get("ticker") or ""),
                "asset_name": rule.get("asset_name"),
                "asset_type": asset_type,
            }
        )

    def _list_active_dca_rules(self, user_id: int) -> List[Dict[str, Any]]:
        with self._db_lock:
            cursor = self._cursor()
            cursor.execute(
                """
                SELECT h.ticker, h.asset_name, h.asset_type,
                       r.enabled, r.frequency, r.weekday, r.monthday, r.amount,
                       r.start_date, r.end_date, r.shift_to_next_trading_day, r.last_run_date,
                       (
                           SELECT MAX(t.trade_date)
                           FROM user_asset_transactions t
                           WHERE t.user_id = h.user_id
                             AND t.ticker = h.ticker
                             AND t.transaction_type = 'RESET'
                       ) AS latest_reset_date
                FROM user_asset_holdings h
                JOIN user_asset_dca_rules r
                  ON h.user_id = r.user_id AND h.ticker = r.ticker
                WHERE h.user_id = ? AND r.enabled = 1 AND r.amount > 0
                ORDER BY h.ticker
                """,
                (int(user_id),),
            )
            return [dict(row) for row in cursor.fetchall()]

    def _load_dca_price_series(
        self,
        ticker: str,
        start_date: dt.date,
        as_of: dt.date,
        price_cache: Dict[str, pd.Series],
        *,
        refresh_stale: bool,
    ) -> pd.Series:
        if ticker in price_cache:
            return price_cache[ticker]

        lookback_days = max((as_of - start_date).days + 30, 120)
        try:
            price_df = load_price_data(
                [ticker],
                days=lookback_days,
                refresh_stale=refresh_stale,
            )
            series = price_df[ticker].dropna() if ticker in price_df.columns else pd.Series(dtype=float)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load price data for DCA %s: %s", ticker, exc)
            series = pd.Series(dtype=float)

        price_cache[ticker] = series
        return series

    def _resolve_dca_occurrences(
        self,
        rule: Dict[str, Any],
        as_of: dt.date,
        calendar_service,
    ) -> List[Dict[str, dt.date]]:
        ticker = str(rule["ticker"])
        market = self._resolve_market(ticker)
        due_dates = self._compute_due_dates(rule, as_of)
        latest_reset = rule.get("latest_reset_date")
        if latest_reset:
            reset_date = dt.date.fromisoformat(str(latest_reset))
            due_dates = [item for item in due_dates if item >= reset_date]
        if not due_dates:
            return []

        delayed_confirmation = self._requires_delayed_fund_confirmation(rule)
        occurrences: List[Dict[str, dt.date]] = []
        for due_date in due_dates:
            effective_date = due_date
            if rule.get("shift_to_next_trading_day"):
                while effective_date <= as_of and not calendar_service.is_trading_day(effective_date, market):
                    effective_date += dt.timedelta(days=1)
            if effective_date > as_of:
                continue

            confirmation_date = effective_date
            if delayed_confirmation:
                confirmation_date = self._next_trading_day(effective_date, market, calendar_service)

            occurrences.append(
                {
                    "effective_date": effective_date,
                    "confirmation_date": confirmation_date,
                }
            )

        return occurrences

    def _build_pending_dca_map(
        self,
        user_id: int,
        rules: Iterable[Dict[str, Any]],
        as_of: dt.date,
    ) -> Dict[str, Dict[str, Any]]:
        pending_map: Dict[str, Dict[str, Any]] = {}
        price_cache: Dict[str, pd.Series] = {}
        calendar_service = get_trading_calendar()

        with self._db_lock:
            cursor = self._cursor()
            for rule in rules:
                if not self._requires_delayed_fund_confirmation(rule):
                    continue

                ticker = str(rule["ticker"])
                start_date = self._date_or_today(rule.get("start_date"))
                series = self._load_dca_price_series(
                    ticker,
                    start_date,
                    as_of,
                    price_cache,
                    refresh_stale=False,
                )

                for occurrence in self._resolve_dca_occurrences(rule, as_of, calendar_service):
                    effective_date = occurrence["effective_date"]
                    confirmation_date = occurrence["confirmation_date"]
                    if confirmation_date <= as_of:
                        continue

                    cursor.execute(
                        """
                        SELECT 1
                        FROM user_asset_transactions
                        WHERE user_id = ? AND ticker = ? AND source = 'dca' AND trade_date = ?
                        LIMIT 1
                        """,
                        (int(user_id), ticker, confirmation_date.isoformat()),
                    )
                    if cursor.fetchone():
                        continue

                    amount = max(0.0, self._to_float(rule.get("amount"), 0.0))
                    estimated_price = self._price_on_date(series, effective_date)
                    estimated_units = (amount / estimated_price) if estimated_price and estimated_price > 0 else None
                    pending_map[ticker] = {
                        "status": "pending_confirmation",
                        "amount": round(amount, 2),
                        "execution_date": effective_date.isoformat(),
                        "confirmation_date": confirmation_date.isoformat(),
                        "price_basis_date": effective_date.isoformat(),
                        "estimated_price": round(estimated_price, 6) if estimated_price and estimated_price > 0 else None,
                        "estimated_units": round(estimated_units, 6) if estimated_units and estimated_units > 0 else None,
                    }
                    break

        return pending_map

    def reconcile_due_dca(self, user_id: int, as_of: Optional[dt.date] = None) -> Dict[str, Any]:
        self._ensure_tables()
        today = as_of or dt.date.today()
        rules = self._list_active_dca_rules(user_id)

        created = 0
        price_cache: Dict[str, pd.Series] = {}
        calendar_service = get_trading_calendar()

        with self._db_lock:
            cursor = self._cursor()
            for rule in rules:
                ticker = str(rule["ticker"])
                start_date = self._date_or_today(rule.get("start_date"))
                series = self._load_dca_price_series(
                    ticker,
                    start_date,
                    today,
                    price_cache,
                    refresh_stale=True,
                )
                executed_dates: List[str] = []
                delayed_confirmation = self._requires_delayed_fund_confirmation(rule)
                for occurrence in self._resolve_dca_occurrences(rule, today, calendar_service):
                    effective_date = occurrence["effective_date"]
                    confirmation_date = occurrence["confirmation_date"]
                    if confirmation_date > today:
                        continue

                    cursor.execute(
                        """
                        SELECT 1
                        FROM user_asset_transactions
                        WHERE user_id = ? AND ticker = ? AND source = 'dca' AND trade_date = ?
                        LIMIT 1
                        """,
                        (int(user_id), ticker, confirmation_date.isoformat()),
                    )
                    if cursor.fetchone():
                        executed_dates.append(confirmation_date.isoformat())
                        continue

                    price = (
                        self._price_on_date(series, effective_date)
                        if delayed_confirmation
                        else self._reference_price(series, effective_date)
                    )
                    if price is None or price <= 0:
                        logger.warning("Skip DCA for %s on %s because price is unavailable", ticker, effective_date)
                        continue

                    amount = max(0.0, self._to_float(rule.get("amount"), 0.0))
                    quantity = round(amount / price, 6)
                    if quantity <= 0:
                        continue

                    self._insert_transaction(
                        cursor,
                        user_id,
                        ticker,
                        transaction_type="BUY",
                        trade_date=confirmation_date.isoformat(),
                        quantity=quantity,
                        price=price,
                        amount=amount,
                        source="dca",
                        note=(
                            f"Auto DCA {amount:.2f} confirmed {confirmation_date.isoformat()}"
                            if confirmation_date != effective_date
                            else f"Auto DCA {amount:.2f}"
                        ),
                    )
                    executed_dates.append(confirmation_date.isoformat())
                    created += 1

                if executed_dates:
                    cursor.execute(
                        """
                        UPDATE user_asset_dca_rules
                        SET last_run_date = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND ticker = ?
                        """,
                        (max(executed_dates), int(user_id), ticker),
                    )

            self.db.conn.commit()

        if created > 0:
            self._invalidate_user_cache(user_id)
        return {"created": created, "rules_checked": len(rules), "as_of": today.isoformat()}

    def _persist_snapshots(self, user_id: int, assets: List[Dict[str, Any]], summary: Dict[str, Any]) -> None:
        today = dt.date.today().isoformat()
        with self._db_lock:
            cursor = self._cursor()
            for asset in assets:
                cursor.execute(
                    """
                    INSERT INTO user_asset_snapshots
                    (
                        user_id, snapshot_date, ticker, current_price, units,
                        market_value, invested_amount, total_return, total_return_pct
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, snapshot_date, ticker) DO UPDATE SET
                        current_price = excluded.current_price,
                        units = excluded.units,
                        market_value = excluded.market_value,
                        invested_amount = excluded.invested_amount,
                        total_return = excluded.total_return,
                        total_return_pct = excluded.total_return_pct
                    """,
                    (
                        int(user_id),
                        today,
                        asset["ticker"],
                        self._to_float(asset.get("current_price"), 0.0),
                        self._to_float(asset.get("units"), 0.0),
                        self._to_float(asset.get("market_value"), 0.0),
                        self._to_float(asset.get("invested_amount"), 0.0),
                        self._to_float(asset.get("total_return"), 0.0),
                        self._to_float(asset.get("total_return_pct"), 0.0),
                    ),
                )

            cursor.execute(
                """
                INSERT INTO user_asset_snapshots
                (
                    user_id, snapshot_date, ticker, current_price, units,
                    market_value, invested_amount, total_return, total_return_pct
                )
                VALUES (?, ?, '__TOTAL__', 0, 0, ?, ?, ?, ?)
                ON CONFLICT(user_id, snapshot_date, ticker) DO UPDATE SET
                    market_value = excluded.market_value,
                    invested_amount = excluded.invested_amount,
                    total_return = excluded.total_return,
                    total_return_pct = excluded.total_return_pct
                """,
                (
                    int(user_id),
                    today,
                    self._to_float(summary.get("total_market_value"), 0.0),
                    self._to_float(summary.get("total_invested_amount"), 0.0),
                    self._to_float(summary.get("total_return"), 0.0),
                    self._to_float(summary.get("total_return_pct"), 0.0),
                ),
            )
            self.db.conn.commit()

    def get_overview(
        self,
        user_id: int,
        sync_dca: bool = True,
        *,
        force_refresh: bool = False,
        force_snapshot: bool = False,
    ) -> Dict[str, Any]:
        self._ensure_tables()
        if sync_dca:
            reconcile_result = self.reconcile_due_dca(user_id)
            if reconcile_result.get("created"):
                force_refresh = True

        if not force_refresh:
            cached = self._get_cached_overview(user_id)
            if cached is not None:
                return cached

        with self._db_lock:
            cursor = self._cursor()
            cursor.execute(
                """
                SELECT ticker, asset_name, asset_category, asset_style, asset_type, notes, updated_at
                FROM user_asset_holdings
                WHERE user_id = ?
                ORDER BY created_at ASC, ticker ASC
                """,
                (int(user_id),),
            )
            holdings = [dict(row) for row in cursor.fetchall()]

            cursor.execute(
                """
                SELECT ticker, transaction_type, trade_date, quantity, price, amount, fee, id
                FROM user_asset_transactions
                WHERE user_id = ?
                ORDER BY ticker ASC, trade_date ASC, id ASC
                """,
                (int(user_id),),
            )
            grouped_transactions: Dict[str, List[Dict[str, Any]]] = {}
            for row in cursor.fetchall():
                item = dict(row)
                grouped_transactions.setdefault(str(item["ticker"]), []).append(item)

            cursor.execute(
                """
                SELECT ticker, enabled, frequency, weekday, monthday, amount, start_date,
                       end_date, shift_to_next_trading_day, last_run_date
                FROM user_asset_dca_rules
                WHERE user_id = ?
                """,
                (int(user_id),),
            )
            dca_rules = {str(row["ticker"]): dict(row) for row in cursor.fetchall()}

        normalized_holdings: List[Dict[str, Any]] = []
        for holding in holdings:
            effective_holding = dict(holding)
            effective_holding["asset_type"] = self._resolve_asset_type(
                str(holding.get("ticker") or ""),
                asset_name=holding.get("asset_name"),
                asset_type=holding.get("asset_type"),
            )
            normalized_holdings.append(effective_holding)

        pending_dca_map = self._build_pending_dca_map(
            user_id,
            self._list_active_dca_rules(user_id),
            dt.date.today(),
        )

        tickers = [str(item["ticker"]) for item in normalized_holdings]
        price_df = pd.DataFrame()
        if tickers:
            try:
                price_df = load_price_data(
                    tickers,
                    days=VALUATION_HISTORY_DAYS,
                    refresh_stale=False,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to load valuation prices: %s", exc)

        fund_nav_df = pd.DataFrame()
        fund_nav_tickers = [str(item["ticker"]) for item in normalized_holdings if self._should_prefer_fund_nav(item)]
        if fund_nav_tickers:
            try:
                fund_nav_df = load_price_data_akshare(fund_nav_tickers, days=FUND_NAV_HISTORY_DAYS)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to load fund NAV prices: %s", exc)

        realtime_quotes: Dict[str, Dict[str, Any]] = {}
        realtime_candidates = [str(item["ticker"]) for item in normalized_holdings if self._supports_realtime_quote(item)]
        if realtime_candidates:
            try:
                realtime_quotes = load_cn_realtime_quotes_sina(realtime_candidates)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to load realtime quotes: %s", exc)

        assets: List[Dict[str, Any]] = []
        summary = {
            "asset_count": len(holdings),
            "total_market_value": 0.0,
            "total_invested_amount": 0.0,
            "total_return": 0.0,
            "total_return_pct": 0.0,
            "day_change": 0.0,
            "week_change": 0.0,
            "month_change": 0.0,
            "year_change": 0.0,
        }
        for holding in normalized_holdings:
            ticker = str(holding["ticker"])
            transactions = grouped_transactions.get(ticker, [])
            state = self._calculate_position_state(transactions)
            if ticker in fund_nav_df.columns:
                series = fund_nav_df[ticker].dropna()
            else:
                series = price_df[ticker].dropna() if ticker in price_df.columns else pd.Series(dtype=float)
            valuation_series = series.copy()
            latest_price = float(series.iloc[-1]) if not series.empty else state["avg_cost"]
            latest_price_date = series.index[-1].date().isoformat() if not series.empty else None

            realtime_quote = realtime_quotes.get(ticker)
            if realtime_quote:
                quote_price = self._to_float(realtime_quote.get("price"), latest_price)
                quote_date = str(realtime_quote.get("trade_date") or "").strip() or None
                if quote_price > 0 and quote_date:
                    latest_price = quote_price
                    latest_price_date = quote_date
                    quote_timestamp = realtime_quote.get("timestamp")
                    if quote_timestamp is not None:
                        valuation_series = pd.concat(
                            [
                                valuation_series,
                                pd.Series([quote_price], index=pd.DatetimeIndex([quote_timestamp])),
                            ]
                        )
                    else:
                        valuation_series = pd.concat(
                            [
                                valuation_series,
                                pd.Series([quote_price], index=pd.DatetimeIndex([pd.Timestamp(quote_date)])),
                            ]
                        )
                    valuation_series = valuation_series[~valuation_series.index.duplicated(keep="last")].sort_index()

            market_value = state["units"] * latest_price
            total_return = market_value - state["invested_amount"]
            total_return_pct = (
                (total_return / state["invested_amount"]) * 100.0
                if state["invested_amount"] > 0
                else 0.0
            )
            valuation_date = None
            if latest_price_date:
                try:
                    valuation_date = dt.date.fromisoformat(str(latest_price_date)[:10])
                except ValueError:
                    valuation_date = None
            latest_trade_date = self._latest_transaction_date(transactions)
            period_changes = self._calculate_period_changes(
                user_id,
                ticker,
                valuation_series,
                transactions,
                state["units"],
                latest_price,
                valuation_date,
                latest_trade_date,
            )

            asset_payload = {
                "ticker": ticker,
                "asset_name": holding.get("asset_name"),
                "asset_category": holding.get("asset_category"),
                "asset_style": holding.get("asset_style"),
                "asset_type": holding.get("asset_type"),
                "notes": holding.get("notes"),
                "units": state["units"],
                "avg_cost": round(state["avg_cost"], 6),
                "invested_amount": round(state["invested_amount"], 2),
                "current_price": round(latest_price, 6),
                "last_price_date": latest_price_date,
                "market_value": round(market_value, 2),
                "total_return": round(total_return, 2),
                "total_return_pct": round(total_return_pct, 4),
                "day_change": round(period_changes["day_change"], 2),
                "week_change": round(period_changes["week_change"], 2),
                "month_change": round(period_changes["month_change"], 2),
                "year_change": round(period_changes["year_change"], 2),
                "day_change_pct": round(period_changes["day_change_pct"], 4),
                "week_change_pct": round(period_changes["week_change_pct"], 4),
                "month_change_pct": round(period_changes["month_change_pct"], 4),
                "year_change_pct": round(period_changes["year_change_pct"], 4),
                "dca_rule": dca_rules.get(ticker),
                "pending_dca": pending_dca_map.get(ticker),
                "updated_at": holding.get("updated_at"),
            }
            assets.append(asset_payload)

            summary["total_market_value"] += market_value
            summary["total_invested_amount"] += state["invested_amount"]
            summary["total_return"] += total_return
            summary["day_change"] += period_changes["day_change"]
            summary["week_change"] += period_changes["week_change"]
            summary["month_change"] += period_changes["month_change"]
            summary["year_change"] += period_changes["year_change"]

        invested_total = summary["total_invested_amount"]
        summary["total_return_pct"] = (
            (summary["total_return"] / invested_total) * 100.0 if invested_total > 0 else 0.0
        )
        summary["total_market_value"] = round(summary["total_market_value"], 2)
        summary["total_invested_amount"] = round(summary["total_invested_amount"], 2)
        summary["total_return"] = round(summary["total_return"], 2)
        summary["total_return_pct"] = round(summary["total_return_pct"], 4)
        summary["day_change"] = round(summary["day_change"], 2)
        summary["week_change"] = round(summary["week_change"], 2)
        summary["month_change"] = round(summary["month_change"], 2)
        summary["year_change"] = round(summary["year_change"], 2)
        summary["updated_at"] = dt.datetime.now().isoformat(timespec="seconds")

        if self._should_persist_snapshots(user_id, assets, summary, force=force_snapshot):
            self._persist_snapshots(user_id, assets, summary)

        payload = {"summary": summary, "assets": assets}
        self._store_cached_overview(user_id, payload)
        return payload

    def seed_assets_if_empty(self, user_id: int, assets: List[Dict[str, Any]]) -> Dict[str, Any]:
        self._ensure_tables()

        with self._db_lock:
            cursor = self._cursor()
            cursor.execute(
                "SELECT COUNT(1) AS total FROM user_asset_holdings WHERE user_id = ?",
                (int(user_id),),
            )
            row = cursor.fetchone()
            existing_total = int(row["total"]) if row else 0

        if existing_total > 0:
            return {"seeded": False, "count": existing_total}

        for item in assets:
            self.upsert_asset(user_id, dict(item))

        return {"seeded": True, "count": len(assets)}

    def run_daily_sync_for_all_users(self, as_of: Optional[dt.date] = None) -> Dict[str, Any]:
        self._ensure_tables()
        with self._db_lock:
            cursor = self._cursor()
            cursor.execute(
                """
                SELECT DISTINCT user_id
                FROM user_asset_holdings
                ORDER BY user_id
                """
            )
            user_ids = [int(row["user_id"]) for row in cursor.fetchall()]

        synced = 0
        for user_id in user_ids:
            self.reconcile_due_dca(user_id, as_of=as_of)
            self._invalidate_user_cache(user_id)
            self.get_overview(user_id, sync_dca=False, force_refresh=True, force_snapshot=True)
            synced += 1

        return {"users_synced": synced, "as_of": (as_of or dt.date.today()).isoformat()}


_service: Optional[UserAssetService] = None


def get_user_asset_service() -> UserAssetService:
    global _service
    if _service is None:
        _service = UserAssetService()
    return _service
