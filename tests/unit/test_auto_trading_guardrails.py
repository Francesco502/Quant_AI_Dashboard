"""Guardrails for automatic paper-trading scheduling."""

from __future__ import annotations

import core.scheduler as scheduler


class _FakeSchedule:
    def __init__(self) -> None:
        self.registered: list[object] = []

    def every(self, interval: int | None = None):
        return _FakeJob(self.registered, interval)


class _FakeJob:
    def __init__(self, registered: list[object], interval: int | None) -> None:
        self.registered = registered
        self.interval = interval
        self.minutes = self

    def do(self, job):
        self.registered.append(job)
        return job


def test_setup_trading_job_requires_allow_auto_trading(monkeypatch):
    fake_schedule = _FakeSchedule()
    monkeypatch.setattr(scheduler, "SCHEDULE_AVAILABLE", True)
    monkeypatch.setattr(scheduler, "schedule", fake_schedule)
    monkeypatch.delenv("ALLOW_AUTO_TRADING", raising=False)

    scheduler.setup_trading_job({"enabled": True, "interval_minutes": 1}, lambda: None)

    assert fake_schedule.registered == []

    monkeypatch.setenv("ALLOW_AUTO_TRADING", "true")
    scheduler.setup_trading_job({"enabled": True, "interval_minutes": 1}, lambda: None)

    assert len(fake_schedule.registered) == 1
