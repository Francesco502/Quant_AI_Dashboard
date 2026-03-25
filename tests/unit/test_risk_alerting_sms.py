"""Risk alerting SMS channel tests."""

from __future__ import annotations

from datetime import datetime

from core.risk_alerting import SMSNotifier
from core.risk_types import AlertSeverity, RiskEvent


def _build_event() -> RiskEvent:
    return RiskEvent(
        event_id="evt-1",
        timestamp=datetime(2026, 3, 19, 12, 0, 0),
        event_type="margin_call",
        severity=AlertSeverity.CRITICAL,
        message="账户风险超限",
        symbol="600519",
        details={"level": "critical"},
    )


def test_sms_notifier_disabled_without_required_config():
    notifier = SMSNotifier(api_key="sid", api_secret="token")

    assert notifier.enabled is False
    assert notifier.send(_build_event()) is False


def test_sms_notifier_sends_via_twilio(monkeypatch):
    calls = []

    class DummyResponse:
        def raise_for_status(self):
            return None

    def fake_post(url, data, auth, timeout):
        calls.append({
            "url": url,
            "data": data,
            "auth": auth,
            "timeout": timeout,
        })
        return DummyResponse()

    monkeypatch.setattr("requests.post", fake_post)

    notifier = SMSNotifier(
        api_key="AC123",
        api_secret="secret",
        from_number="+15550000001",
        to_numbers=["+15550000002", "+15550000003"],
    )

    assert notifier.send(_build_event()) is True
    assert len(calls) == 2
    assert calls[0]["url"] == "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages.json"
    assert calls[0]["auth"] == ("AC123", "secret")
    assert calls[0]["data"]["From"] == "+15550000001"
    assert calls[0]["data"]["To"] == "+15550000002"
    assert "margin_call" in calls[0]["data"]["Body"]
