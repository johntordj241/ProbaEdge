import utils.supervision as sup


def test_health_snapshot_offline(monkeypatch):
    sup._CALLS.clear()
    sup._QUOTA["limit"] = 100
    sup._QUOTA["remaining"] = 50
    sup._QUOTA["reset"] = None

    monkeypatch.setattr(sup, "cache_stats", lambda: {"offline": True, "offline_reason": "quota"})

    snapshot = sup.health_snapshot()

    assert snapshot["offline"] is True
    assert snapshot["offline_reason"] == "quota"


def test_render_supervision_status_triggers_notification(monkeypatch):
    notifications = []

    def fake_notify(title, message, **kwargs):
        notifications.append((title, message, kwargs))
        return True

    monkeypatch.setattr(sup, "notify_event", fake_notify)

    class DummyContainer:
        def __init__(self):
            self.messages = []

        def info(self, msg, **kwargs):
            self.messages.append(("info", msg))

        def warning(self, msg, **kwargs):
            self.messages.append(("warning", msg))

        def error(self, msg, **kwargs):
            self.messages.append(("error", msg))

    dummy = DummyContainer()
    monkeypatch.setattr(
        sup,
        "health_snapshot",
        lambda: {
            "offline": True,
            "offline_reason": "maintenance",
            "low_quota": False,
            "recent_failures": 0,
            "max_retry": 0,
        },
    )

    sup.render_supervision_status(dummy)

    assert notifications, "notify_event should be called when offline"
    assert notifications[0][0] == "Mode hors ligne detecte"
    assert dummy.messages[0][0] == "error"
