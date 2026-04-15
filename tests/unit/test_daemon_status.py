import json

from core import daemon


def test_default_config_disables_auto_training_and_auto_trading():
    config = daemon._default_config()

    assert config["training"]["enabled"] is False
    assert config["trading"]["enabled"] is False


def test_load_status_marks_missing_pid_as_not_running(monkeypatch, tmp_path):
    status_path = tmp_path / "daemon_status.json"
    status_path.write_text(
        json.dumps({"daemon_running": True, "daemon_pid": 424242, "last_started_at": "2026-03-31 09:00:00"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(daemon, "STATUS_PATH", str(status_path))
    monkeypatch.setattr(daemon, "_is_pid_running", lambda pid: False)

    status = daemon.load_status()

    assert status["daemon_running"] is False
    assert status["daemon_pid"] == 424242
