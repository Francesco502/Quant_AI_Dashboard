"""Application-local time helpers."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_APP_TIMEZONE = "Asia/Shanghai"


def get_app_timezone_name() -> str:
    for key in ("APP_TIMEZONE", "TZ"):
        value = (os.getenv(key) or "").strip()
        if value:
            return value
    return DEFAULT_APP_TIMEZONE


def get_app_timezone():
    tz_name = get_app_timezone_name()
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        if tz_name == DEFAULT_APP_TIMEZONE:
            return timezone(timedelta(hours=8))
        return timezone.utc


def local_now() -> datetime:
    return datetime.now(get_app_timezone())


def local_now_iso(timespec: str = "seconds") -> str:
    return local_now().isoformat(timespec=timespec)


def local_now_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    return local_now().strftime(fmt)


def local_today_str() -> str:
    return local_now().strftime("%Y-%m-%d")
