import utils.notifications as notif


def _reset_manager():
    notif._MANAGER = None  # reset singleton


def test_notify_event_without_channels(tmp_path, monkeypatch):
    log_file = tmp_path / "notifications.log"
    monkeypatch.setattr(notif, "LOG_FILE", log_file)
    monkeypatch.setattr(notif, "get_secret", lambda name: "")
    _reset_manager()

    result = notif.notify_event("Titre", "Message test", dedup_key="k1")

    assert result is False
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "Titre" in content


def test_notify_event_with_channels_and_dedup(monkeypatch, tmp_path):
    log_file = tmp_path / "notifications.log"
    monkeypatch.setattr(notif, "LOG_FILE", log_file)
    # Simule un webhook Slack unique
    def fake_get_secret(name):
        if name == "SLACK_WEBHOOK_URL":
            return "https://hooks.slack.test/xyz"
        return ""

    monkeypatch.setattr(notif, "get_secret", fake_get_secret)

    posts = []

    class FakeResponse:
        def raise_for_status(self):
            return None

    def fake_post(url, json, timeout):
        posts.append((url, json))
        return FakeResponse()

    monkeypatch.setattr(notif.requests, "post", fake_post)

    # Contrôle du temps pour la déduplication
    times = [1000, 1005, 2000]

    def fake_time():
        return times.pop(0)

    monkeypatch.setattr(notif.time, "time", fake_time)

    _reset_manager()

    first = notif.notify_event("Edge", "Message", dedup_key="edge_fixture")
    second = notif.notify_event("Edge", "Message", dedup_key="edge_fixture")
    third = notif.notify_event("Edge", "Message", dedup_key="edge_fixture", ttl_seconds=10)

    assert first is True  # premier envoi
    assert second is False  # déduplication (temps insuffisant)
    assert third is True  # TTL expiré (temps avancé)
    assert len(posts) == 2
    assert posts[0][0].startswith("https://hooks.slack.test")
