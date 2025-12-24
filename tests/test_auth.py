from pathlib import Path

import utils.auth as auth


def test_create_and_authenticate_user(tmp_path, monkeypatch):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)

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

    auth.create_user("foo@bar.com", "oldpass", "Foo Bar")
    assert auth.change_password("foo@bar.com", "oldpass", "newpass")
    assert not auth.change_password("foo@bar.com", "wrong", "another")
    assert auth.authenticate_user("foo@bar.com", "newpass")
