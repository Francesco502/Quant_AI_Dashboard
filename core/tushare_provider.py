"""Tushare enhanced provider for China market data.

This module centralizes Tushare token handling and a small set of
high-value A-share helpers so upper layers can reuse one consistent
integration path.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

try:
    import tushare as ts  # type: ignore[import]

    TUSHARE_AVAILABLE = True
except Exception:  # pragma: no cover
    ts = None  # type: ignore[assignment]
    TUSHARE_AVAILABLE = False


logger = logging.getLogger(__name__)

_CN_INDEX_MAP = {
    "000001.SH": "上证指数",
    "399001.SZ": "深证成指",
    "399006.SZ": "创业板指",
}


def get_tushare_token() -> Optional[str]:
    """Read Tushare token from env or configured user state."""
    token = os.getenv("TUSHARE_TOKEN", "").strip()
    if token:
        return token

    try:
        from core.data_service import get_api_keys

        token = (get_api_keys().get("TUSHARE_TOKEN") or "").strip()
        return token or None
    except Exception as exc:  # pragma: no cover - defensive path
        logger.debug("读取 Tushare token 失败: %s", exc)
        return None


@lru_cache(maxsize=2)
def _get_pro_api(token: str):
    if not TUSHARE_AVAILABLE or not token:
        return None

    try:
        ts.set_token(token)
        return ts.pro_api()
    except Exception as exc:  # pragma: no cover - defensive path
        logger.debug("初始化 Tushare Pro API 失败: %s", exc)
        return None


def _get_configured_pro_api():
    token = get_tushare_token()
    if not token:
        return None
    return _get_pro_api(token)


def _coerce_date(value: Optional[dt.date]) -> dt.date:
    return value or dt.date.today()


def _date_str(value: dt.date) -> str:
    return value.strftime("%Y%m%d")


def normalize_cn_ticker(ticker: str) -> Optional[str]:
    """Normalize common A-share / ETF / fund ticker formats to ts_code."""
    text = str(ticker or "").strip().upper()
    if not text:
        return None

    if text.endswith((".SZ", ".SH")):
        return text

    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) != 6:
        return None

    if digits.startswith(("00", "15", "16", "18", "30", "39")):
        suffix = ".SZ"
    elif digits.startswith(("50", "51", "56", "58", "60", "68", "90", "11", "12")):
        suffix = ".SH"
    else:
        suffix = ".SZ"
    return f"{digits}{suffix}"


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


@lru_cache(maxsize=512)
def get_cn_security_name(ticker: str) -> Optional[str]:
    """Resolve A-share / ETF / fund display name from Tushare."""
    pro = _get_configured_pro_api()
    ts_code = normalize_cn_ticker(ticker)
    if pro is None or ts_code is None:
        return None

    for method_name in ("stock_basic", "fund_basic"):
        method = getattr(pro, method_name, None)
        if method is None:
            continue
        try:
            df = method(ts_code=ts_code, fields="ts_code,name")
            if df is not None and not df.empty:
                name = str(df.iloc[0].get("name") or "").strip()
                if name:
                    return name
        except TypeError:
            try:
                df = method(market="E", status="L")
                if df is not None and not df.empty and "ts_code" in df.columns:
                    rows = df[df["ts_code"].astype(str).str.upper() == ts_code]
                    if not rows.empty:
                        name = str(rows.iloc[0].get("name") or "").strip()
                        if name:
                            return name
            except Exception:
                continue
        except Exception:
            continue

    return None


@lru_cache(maxsize=512)
def get_cn_security_profile(ticker: str) -> Dict[str, Any]:
    """Resolve a minimal profile plus latest valuation fields for A-share symbols."""
    pro = _get_configured_pro_api()
    ts_code = normalize_cn_ticker(ticker)
    if pro is None or ts_code is None:
        return {}

    profile: Dict[str, Any] = {"ticker": ticker, "ts_code": ts_code}

    stock_basic = getattr(pro, "stock_basic", None)
    if stock_basic is not None:
        try:
            df = stock_basic(
                ts_code=ts_code,
                fields="ts_code,name,industry,market,area,list_date",
            )
            if df is not None and not df.empty:
                row = df.iloc[0]
                profile.update(
                    {
                        "asset_type": "stock",
                        "name": row.get("name"),
                        "industry": row.get("industry"),
                        "market": row.get("market"),
                        "area": row.get("area"),
                        "list_date": row.get("list_date"),
                    }
                )
        except Exception as exc:
            logger.debug("Tushare stock_basic lookup failed for %s: %s", ts_code, exc)

    if "asset_type" not in profile:
        fund_basic = getattr(pro, "fund_basic", None)
        if fund_basic is not None:
            try:
                df = fund_basic(market="E")
                if df is not None and not df.empty and "ts_code" in df.columns:
                    rows = df[df["ts_code"].astype(str).str.upper() == ts_code]
                    if not rows.empty:
                        row = rows.iloc[0]
                        profile.update(
                            {
                                "asset_type": "fund",
                                "name": row.get("name"),
                                "management": row.get("management"),
                                "fund_type": row.get("fund_type"),
                                "list_date": row.get("list_date"),
                                "market": row.get("market"),
                            }
                        )
            except Exception as exc:
                logger.debug("Tushare fund_basic lookup failed for %s: %s", ts_code, exc)

    daily_basic = getattr(pro, "daily_basic", None)
    if daily_basic is not None:
        start_date = _date_str(dt.date.today() - dt.timedelta(days=10))
        end_date = _date_str(dt.date.today())
        try:
            df = daily_basic(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                fields="ts_code,trade_date,pe_ttm,pb,total_mv,circ_mv,turnover_rate,volume_ratio",
            )
            if df is not None and not df.empty:
                df = df.sort_values("trade_date", ascending=False).reset_index(drop=True)
                row = df.iloc[0]
                profile["valuation"] = {
                    "trade_date": row.get("trade_date"),
                    "pe_ttm": _safe_float(row.get("pe_ttm")),
                    "pb": _safe_float(row.get("pb")),
                    "total_mv": _safe_float(row.get("total_mv")),
                    "circ_mv": _safe_float(row.get("circ_mv")),
                    "turnover_rate": _safe_float(row.get("turnover_rate")),
                    "volume_ratio": _safe_float(row.get("volume_ratio")),
                }
        except Exception as exc:
            logger.debug("Tushare daily_basic lookup failed for %s: %s", ts_code, exc)

    return profile


def is_a_share_trading_day(date: Optional[dt.date] = None) -> Optional[bool]:
    """Check A-share trading day using Tushare trade_cal."""
    pro = _get_configured_pro_api()
    target = _coerce_date(date)
    if pro is None:
        return None

    try:
        df = pro.trade_cal(exchange="SSE", start_date=_date_str(target), end_date=_date_str(target))
        if df is None or df.empty:
            return None
        row = df.iloc[0]
        is_open = row.get("is_open")
        if is_open is None:
            return None
        return str(is_open) == "1"
    except Exception as exc:
        logger.debug("Tushare trade_cal 查询失败: %s", exc)
        return None


def get_next_a_share_trading_day(
    from_date: Optional[dt.date] = None,
    days: int = 1,
) -> Optional[dt.date]:
    """Get the next A-share trading day using trade_cal."""
    pro = _get_configured_pro_api()
    start = _coerce_date(from_date)
    if pro is None:
        return None

    end = start + dt.timedelta(days=max(days * 14, 14))
    try:
        df = pro.trade_cal(
            exchange="SSE",
            start_date=_date_str(start),
            end_date=_date_str(end),
            is_open="1",
        )
        if df is None or df.empty:
            return None
        if "cal_date" not in df.columns:
            return None

        dates: List[dt.date] = []
        for raw in df["cal_date"].tolist():
            try:
                parsed = dt.datetime.strptime(str(raw), "%Y%m%d").date()
                if parsed > start:
                    dates.append(parsed)
            except Exception:
                continue

        if len(dates) < days:
            return None
        return dates[days - 1]
    except Exception as exc:
        logger.debug("Tushare next trading day 查询失败: %s", exc)
        return None


def get_cn_index_snapshots() -> List[Dict[str, Any]]:
    """Fetch major A-share index snapshots from Tushare."""
    pro = _get_configured_pro_api()
    if pro is None:
        return []

    results: List[Dict[str, Any]] = []
    start_date = _date_str(dt.date.today() - dt.timedelta(days=10))
    end_date = _date_str(dt.date.today())

    for ts_code, name in _CN_INDEX_MAP.items():
        try:
            df = pro.index_daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                fields="ts_code,trade_date,open,high,low,close,vol,amount",
            )
            if df is None or df.empty or len(df) < 2:
                continue

            df = df.sort_values("trade_date", ascending=False).reset_index(drop=True)
            today = df.iloc[0]
            prev = df.iloc[1]

            close = _safe_float(today.get("close"))
            prev_close = _safe_float(prev.get("close"))
            high = _safe_float(today.get("high"))
            low = _safe_float(today.get("low"))
            volume = _safe_float(today.get("vol"))
            amount = _safe_float(today.get("amount"))

            if close is None or prev_close in (None, 0):
                continue

            pct_change = round((close / prev_close - 1.0) * 100.0, 2)
            amplitude = None
            if high is not None and low is not None and prev_close:
                amplitude = round((high - low) / prev_close * 100.0, 2)

            results.append(
                {
                    "name": name,
                    "value": round(close, 2),
                    "pct_change": pct_change,
                    "volume": int(volume) if volume is not None else None,
                    "amount": round(amount / 1e8, 2) if amount is not None else None,
                    "amplitude": amplitude,
                    "turn_rate": None,
                }
            )
        except Exception as exc:
            logger.debug("Tushare 指数 %s 获取失败: %s", ts_code, exc)

    return results


def get_cn_northbound_flow() -> Dict[str, Any]:
    """Fetch northbound capital flow summary from Tushare."""
    pro = _get_configured_pro_api()
    info: Dict[str, Any] = {"net_inflow": None, "unit": "亿元", "description": ""}
    if pro is None:
        return info

    method = getattr(pro, "moneyflow_hsgt", None)
    if method is None:
        return info

    start_date = _date_str(dt.date.today() - dt.timedelta(days=7))
    end_date = _date_str(dt.date.today())
    try:
        df = method(start_date=start_date, end_date=end_date)
        if df is None or df.empty:
            return info
        if "trade_date" in df.columns:
            df = df.sort_values("trade_date", ascending=False).reset_index(drop=True)
        row = df.iloc[0]

        north_money = _safe_float(row.get("north_money"))
        if north_money is None:
            hgt = _safe_float(row.get("hgt"))
            sgt = _safe_float(row.get("sgt"))
            if hgt is not None or sgt is not None:
                north_money = (hgt or 0.0) + (sgt or 0.0)

        if north_money is not None:
            info["net_inflow"] = round(north_money, 2)
            info["description"] = f"北向资金当日净流入 {north_money:.2f} 亿元"
    except Exception as exc:
        logger.debug("Tushare 北向资金获取失败: %s", exc)

    return info


@lru_cache(maxsize=4)
def _get_cn_market_context_cached(today_iso: str) -> Dict[str, Any]:
    target = dt.date.fromisoformat(today_iso)
    is_open = is_a_share_trading_day(target)
    next_day = get_next_a_share_trading_day(target)
    return {
        "calendar": {
            "today": target.isoformat(),
            "is_trading_day": is_open,
            "next_trading_day": next_day.isoformat() if next_day else None,
        },
        "indices": get_cn_index_snapshots(),
        "northbound": get_cn_northbound_flow(),
    }


def get_cn_market_context(date: Optional[dt.date] = None) -> Dict[str, Any]:
    """Return a small structured market context for analysis and agent tools."""
    return _get_cn_market_context_cached(_coerce_date(date).isoformat())


@lru_cache(maxsize=4)
def list_active_a_share_tickers(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Return active A-share tickers with basic metadata, preferring Tushare."""
    pro = _get_configured_pro_api()
    if pro is None:
        return []

    stock_basic = getattr(pro, "stock_basic", None)
    if stock_basic is None:
        return []

    try:
        df = stock_basic(
            exchange="",
            list_status="L",
            fields="ts_code,symbol,name,market,list_date",
        )
    except Exception as exc:
        logger.debug("Tushare stock universe lookup failed: %s", exc)
        return []

    if df is None or df.empty:
        return []

    rows: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        symbol = str(row.get("symbol") or "").strip().upper()
        name = str(row.get("name") or "").strip()
        if len(symbol) != 6 or not symbol.isdigit() or not name:
            continue

        upper_name = name.upper()
        if upper_name.startswith(("ST", "*ST", "S*ST", "SST")) or "退" in name:
            continue

        rows.append(
            {
                "ticker": symbol,
                "name": name,
                "market": row.get("market") or "A股",
                "list_date": row.get("list_date"),
                "source": "Tushare",
            }
        )

    rows.sort(key=lambda item: item["ticker"])
    if limit and limit > 0:
        return rows[: int(limit)]
    return rows
