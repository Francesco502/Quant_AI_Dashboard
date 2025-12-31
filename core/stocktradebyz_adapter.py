"""StockTradebyZ 战法适配层

职责（第一步）：
- 隔离 `Quant_AI_Dashboard` 与 `abandoned/StockTradebyZ_lab/StockTradebyZ` 之间的依赖；
- 统一使用本项目的 `load_ohlcv_data` 获取 K 线数据，而不是原项目的 CSV / `fetch_kline.py`；
- 提供两个核心接口，供后续在 Streamlit 中集成选股与回测：
  - `run_selector_for_ticker(ohlcv_df, selector_name, params) -> pd.Series[bool]`
  - `run_selectors_for_universe(tickers, trade_date, selector_names, selector_params) -> pd.DataFrame`

当前实现采用“方案 A”：
- 直接 import 原项目的 `Selector.py`，在适配层中构造其所需的 DataFrame 结构：
  `date, open, close, high, low, volume`
- 默认参数从 `configs.json` 读取，可在调用时覆盖。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

import sys
import os

from .data_service import load_ohlcv_data


# ----------------------------------------------------------------------
#  定位 StockTradebyZ 项目与 Selector 模块
# ----------------------------------------------------------------------

# StockTradebyZ 文件已整合到项目内 core/stocktradebyz/ 目录
# 从 core/stocktradebyz_adapter.py 同级目录下的 stocktradebyz 文件夹
_current_file = Path(__file__).resolve()
_core_dir = _current_file.parent  # core 目录
STZ_DIR = _core_dir / "stocktradebyz"  # core/stocktradebyz
STZ_CONFIG_PATH = STZ_DIR / "configs.json"

try:
    if not STZ_DIR.exists():
        raise ImportError(f"StockTradebyZ 目录不存在: {STZ_DIR}")
    
    if str(STZ_DIR) not in sys.path:
        sys.path.append(str(STZ_DIR))
    
    # 检查 scipy 是否可用
    try:
        import scipy  # type: ignore[import]
    except ImportError:
        raise ImportError("scipy 未安装，请运行: pip install scipy")
    
    import Selector as stz_selector  # type: ignore[import]

    STOCKTRADEBYZ_AVAILABLE = True
except Exception as e:  # pragma: no cover - 运行环境中若不存在该项目则简单降级
    stz_selector = None  # type: ignore[assignment]
    STOCKTRADEBYZ_AVAILABLE = False
    # 保存错误信息以便调试
    _stz_error = str(e)


@dataclass
class SelectorConfig:
    """从 configs.json 抽象出来的 Selector 配置"""

    class_name: str
    alias: str
    activate: bool
    params: Dict[str, Any]


def _ensure_available() -> None:
    """确保 StockTradebyZ 代码可用，否则抛出友好异常"""
    if not STOCKTRADEBYZ_AVAILABLE:
        error_msg = (
            f"未找到 StockTradebyZ Selector 模块。\n"
            f"请确认路径 `{STZ_DIR}` 存在，"
            f"并且已安装其依赖（尤其是 scipy）。\n"
        )
        if '_stz_error' in globals():
            error_msg += f"\n详细错误: {_stz_error}"
        raise ImportError(error_msg)


# ----------------------------------------------------------------------
#  配置加载与 Selector 实例化
# ----------------------------------------------------------------------


def _load_default_configs() -> List[SelectorConfig]:
    """从原项目的 configs.json 读取默认 Selector 配置"""
    _ensure_available()
    if not STZ_CONFIG_PATH.exists():
        raise FileNotFoundError(f"未找到 StockTradebyZ 配置文件: {STZ_CONFIG_PATH}")

    import json

    with STZ_CONFIG_PATH.open(encoding="utf-8") as f:
        raw = json.load(f)

    if isinstance(raw, list):
        cfgs = raw
    elif isinstance(raw, dict) and "selectors" in raw:
        cfgs = raw["selectors"]
    else:
        cfgs = [raw]

    result: List[SelectorConfig] = []
    for cfg in cfgs:
        class_name = cfg.get("class")
        if not class_name:
            continue
        alias = cfg.get("alias", class_name)
        activate = cfg.get("activate", True)
        params = cfg.get("params", {}) or {}
        result.append(
            SelectorConfig(
                class_name=class_name,
                alias=alias,
                activate=bool(activate),
                params=dict(params),
            )
        )
    return result


def _instantiate_selector(
    class_name: str, params: Optional[Dict[str, Any]] = None
) -> Any:
    """根据类名与参数实例化 Selector"""
    _ensure_available()
    if not hasattr(stz_selector, class_name):
        raise ValueError(f"StockTradebyZ.Selector 中未找到类: {class_name}")
    cls = getattr(stz_selector, class_name)
    return cls(**(params or {}))


def get_default_selector_configs(
    selector_names: Optional[Iterable[str]] = None,
) -> List[SelectorConfig]:
    """
    获取（并可按类名筛选）默认 Selector 配置。

    参数
    ----
    selector_names:
        类名列表（如 ["BBIKDJSelector", "SuperB1Selector"]）。为 None 时返回所有激活的配置。
    """
    cfgs = _load_default_configs()
    if selector_names is None:
        return [c for c in cfgs if c.activate]

    wanted = {name for name in selector_names}
    return [c for c in cfgs if c.class_name in wanted and c.activate]


def _ohlcv_to_stocktradebyz_df(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """
    将本项目的 OHLCV DataFrame 转换为 StockTradebyZ 期望的结构：
    - index: 任意（不强依赖），我们保持时间顺序即可；
    - columns: 至少包含 ['date', 'open', 'close', 'high', 'low', 'volume']。
    """
    if ohlcv is None or ohlcv.empty:
        return pd.DataFrame(
            columns=["date", "open", "close", "high", "low", "volume"]
        )

    df = ohlcv.copy().sort_index()
    # 确保列存在
    for col in ["open", "high", "low", "close", "volume"]:
        if col not in df.columns:
            df[col] = np.nan

    # 将索引作为 date 列
    df = df[["open", "close", "high", "low", "volume"]].rename_axis("date").reset_index()
    # 列顺序：date, open, close, high, low, volume
    return df[["date", "open", "close", "high", "low", "volume"]]


# ----------------------------------------------------------------------
#  从 StockTradebyZ 本地 CSV 仓库加载全市场行情
# ----------------------------------------------------------------------


def _load_market_data_from_csv() -> Dict[str, pd.DataFrame]:
    """
    从 StockTradebyZ 项目的 ./data 目录加载全市场日线行情。

    要求：
    - 你已经在 StockTradebyZ 项目里运行过 fetch_kline.py，将 A 股日线写入 data 目录；
    - 每个 CSV 的列至少包含：date, open, close, high, low, volume。
    """
    _ensure_available()
    data_dir = STZ_DIR / "data"
    if not data_dir.exists():
        raise FileNotFoundError(
            f"未找到 StockTradebyZ 数据目录: {data_dir}。请先在该项目中运行 fetch_kline.py 抓取日线行情。"
        )

    frames: Dict[str, pd.DataFrame] = {}
    for fp in sorted(data_dir.glob("*.csv")):
        code = fp.stem
        try:
            df = pd.read_csv(fp, parse_dates=["date"])
            if "date" not in df.columns:
                continue
            df = df.sort_values("date")
            # 仅保留必要列，其他列暂不使用
            needed_cols = ["date", "open", "close", "high", "low", "volume"]
            for c in needed_cols:
                if c not in df.columns:
                    # 缺失关键列时跳过该标的
                    break
            else:
                frames[code] = df[needed_cols].copy()
        except Exception:
            continue

    return frames


# ----------------------------------------------------------------------
#  对单只股票生成“逐日战法信号”——为后续回测做准备
# ----------------------------------------------------------------------


def run_selector_for_ticker(
    ohlcv_df: pd.DataFrame,
    selector_name: str,
    params: Optional[Dict[str, Any]] = None,
) -> pd.Series:
    """
    对单只股票运行指定 Selector，返回“逐日是否满足条件”的布尔序列。

    实现方式：
    - 使用本项目的 OHLCV 数据（参数 ohlcv_df）；
    - 按时间顺序遍历每个交易日，将该日前所有历史传入 Selector 的内部 `_passes_filters`，
      与原项目的逻辑保持尽量一致；
    - 适合在回测中将战法转为交易信号。
    """
    _ensure_available()

    if ohlcv_df is None or ohlcv_df.empty:
        return pd.Series(dtype=bool)

    # 若未显式给出参数，则从默认 configs.json 中加载一份
    effective_params = dict(params or {})
    if not effective_params:
        for cfg in _load_default_configs():
            if cfg.class_name == selector_name:
                effective_params = dict(cfg.params)
                break

    selector = _instantiate_selector(selector_name, effective_params)

    df = _ohlcv_to_stocktradebyz_df(ohlcv_df)
    dates = pd.to_datetime(df["date"].values)

    signals: List[bool] = []

    # 逐日构造历史窗口，调用 Selector 内部的 _passes_filters
    for i in range(len(df)):
        hist = df.iloc[: i + 1].copy()
        # 各 Selector 自身会检查样本量是否足够
        if hasattr(selector, "_passes_filters"):
            try:
                ok = bool(selector._passes_filters(hist))  # type: ignore[attr-defined]
            except Exception:
                ok = False
        else:
            ok = False
        signals.append(ok)

    return pd.Series(signals, index=dates, name=f"{selector_name}_signal")


# ----------------------------------------------------------------------
#  单资产：基于 Selector 生成用于回测的交易信号
# ----------------------------------------------------------------------


def generate_selector_signals_for_series(
    ohlcv: pd.DataFrame,
    selector_name: str,
    params: Optional[Dict[str, Any]] = None,
    hold_days: int = 5,
) -> pd.Series:
    """
    将单只股票上的 Z 战法 Selector 转换为用于回测的交易信号序列。

    约定：
    - 1 = 建仓/加仓信号（当天触发战法，且当前无持仓时发出一次买入信号）；
    - -1 = 清仓信号（持仓满 hold_days 天后，在当日发出一次卖出信号）；
    - 0 = 无操作。

    这是一个“简单入场 + 固定持有期退出”的基础模型，后续可根据需要扩展更精细的出场逻辑。
    """
    if ohlcv is None or ohlcv.empty:
        return pd.Series(dtype=int)

    # 先获取逐日“是否满足战法条件”的布尔序列
    cond = run_selector_for_ticker(ohlcv, selector_name, params)
    if cond is None or cond.empty:
        return pd.Series(0, index=ohlcv.index, dtype=int)

    # 对齐到完整 OHLCV 索引（某些日期可能因缺失被 cond 跳过）
    cond = cond.reindex(ohlcv.index).fillna(False)

    signals = pd.Series(0, index=cond.index, dtype=int)
    in_position = False
    days_in_pos = 0

    for idx, flag in cond.items():
        if not in_position:
            if bool(flag):
                # 仅在当前无持仓且当日满足战法条件时发出买入信号
                signals.at[idx] = 1
                in_position = True
                days_in_pos = 0
            else:
                signals.at[idx] = 0
        else:
            # 已有持仓，计数持有天数
            days_in_pos += 1
            if hold_days > 0 and days_in_pos >= hold_days:
                # 达到持有期限，发出一次性卖出信号并清仓
                signals.at[idx] = -1
                in_position = False
                days_in_pos = 0
            else:
                signals.at[idx] = 0

    return signals


# ----------------------------------------------------------------------
#  对多只股票 + 多个 Selector 在某个交易日进行选股
# ----------------------------------------------------------------------


def run_selectors_for_universe(
    tickers: List[str],
    trade_date: datetime | str,
    selector_names: Optional[List[str]] = None,
    selector_params: Optional[Dict[str, Dict[str, Any]]] = None,
    *,
    days: int = 365 * 3,
    name_map: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    """
    在指定交易日，对一篮子标的运行一个或多个 StockTradebyZ Selector，返回选股结果表。

    参数
    ----
    tickers:
        待选股的标的列表（通常为 A 股 / 基金代码，如 '600519.SS' 等）。
    trade_date:
        交易日，可以是 str / datetime / pandas.Timestamp。
    selector_names:
        Selector 类名列表；若为 None，则使用 configs.json 中所有 activate=true 的 Selector。
    selector_params:
        形如 {"BBIKDJSelector": {...}, "SuperB1Selector": {...}} 的参数覆盖字典。
        未给出的类名将使用默认配置。
    days:
        从 trade_date 往前回看多少天用于构建历史窗口（默认约 3 年）。
    name_map:
        可选的代码->名称映射，用于结果表中展示中文名。

    返回
    ----
    pd.DataFrame，列包含：
    - ticker         代码
    - name           可选显示名称
    - selector_class Selector 类名
    - selector_alias 中文别名（如 “少妇战法”）
    - trade_date     交易日
    - last_close     当日收盘价
    """
    _ensure_available()

    if not tickers:
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

    trade_ts = pd.to_datetime(trade_date)

    # 1) 先加载 OHLCV 数据（统一入口），再转换为 StockTradebyZ 期望的结构
    ohlcv_map = load_ohlcv_data(tickers=tickers, days=days)
    if not ohlcv_map:
        return pd.DataFrame()

    data: Dict[str, pd.DataFrame] = {}
    for t, df in ohlcv_map.items():
        if df is None or df.empty:
            continue
        stz_df = _ohlcv_to_stocktradebyz_df(df)
        # 仅保留 trade_date 之前的历史
        stz_df = stz_df[stz_df["date"] <= trade_ts]
        if stz_df.empty:
            continue
        data[t] = stz_df

    if not data:
        return pd.DataFrame()

    # 2) 准备 Selector 配置
    cfgs = get_default_selector_configs(selector_names)
    if not cfgs:
        return pd.DataFrame()

    selector_params = selector_params or {}

    records: List[Dict[str, Any]] = []

    for cfg in cfgs:
        base_params = dict(cfg.params)
        override = selector_params.get(cfg.class_name) or {}
        base_params.update(override)

        selector = _instantiate_selector(cfg.class_name, base_params)
        # 调用原生 select 接口：select(trade_date, data_dict)
        try:
            picks: List[str] = selector.select(trade_ts, data)  # type: ignore[attr-defined]
        except Exception:
            picks = []

        for code in picks:
            df = data.get(code)
            if df is None or df.empty:
                continue
            # 取当日最后一根 K 线的收盘价
            last_row = df.iloc[-1]
            last_close = float(last_row["close"])

            records.append(
                {
                    "ticker": code,
                    "name": (name_map or {}).get(code, code) if name_map else code,
                    "selector_class": cfg.class_name,
                    "selector_alias": cfg.alias,
                    "trade_date": trade_ts.normalize(),
                    "last_close": last_close,
                }
            )

    if not records:
        return pd.DataFrame()

    result = pd.DataFrame(records).sort_values(
        ["selector_class", "ticker"]
    ).reset_index(drop=True)
    return result


def run_selectors_for_market(
    trade_date: datetime | str,
    selector_names: Optional[List[str]] = None,
    selector_params: Optional[Dict[str, Dict[str, Any]]] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> pd.DataFrame:
    """
    使用全 A 股股票清单 + 本项目的 OHLCV 数据接口，在指定交易日运行一个或多个战法选股。

    逻辑说明：
    - 优先从本地 Parquet 仓库加载 OHLCV（`load_ohlcv_data`）；
    - 若本地不存在，则自动从远程数据源（AkShare / Tushare / Binance / AlphaVantage / yfinance）抓取并写入本地；
    - 选股使用 StockTradebyZ 的 Selector 实现，与其原 CLI 行为保持一致。
    """
    _ensure_available()

    def _report(progress: float, message: str) -> None:
        if progress_callback is not None:
            try:
                progress_callback(float(progress), str(message))
            except Exception:
                # 回调出错时静默忽略，避免影响主逻辑
                pass
    trade_ts = pd.to_datetime(trade_date)

    # 1) 获取 A 股股票池：优先从本地 parquet 数据目录扫描，备选 stocklist.csv
    tickers: List[str] = []
    
    # 方案 A：从本地 parquet 数据目录扫描（推荐，使用重写后的数据存储）
    try:
        from .data_store import BASE_DIR
        a_stock_dir = Path(BASE_DIR) / "prices" / "A股"
        if a_stock_dir.exists():
            parquet_files = list(a_stock_dir.glob("*.parquet"))
            for pf in parquet_files:
                # 从文件名提取 ticker（去掉 .parquet 后缀）
                ticker = pf.stem
                # 过滤掉明显不是股票代码的文件
                if ticker and not ticker.startswith("."):
                    tickers.append(ticker)
            if tickers:
                _report(0.02, f"从本地数据目录扫描到 {len(tickers)} 只 A 股股票")
    except Exception as e:
        # 如果扫描失败，继续尝试 stocklist.csv
        pass
    
    # 方案 B：从 stocklist.csv 读取（备选）
    if not tickers:
        stocklist_path = STZ_DIR / "stocklist.csv"
        if stocklist_path.exists():
            try:
                df_sl = pd.read_csv(stocklist_path)
                for col in ["ts_code", "ticker", "symbol"]:
                    if col in df_sl.columns:
                        codes = df_sl[col].astype(str).str.strip()
                        tickers = [c for c in codes if c]
                        break
                if tickers:
                    _report(0.02, f"从 stocklist.csv 解析到 {len(tickers)} 只股票")
            except Exception:
                tickers = []
    
    if not tickers:
        # 如果股票池为空，则直接返回空结果表
        _report(0.0, "未找到股票池，请确保数据目录中有 A 股 parquet 文件或存在 stocklist.csv")
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

    _report(0.05, f"已从 stocklist.csv 解析到 {len(tickers)} 只股票，开始加载行情数据...")

    # 2) 通过 load_ohlcv_data 自动加载/拉取 OHLCV（本地优先，远程兜底）
    # 为保证战法计算有足够历史，这里统一抓取约 10 年窗口
    alpha_vantage_key = os.getenv("ALPHA_VANTAGE_KEY", None)
    tushare_token = os.getenv("TUSHARE_TOKEN", None)

    ohlcv_map = load_ohlcv_data(
        tickers=tickers,
        days=3650,
        data_sources=None,
        alpha_vantage_key=alpha_vantage_key,
        tushare_token=tushare_token,
    )
    if not ohlcv_map:
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

    _report(
        0.4,
        f"行情加载完成，共 {len(ohlcv_map)} 只股票获取到有效 OHLCV 数据，正在构建战法所需的 K 线结构...",
    )

    # 3) 将 OHLCV 映射为 StockTradebyZ 期望的 {code: DataFrame(date, open, close, high, low, volume)}
    data: Dict[str, pd.DataFrame] = {}
    for code, ohlcv_df in ohlcv_map.items():
        if ohlcv_df is None or ohlcv_df.empty:
            continue
        stz_df = _ohlcv_to_stocktradebyz_df(ohlcv_df)
        stz_df = stz_df[stz_df["date"] <= trade_ts]
        if stz_df.empty:
            continue
        data[code] = stz_df

    if not data:
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

    _report(0.5, f"K 线预处理完成，共 {len(data)} 只股票可用于战法运算，开始运行各个战法筛选...")

    # 4) 运行战法选股
    cfgs = get_default_selector_configs(selector_names)
    if not cfgs:
        return pd.DataFrame()

    selector_params = selector_params or {}
    records: List[Dict[str, Any]] = []

    total_selectors = len(cfgs)

    for idx, cfg in enumerate(cfgs):
        base_params = dict(cfg.params)
        override = selector_params.get(cfg.class_name) or {}
        base_params.update(override)

        selector = _instantiate_selector(cfg.class_name, base_params)

        _report(
            0.5 + 0.4 * (idx / max(total_selectors, 1)),
            f"正在运行战法：{cfg.alias}（{cfg.class_name}）...",
        )

        try:
            picks: List[str] = selector.select(trade_ts, data)  # type: ignore[attr-defined]
        except Exception:
            picks = []

        for code in picks:
            df = data.get(code)
            if df is None or df.empty:
                continue

            hist = df[df["date"] <= trade_ts]
            if hist.empty:
                continue

            last_close = float(hist["close"].iloc[-1])
            records.append(
                {
                    "ticker": code,
                    "name": code,  # 暂无名称映射，直接使用代码
                    "selector_class": cfg.class_name,
                    "selector_alias": cfg.alias,
                    "trade_date": trade_ts.normalize(),
                    "last_close": last_close,
                }
            )

    if not records:
        _report(1.0, "战法运行完成，本次未找到任何符合条件的股票。")
        return pd.DataFrame()

    result = pd.DataFrame(records).sort_values(
        ["selector_class", "ticker"]
    ).reset_index(drop=True)

    _report(1.0, f"战法运行完成，共选出 {len(result)} 条信号记录。")
    return result



