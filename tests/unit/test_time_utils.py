from __future__ import annotations

from datetime import timedelta

from core import time_utils


def test_default_timezone_is_asia_shanghai(monkeypatch):
    monkeypatch.delenv("APP_TIMEZONE", raising=False)
    monkeypatch.delenv("TZ", raising=False)

    tz = time_utils.get_app_timezone()

    assert time_utils.get_app_timezone_name() == "Asia/Shanghai"
    assert tz.utcoffset(time_utils.local_now()) == timedelta(hours=8)


def test_app_timezone_override_takes_precedence(monkeypatch):
    monkeypatch.setenv("TZ", "UTC")
    monkeypatch.setenv("APP_TIMEZONE", "Asia/Shanghai")

    assert time_utils.get_app_timezone_name() == "Asia/Shanghai"
