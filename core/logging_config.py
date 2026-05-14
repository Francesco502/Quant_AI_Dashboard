"""Structured logging with JSON formatting and correlation-ID support.

Usage:
    from core.logging_config import get_logger, set_correlation_id
    logger = get_logger(__name__)
    logger.info("Order placed", extra={"order_id": "X", "ticker": "600519"})
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def set_correlation_id(request_id: Optional[str] = None) -> str:
    """Set the correlation ID for the current async context. Returns the ID."""
    cid = request_id or uuid.uuid4().hex[:12]
    _correlation_id.set(cid)
    return cid


def get_correlation_id() -> Optional[str]:
    """Return the current correlation ID, or None."""
    return _correlation_id.get()


class JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects with standard fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        cid = get_correlation_id()
        if cid:
            payload["correlation_id"] = cid

        if record.exc_info and record.exc_info[1]:
            payload["error"] = str(record.exc_info[1])

        # Merge any extra dict passed via logger.info(..., extra={...})
        extra = getattr(record, "__dict_extra__", None)
        if isinstance(extra, dict):
            for key, value in extra.items():
                if key not in {"ts", "level", "logger", "msg", "correlation_id", "error"}:
                    payload[key] = value

        return json.dumps(payload, ensure_ascii=False, default=str)


class _ExtraAdapter(logging.LoggerAdapter):
    """LoggerAdapter that passes keyword extras as structured fields."""

    def process(self, msg: Any, kwargs: Dict[str, Any]) -> tuple:
        extra_dict = kwargs.pop("extra", {})
        if extra_dict:
            kwargs["extra"] = {"__dict_extra__": extra_dict}
        return msg, kwargs


def get_logger(name: str) -> _ExtraAdapter:
    """Return a structured logger for the given module name."""
    return _ExtraAdapter(logging.getLogger(name), {})


def configure_root_logger(*, json_output: bool = True, level: int = logging.INFO) -> None:
    """Configure the root logger with JSON formatting (or plain text for dev).

    Call once at application startup.
    """
    root = logging.getLogger()
    root.setLevel(level)

    # Remove any handlers added by uvicorn or other frameworks
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler()
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] %(levelname)-5s %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    root.addHandler(handler)


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def setup_logging() -> None:
    """One-shot logging setup driven by environment variables.

    Set LOG_JSON=false for human-readable console output in development.
    """
    use_json = not _env_flag("LOG_PLAINTEXT")
    configure_root_logger(json_output=use_json)
