"""Scratchpad 分析过程日志（Dexter 借鉴）

每次每日分析请求产生一条 JSONL 记录，便于调试、审计与后续 Agent 扩展。
与 Dexter 的 init / llm_call / result 格式对齐，预留 tool_result、thinking。
"""

from __future__ import annotations

import json
import os
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

PREVIEW_MAX = 500


def _default_scratchpad_dir() -> Path:
    raw = os.getenv("SCRATCHPAD_DIR", "data/scratchpad")
    p = Path(raw)
    if not p.is_absolute():
        # 相对路径基于项目根（当前工作目录或上级）
        p = Path.cwd() / p
    return p


def is_scratchpad_enabled() -> bool:
    """根据环境变量 SCRATCHPAD_ENABLED（默认 true）决定是否写入。"""
    val = os.getenv("SCRATCHPAD_ENABLED", "true").strip().lower()
    return val in ("1", "true", "yes", "on")


def _generate_request_id(ticker: str, market: str) -> str:
    """生成请求 ID：日期 + 短 hash。"""
    now = datetime.now()
    date_part = now.strftime("%Y-%m-%d-%H%M%S")
    raw = f"{ticker}_{market}_{date_part}"
    h = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"{date_part}_{h}"


def generate_request_id(ticker: str, market: str) -> str:
    """生成本次分析的 request_id，供 create_scratchpad 使用。"""
    return _generate_request_id(ticker, market)


def _ensure_dir(dir_path: Path) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)


def _append_line(filepath: Path, obj: dict) -> None:
    _ensure_dir(filepath.parent)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def create_scratchpad(
    request_id: str,
    ticker: str,
    market: str,
    text_context_preview: str,
) -> Path:
    """创建本次请求的 scratchpad 文件，写入 init 行。返回 filepath。"""
    base = _default_scratchpad_dir()
    _ensure_dir(base)
    filepath = base / f"{request_id}.jsonl"
    entry = {
        "type": "init",
        "request_id": request_id,
        "timestamp": datetime.now().isoformat(),
        "ticker": ticker,
        "market": market,
        "text_context_preview": (text_context_preview or "")[:PREVIEW_MAX],
    }
    _append_line(filepath, entry)
    return filepath


def append_llm_call(
    filepath: Path,
    model: str,
    prompt_token_estimate: int,
    response_preview: str,
) -> None:
    """追加 llm_call 行。"""
    entry = {
        "type": "llm_call",
        "request_id": None,  # 可从文件名校验
        "timestamp": datetime.now().isoformat(),
        "model": model or "",
        "prompt_token_estimate": prompt_token_estimate,
        "response_preview": (response_preview or "")[:PREVIEW_MAX],
    }
    _append_line(filepath, entry)


def append_result(
    filepath: Path,
    action: str,
    score: Optional[float],
    elapsed_ms: int,
) -> None:
    """追加 result 行。"""
    entry = {
        "type": "result",
        "timestamp": datetime.now().isoformat(),
        "action": action or "",
        "score": score,
        "elapsed_ms": elapsed_ms,
    }
    _append_line(filepath, entry)


def append_tool_result(
    filepath: Path,
    tool_name: str,
    args: dict,
    data_preview: str,
) -> None:
    """追加 tool_result 行，供 Agent 记录工具调用结果摘要。"""
    entry = {
        "type": "tool_result",
        "timestamp": datetime.now().isoformat(),
        "tool_name": tool_name,
        "args": args,
        "data_preview": (data_preview or "")[:PREVIEW_MAX],
    }
    _append_line(filepath, entry)


def append_thinking(filepath: Path, content: str) -> None:
    """追加 thinking 行，记录 LLM 的中间思考。"""
    entry = {
        "type": "thinking",
        "timestamp": datetime.now().isoformat(),
        "content": (content or "")[:PREVIEW_MAX],
    }
    _append_line(filepath, entry)
