from pathlib import Path

import utils.auth as auth


def test_create_and_authenticate_user(tmp_path, monkeypatch):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    monkeypatch.setattr(auth, "get_secret", lambda name: "")

    created = auth.create_user("Test@Example.com", "secret42", "Test User")
    assert created["email"] == "test@example.com"
    assert users_path.exists()

    authenticated = auth.authenticate_user("test@example.com", "secret42")
    assert authenticated is not None
    assert authenticated["email"] == "test@example.com"

    assert auth.authenticate_user("test@example.com", "badpass") is None


def test_change_password(tmp_path, monkeypatch):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    monkeypatch.setattr(auth, "get_secret", lambda name: "")

    auth.create_user("foo@bar.com", "oldpass", "Foo Bar")
    assert auth.change_password("foo@bar.com", "oldpass", "newpass")
    assert not auth.change_password("foo@bar.com", "wrong", "another")
    assert auth.authenticate_user("foo@bar.com", "newpass")


def test_beta_plan_via_code(tmp_path, monkeypatch):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)

    def fake_get_secret(name):
        if name == auth.BETA_CODES_ENV:
            return "beta-2025"
        return ""

    monkeypatch.setattr(auth, "get_secret", fake_get_secret)

    user = auth.create_user("beta@example.com", "secret42", "Beta User", access_code="beta-2025")
    assert user["plan"] == "beta"


def test_beta_plan_via_domain(tmp_path, monkeypatch):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)

    def fake_get_secret(name):
        if name == auth.BETA_DOMAINS_ENV:
            return "partners.club, example.org"
        return ""

    monkeypatch.setattr(auth, "get_secret", fake_get_secret)

    user = auth.create_user("coach@partners.club", "secret42", "Coach User")
    assert user["plan"] == "beta"
