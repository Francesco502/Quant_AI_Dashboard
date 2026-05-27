"""Safety guardrails for automatic paper-trading execution."""

from __future__ import annotations

import os


TRUE_VALUES = {"1", "true", "yes", "on"}


def is_auto_trading_allowed() -> bool:
    """Return whether automatic paper trading has been explicitly enabled."""
    return os.getenv("ALLOW_AUTO_TRADING", "").strip().lower() in TRUE_VALUES


def require_auto_trading_allowed() -> None:
    """Raise unless automatic paper trading is explicitly enabled."""
    if not is_auto_trading_allowed():
        raise PermissionError("Automatic paper trading requires ALLOW_AUTO_TRADING=true")
