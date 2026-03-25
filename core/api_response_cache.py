"""API 响应文件缓存（Dexter 借鉴）

按 endpoint + params 生成确定性缓存键，存 JSON 文件，带 TTL 与结构校验。
与 MultiLevelCache 并存，不替换现有逻辑。
"""

from __future__ import annotations

import json
import os
import hashlib
import logging
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# 默认 TTL 映射（秒）
DEFAULT_TTL: Dict[str, int] = {
    "prices": 300,
    "ohlcv": 300,
    "market_review": 600,
}


def _cache_dir() -> Path:
    raw = os.getenv("API_CACHE_DIR", "data/api_cache")
    p = Path(raw)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


def is_api_cache_enabled() -> bool:
    """是否启用 API 响应文件缓存。"""
    val = os.getenv("API_RESPONSE_CACHE_ENABLED", "true").strip().lower()
    return val in ("1", "true", "yes", "on")


def get_ttl_seconds(endpoint: str) -> int:
    """根据 endpoint 或环境变量返回 TTL（秒）。"""
    key = f"API_CACHE_TTL_{endpoint.upper().replace('/', '_')}"
    val = os.getenv(key)
    if val is not None:
        try:
            return int(val)
        except ValueError:
            pass
    default = os.getenv("API_CACHE_TTL_SECONDS")
    if default is not None:
        try:
            return int(default)
        except ValueError:
            pass
    return DEFAULT_TTL.get(endpoint, 300)


def _normalize_params(params: dict) -> dict:
    """使 params 可哈希、可 JSON 序列化（排序 key，list 转 tuple 等）。"""
    out: Dict[str, Any] = {}
    for k in sorted(params.keys()):
        v = params[k]
        if isinstance(v, list):
            v = tuple(sorted(str(x) for x in v))
        elif v is None:
            continue
        out[k] = v
    return out


def _build_cache_key(endpoint: str, params: dict) -> str:
    """生成缓存文件相对路径：endpoint/prefix_hash.json。"""
    norm = _normalize_params(params)
    raw = f"{endpoint}?{json.dumps(norm, sort_keys=True)}"
    h = hashlib.md5(raw.encode()).hexdigest()[:12]
    clean_endpoint = endpoint.replace("/", "_").strip("_") or "default"
    ticker = norm.get("ticker") or (norm.get("tickers") and norm["tickers"][0] if norm.get("tickers") else None)
    if ticker is not None:
        prefix = f"{str(ticker).upper()}_"
    else:
        prefix = ""
    return f"{clean_endpoint}/{prefix}{h}.json"


def _is_valid_entry(obj: Any) -> bool:
    """校验是否为合法 CacheEntry 结构。"""
    if not isinstance(obj, dict):
        return False
    return (
        isinstance(obj.get("endpoint"), str)
        and isinstance(obj.get("url", ""), str)
        and isinstance(obj.get("cached_at"), str)
        and "data" in obj
    )


def _make_json_safe(value: Any) -> Any:
    """递归转换为可 JSON 序列化的结构，避免缓存文件写出半截内容。"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _make_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_make_json_safe(v) for v in value]
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()

    # pandas.Timestamp / numpy 标量等常见对象
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    if hasattr(value, "item"):
        try:
            return _make_json_safe(value.item())
        except Exception:
            pass

    return str(value)


def get_cached(endpoint: str, params: dict) -> Optional[dict]:
    """
    若存在且未过期且结构合法，返回 entry["data"]，否则 None。
    若文件损坏则删除并返回 None。
    """
    if not is_api_cache_enabled():
        return None
    key = _build_cache_key(endpoint, params)
    filepath = _cache_dir() / key
    if not filepath.exists():
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            entry = json.load(f)
        if not _is_valid_entry(entry):
            logger.warning("API cache entry invalid structure: %s", filepath)
            filepath.unlink(missing_ok=True)
            return None
        cached_at = datetime.fromisoformat(entry["cached_at"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=timezone.utc)
        ttl = get_ttl_seconds(endpoint)
        if (now - cached_at).total_seconds() > ttl:
            filepath.unlink(missing_ok=True)
            return None
        return entry["data"]
    except Exception as e:
        logger.warning("API cache read error %s: %s", filepath, e)
        filepath.unlink(missing_ok=True)
        return None


def set_cached(endpoint: str, params: dict, data: dict) -> None:
    """写入 JSON 文件，含 endpoint、params、data、cached_at。"""
    if not is_api_cache_enabled():
        return
    key = _build_cache_key(endpoint, params)
    filepath = _cache_dir() / key
    filepath.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "endpoint": endpoint,
        "params": _normalize_params(params),
        "data": data,
        "url": "",
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }
    tmp_path = filepath.with_suffix(f"{filepath.suffix}.tmp")
    try:
        safe_entry = _make_json_safe(entry)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(safe_entry, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, filepath)
    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        logger.warning("API cache write error %s: %s", filepath, e)


def clear_cached(endpoint: Optional[str] = None) -> int:
    """Clear cached API response files.

    Returns the number of deleted cache files.
    """
    cache_root = _cache_dir()
    if not cache_root.exists():
        return 0

    deleted = 0
    if endpoint:
        target_dir = cache_root / endpoint.replace("/", "_").strip("_")
        targets = [target_dir] if target_dir.exists() else []
    else:
        targets = [item for item in cache_root.iterdir() if item.is_dir()]

    for directory in targets:
        for path in directory.rglob("*.json"):
            try:
                path.unlink(missing_ok=True)
                deleted += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("API cache delete error %s: %s", path, exc)
        try:
            directory.rmdir()
        except OSError:
            pass

    return deleted
