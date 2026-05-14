"""Standalone personal asset daily report for agent runners.

This script intentionally does not import the dashboard ``core`` package.  It
keeps the small subset needed by OpenClaw/Hermes-style agents in one file:

- a compact SQLite ledger for holdings, transactions, DCA rules, price cache,
  and snapshots;
- DCA reconciliation with delayed confirmation for OTC funds;
- valuation rules that avoid reading OTC funds as stocks;
- Markdown/JSON output for direct notification forwarding.

Typical first-time setup:

    python scripts/daily_asset_report.py --import-dashboard-db data/quant.db --username admin --replace

The default runtime files live next to this script:

- scripts/personal_assets_agent.db
- scripts/personal_assets.json, if present

Daily run after that:

    python scripts/daily_asset_report.py
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import html
import json
import logging
import math
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence, Tuple


logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
VALUATION_HISTORY_DAYS = 400
FUND_NAV_HISTORY_DAYS = 400
DEFAULT_STORE = SCRIPT_DIR / "personal_assets_agent.db"
DEFAULT_CONFIG = SCRIPT_DIR / "personal_assets.json"


@dataclass(frozen=True)
class PricePoint:
    date: dt.date
    price: float
    source: str


@dataclass(frozen=True)
class ReportTarget:
    username: str


class PriceProvider(Protocol):
    def fetch_series(
        self,
        ticker: str,
        *,
        asset_name: Optional[str],
        asset_type: str,
        days: int,
    ) -> List[PricePoint]:
        ...


def to_float(value: Any, fallback: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    if math.isnan(parsed) or math.isinf(parsed):
        return fallback
    return parsed


def to_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def parse_date(value: Any, fallback: Optional[dt.date] = None) -> Optional[dt.date]:
    if isinstance(value, dt.date):
        return value
    text = str(value or "").strip()
    if not text:
        return fallback
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return fallback


def today_date() -> dt.date:
    return dt.date.today()


def normalize_ticker(ticker: str) -> str:
    return str(ticker or "").strip().upper()


def normalize_asset_type(value: Any) -> Optional[str]:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    aliases = {
        "fund": "fund",
        "mutual_fund": "fund",
        "otc_fund": "fund",
        "场外基金": "fund",
        "基金": "fund",
        "etf": "etf",
        "lof": "etf",
        "exchange_fund": "etf",
        "场内基金": "etf",
        "场内etf": "etf",
        "stock": "stock",
        "equity": "stock",
        "股票": "stock",
        "gold": "gold",
        "黄金": "gold",
        "other": "other",
        "其他": "other",
    }
    return aliases.get(raw)


def looks_like_linked_or_otc_fund(asset_name: Optional[str]) -> bool:
    name = str(asset_name or "")
    if not name:
        return False
    keywords = (
        "基金",
        "联接",
        "连接",
        "场外",
        "股票",
        "混合",
        "指数",
        "量化",
        "多因子",
        "增强",
        "债",
        "债券",
        "货币",
        "现金",
        "滚动持有",
        "中短债",
        "理财",
    )
    return any(keyword in name for keyword in keywords)


def is_exchange_traded_asset(ticker: str, asset_name: Optional[str]) -> bool:
    code = normalize_ticker(ticker)
    name = str(asset_name or "").upper()
    if not (code.isdigit() and len(code) == 6):
        return False
    if "联接" in str(asset_name or "") or "连接" in str(asset_name or "") or "场外" in str(asset_name or ""):
        return False
    if code.startswith(("15", "50", "51", "56", "58")):
        return True
    return "ETF" in name or "LOF" in name


def resolve_asset_type(
    ticker: str,
    *,
    asset_name: Optional[str] = None,
    asset_type: Optional[str] = None,
) -> str:
    code = normalize_ticker(ticker)
    normalized = normalize_asset_type(asset_type)
    if is_exchange_traded_asset(code, asset_name):
        return "etf"
    if looks_like_linked_or_otc_fund(asset_name):
        return "fund"
    if normalized:
        return normalized
    if code.endswith(".HK") or code.endswith(".US") or code.isalpha():
        return "stock"
    return "other"


def supports_realtime_quote(ticker: str, asset_name: Optional[str], asset_type: str) -> bool:
    code = normalize_ticker(ticker)
    if not (code.isdigit() and len(code) == 6):
        return False
    if "联接" in str(asset_name or "") or "连接" in str(asset_name or ""):
        return False
    if code.startswith(("15", "50", "51", "56", "58")):
        return True
    return asset_type in {"stock", "etf"}


def should_prefer_fund_nav(ticker: str, asset_name: Optional[str], asset_type: str) -> bool:
    return asset_type == "fund" and not supports_realtime_quote(ticker, asset_name, asset_type)


def is_business_day(value: dt.date) -> bool:
    return value.weekday() < 5


def next_business_day(value: dt.date) -> dt.date:
    cursor = value + dt.timedelta(days=1)
    while not is_business_day(cursor):
        cursor += dt.timedelta(days=1)
    return cursor


def clean_html_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value)
    return html.unescape(text).replace("\xa0", " ").strip()


def http_get_text(url: str, *, encoding: Optional[str] = None, timeout: int = 15) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.sina.com.cn",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        resolved_encoding = encoding or response.headers.get_content_charset() or "utf-8"
    try:
        return raw.decode(resolved_encoding)
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def parse_fund_nav_history(payload: str) -> List[PricePoint]:
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html.unescape(payload), flags=re.S | re.I)
    points: List[PricePoint] = []
    for row in rows:
        cells = [clean_html_text(item) for item in re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S | re.I)]
        if len(cells) < 2:
            continue
        price_date = parse_date(cells[0])
        price = to_float(cells[1], 0.0)
        if price_date and price > 0:
            points.append(PricePoint(price_date, price, "eastmoney_fund_nav"))
    return dedupe_price_points(points)


def eastmoney_stock_secids(ticker: str) -> List[str]:
    code = normalize_ticker(ticker)
    if code.endswith(".SZ"):
        return [f"0.{code[:-3]}"]
    if code.endswith(".SH") or code.endswith(".SS"):
        return [f"1.{code[:-3]}"]
    if code.endswith(".HK"):
        return [f"116.{code[:-3].zfill(5)}", f"116.{code[:-3]}"]
    if code.isdigit() and len(code) == 6:
        if code.startswith(("5", "6", "9", "11", "12")):
            return [f"1.{code}", f"0.{code}"]
        return [f"0.{code}", f"1.{code}"]
    return []


def sina_symbol(ticker: str) -> Optional[str]:
    code = normalize_ticker(ticker)
    digits = "".join(ch for ch in code if ch.isdigit())
    if len(digits) != 6:
        return None
    prefix = "sh" if digits.startswith(("5", "6", "9", "11", "12")) else "sz"
    return f"{prefix}{digits}"


class HttpPriceProvider:
    """Small direct HTTP provider used by the standalone agent script."""

    def fetch_series(
        self,
        ticker: str,
        *,
        asset_name: Optional[str],
        asset_type: str,
        days: int,
    ) -> List[PricePoint]:
        resolved = resolve_asset_type(ticker, asset_name=asset_name, asset_type=asset_type)
        if should_prefer_fund_nav(ticker, asset_name, resolved):
            points = self.fetch_fund_nav(ticker, days=max(days, FUND_NAV_HISTORY_DAYS))
            return points

        if normalize_ticker(ticker).isdigit() and len(normalize_ticker(ticker)) == 6:
            points = self.fetch_eastmoney_kline(ticker, days=days)
            realtime = self.fetch_sina_realtime(ticker)
            if realtime:
                points.append(realtime)
            return dedupe_price_points(points)

        points = self.fetch_yahoo_chart(ticker, days=days)
        return points

    def fetch_fund_nav(self, ticker: str, *, days: int) -> List[PricePoint]:
        code = normalize_ticker(ticker).replace(".OF", "")
        if not (code.isdigit() and len(code) == 6):
            return []
        target_start = today_date() - dt.timedelta(days=max(days + 30, 120))
        per_page = 49
        max_pages = max(1, min(24, math.ceil(max(days * 1.8, per_page) / per_page)))
        points: List[PricePoint] = []
        for page in range(1, max_pages + 1):
            query = urllib.parse.urlencode(
                {
                    "type": "lsjz",
                    "code": code,
                    "page": str(page),
                    "per": str(per_page),
                    "sdate": "",
                    "edate": "",
                }
            )
            url = f"https://fundf10.eastmoney.com/F10DataApi.aspx?{query}"
            try:
                page_points = parse_fund_nav_history(http_get_text(url, timeout=20))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to fetch fund NAV for %s page %s: %s", ticker, page, exc)
                break
            if not page_points:
                break
            points.extend(page_points)
            if page_points[0].date <= target_start:
                break
        return dedupe_price_points(points)

    def fetch_eastmoney_kline(self, ticker: str, *, days: int) -> List[PricePoint]:
        end = dt.date.today().strftime("%Y%m%d")
        begin = (dt.date.today() - dt.timedelta(days=max(days * 3, 120))).strftime("%Y%m%d")
        for secid in eastmoney_stock_secids(ticker):
            query = urllib.parse.urlencode(
                {
                    "secid": secid,
                    "fields1": "f1,f2,f3,f4,f5,f6",
                    "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                    "klt": "101",
                    "fqt": "1",
                    "beg": begin,
                    "end": end,
                }
            )
            url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?{query}"
            try:
                payload = json.loads(http_get_text(url, timeout=20))
            except Exception as exc:  # noqa: BLE001
                logger.debug("Eastmoney kline failed for %s via %s: %s", ticker, secid, exc)
                continue
            data = payload.get("data") or {}
            klines = data.get("klines") or []
            points: List[PricePoint] = []
            for item in klines:
                parts = str(item).split(",")
                if len(parts) < 3:
                    continue
                price_date = parse_date(parts[0])
                close = to_float(parts[2], 0.0)
                if price_date and close > 0:
                    points.append(PricePoint(price_date, close, "eastmoney_kline"))
            if points:
                return dedupe_price_points(points)
        return []

    def fetch_sina_realtime(self, ticker: str) -> Optional[PricePoint]:
        symbol = sina_symbol(ticker)
        if not symbol:
            return None
        url = f"https://hq.sinajs.cn/list={symbol}"
        try:
            payload = http_get_text(url, encoding="gbk", timeout=12)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Sina realtime failed for %s: %s", ticker, exc)
            return None

        if '="' not in payload:
            return None
        fields = payload.split('="', 1)[1].rstrip('";\n').split(",")
        if len(fields) < 32:
            return None
        price = to_float(fields[3], 0.0)
        price_date = parse_date(fields[30])
        if price <= 0 or price_date is None:
            return None
        return PricePoint(price_date, price, "sina_realtime")

    def fetch_yahoo_chart(self, ticker: str, *, days: int) -> List[PricePoint]:
        symbol = normalize_ticker(ticker)
        if symbol.endswith(".US"):
            symbol = symbol[:-3]
        encoded = urllib.parse.quote(symbol, safe="")
        range_days = max(days + 30, 60)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?range={range_days}d&interval=1d"
        try:
            payload = json.loads(http_get_text(url, timeout=20))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to fetch Yahoo chart for %s: %s", ticker, exc)
            return []
        result = ((payload.get("chart") or {}).get("result") or [None])[0] or {}
        timestamps = result.get("timestamp") or []
        quote = (((result.get("indicators") or {}).get("quote") or [None])[0] or {})
        closes = quote.get("close") or []
        points: List[PricePoint] = []
        for stamp, close in zip(timestamps, closes):
            price = to_float(close, 0.0)
            if price <= 0:
                continue
            price_date = dt.datetime.fromtimestamp(int(stamp), tz=dt.timezone.utc).date()
            points.append(PricePoint(price_date, price, "yahoo_chart"))
        return dedupe_price_points(points)


def dedupe_price_points(points: Iterable[PricePoint]) -> List[PricePoint]:
    by_date: Dict[dt.date, PricePoint] = {}
    for point in points:
        if point.price > 0:
            by_date[point.date] = point
    return [by_date[key] for key in sorted(by_date)]


def reference_price(series: List[PricePoint], target_date: dt.date) -> Optional[float]:
    candidates = [point for point in series if point.date <= target_date and point.price > 0]
    return candidates[-1].price if candidates else None


def price_on_date(series: List[PricePoint], target_date: dt.date) -> Optional[float]:
    for point in reversed(series):
        if point.date == target_date and point.price > 0:
            return point.price
    return None


class AssetStore:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.ensure_tables()

    def close(self) -> None:
        self.conn.close()

    def ensure_tables(self) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS holdings (
                ticker TEXT PRIMARY KEY,
                asset_name TEXT,
                asset_category TEXT,
                asset_style TEXT,
                asset_type TEXT,
                notes TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                quantity REAL NOT NULL DEFAULT 0,
                price REAL NOT NULL DEFAULT 0,
                amount REAL,
                fee REAL NOT NULL DEFAULT 0,
                source TEXT DEFAULT 'manual',
                source_id TEXT UNIQUE,
                note TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS dca_rules (
                ticker TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 0,
                frequency TEXT NOT NULL DEFAULT 'weekly',
                weekday INTEGER,
                monthday INTEGER,
                amount REAL NOT NULL DEFAULT 0,
                start_date TEXT NOT NULL,
                end_date TEXT,
                shift_to_next_trading_day INTEGER NOT NULL DEFAULT 1,
                last_run_date TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                current_price REAL NOT NULL DEFAULT 0,
                units REAL NOT NULL DEFAULT 0,
                market_value REAL NOT NULL DEFAULT 0,
                invested_amount REAL NOT NULL DEFAULT 0,
                total_return REAL NOT NULL DEFAULT 0,
                total_return_pct REAL NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(snapshot_date, ticker)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS price_cache (
                ticker TEXT NOT NULL,
                price_date TEXT NOT NULL,
                price REAL NOT NULL,
                source TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(ticker, price_date)
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_ticker_date ON transactions(ticker, trade_date, id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_ticker_date ON snapshots(ticker, snapshot_date)")
        self.conn.commit()

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self.conn.commit()

    def get_meta(self, key: str, fallback: str = "") -> str:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row and row["value"] is not None else fallback

    def clear_portfolio(self) -> None:
        cursor = self.conn.cursor()
        for table_name in ("holdings", "transactions", "dca_rules", "snapshots"):
            cursor.execute(f"DELETE FROM {table_name}")
        self.conn.commit()

    def upsert_holding(self, item: Dict[str, Any]) -> None:
        ticker = normalize_ticker(str(item.get("ticker") or ""))
        if not ticker:
            raise ValueError("ticker is required")
        asset_name = item.get("asset_name") or item.get("name")
        asset_type = resolve_asset_type(ticker, asset_name=asset_name, asset_type=item.get("asset_type"))
        self.conn.execute(
            """
            INSERT INTO holdings(ticker, asset_name, asset_category, asset_style, asset_type, notes, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(ticker) DO UPDATE SET
                asset_name = excluded.asset_name,
                asset_category = excluded.asset_category,
                asset_style = excluded.asset_style,
                asset_type = excluded.asset_type,
                notes = excluded.notes,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                ticker,
                asset_name,
                item.get("asset_category"),
                item.get("asset_style"),
                asset_type,
                item.get("notes"),
            ),
        )
        self.conn.commit()

    def save_dca_rule(self, ticker: str, rule: Optional[Dict[str, Any]]) -> None:
        if rule is None:
            return
        normalized_ticker = normalize_ticker(ticker)
        enabled = 1 if bool(rule.get("enabled")) else 0
        frequency = str(rule.get("frequency") or "weekly").lower()
        if frequency not in {"weekly", "monthly"}:
            frequency = "weekly"
        self.conn.execute(
            """
            INSERT INTO dca_rules(
                ticker, enabled, frequency, weekday, monthday, amount, start_date,
                end_date, shift_to_next_trading_day, last_run_date, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(ticker) DO UPDATE SET
                enabled = excluded.enabled,
                frequency = excluded.frequency,
                weekday = excluded.weekday,
                monthday = excluded.monthday,
                amount = excluded.amount,
                start_date = excluded.start_date,
                end_date = excluded.end_date,
                shift_to_next_trading_day = excluded.shift_to_next_trading_day,
                last_run_date = COALESCE(dca_rules.last_run_date, excluded.last_run_date),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                normalized_ticker,
                enabled,
                frequency,
                rule.get("weekday"),
                rule.get("monthday"),
                max(0.0, to_float(rule.get("amount"), 0.0)),
                str(rule.get("start_date") or today_date().isoformat()),
                rule.get("end_date"),
                1 if rule.get("shift_to_next_trading_day", True) else 0,
                rule.get("last_run_date"),
            ),
        )
        self.conn.commit()

    def insert_transaction(self, ticker: str, item: Dict[str, Any], *, source_id: Optional[str] = None) -> None:
        normalized_ticker = normalize_ticker(ticker)
        quantity = max(0.0, to_float(item.get("quantity"), 0.0))
        price = max(0.0, to_float(item.get("price"), 0.0))
        amount = item.get("amount")
        if amount is None:
            amount = quantity * price
        payload = (
            normalized_ticker,
            str(item.get("transaction_type") or "BUY").upper(),
            str(item.get("trade_date") or today_date().isoformat())[:10],
            quantity,
            price,
            to_float(amount, quantity * price),
            max(0.0, to_float(item.get("fee"), 0.0)),
            str(item.get("source") or "manual"),
            source_id or item.get("source_id"),
            item.get("note"),
        )
        self.conn.execute(
            """
            INSERT INTO transactions(
                ticker, transaction_type, trade_date, quantity, price, amount,
                fee, source, source_id, note
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
                ticker = excluded.ticker,
                transaction_type = excluded.transaction_type,
                trade_date = excluded.trade_date,
                quantity = excluded.quantity,
                price = excluded.price,
                amount = excluded.amount,
                fee = excluded.fee,
                source = excluded.source,
                note = excluded.note
            """,
            payload,
        )
        self.conn.commit()

    def has_transactions(self, ticker: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM transactions WHERE ticker = ? LIMIT 1",
            (normalize_ticker(ticker),),
        ).fetchone()
        return row is not None

    def list_holdings(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT ticker, asset_name, asset_category, asset_style, asset_type, notes, updated_at
            FROM holdings
            ORDER BY ticker
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def list_transactions(self, ticker: Optional[str] = None) -> List[Dict[str, Any]]:
        if ticker:
            rows = self.conn.execute(
                """
                SELECT id, ticker, transaction_type, trade_date, quantity, price, amount, fee, source, note
                FROM transactions
                WHERE ticker = ?
                ORDER BY trade_date ASC, id ASC
                """,
                (normalize_ticker(ticker),),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT id, ticker, transaction_type, trade_date, quantity, price, amount, fee, source, note
                FROM transactions
                ORDER BY ticker ASC, trade_date ASC, id ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def active_dca_rules(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT h.ticker, h.asset_name, h.asset_type,
                   r.enabled, r.frequency, r.weekday, r.monthday, r.amount,
                   r.start_date, r.end_date, r.shift_to_next_trading_day, r.last_run_date,
                   (
                       SELECT MAX(t.trade_date)
                       FROM transactions t
                       WHERE t.ticker = h.ticker AND t.transaction_type = 'RESET'
                   ) AS latest_reset_date
            FROM holdings h
            JOIN dca_rules r ON h.ticker = r.ticker
            WHERE r.enabled = 1 AND r.amount > 0
            ORDER BY h.ticker
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def update_dca_last_run(self, ticker: str, last_run_date: dt.date) -> None:
        self.conn.execute(
            "UPDATE dca_rules SET last_run_date = ?, updated_at = CURRENT_TIMESTAMP WHERE ticker = ?",
            (last_run_date.isoformat(), normalize_ticker(ticker)),
        )
        self.conn.commit()

    def save_price_points(self, ticker: str, points: Iterable[PricePoint]) -> None:
        rows = [
            (normalize_ticker(ticker), point.date.isoformat(), point.price, point.source)
            for point in points
            if point.price > 0
        ]
        if not rows:
            return
        self.conn.executemany(
            """
            INSERT INTO price_cache(ticker, price_date, price, source, updated_at)
            VALUES(?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(ticker, price_date) DO UPDATE SET
                price = excluded.price,
                source = excluded.source,
                updated_at = CURRENT_TIMESTAMP
            """,
            rows,
        )
        self.conn.commit()

    def load_price_points(self, ticker: str, since: Optional[dt.date] = None) -> List[PricePoint]:
        params: List[Any] = [normalize_ticker(ticker)]
        query = "SELECT price_date, price, source FROM price_cache WHERE ticker = ?"
        if since:
            query += " AND price_date >= ?"
            params.append(since.isoformat())
        query += " ORDER BY price_date ASC"
        rows = self.conn.execute(query, params).fetchall()
        return [
            PricePoint(parse_date(row["price_date"]) or today_date(), to_float(row["price"]), str(row["source"] or "cache"))
            for row in rows
            if to_float(row["price"]) > 0
        ]

    def snapshot_value(self, ticker: str, target_date: dt.date) -> Optional[float]:
        row = self.conn.execute(
            """
            SELECT market_value
            FROM snapshots
            WHERE ticker = ? AND snapshot_date <= ?
            ORDER BY snapshot_date DESC
            LIMIT 1
            """,
            (normalize_ticker(ticker), target_date.isoformat()),
        ).fetchone()
        if row is None:
            return None
        return to_float(row["market_value"], 0.0)

    def persist_snapshots(self, assets: List[Dict[str, Any]], summary: Dict[str, Any], snapshot_date: dt.date) -> None:
        rows = [
            (
                snapshot_date.isoformat(),
                asset["ticker"],
                to_float(asset.get("current_price")),
                to_float(asset.get("units")),
                to_float(asset.get("market_value")),
                to_float(asset.get("invested_amount")),
                to_float(asset.get("total_return")),
                to_float(asset.get("total_return_pct")),
            )
            for asset in assets
        ]
        rows.append(
            (
                snapshot_date.isoformat(),
                "__TOTAL__",
                0.0,
                0.0,
                to_float(summary.get("total_market_value")),
                to_float(summary.get("total_invested_amount")),
                to_float(summary.get("total_return")),
                to_float(summary.get("total_return_pct")),
            )
        )
        self.conn.executemany(
            """
            INSERT INTO snapshots(
                snapshot_date, ticker, current_price, units, market_value,
                invested_amount, total_return, total_return_pct
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(snapshot_date, ticker) DO UPDATE SET
                current_price = excluded.current_price,
                units = excluded.units,
                market_value = excluded.market_value,
                invested_amount = excluded.invested_amount,
                total_return = excluded.total_return,
                total_return_pct = excluded.total_return_pct
            """,
            rows,
        )
        self.conn.commit()

    def upsert_snapshot_rows(self, rows: Iterable[Dict[str, Any]]) -> None:
        payload = []
        for row in rows:
            snapshot_date = parse_date(row.get("snapshot_date"))
            ticker = normalize_ticker(str(row.get("ticker") or ""))
            if snapshot_date is None or not ticker:
                continue
            payload.append(
                (
                    snapshot_date.isoformat(),
                    ticker,
                    to_float(row.get("current_price"), 0.0),
                    to_float(row.get("units"), 0.0),
                    to_float(row.get("market_value"), 0.0),
                    to_float(row.get("invested_amount"), 0.0),
                    to_float(row.get("total_return"), 0.0),
                    to_float(row.get("total_return_pct"), 0.0),
                    row.get("created_at"),
                )
            )
        if not payload:
            return
        self.conn.executemany(
            """
            INSERT INTO snapshots(
                snapshot_date, ticker, current_price, units, market_value,
                invested_amount, total_return, total_return_pct, created_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
            ON CONFLICT(snapshot_date, ticker) DO UPDATE SET
                current_price = excluded.current_price,
                units = excluded.units,
                market_value = excluded.market_value,
                invested_amount = excluded.invested_amount,
                total_return = excluded.total_return,
                total_return_pct = excluded.total_return_pct,
                created_at = excluded.created_at
            """,
            payload,
        )
        self.conn.commit()


class DailyAssetEngine:
    def __init__(self, store: AssetStore, provider: Optional[PriceProvider] = None):
        self.store = store
        self.provider = provider or HttpPriceProvider()

    def load_price_series(
        self,
        holding: Dict[str, Any],
        *,
        days: int,
        refresh: bool,
        as_of: Optional[dt.date] = None,
    ) -> Tuple[List[PricePoint], List[str]]:
        warnings: List[str] = []
        ticker = normalize_ticker(str(holding.get("ticker") or ""))
        asset_name = holding.get("asset_name")
        asset_type = resolve_asset_type(ticker, asset_name=asset_name, asset_type=holding.get("asset_type"))
        valuation_date = as_of or today_date()
        cutoff = valuation_date - dt.timedelta(days=max(days * 2, days + 30))
        cached = self.store.load_price_points(ticker, since=cutoff)
        cached = [point for point in cached if point.date <= valuation_date]

        if refresh and self.should_refresh(cached, asset_type, valuation_date, days):
            try:
                remote = self.provider.fetch_series(ticker, asset_name=asset_name, asset_type=asset_type, days=days)
            except Exception as exc:  # noqa: BLE001
                remote = []
                warnings.append(f"{ticker} 行情刷新失败，使用本地缓存：{exc}")
            if remote:
                self.store.save_price_points(ticker, remote)
                cached = self.store.load_price_points(ticker, since=cutoff)
                cached = [point for point in cached if point.date <= valuation_date]
            elif not cached:
                warnings.append(f"{ticker} 暂无可用行情数据")

        return dedupe_price_points(cached), warnings

    @staticmethod
    def should_refresh(series: List[PricePoint], asset_type: str, as_of: dt.date, days: int = VALUATION_HISTORY_DAYS) -> bool:
        if not series:
            return True
        required_start = as_of - dt.timedelta(days=max(days, 120))
        if series[0].date > required_start:
            return True
        latest = series[-1].date
        if asset_type == "fund":
            return latest < (as_of - dt.timedelta(days=1))
        return latest < as_of

    def calculate_position_state(
        self,
        transactions: Iterable[Dict[str, Any]],
        *,
        as_of: Optional[dt.date] = None,
    ) -> Dict[str, float]:
        units = 0.0
        cost_total = 0.0
        for tx in transactions:
            trade_date = parse_date(tx.get("trade_date"))
            if as_of is not None and trade_date is not None and trade_date > as_of:
                continue
            tx_type = str(tx.get("transaction_type") or "").upper()
            quantity = max(0.0, to_float(tx.get("quantity"), 0.0))
            price = max(0.0, to_float(tx.get("price"), 0.0))
            fee = max(0.0, to_float(tx.get("fee"), 0.0))
            amount = to_float(tx.get("amount"), quantity * price)

            if tx_type == "RESET":
                units = quantity
                cost_total = quantity * price
            elif tx_type in {"BUY", "ADJUSTMENT_IN"}:
                units += quantity
                cost_total += amount + fee
            elif tx_type in {"SELL", "ADJUSTMENT_OUT"} and units > 0:
                sell_qty = min(quantity, units)
                avg_cost = cost_total / units if units > 0 else 0.0
                cost_total = max(0.0, cost_total - avg_cost * sell_qty)
                units = max(0.0, units - sell_qty)

        if units <= 1e-10:
            units = 0.0
            cost_total = 0.0
        return {
            "units": round(units, 6),
            "avg_cost": cost_total / units if units > 0 else 0.0,
            "invested_amount": cost_total,
        }

    def period_net_flow(self, transactions: Iterable[Dict[str, Any]], start_date: dt.date, end_date: dt.date) -> float:
        net_flow = 0.0
        for tx in transactions:
            trade_date = parse_date(tx.get("trade_date"))
            if trade_date is None or trade_date <= start_date or trade_date > end_date:
                continue
            tx_type = str(tx.get("transaction_type") or "").upper()
            quantity = max(0.0, to_float(tx.get("quantity"), 0.0))
            price = max(0.0, to_float(tx.get("price"), 0.0))
            fee = max(0.0, to_float(tx.get("fee"), 0.0))
            amount = to_float(tx.get("amount"), quantity * price)
            if tx_type in {"BUY", "ADJUSTMENT_IN"}:
                net_flow += amount + fee
            elif tx_type in {"SELL", "ADJUSTMENT_OUT"}:
                net_flow -= max(0.0, amount - fee)
        return net_flow

    def infer_opening_reset_state(
        self,
        transactions: Iterable[Dict[str, Any]],
        start_date: dt.date,
        end_date: dt.date,
    ) -> Optional[Dict[str, Any]]:
        earliest_reset: Optional[Dict[str, Any]] = None
        has_activity_before_period = False
        for tx in transactions:
            trade_date = parse_date(tx.get("trade_date"))
            if trade_date is None:
                continue
            if trade_date <= start_date:
                has_activity_before_period = True
            if str(tx.get("transaction_type") or "").upper() != "RESET" or trade_date > end_date:
                continue
            if earliest_reset is None:
                earliest_reset = tx
                continue
            previous_date = parse_date(earliest_reset.get("trade_date"))
            previous_id = to_int(earliest_reset.get("id"), 0)
            current_id = to_int(tx.get("id"), 0)
            if previous_date is None or trade_date < previous_date or (trade_date == previous_date and current_id < previous_id):
                earliest_reset = tx

        if has_activity_before_period or earliest_reset is None:
            return None
        reset_units = max(0.0, to_float(earliest_reset.get("quantity"), 0.0))
        reset_price = max(0.0, to_float(earliest_reset.get("price"), 0.0))
        if reset_units <= 0 or reset_price <= 0:
            return None
        return {"units": reset_units, "price": reset_price, "trade_date": parse_date(earliest_reset.get("trade_date"))}

    def calculate_period_changes(
        self,
        ticker: str,
        series: List[PricePoint],
        transactions: List[Dict[str, Any]],
        units: float,
        latest_price: float,
        latest_date: Optional[dt.date],
        flow_end_date: Optional[dt.date],
    ) -> Dict[str, float]:
        zero = {
            "day_change": 0.0,
            "week_change": 0.0,
            "month_change": 0.0,
            "year_change": 0.0,
            "day_change_pct": 0.0,
            "week_change_pct": 0.0,
            "month_change_pct": 0.0,
            "year_change_pct": 0.0,
        }
        if units <= 0 or latest_price <= 0 or latest_date is None:
            return zero

        current_market_value = units * latest_price
        resolved_flow_end = flow_end_date or latest_date
        if resolved_flow_end < latest_date:
            resolved_flow_end = latest_date

        periods = {
            "day": latest_date - dt.timedelta(days=1),
            "week": latest_date - dt.timedelta(days=7),
            "month": latest_date - dt.timedelta(days=30),
            "year": latest_date - dt.timedelta(days=365),
        }
        result: Dict[str, float] = {}
        for name, ref_date in periods.items():
            net_flow = self.period_net_flow(transactions, ref_date, resolved_flow_end)
            ref_market_value = self.store.snapshot_value(ticker, ref_date)
            opening_reset = self.infer_opening_reset_state(transactions, ref_date, resolved_flow_end)
            if ref_market_value is None or ref_market_value <= 0:
                ref_state = self.calculate_position_state(transactions, as_of=ref_date)
                ref_units = ref_state["units"]
                if ref_units <= 0 and abs(net_flow) <= 1e-10:
                    ref_units = units
                elif ref_units <= 0 and opening_reset is not None:
                    ref_units = to_float(opening_reset.get("units"), 0.0)

                if ref_units > 0:
                    ref_price = reference_price(series, ref_date)
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
            result[f"{name}_change_pct"] = (change_value / ref_market_value * 100.0) if ref_market_value > 0 else 0.0
        return result

    def compute_due_dates(self, rule: Dict[str, Any], as_of: dt.date) -> List[dt.date]:
        if not rule.get("enabled"):
            return []
        start_date = parse_date(rule.get("start_date"), as_of) or as_of
        end_date = parse_date(rule.get("end_date"), as_of) if rule.get("end_date") else as_of
        if end_date > as_of:
            end_date = as_of
        last_run = parse_date(rule.get("last_run_date"))
        candidate_start = last_run + dt.timedelta(days=1) if last_run else start_date
        latest_reset = parse_date(rule.get("latest_reset_date"))
        if latest_reset and candidate_start < latest_reset:
            candidate_start = latest_reset
        if candidate_start > end_date:
            return []

        frequency = str(rule.get("frequency") or "weekly").lower()
        due_dates: List[dt.date] = []
        if frequency == "monthly":
            monthday = max(1, min(31, to_int(rule.get("monthday"), 1)))
            cursor = dt.date(candidate_start.year, candidate_start.month, 1)
            while cursor <= end_date and len(due_dates) < 120:
                last_day = calendar.monthrange(cursor.year, cursor.month)[1]
                scheduled = dt.date(cursor.year, cursor.month, min(monthday, last_day))
                if candidate_start <= scheduled <= end_date:
                    due_dates.append(scheduled)
                cursor = dt.date(cursor.year + 1, 1, 1) if cursor.month == 12 else dt.date(cursor.year, cursor.month + 1, 1)
        else:
            weekday = to_int(rule.get("weekday"), 3)
            cursor = candidate_start
            while cursor <= end_date and len(due_dates) < 120:
                if cursor.weekday() == weekday:
                    due_dates.append(cursor)
                cursor += dt.timedelta(days=1)
        return due_dates

    def resolve_dca_occurrences(
        self,
        rule: Dict[str, Any],
        as_of: dt.date,
        series: List[PricePoint],
    ) -> List[Dict[str, dt.date]]:
        occurrences: List[Dict[str, dt.date]] = []
        for due_date in self.compute_due_dates(rule, as_of):
            effective_date = due_date
            if rule.get("shift_to_next_trading_day", True):
                future_prices = [point.date for point in series if due_date <= point.date <= as_of]
                if future_prices:
                    effective_date = future_prices[0]
                else:
                    while effective_date <= as_of and not is_business_day(effective_date):
                        effective_date += dt.timedelta(days=1)
            if effective_date > as_of:
                continue
            confirmation_date = effective_date
            if self.requires_delayed_fund_confirmation(rule):
                confirmation_date = next_business_day(effective_date)
            occurrences.append({"effective_date": effective_date, "confirmation_date": confirmation_date})
        return occurrences

    @staticmethod
    def requires_delayed_fund_confirmation(rule: Dict[str, Any]) -> bool:
        asset_type = resolve_asset_type(
            str(rule.get("ticker") or ""),
            asset_name=rule.get("asset_name"),
            asset_type=rule.get("asset_type"),
        )
        return should_prefer_fund_nav(str(rule.get("ticker") or ""), rule.get("asset_name"), asset_type)

    def reconcile_due_dca(self, as_of: Optional[dt.date] = None) -> Dict[str, Any]:
        today = as_of or today_date()
        rules = self.store.active_dca_rules()
        created = 0
        skipped: List[str] = []

        for rule in rules:
            ticker = str(rule["ticker"])
            holding = {
                "ticker": ticker,
                "asset_name": rule.get("asset_name"),
                "asset_type": rule.get("asset_type"),
            }
            start_date = parse_date(rule.get("start_date"), today) or today
            days = max((today - start_date).days + 30, 120)
            series, warnings = self.load_price_series(holding, days=days, refresh=True, as_of=today)
            skipped.extend(warnings)
            executed_dates: List[dt.date] = []
            delayed = self.requires_delayed_fund_confirmation(rule)
            for occurrence in self.resolve_dca_occurrences(rule, today, series):
                effective_date = occurrence["effective_date"]
                confirmation_date = occurrence["confirmation_date"]
                if confirmation_date > today:
                    continue
                price = price_on_date(series, effective_date) if delayed else reference_price(series, effective_date)
                if price is None or price <= 0:
                    skipped.append(f"{ticker} {effective_date.isoformat()} 定投缺少价格，已跳过")
                    continue
                amount = max(0.0, to_float(rule.get("amount"), 0.0))
                quantity = round(amount / price, 6)
                if quantity <= 0:
                    continue
                source_id = f"dca:{ticker}:{confirmation_date.isoformat()}"
                self.store.insert_transaction(
                    ticker,
                    {
                        "transaction_type": "BUY",
                        "trade_date": confirmation_date.isoformat(),
                        "quantity": quantity,
                        "price": price,
                        "amount": amount,
                        "source": "dca",
                        "note": (
                            f"Auto DCA {amount:.2f} confirmed {confirmation_date.isoformat()}"
                            if confirmation_date != effective_date
                            else f"Auto DCA {amount:.2f}"
                        ),
                    },
                    source_id=source_id,
                )
                executed_dates.append(confirmation_date)
                created += 1

            if executed_dates:
                self.store.update_dca_last_run(ticker, max(executed_dates))

        return {"created": created, "rules_checked": len(rules), "as_of": today.isoformat(), "warnings": skipped}

    def build_pending_dca_map(self, as_of: dt.date) -> Dict[str, Dict[str, Any]]:
        pending: Dict[str, Dict[str, Any]] = {}
        for rule in self.store.active_dca_rules():
            if not self.requires_delayed_fund_confirmation(rule):
                continue
            ticker = str(rule["ticker"])
            holding = {"ticker": ticker, "asset_name": rule.get("asset_name"), "asset_type": rule.get("asset_type")}
            start_date = parse_date(rule.get("start_date"), as_of) or as_of
            days = max((as_of - start_date).days + 30, 120)
            series, _warnings = self.load_price_series(holding, days=days, refresh=False, as_of=as_of)
            for occurrence in self.resolve_dca_occurrences(rule, as_of, series):
                effective_date = occurrence["effective_date"]
                confirmation_date = occurrence["confirmation_date"]
                if confirmation_date <= as_of:
                    continue
                amount = max(0.0, to_float(rule.get("amount"), 0.0))
                estimated_price = price_on_date(series, effective_date)
                estimated_units = amount / estimated_price if estimated_price and estimated_price > 0 else None
                pending[ticker] = {
                    "status": "pending_confirmation",
                    "amount": round(amount, 2),
                    "execution_date": effective_date.isoformat(),
                    "confirmation_date": confirmation_date.isoformat(),
                    "price_basis_date": effective_date.isoformat(),
                    "estimated_price": round(estimated_price, 6) if estimated_price and estimated_price > 0 else None,
                    "estimated_units": round(estimated_units, 6) if estimated_units and estimated_units > 0 else None,
                }
                break
        return pending

    def get_overview(
        self,
        *,
        refresh_prices: bool = True,
        force_snapshot: bool = True,
        as_of: Optional[dt.date] = None,
    ) -> Dict[str, Any]:
        valuation_date = as_of or today_date()
        holdings = self.store.list_holdings()
        pending_map = self.build_pending_dca_map(valuation_date)
        warnings: List[str] = []
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

        for holding in holdings:
            ticker = str(holding["ticker"])
            asset_type = resolve_asset_type(ticker, asset_name=holding.get("asset_name"), asset_type=holding.get("asset_type"))
            holding["asset_type"] = asset_type
            transactions = self.store.list_transactions(ticker)
            state = self.calculate_position_state(transactions, as_of=valuation_date)
            series, price_warnings = self.load_price_series(
                holding,
                days=VALUATION_HISTORY_DAYS,
                refresh=refresh_prices,
                as_of=valuation_date,
            )
            warnings.extend(price_warnings)
            latest = series[-1] if series else None
            latest_price = latest.price if latest else state["avg_cost"]
            latest_price_date = latest.date if latest else None
            if not latest:
                warnings.append(f"{ticker} 无行情数据，暂按成本价估值")

            market_value = state["units"] * latest_price
            total_return = market_value - state["invested_amount"]
            total_return_pct = total_return / state["invested_amount"] * 100.0 if state["invested_amount"] > 0 else 0.0
            dated_transactions = [
                trade_date
                for trade_date in (parse_date(tx.get("trade_date")) for tx in transactions)
                if trade_date is not None and trade_date <= valuation_date
            ]
            latest_trade_date = max(dated_transactions, default=None)
            period_changes = self.calculate_period_changes(
                ticker,
                series,
                transactions,
                state["units"],
                latest_price,
                latest_price_date,
                latest_trade_date,
            )

            asset = {
                "ticker": ticker,
                "asset_name": holding.get("asset_name"),
                "asset_category": holding.get("asset_category"),
                "asset_style": holding.get("asset_style"),
                "asset_type": asset_type,
                "notes": holding.get("notes"),
                "units": state["units"],
                "avg_cost": round(state["avg_cost"], 6),
                "invested_amount": round(state["invested_amount"], 2),
                "current_price": round(latest_price, 6),
                "last_price_date": latest_price_date.isoformat() if latest_price_date else None,
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
                "pending_dca": pending_map.get(ticker),
                "updated_at": holding.get("updated_at"),
            }
            assets.append(asset)
            summary["total_market_value"] += market_value
            summary["total_invested_amount"] += state["invested_amount"]
            summary["total_return"] += total_return
            summary["day_change"] += period_changes["day_change"]
            summary["week_change"] += period_changes["week_change"]
            summary["month_change"] += period_changes["month_change"]
            summary["year_change"] += period_changes["year_change"]

        invested_total = summary["total_invested_amount"]
        summary["total_return_pct"] = summary["total_return"] / invested_total * 100.0 if invested_total > 0 else 0.0
        for key in ("total_market_value", "total_invested_amount", "total_return", "day_change", "week_change", "month_change", "year_change"):
            summary[key] = round(summary[key], 2)
        summary["total_return_pct"] = round(summary["total_return_pct"], 4)
        summary["updated_at"] = dt.datetime.now().isoformat(timespec="seconds")

        if force_snapshot:
            self.store.persist_snapshots(assets, summary, valuation_date)

        return {"summary": summary, "assets": assets, "warnings": warnings}


def apply_config(store: AssetStore, config_path: str | Path, *, replace: bool = False) -> None:
    path = resolve_existing_path(config_path)
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if replace:
        store.clear_portfolio()
    username = str(data.get("username") or data.get("name") or "").strip()
    if username:
        store.set_meta("username", username)
    for item in data.get("assets") or []:
        store.upsert_holding(item)
        ticker = normalize_ticker(str(item.get("ticker") or ""))
        store.save_dca_rule(ticker, item.get("dca_rule"))
        for tx in item.get("transactions") or []:
            source_id = tx.get("source_id")
            store.insert_transaction(ticker, tx, source_id=source_id)
        if not store.has_transactions(ticker) and to_float(item.get("units"), 0.0) >= 0:
            store.insert_transaction(
                ticker,
                {
                    "transaction_type": "RESET",
                    "trade_date": item.get("trade_date") or today_date().isoformat(),
                    "quantity": to_float(item.get("units"), 0.0),
                    "price": to_float(item.get("avg_cost"), 0.0),
                    "amount": to_float(item.get("units"), 0.0) * to_float(item.get("avg_cost"), 0.0),
                    "source": "config",
                    "note": "Initial holdings from config",
                },
                source_id=f"config-reset:{ticker}",
            )


def import_dashboard_db(
    store: AssetStore,
    source_db_path: str | Path,
    *,
    username: Optional[str] = None,
    user_id: Optional[int] = None,
    replace: bool = False,
) -> str:
    source_path = resolve_existing_path(source_db_path)
    if not source_path.exists():
        raise SystemExit(f"Dashboard database not found: {source_path}")
    source = sqlite3.connect(str(source_path))
    source.row_factory = sqlite3.Row
    try:
        resolved_user_id, resolved_username = resolve_dashboard_user(source, username=username, user_id=user_id)
        if replace:
            store.clear_portfolio()
        store.set_meta("username", resolved_username)

        holdings = source.execute(
            """
            SELECT ticker, asset_name, asset_category, asset_style, asset_type, notes
            FROM user_asset_holdings
            WHERE user_id = ?
            ORDER BY ticker
            """,
            (resolved_user_id,),
        ).fetchall()
        for row in holdings:
            store.upsert_holding(dict(row))

        transactions = source.execute(
            """
            SELECT id, ticker, transaction_type, trade_date, quantity, price, amount, fee, source, note
            FROM user_asset_transactions
            WHERE user_id = ?
            ORDER BY ticker, trade_date, id
            """,
            (resolved_user_id,),
        ).fetchall()
        for row in transactions:
            item = dict(row)
            store.insert_transaction(
                str(item["ticker"]),
                item,
                source_id=f"dashboard:{resolved_user_id}:{item['id']}",
            )

        rules = source.execute(
            """
            SELECT ticker, enabled, frequency, weekday, monthday, amount, start_date,
                   end_date, shift_to_next_trading_day, last_run_date
            FROM user_asset_dca_rules
            WHERE user_id = ?
            ORDER BY ticker
            """,
            (resolved_user_id,),
        ).fetchall()
        for row in rules:
            store.save_dca_rule(str(row["ticker"]), dict(row))

        snapshots = source.execute(
            """
            SELECT snapshot_date, ticker, current_price, units, market_value,
                   invested_amount, total_return, total_return_pct, created_at
            FROM user_asset_snapshots
            WHERE user_id = ?
            ORDER BY snapshot_date, ticker
            """,
            (resolved_user_id,),
        ).fetchall()
        store.upsert_snapshot_rows(dict(row) for row in snapshots)
        return resolved_username
    finally:
        source.close()


def resolve_dashboard_user(
    conn: sqlite3.Connection,
    *,
    username: Optional[str],
    user_id: Optional[int],
) -> Tuple[int, str]:
    if user_id is not None:
        row = conn.execute("SELECT id, username FROM users WHERE id = ?", (int(user_id),)).fetchone()
        if row:
            return int(row["id"]), str(row["username"])
        return int(user_id), f"user-{user_id}"
    if username:
        row = conn.execute("SELECT id, username FROM users WHERE username = ?", (username,)).fetchone()
        if row is None:
            raise SystemExit(f"Dashboard user not found: {username}")
        return int(row["id"]), str(row["username"])
    rows = conn.execute(
        """
        SELECT DISTINCT h.user_id, u.username
        FROM user_asset_holdings h
        LEFT JOIN users u ON u.id = h.user_id
        ORDER BY h.user_id
        """
    ).fetchall()
    if len(rows) == 1:
        return int(rows[0]["user_id"]), str(rows[0]["username"] or f"user-{rows[0]['user_id']}")
    admin_rows = [row for row in rows if str(row["username"] or "").lower() == "admin"]
    if len(admin_rows) == 1:
        return int(admin_rows[0]["user_id"]), str(admin_rows[0]["username"])
    raise SystemExit("Multiple dashboard users have holdings. Pass --username or --user-id for import.")


def format_money(value: Any, *, signed: bool = False) -> str:
    amount = to_float(value)
    if not signed:
        return f"¥{amount:,.2f}"
    sign = "+" if amount > 0 else "-" if amount < 0 else ""
    return f"{sign}¥{abs(amount):,.2f}"


def format_pct(value: Any, *, signed: bool = False) -> str:
    pct = to_float(value)
    if not signed:
        return f"{pct:.2f}%"
    sign = "+" if pct > 0 else "-" if pct < 0 else ""
    return f"{sign}{abs(pct):.2f}%"


def format_price(value: Any) -> str:
    price = to_float(value)
    return "-" if price <= 0 else f"{price:,.4f}"


def markdown_cell(value: Any) -> str:
    text = str(value if value is not None else "-").replace("\n", " ").strip()
    return text.replace("|", "\\|") or "-"


def top_movers(assets: Iterable[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    return sorted(assets, key=lambda item: abs(to_float(item.get("day_change"))), reverse=True)[: max(0, limit)]


def pending_dca_items(assets: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [asset for asset in assets if isinstance(asset.get("pending_dca"), dict)]


def approximate_period_pct(summary: Dict[str, Any], key: str) -> float:
    current_value = to_float(summary.get("total_market_value"))
    change = to_float(summary.get(key))
    base = current_value - change
    return change / base * 100.0 if base > 0 else 0.0


def stale_price_warnings(assets: Iterable[Dict[str, Any]], *, today: dt.date, stale_days: int) -> List[str]:
    warnings: List[str] = []
    for asset in assets:
        ticker = str(asset.get("ticker") or "")
        price_date = parse_date(asset.get("last_price_date"))
        if not ticker:
            continue
        if price_date is None:
            warnings.append(f"{ticker} 暂无估值日期")
            continue
        age = (today - price_date).days
        if age > stale_days:
            warnings.append(f"{ticker} 最新估值日期为 {price_date.isoformat()}，已滞后 {age} 天")
    return warnings


def build_asset_table(assets: List[Dict[str, Any]]) -> str:
    if not assets:
        return "当前没有可展示的持仓。"
    lines = [
        "| 标的 | 最新价 | 价格日 | 市值 | 今日 | 累计 |",
        "| --- | ---: | --- | ---: | ---: | ---: |",
    ]
    for asset in assets:
        label = f"{asset.get('asset_name') or asset.get('ticker')} ({asset.get('ticker')})"
        day_text = f"{format_money(asset.get('day_change'), signed=True)} ({format_pct(asset.get('day_change_pct'), signed=True)})"
        total_text = f"{format_money(asset.get('total_return'), signed=True)} ({format_pct(asset.get('total_return_pct'), signed=True)})"
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(label),
                    markdown_cell(format_price(asset.get("current_price"))),
                    markdown_cell(asset.get("last_price_date") or "-"),
                    markdown_cell(format_money(asset.get("market_value"))),
                    markdown_cell(day_text),
                    markdown_cell(total_text),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def build_pending_dca_section(assets: List[Dict[str, Any]]) -> str:
    items = pending_dca_items(assets)
    if not items:
        return ""
    lines = ["## 待确认定投"]
    for asset in items:
        pending = asset["pending_dca"]
        estimate_text = ""
        if to_float(pending.get("estimated_price")) > 0 and to_float(pending.get("estimated_units")) > 0:
            estimate_text = (
                f"，估算价格 {format_price(pending.get('estimated_price'))}"
                f"，估算份额 {to_float(pending.get('estimated_units')):,.4f}"
            )
        lines.append(
            "- "
            f"{asset.get('ticker')}: {pending.get('execution_date')} 发起 {format_money(pending.get('amount'))}，"
            f"预计 {pending.get('confirmation_date')} 确认{estimate_text}"
        )
    return "\n".join(lines)


def build_markdown_report(
    target: ReportTarget,
    overview: Dict[str, Any],
    *,
    reconcile: Optional[Dict[str, Any]],
    generated_at: dt.datetime,
    warnings: Optional[List[str]] = None,
    top_limit: int = 8,
    include_all_assets: bool = False,
    stale_days: int = 5,
) -> str:
    summary = dict(overview.get("summary") or {})
    assets = list(overview.get("assets") or [])
    selected_assets = assets if include_all_assets else top_movers(assets, top_limit)
    all_warnings = list(overview.get("warnings") or []) + list(warnings or [])
    all_warnings.extend(stale_price_warnings(assets, today=generated_at.date(), stale_days=stale_days))

    reconcile_text = "已跳过"
    if reconcile:
        reconcile_text = (
            f"新增 {int(reconcile.get('created') or 0)} 笔 / "
            f"检查 {int(reconcile.get('rules_checked') or 0)} 条 / "
            f"日期 {reconcile.get('as_of') or '-'}"
        )
        for item in reconcile.get("warnings") or []:
            all_warnings.append(str(item))

    lines = [
        f"# 个人资产日报 - {target.username}",
        f"生成时间: {generated_at.isoformat(timespec='seconds')}",
        f"估值更新时间: {summary.get('updated_at') or '-'}",
        "",
        "## 汇总",
        f"- 总市值: {format_money(summary.get('total_market_value'))}",
        f"- 投入本金: {format_money(summary.get('total_invested_amount'))}",
        f"- 累计收益: {format_money(summary.get('total_return'), signed=True)} ({format_pct(summary.get('total_return_pct'), signed=True)})",
        f"- 今日收益: {format_money(summary.get('day_change'), signed=True)} (约 {format_pct(approximate_period_pct(summary, 'day_change'), signed=True)})",
        f"- 近7日: {format_money(summary.get('week_change'), signed=True)} (约 {format_pct(approximate_period_pct(summary, 'week_change'), signed=True)})",
        f"- 近30日: {format_money(summary.get('month_change'), signed=True)} (约 {format_pct(approximate_period_pct(summary, 'month_change'), signed=True)})",
        f"- 近365日: {format_money(summary.get('year_change'), signed=True)} (约 {format_pct(approximate_period_pct(summary, 'year_change'), signed=True)})",
        f"- 资产数: {int(summary.get('asset_count') or len(assets))}",
        f"- 定投补算: {reconcile_text}",
        "",
        "## 今日波动靠前" if not include_all_assets else "## 全部持仓",
        build_asset_table(selected_assets),
    ]

    pending_section = build_pending_dca_section(assets)
    if pending_section:
        lines.extend(["", pending_section])

    unique_warnings = list(dict.fromkeys(item for item in all_warnings if item))
    if unique_warnings:
        lines.extend(["", "## 数据提示"])
        lines.extend(f"- {item}" for item in unique_warnings)
    return "\n".join(lines).rstrip() + "\n"


def build_report_payload(
    target: ReportTarget,
    overview: Dict[str, Any],
    *,
    reconcile: Optional[Dict[str, Any]],
    generated_at: dt.datetime,
    top_limit: int,
    include_all_assets: bool,
    stale_days: int,
) -> Dict[str, Any]:
    assets = list(overview.get("assets") or [])
    markdown = build_markdown_report(
        target,
        overview,
        reconcile=reconcile,
        generated_at=generated_at,
        top_limit=top_limit,
        include_all_assets=include_all_assets,
        stale_days=stale_days,
    )
    return {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "user": {"username": target.username},
        "reconcile": reconcile,
        "summary": overview.get("summary") or {},
        "assets": assets,
        "top_movers": top_movers(assets, top_limit),
        "pending_dca": pending_dca_items(assets),
        "warnings": overview.get("warnings") or [],
        "markdown": markdown,
    }


def render_output(payloads: List[Dict[str, Any]], output_format: str) -> str:
    if output_format == "json":
        return json.dumps(
            {
                "generated_at": payloads[0]["generated_at"] if payloads else dt.datetime.now().isoformat(timespec="seconds"),
                "count": len(payloads),
                "reports": payloads,
            },
            ensure_ascii=False,
            indent=2,
        )
    return "\n---\n\n".join(str(payload["markdown"]).rstrip() for payload in payloads) + "\n"


def write_optional_output(path: Optional[str], content: str) -> None:
    if not path:
        return
    output_path = resolve_script_path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def resolve_script_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (SCRIPT_DIR / candidate).resolve()


def resolve_existing_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    cwd_candidate = (Path.cwd() / candidate).resolve()
    if cwd_candidate.exists():
        return cwd_candidate
    return (SCRIPT_DIR / candidate).resolve()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Standalone daily personal asset report for agent runners.")
    parser.add_argument(
        "--store",
        default=DEFAULT_STORE,
        help="Standalone agent SQLite store path. Relative paths are resolved under scripts/.",
    )
    parser.add_argument(
        "--config",
        help="Optional JSON config to initialize/update holdings. Defaults to scripts/personal_assets.json when it exists.",
    )
    parser.add_argument("--replace", action="store_true", help="Replace local portfolio when applying --config or --import-dashboard-db.")
    parser.add_argument("--import-dashboard-db", help="One-time import from the dashboard quant.db.")
    parser.add_argument("--username", help="Dashboard username for import, or report label override.")
    parser.add_argument("--user-id", type=int, help="Dashboard user id for import.")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", help="Optional output file path.")
    parser.add_argument("--as-of", help="Run date in YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--top", type=int, default=8, help="Number of biggest daily movers to include.")
    parser.add_argument("--all-assets", action="store_true", help="Include every holding in the table.")
    parser.add_argument("--skip-price-refresh", action="store_true", help="Use local price cache only.")
    parser.add_argument("--skip-dca", action="store_true", help="Skip due DCA reconciliation.")
    parser.add_argument("--no-snapshot", action="store_true", help="Do not persist today's valuation snapshot.")
    parser.add_argument("--stale-days", type=int, default=5, help="Warn when price date is older than this many days.")
    parser.add_argument("--log-level", default="WARNING", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return parser.parse_args(argv)


def parse_as_of(value: Optional[str]) -> Optional[dt.date]:
    if not value:
        return None
    parsed = parse_date(value)
    if parsed is None:
        raise SystemExit(f"--as-of must be YYYY-MM-DD, got: {value}")
    return parsed


def main(argv: Optional[Sequence[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s %(name)s: %(message)s")
    store = AssetStore(resolve_script_path(args.store))
    try:
        if args.import_dashboard_db:
            imported_username = import_dashboard_db(
                store,
                args.import_dashboard_db,
                username=args.username,
                user_id=args.user_id,
                replace=args.replace,
            )
            logger.info("Imported dashboard assets for %s into %s", imported_username, store.path)
        config_path = args.config or (DEFAULT_CONFIG if DEFAULT_CONFIG.exists() else None)
        if config_path:
            apply_config(store, config_path, replace=args.replace)

        engine = DailyAssetEngine(store)
        as_of = parse_as_of(args.as_of)
        reconcile = None
        if not args.skip_dca:
            reconcile = engine.reconcile_due_dca(as_of=as_of)
        overview = engine.get_overview(
            refresh_prices=not args.skip_price_refresh,
            force_snapshot=not args.no_snapshot,
            as_of=as_of,
        )
        username = args.username or store.get_meta("username", "personal")
        payload = build_report_payload(
            ReportTarget(username=username),
            overview,
            reconcile=reconcile,
            generated_at=dt.datetime.now(),
            top_limit=args.top,
            include_all_assets=args.all_assets,
            stale_days=args.stale_days,
        )
        content = render_output([payload], args.format)
        write_optional_output(args.output, content)
        print(content)
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
