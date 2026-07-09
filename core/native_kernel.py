"""Optional native acceleration facade with Python fallback."""

from __future__ import annotations

import importlib
import os
from typing import Any

import numpy as np
import pandas as pd


def _load_module() -> Any | None:
    try:
        return importlib.import_module("quant_kernel")
    except Exception:
        return None


def _as_array(rows: pd.DataFrame | dict[str, Any]) -> dict[str, np.ndarray]:
    if isinstance(rows, pd.DataFrame):
        return {col: pd.to_numeric(rows.get(col), errors="coerce").to_numpy(dtype=float) for col in rows.columns}
    return {str(k): np.asarray(v, dtype=float) for k, v in rows.items()}


def score_feature_rows_python(rows: pd.DataFrame | dict[str, Any]) -> np.ndarray:
    arrays = _as_array(rows)
    close = arrays.get("close", np.array([], dtype=float))
    n = len(close)
    if n == 0:
        return np.array([], dtype=float)
    ma20 = arrays.get("ma_20", np.full(n, np.nan))
    ma60 = arrays.get("ma_60", np.full(n, np.nan))
    ret20 = arrays.get("return_20d", np.zeros(n))
    rsi = arrays.get("rsi_14", np.full(n, 50.0))
    vol = arrays.get("volatility_20d", np.zeros(n))
    volume_ratio = arrays.get("volume_ratio_20d", np.ones(n))

    trend = np.where(np.isfinite(ma20) & np.isfinite(ma60) & (ma60 != 0), (ma20 / ma60 - 1.0) * 100.0, 0.0)
    price_vs_ma = np.where(np.isfinite(ma20) & (ma20 != 0), (close / ma20 - 1.0) * 100.0, 0.0)
    momentum = np.nan_to_num(ret20, nan=0.0) * 100.0
    rsi_component = 50.0 - np.abs(np.nan_to_num(rsi, nan=50.0) - 55.0)
    volume_component = np.clip(np.nan_to_num(volume_ratio, nan=1.0), 0.0, 3.0) * 8.0
    volatility_penalty = np.nan_to_num(vol, nan=0.0) * 120.0
    raw = 50.0 + momentum * 1.8 + trend * 1.2 + price_vs_ma * 0.5 + rsi_component * 0.35 + volume_component - volatility_penalty
    return np.clip(raw, 0.0, 100.0)


def score_feature_rows(rows: pd.DataFrame | dict[str, Any]) -> np.ndarray:
    mode = os.getenv("QUANT_NATIVE_KERNEL", "auto").strip().lower()
    if mode in {"0", "false", "off", "python"}:
        return score_feature_rows_python(rows)
    module = _load_module()
    if module is not None and hasattr(module, "score_feature_rows"):
        try:
            return np.asarray(module.score_feature_rows(_as_array(rows)), dtype=float)
        except Exception:
            if mode in {"1", "true", "on", "required"}:
                raise
    return score_feature_rows_python(rows)
