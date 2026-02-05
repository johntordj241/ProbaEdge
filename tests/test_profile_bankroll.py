import json

import pytest

import utils.profile as profile


def _bootstrap_profile(tmp_path, monkeypatch):
    profile_path = tmp_path / "profile.json"
    monkeypatch.setattr(profile, "PROFILE_PATH", profile_path)
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    base = json.loads(json.dumps(profile.DEFAULT_PROFILE))
    profile.save_profile(base)
    return profile_path


def test_create_and_activate_bankroll_profiles(tmp_path, monkeypatch):
    _bootstrap_profile(tmp_path, monkeypatch)
    initial_profiles = profile.list_bankroll_profiles()
    assert len(initial_profiles) == 1
    new_entry = profile.create_bankroll_profile(
        "Test agressif",
        settings={"amount": 1000.0, "strategy": "flat", "flat_stake": 10.0},
        activate=True,
    )
    profiles = profile.list_bankroll_profiles()
    assert len(profiles) == 2
    assert any(entry["id"] == new_entry["id"] for entry in profiles)
    active = profile.get_active_bankroll_profile()
    assert active["id"] == new_entry["id"]
    profile.set_active_bankroll_profile(initial_profiles[0]["id"])
    active_after = profile.get_active_bankroll_profile()
    assert active_after["id"] == initial_profiles[0]["id"]


def test_save_bankroll_settings_scopes_to_selected_profile(tmp_path, monkeypatch):
    _bootstrap_profile(tmp_path, monkeypatch)
    secondary = profile.create_bankroll_profile(
        "Secondaire",
        settings={"amount": 300.0, "strategy": "percent", "percent": 2.0},
        activate=False,
    )
    payload = {
        "amount": 123.0,
        "strategy": "flat",
        "flat_stake": 8.0,
        "percent": 2.0,
        "kelly_fraction": 0.5,
        "default_odds": 2.1,
        "min_stake": 1.0,
        "max_stake": 40.0,
    }
    profile.save_bankroll_settings(payload, profile_id=secondary["id"])
    updated_secondary = profile.get_bankroll_settings(secondary["id"])
    assert pytest.approx(updated_secondary["amount"], 1e-6) == 123.0
    assert updated_secondary["strategy"] == "flat"
    active_profile = profile.get_active_bankroll_profile()
    assert active_profile["id"] != secondary["id"]
    primary_settings = profile.get_bankroll_settings(active_profile["id"])
    assert primary_settings["amount"] == profile.DEFAULT_BANKROLL["amount"]


def test_alert_settings_roundtrip(tmp_path, monkeypatch):
    _bootstrap_profile(tmp_path, monkeypatch)
    defaults = profile.get_alert_settings()
    assert defaults["edge_threshold_pct"] == profile.DEFAULT_ALERT_SETTINGS["edge_threshold_pct"]
    profile.save_alert_settings(
        {
            "edge_threshold_pct": 12.0,
            "edge_dedup_minutes": 15,
            "cashout_alert_enabled": False,
            "context_alert_enabled": False,
            "cashout_dedup_minutes": 10,
        }
    )
    updated = profile.get_alert_settings()
    assert updated["edge_threshold_pct"] == 12.0
    assert updated["edge_dedup_minutes"] == 15
    assert updated["cashout_alert_enabled"] is False
    assert updated["context_alert_enabled"] is False


def test_scene_crud(tmp_path, monkeypatch):
    _bootstrap_profile(tmp_path, monkeypatch)
    assert profile.list_saved_scenes() == []
    config = {
        "league_id": 39,
        "season": 2025,
        "team_id": None,
        "scope": "A venir",
        "limit": 20,
        "highlight_threshold_pts": 6,
        "over_filters_enabled": False,
        "over_thresholds": {},
        "under_filters_enabled": False,
        "under_min_prob": None,
        "under_limit_intensity": False,
        "under_max_intensity": 65,
    }
    created = profile.upsert_scene("Scene test", config)
    assert created["name"] == "Scene test"
    assert profile.list_saved_scenes()
    profile.upsert_scene("Scene edit", {**config, "scope": "Joues"}, scene_id=created["id"])
    updated = next(scene for scene in profile.list_saved_scenes() if scene["id"] == created["id"])
    assert updated["name"] == "Scene edit"
    assert updated["config"]["scope"] == "Joues"
    profile.delete_scene(created["id"])
    assert not profile.list_saved_scenes()
