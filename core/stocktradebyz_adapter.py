"""Adapter for integrated StockTradebyZ selectors."""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from .data_service import load_ohlcv_data


_core_dir = Path(__file__).resolve().parent
STZ_DIR = _core_dir / "stocktradebyz"
STZ_CONFIG_PATH = STZ_DIR / "configs.json"

stz_selector = None
STOCKTRADEBYZ_AVAILABLE = False
_stz_error = ""

try:
    if str(STZ_DIR) not in sys.path:
        sys.path.append(str(STZ_DIR))
    import Selector as _selector_module  # type: ignore[import]

    stz_selector = _selector_module
    STOCKTRADEBYZ_AVAILABLE = True
except Exception as e:  # pragma: no cover
    _stz_error = str(e)


@dataclass
class SelectorConfig:
    class_name: str
    alias: str
    activate: bool
    params: Dict[str, Any]


def _ensure_available() -> None:
    if not STOCKTRADEBYZ_AVAILABLE or stz_selector is None:
        raise ImportError(
            "StockTradebyZ selector module is unavailable. "
            f"Path={STZ_DIR}. Detail={_stz_error}"
        )


def _load_default_configs() -> List[SelectorConfig]:
    _ensure_available()
    if not STZ_CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config file: {STZ_CONFIG_PATH}")

    with STZ_CONFIG_PATH.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    if isinstance(raw, dict):
        cfgs = raw.get("selectors", [])
    elif isinstance(raw, list):
        cfgs = raw
    else:
        cfgs = []

    result: List[SelectorConfig] = []
    for cfg in cfgs:
        if not isinstance(cfg, dict):
            continue
        class_name = str(cfg.get("class", "")).strip()
        if not class_name:
            continue
        result.append(
            SelectorConfig(
                class_name=class_name,
                alias=str(cfg.get("alias", class_name)),
                activate=bool(cfg.get("activate", True)),
                params=dict(cfg.get("params", {}) or {}),
            )
        )
    return result


def get_default_selector_configs(
    selector_names: Optional[Iterable[str]] = None,
) -> List[SelectorConfig]:
    cfgs = [c for c in _load_default_configs() if c.activate]
    if selector_names is None:
        return cfgs

    wanted = {str(x).strip() for x in selector_names if str(x).strip()}
    if not wanted:
        return cfgs
    return [c for c in cfgs if c.class_name in wanted]


def _instantiate_selector(class_name: str, params: Optional[Dict[str, Any]] = None) -> Any:
    _ensure_available()
    if not hasattr(stz_selector, class_name):  # type: ignore[arg-type]
        raise ValueError(f"Selector class not found: {class_name}")
    cls = getattr(stz_selector, class_name)  # type: ignore[arg-type]
    return cls(**(params or {}))


def _ohlcv_to_stocktradebyz_df(ohlcv: pd.DataFrame) -> pd.DataFrame:
    if ohlcv is None or ohlcv.empty:
        return pd.DataFrame(columns=["date", "open", "close", "high", "low", "volume"])

    df = ohlcv.copy().sort_index()
    if "close" not in df.columns:
        numeric_cols = list(df.select_dtypes(include=[np.number]).columns)
        if numeric_cols:
            df["close"] = df[numeric_cols[0]]
        else:
            return pd.DataFrame(columns=["date", "open", "close", "high", "low", "volume"])

    for col in ["open", "high", "low"]:
        if col not in df.columns:
            df[col] = df["close"]
    if "volume" not in df.columns:
        df["volume"] = 0.0

    out = (
        df[["open", "close", "high", "low", "volume"]]
        .rename_axis("date")
        .reset_index()
    )
    out["date"] = pd.to_datetime(out["date"])
    return out[["date", "open", "close", "high", "low", "volume"]]


def run_selector_for_ticker(
    ohlcv_df: pd.DataFrame,
    selector_name: str,
    params: Optional[Dict[str, Any]] = None,
) -> pd.Series:
    _ensure_available()
    if ohlcv_df is None or ohlcv_df.empty:
        return pd.Series(dtype=bool)

    effective_params = dict(params or {})
    if not effective_params:
        for cfg in _load_default_configs():
            if cfg.class_name == selector_name:
                effective_params = dict(cfg.params)
                break

    selector = _instantiate_selector(selector_name, effective_params)
    df = _ohlcv_to_stocktradebyz_df(ohlcv_df)
    if df.empty:
        return pd.Series(dtype=bool)

    dates = pd.to_datetime(df["date"].values)
    signals: List[bool] = []
    for i in range(len(df)):
        hist = df.iloc[: i + 1].copy()
        if hasattr(selector, "_passes_filters"):
            try:
                ok = bool(selector._passes_filters(hist))  # type: ignore[attr-defined]
            except Exception:
                ok = False
        else:
            ok = False
        signals.append(ok)

    return pd.Series(signals, index=dates, name=f"{selector_name}_signal")


def generate_selector_signals_for_series(
    ohlcv: pd.DataFrame,
    selector_name: str,
    params: Optional[Dict[str, Any]] = None,
    hold_days: int = 5,
) -> pd.Series:
    if ohlcv is None or ohlcv.empty:
        return pd.Series(dtype=int)

    cond = run_selector_for_ticker(ohlcv, selector_name, params)
    if cond is None or cond.empty:
        return pd.Series(0, index=ohlcv.index, dtype=int)

    cond = cond.reindex(ohlcv.index).fillna(False)
    signals = pd.Series(0, index=cond.index, dtype=int)
    in_position = False
    days_in_pos = 0

    for idx, flag in cond.items():
        if not in_position:
            if bool(flag):
                signals.at[idx] = 1
                in_position = True
                days_in_pos = 0
            continue

        days_in_pos += 1
        if hold_days > 0 and days_in_pos >= hold_days:
            signals.at[idx] = -1
            in_position = False
            days_in_pos = 0

    return signals


def _empty_result_df() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "ticker",
            "name",
            "selector_class",
            "selector_alias",
            "trade_date",
            "last_close",
        ]
    )


def _prepare_selector_data(
    ohlcv_map: Dict[str, pd.DataFrame],
    trade_ts: pd.Timestamp,
) -> Dict[str, pd.DataFrame]:
    data: Dict[str, pd.DataFrame] = {}
    for code, ohlcv_df in ohlcv_map.items():
        if ohlcv_df is None or ohlcv_df.empty:
            continue
        stz_df = _ohlcv_to_stocktradebyz_df(ohlcv_df)
        stz_df = stz_df[stz_df["date"] <= trade_ts]
        if stz_df.empty:
            continue
        data[code] = stz_df
    return data


def _run_selectors(
    *,
    trade_ts: pd.Timestamp,
    data: Dict[str, pd.DataFrame],
    selector_names: Optional[List[str]],
    selector_params: Optional[Dict[str, Dict[str, Any]]],
    progress_callback: Optional[Callable[[float, str], None]],
    name_map: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    cfgs = get_default_selector_configs(selector_names)
    if not cfgs:
        return pd.DataFrame()

    selector_params = selector_params or {}
    records: List[Dict[str, Any]] = []
    total = max(len(cfgs), 1)

    def _report(p: float, msg: str) -> None:
        if progress_callback is None:
            return
        try:
            progress_callback(float(p), str(msg))
        except Exception:
            pass

    for idx, cfg in enumerate(cfgs):
        merged_params = dict(cfg.params)
        merged_params.update(selector_params.get(cfg.class_name) or {})

        selector = _instantiate_selector(cfg.class_name, merged_params)
        _report(0.5 + 0.4 * (idx / total), f"Running selector: {cfg.class_name}")

        try:
            picks: List[str] = selector.select(trade_ts, data)  # type: ignore[attr-defined]
        except Exception:
            picks = []

        for code in picks:
            df = data.get(code)
            if df is None or df.empty:
                continue
            last_close = float(df["close"].iloc[-1])
            records.append(
                {
                    "ticker": code,
                    "name": (name_map or {}).get(code, code),
                    "selector_class": cfg.class_name,
                    "selector_alias": cfg.alias,
                    "trade_date": trade_ts.normalize(),
                    "last_close": last_close,
                }
            )

    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).sort_values(["selector_class", "ticker"]).reset_index(drop=True)


def run_selectors_for_universe(
    tickers: List[str],
    trade_date: datetime | str,
    selector_names: Optional[List[str]] = None,
    selector_params: Optional[Dict[str, Dict[str, Any]]] = None,
    *,
    days: int = 365 * 3,
    name_map: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    _ensure_available()
    if not tickers:
        return _empty_result_df()

    trade_ts = pd.to_datetime(trade_date)
    ohlcv_map = load_ohlcv_data(tickers=tickers, days=days)
    if not ohlcv_map:
        return pd.DataFrame()

    data = _prepare_selector_data(ohlcv_map, trade_ts)
    if not data:
        return pd.DataFrame()

    return _run_selectors(
        trade_ts=trade_ts,
        data=data,
        selector_names=selector_names,
        selector_params=selector_params,
        progress_callback=None,
        name_map=name_map,
    )


def run_selectors_for_market(
    trade_date: datetime | str,
    selector_names: Optional[List[str]] = None,
    selector_params: Optional[Dict[str, Dict[str, Any]]] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    market: str = "CN",
) -> pd.DataFrame:
    _ensure_available()
    trade_ts = pd.to_datetime(trade_date)
    market = str(market or "CN").upper()
    if market not in {"CN", "HK"}:
        raise ValueError(f"Unsupported market: {market}")

    def _report(p: float, msg: str) -> None:
        if progress_callback is None:
            return
        try:
            progress_callback(float(p), str(msg))
        except Exception:
            pass

    def _is_cn(code: str) -> bool:
        return bool(re.fullmatch(r"\d{6}(\.(SZ|SS))?", code.upper()))

    def _is_hk(code: str) -> bool:
        uc = code.upper()
        return uc.endswith(".HK") or bool(re.fullmatch(r"\d{5}", uc))

    def _hk_normalize(code: str) -> str:
        uc = code.upper()
        return uc if uc.endswith(".HK") else f"{uc}.HK"

    tickers: List[str] = []

    # Local-first universe from parquet filenames.
    try:
        from .data_store import BASE_DIR

        prices_dir = Path(BASE_DIR) / "prices"
        if prices_dir.exists():
            for fp in prices_dir.rglob("*.parquet"):
                code = fp.stem.strip().upper()
                if not code or code.startswith("."):
                    continue
                if market == "CN" and _is_cn(code):
                    tickers.append(code)
                elif market == "HK" and _is_hk(code):
                    tickers.append(_hk_normalize(code))
    except Exception:
        pass
    tickers = list(dict.fromkeys(tickers))
    if tickers:
        _report(0.02, f"Local {market} universe size: {len(tickers)}")

    # Dynamic market list fallback.
    if not tickers:
        try:
            from .market_scanner import MarketScanner

            rows = MarketScanner().get_market_tickers(market=market)
            for row in rows:
                code = str((row or {}).get("ticker", "")).strip().upper()
                if not code:
                    continue
                if market == "CN" and _is_cn(code):
                    tickers.append(code)
                elif market == "HK" and _is_hk(code):
                    tickers.append(_hk_normalize(code))
            tickers = list(dict.fromkeys(tickers))
            if tickers:
                _report(0.03, f"Remote {market} universe size: {len(tickers)}")
        except Exception:
            tickers = []

    # Legacy CN fallback.
    if not tickers and market == "CN":
        stocklist_path = STZ_DIR / "stocklist.csv"
        if stocklist_path.exists():
            try:
                df_sl = pd.read_csv(stocklist_path)
                for col in ["ts_code", "ticker", "symbol"]:
                    if col not in df_sl.columns:
                        continue
                    codes = df_sl[col].astype(str).str.strip().str.upper()
                    tickers = [c for c in codes if _is_cn(c)]
                    if tickers:
                        break
                tickers = list(dict.fromkeys(tickers))
                if tickers:
                    _report(0.03, f"Legacy CN stocklist size: {len(tickers)}")
            except Exception:
                tickers = []

    if not tickers:
        _report(0.0, f"No tickers found for market={market}")
        return _empty_result_df()

    scan_lookback_days = int(os.getenv("MARKET_SCAN_LOOKBACK_DAYS", "730"))
    scan_lookback_days = max(180, min(scan_lookback_days, 3650))

    _report(
        0.05,
        f"Loading OHLCV for {len(tickers)} symbols from market={market}, lookback_days={scan_lookback_days}...",
    )
    ohlcv_map = load_ohlcv_data(tickers=tickers, days=scan_lookback_days)
    if not ohlcv_map:
        return _empty_result_df()
    _report(0.4, f"Loaded OHLCV for {len(ohlcv_map)} symbols")

    data = _prepare_selector_data(ohlcv_map, trade_ts)
    if not data:
        return _empty_result_df()
    _report(0.5, f"Prepared {len(data)} symbols for selectors")

    result = _run_selectors(
        trade_ts=trade_ts,
        data=data,
        selector_names=selector_names,
        selector_params=selector_params,
        progress_callback=progress_callback,
    )
    _report(1.0, f"Selector run completed with {len(result)} records")
    return result
