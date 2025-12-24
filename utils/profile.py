from __future__ import annotations

from pathlib import Path
from datetime import datetime
import json
from typing import Any, Dict, List, Optional
from uuid import uuid4

PROFILE_PATH = Path("data/profile.json")

DEFAULT_BANKROLL: Dict[str, Any] = {
    "amount": 200.0,
    "strategy": "percent",
    "flat_stake": 5.0,
    "percent": 2.0,
    "kelly_fraction": 0.5,
    "default_odds": 2.0,
    "min_stake": 1.0,
    "max_stake": 100.0,
}

DEFAULT_BANKROLL_PROFILE: Dict[str, Any] = {
    "id": "default",
    "name": "Profil principal",
    "settings": DEFAULT_BANKROLL.copy(),
    "active": True,
}

DEFAULT_INTENSITY_WEIGHTS: Dict[str, float] = {
    "xg": 0.45,
    "over": 0.35,
    "btts": 0.20,
}

DEFAULT_UI_DEFAULTS: Dict[str, Any] = {
    "league_id": None,
    "season": None,
    "bookmakers": [],
    "horizon_days": 1,
}

DEFAULT_AI_PREFERENCES: Dict[str, Any] = {
    "analysis_instruction": "",
    "commentator_instruction": "",
    "commentator_enabled": True,
}

DEFAULT_ALERT_SETTINGS: Dict[str, Any] = {
    "edge_threshold_pct": 7.5,
    "edge_dedup_minutes": 45,
    "cashout_alert_enabled": True,
    "context_alert_enabled": True,
    "cashout_dedup_minutes": 20,
    "channel_slack": True,
    "channel_discord": True,
    "channel_email": False,
    "channel_webhook": False,
    "channel_telegram": False,
    "channel_x": False,
}


DEFAULT_PROFILE: Dict[str, Any] = {
    "custom_bookmakers": [],
    "bankroll": DEFAULT_BANKROLL.copy(),
    "bankroll_profiles": [DEFAULT_BANKROLL_PROFILE.copy()],
    "active_bankroll_profile_id": DEFAULT_BANKROLL_PROFILE["id"],
    "favorite_competitions": [],
    "intensity_weights": DEFAULT_INTENSITY_WEIGHTS.copy(),
    "ui_defaults": DEFAULT_UI_DEFAULTS.copy(),
    "ai_preferences": DEFAULT_AI_PREFERENCES.copy(),
    "alert_settings": DEFAULT_ALERT_SETTINGS.copy(),
    "saved_scenes": [],
}


def _ensure_file() -> None:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not PROFILE_PATH.exists():
        PROFILE_PATH.write_text(json.dumps(DEFAULT_PROFILE, indent=2), encoding="utf-8")


def _generate_profile_id(existing: Optional[set[str]] = None) -> str:
    existing = existing or set()
    while True:
        token = f"br_{uuid4().hex[:8]}"
        if token not in existing:
            return token


def _normalize_bankroll(bankroll: Any) -> Dict[str, Any]:
    normalized = DEFAULT_BANKROLL.copy()
    if isinstance(bankroll, dict):
        for key in normalized:
            value = bankroll.get(key)
            if key == "strategy":
                if isinstance(value, str) and value in {"flat", "percent", "kelly"}:
                    normalized[key] = value
            elif value is not None:
                try:
                    normalized[key] = float(value)
                except (TypeError, ValueError):
                    continue
    normalized["amount"] = max(0.0, normalized.get("amount", 0.0))
    normalized["flat_stake"] = max(0.0, normalized.get("flat_stake", 0.0))
    normalized["percent"] = max(0.0, normalized.get("percent", 0.0))
    normalized["kelly_fraction"] = max(0.0, min(1.0, normalized.get("kelly_fraction", 0.0)))
    normalized["default_odds"] = max(1.01, normalized.get("default_odds", 1.01))
    normalized["min_stake"] = max(0.0, normalized.get("min_stake", 0.0))
    normalized["max_stake"] = max(0.0, normalized.get("max_stake", 0.0))
    if normalized["max_stake"] and normalized["min_stake"] > normalized["max_stake"]:
        normalized["max_stake"] = normalized["min_stake"]
    return normalized


def _normalize_bankroll_profiles(
    raw: Any,
    fallback: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    profiles: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    if isinstance(raw, list):
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            profile_id = str(entry.get("id") or "").strip()
            if not profile_id:
                profile_id = _generate_profile_id(seen_ids)
            if profile_id in seen_ids:
                profile_id = _generate_profile_id(seen_ids)
            seen_ids.add(profile_id)
            profile_name = str(entry.get("name") or "Profil perso").strip() or "Profil perso"
            settings_payload = entry.get("settings") or entry.get("bankroll") or {}
            settings = _normalize_bankroll(settings_payload)
            profiles.append(
                {
                    "id": profile_id,
                    "name": profile_name,
                    "settings": settings,
                    "active": bool(entry.get("active", False)),
                }
            )
    if not profiles:
        base_settings = _normalize_bankroll(fallback or DEFAULT_BANKROLL)
        profiles = [
            {
                "id": DEFAULT_BANKROLL_PROFILE["id"],
                "name": DEFAULT_BANKROLL_PROFILE["name"],
                "settings": base_settings,
                "active": True,
            }
        ]
    if not any(profile.get("active") for profile in profiles):
        profiles[0]["active"] = True
    return profiles


def _active_bankroll_profile(profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not profiles:
        return {
            "id": DEFAULT_BANKROLL_PROFILE["id"],
            "name": DEFAULT_BANKROLL_PROFILE["name"],
            "settings": DEFAULT_BANKROLL.copy(),
            "active": True,
        }
    for entry in profiles:
        if entry.get("active"):
            return entry
    profiles[0]["active"] = True
    return profiles[0]


def _normalize_favorites(raw: Any) -> List[Dict[str, Any]]:
    favorites: List[Dict[str, Any]] = []
    if not isinstance(raw, list):
        return favorites
    for item in raw:
        if not isinstance(item, dict):
            continue
        league_id = item.get("league_id")
        try:
            league_id = int(league_id)
        except (TypeError, ValueError):
            continue
        season = item.get("season")
        try:
            season_value = int(season) if season is not None else None
        except (TypeError, ValueError):
            season_value = None
        favorites.append(
            {
                "league_id": league_id,
                "season": season_value,
                "label": str(item.get("label") or f"Ligue {league_id}"),
                "country": item.get("country") or None,
                "type": item.get("type") or None,
                "categories": [str(cat) for cat in item.get("categories", []) if cat],
                "query": str(item.get("query") or ""),
            }
            )
    return favorites


def _normalize_ui_defaults(raw: Any) -> Dict[str, Any]:
    defaults = DEFAULT_UI_DEFAULTS.copy()
    if isinstance(raw, dict):
        league = raw.get("league_id")
        try:
            defaults["league_id"] = int(league) if league is not None else None
        except (TypeError, ValueError):
            defaults["league_id"] = None
        season = raw.get("season")
        try:
            defaults["season"] = int(season) if season is not None else None
        except (TypeError, ValueError):
            defaults["season"] = None
        bookmakers = raw.get("bookmakers")
        if isinstance(bookmakers, list):
            cleaned: List[str] = []
            for name in bookmakers:
                if not name:
                    continue
                label = str(name)
                if label not in cleaned:
                    cleaned.append(label)
            defaults["bookmakers"] = cleaned
        horizon = raw.get("horizon_days")
        try:
            horizon_int = int(horizon)
        except (TypeError, ValueError):
            horizon_int = 1
        defaults["horizon_days"] = min(30, max(1, horizon_int))
    return defaults


def _normalize_ai_preferences(raw: Any) -> Dict[str, Any]:
    prefs = DEFAULT_AI_PREFERENCES.copy()
    if isinstance(raw, dict):
        analysis_note = raw.get("analysis_instruction")
        prefs["analysis_instruction"] = str(analysis_note).strip() if analysis_note else ""
        commentator_note = raw.get("commentator_instruction")
        prefs["commentator_instruction"] = str(commentator_note).strip() if commentator_note else ""
        prefs["commentator_enabled"] = bool(raw.get("commentator_enabled", prefs["commentator_enabled"]))
    return prefs


def _normalize_alert_settings(raw: Any) -> Dict[str, Any]:
    settings = DEFAULT_ALERT_SETTINGS.copy()
    if isinstance(raw, dict):
        try:
            settings["edge_threshold_pct"] = float(raw.get("edge_threshold_pct", settings["edge_threshold_pct"]))
        except (TypeError, ValueError):
            pass
        try:
            settings["edge_dedup_minutes"] = int(raw.get("edge_dedup_minutes", settings["edge_dedup_minutes"]))
        except (TypeError, ValueError):
            pass
        settings["cashout_alert_enabled"] = bool(
            raw.get("cashout_alert_enabled", settings["cashout_alert_enabled"])
        )
        settings["context_alert_enabled"] = bool(
            raw.get("context_alert_enabled", settings["context_alert_enabled"])
        )
        try:
            settings["cashout_dedup_minutes"] = int(
                raw.get("cashout_dedup_minutes", settings["cashout_dedup_minutes"])
            )
        except (TypeError, ValueError):
            pass
        for key in (
            "channel_slack",
            "channel_discord",
            "channel_email",
            "channel_webhook",
            "channel_telegram",
            "channel_x",
        ):
            if key in raw:
                settings[key] = bool(raw.get(key, settings[key]))
    settings["edge_threshold_pct"] = min(20.0, max(1.0, float(settings["edge_threshold_pct"])))
    settings["edge_dedup_minutes"] = int(min(180, max(5, settings["edge_dedup_minutes"])))
    settings["cashout_dedup_minutes"] = int(min(120, max(5, settings["cashout_dedup_minutes"])))
    return settings


def _normalize_scenes(raw: Any) -> List[Dict[str, Any]]:
    scenes: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        seen_ids: set[str] = set()
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            scene_id = str(entry.get("id") or "").strip()
            if not scene_id or scene_id in seen_ids:
                scene_id = _generate_profile_id(seen_ids)
            seen_ids.add(scene_id)
            name = str(entry.get("name") or f"Scene {len(scenes) + 1}").strip()
            config = entry.get("config")
            if not isinstance(config, dict):
                config = {}
            scenes.append(
                {
                    "id": scene_id,
                    "name": name or f"Scene {len(scenes) + 1}",
                    "config": config,
                    "updated_at": entry.get("updated_at"),
                }
            )
    return scenes


def load_profile() -> Dict[str, Any]:
    _ensure_file()
    try:
        data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return DEFAULT_PROFILE.copy()
        data.setdefault("custom_bookmakers", [])
        custom: List[Dict[str, Any]] = []
        for item in data["custom_bookmakers"]:
            if isinstance(item, dict) and item.get("label"):
                aliases = item.get("aliases") or []
                if isinstance(aliases, list):
                    custom.append(
                        {
                            "label": str(item["label"]),
                            "aliases": [str(alias) for alias in aliases if alias],
                        }
                    )
        data["custom_bookmakers"] = custom
        data["favorite_competitions"] = _normalize_favorites(data.get("favorite_competitions"))
        data["bankroll"] = _normalize_bankroll(data.get("bankroll"))
        data["bankroll_profiles"] = _normalize_bankroll_profiles(
            data.get("bankroll_profiles"),
            fallback=data["bankroll"],
        )
        active_profile = _active_bankroll_profile(data["bankroll_profiles"])
        data["bankroll"] = active_profile["settings"]
        data["active_bankroll_profile_id"] = active_profile["id"]
        data["intensity_weights"] = _normalize_intensity_weights(data.get("intensity_weights"))
        data["ui_defaults"] = _normalize_ui_defaults(data.get("ui_defaults"))
        data["ai_preferences"] = _normalize_ai_preferences(data.get("ai_preferences"))
        data["alert_settings"] = _normalize_alert_settings(data.get("alert_settings"))
        data["saved_scenes"] = _normalize_scenes(data.get("saved_scenes"))
        return data
    except Exception:
        fallback = DEFAULT_PROFILE.copy()
        fallback["bankroll"] = DEFAULT_BANKROLL.copy()
        fallback["bankroll_profiles"] = [DEFAULT_BANKROLL_PROFILE.copy()]
        fallback["active_bankroll_profile_id"] = DEFAULT_BANKROLL_PROFILE["id"]
        fallback["intensity_weights"] = DEFAULT_INTENSITY_WEIGHTS.copy()
        fallback["ui_defaults"] = DEFAULT_UI_DEFAULTS.copy()
        fallback["alert_settings"] = DEFAULT_ALERT_SETTINGS.copy()
        fallback["saved_scenes"] = []
        return fallback


def save_profile(profile: Dict[str, Any]) -> None:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    profile = dict(profile)
    profile["bankroll"] = _normalize_bankroll(profile.get("bankroll"))
    profile["bankroll_profiles"] = _normalize_bankroll_profiles(
        profile.get("bankroll_profiles"),
        fallback=profile["bankroll"],
    )
    requested_active_id = str(profile.get("active_bankroll_profile_id") or "").strip()
    active_entry = None
    for entry in profile["bankroll_profiles"]:
        if requested_active_id:
            entry["active"] = entry["id"] == requested_active_id
        if entry.get("active"):
            active_entry = entry
    if active_entry is None:
        active_entry = _active_bankroll_profile(profile["bankroll_profiles"])
        requested_active_id = active_entry["id"]
        for entry in profile["bankroll_profiles"]:
            entry["active"] = entry["id"] == requested_active_id
    profile["active_bankroll_profile_id"] = requested_active_id
    profile["bankroll"] = active_entry["settings"]
    profile["favorite_competitions"] = _normalize_favorites(profile.get("favorite_competitions"))
    profile["intensity_weights"] = _normalize_intensity_weights(profile.get("intensity_weights"))
    profile["ui_defaults"] = _normalize_ui_defaults(profile.get("ui_defaults"))
    profile["ai_preferences"] = _normalize_ai_preferences(profile.get("ai_preferences"))
    profile["alert_settings"] = _normalize_alert_settings(profile.get("alert_settings"))
    profile["saved_scenes"] = _normalize_scenes(profile.get("saved_scenes"))
    PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")


def get_custom_bookmakers() -> List[Dict[str, Any]]:
    return load_profile().get("custom_bookmakers", [])


def upsert_bookmaker(label: str, aliases: List[str]) -> Dict[str, Any]:
    profile = load_profile()
    custom = profile.setdefault("custom_bookmakers", [])
    normalized = label.strip()
    if not normalized:
        return profile
    aliases_clean = [alias.strip() for alias in aliases if alias.strip()]
    existing = next((item for item in custom if item.get("label", "").lower() == normalized.lower()), None)
    if existing:
        existing["label"] = normalized
        existing["aliases"] = aliases_clean
    else:
        custom.append({"label": normalized, "aliases": aliases_clean})
    save_profile(profile)
    return profile


def delete_bookmaker(label: str) -> Dict[str, Any]:
    profile = load_profile()
    custom = profile.setdefault("custom_bookmakers", [])
    custom = [item for item in custom if item.get("label", "").lower() != label.lower()]
    profile["custom_bookmakers"] = custom
    save_profile(profile)
    return profile


def aliases_map() -> Dict[str, List[str]]:
    mapping: Dict[str, List[str]] = {}
    for item in get_custom_bookmakers():
        mapping[item["label"]] = item.get("aliases", [])
    return mapping


def get_favorite_competitions() -> List[Dict[str, Any]]:
    return load_profile().get("favorite_competitions", [])


def get_ui_defaults() -> Dict[str, Any]:
    profile = load_profile()
    defaults = profile.get("ui_defaults", DEFAULT_UI_DEFAULTS.copy())
    return dict(defaults)


def get_intensity_weights() -> Dict[str, float]:
    profile = load_profile()
    return profile.get("intensity_weights", DEFAULT_INTENSITY_WEIGHTS.copy())


def save_intensity_weights(weights: Dict[str, Any]) -> Dict[str, Any]:
    profile = load_profile()
    profile["intensity_weights"] = _normalize_intensity_weights(weights)
    save_profile(profile)
    return profile


def add_favorite_competition(
    league_id: int,
    season: Optional[int],
    label: str,
    *,
    country: Optional[str] = None,
    comp_type: Optional[str] = None,
    categories: Optional[List[str]] = None,
    query: str = "",
) -> Dict[str, Any]:
    profile = load_profile()
    favorites = profile.setdefault("favorite_competitions", [])
    entry = {
        "league_id": int(league_id),
        "season": int(season) if season is not None else None,
        "label": label,
        "country": country,
        "type": comp_type,
        "categories": [str(cat) for cat in (categories or []) if cat],
        "query": query or "",
    }
    for item in favorites:
        if item.get("league_id") == entry["league_id"] and item.get("season") == entry["season"]:
            item.update(entry)
            break
    else:
        favorites.append(entry)
    save_profile(profile)
    return entry


def remove_favorite_competition(league_id: int, season: Optional[int] = None) -> Dict[str, Any]:
    profile = load_profile()
    favorites = profile.setdefault("favorite_competitions", [])
    profile["favorite_competitions"] = [
        item
        for item in favorites
        if not (item.get("league_id") == league_id and (season is None or item.get("season") == season))
    ]
    save_profile(profile)
    return profile


def list_bankroll_profiles() -> List[Dict[str, Any]]:
    profile = load_profile()
    profiles = profile.get("bankroll_profiles", [])
    serialized: List[Dict[str, Any]] = []
    for entry in profiles:
        clone = dict(entry)
        clone["settings"] = dict(entry.get("settings", {}))
        serialized.append(clone)
    return serialized


def get_bankroll_settings(profile_id: Optional[str] = None) -> Dict[str, Any]:
    profile = load_profile()
    profiles = profile.get("bankroll_profiles", [])
    if profile_id:
        for entry in profiles:
            if entry.get("id") == profile_id:
                payload = dict(entry.get("settings", {}))
                payload.setdefault("profile_id", entry.get("id"))
                payload.setdefault("profile_name", entry.get("name"))
                return payload
    if profiles:
        active_entry = _active_bankroll_profile([dict(entry) for entry in profiles])
        payload = dict(active_entry.get("settings", {}))
        payload.setdefault("profile_id", active_entry.get("id"))
        payload.setdefault("profile_name", active_entry.get("name"))
        return payload
    fallback = dict(profile.get("bankroll", DEFAULT_BANKROLL.copy()))
    fallback.setdefault("profile_id", DEFAULT_BANKROLL_PROFILE["id"])
    fallback.setdefault("profile_name", DEFAULT_BANKROLL_PROFILE["name"])
    return fallback


def get_active_bankroll_profile() -> Dict[str, Any]:
    profiles = list_bankroll_profiles()
    return _active_bankroll_profile([dict(entry) for entry in profiles])


def save_bankroll_settings(settings: Dict[str, Any], profile_id: Optional[str] = None) -> Dict[str, Any]:
    profile = load_profile()
    normalized = _normalize_bankroll(settings)
    target_id = profile_id or profile.get("active_bankroll_profile_id")
    profiles = profile.get("bankroll_profiles", [])
    target_entry = None
    for entry in profiles:
        if entry.get("id") == target_id:
            entry["settings"] = normalized
            target_entry = entry
            break
    if target_entry is None:
        existing_ids = {entry["id"] for entry in profiles}
        target_entry = {
            "id": target_id or _generate_profile_id(existing_ids),
            "name": "Profil perso",
            "settings": normalized,
            "active": False,
        }
        profiles.append(target_entry)
    profile["bankroll_profiles"] = profiles
    if not target_id:
        target_entry["active"] = True
        profile["active_bankroll_profile_id"] = target_entry["id"]
    elif target_entry.get("active"):
        profile["active_bankroll_profile_id"] = target_entry["id"]
    profile["bankroll"] = (
        normalized if target_entry.get("active") else profile.get("bankroll", DEFAULT_BANKROLL.copy())
    )
    save_profile(profile)
    return dict(target_entry["settings"])


def set_active_bankroll_profile(profile_id: str) -> Dict[str, Any]:
    profile = load_profile()
    profiles = profile.get("bankroll_profiles", [])
    found = False
    for entry in profiles:
        if entry.get("id") == profile_id:
            entry["active"] = True
            found = True
        else:
            entry["active"] = False
    if not found:
        raise ValueError(f"Profil bankroll introuvable : {profile_id}")
    profile["bankroll_profiles"] = profiles
    profile["active_bankroll_profile_id"] = profile_id
    save_profile(profile)
    return next(entry for entry in profiles if entry.get("id") == profile_id)


def create_bankroll_profile(
    name: str,
    settings: Optional[Dict[str, Any]] = None,
    *,
    activate: bool = False,
) -> Dict[str, Any]:
    profile = load_profile()
    existing_ids = {entry["id"] for entry in profile.get("bankroll_profiles", [])}
    entry = {
        "id": _generate_profile_id(existing_ids),
        "name": name.strip() or "Profil perso",
        "settings": _normalize_bankroll(settings or profile.get("bankroll")),
        "active": False,
    }
    profile.setdefault("bankroll_profiles", []).append(entry)
    if activate or not profile.get("active_bankroll_profile_id"):
        for other in profile["bankroll_profiles"]:
            other["active"] = other["id"] == entry["id"]
        profile["active_bankroll_profile_id"] = entry["id"]
    save_profile(profile)
    return entry


def rename_bankroll_profile(profile_id: str, new_name: str) -> Dict[str, Any]:
    profile = load_profile()
    profiles = profile.get("bankroll_profiles", [])
    for entry in profiles:
        if entry.get("id") == profile_id:
            entry["name"] = new_name.strip() or entry["name"]
            profile["bankroll_profiles"] = profiles
            save_profile(profile)
            return entry
    raise ValueError(f"Profil bankroll introuvable : {profile_id}")


def delete_bankroll_profile(profile_id: str) -> List[Dict[str, Any]]:
    profile = load_profile()
    profiles = profile.get("bankroll_profiles", [])
    if len(profiles) <= 1:
        raise ValueError("Impossible de supprimer le dernier profil bankroll.")
    filtered = [entry for entry in profiles if entry.get("id") != profile_id]
    if len(filtered) == len(profiles):
        raise ValueError(f"Profil bankroll introuvable : {profile_id}")
    profile["bankroll_profiles"] = filtered
    if profile.get("active_bankroll_profile_id") == profile_id:
        filtered[0]["active"] = True
        profile["active_bankroll_profile_id"] = filtered[0]["id"]
    save_profile(profile)
    return filtered


def save_ui_defaults(defaults: Dict[str, Any]) -> Dict[str, Any]:
    profile = load_profile()
    profile["ui_defaults"] = _normalize_ui_defaults(defaults)
    save_profile(profile)
    return dict(profile["ui_defaults"])


def get_ai_preferences() -> Dict[str, Any]:
    profile = load_profile()
    return profile.get("ai_preferences", DEFAULT_AI_PREFERENCES.copy())


def save_ai_preferences(preferences: Dict[str, Any]) -> Dict[str, Any]:
    profile = load_profile()
    profile["ai_preferences"] = _normalize_ai_preferences(preferences)
    save_profile(profile)
    return dict(profile["ai_preferences"])


def get_alert_settings() -> Dict[str, Any]:
    profile = load_profile()
    return dict(profile.get("alert_settings", DEFAULT_ALERT_SETTINGS.copy()))


def save_alert_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    profile = load_profile()
    profile["alert_settings"] = _normalize_alert_settings(settings)
    save_profile(profile)
    return dict(profile["alert_settings"])


def list_saved_scenes() -> List[Dict[str, Any]]:
    profile = load_profile()
    scenes = profile.get("saved_scenes", [])
    return [dict(scene) for scene in scenes]


def upsert_scene(name: str, config: Dict[str, Any], scene_id: Optional[str] = None) -> Dict[str, Any]:
    profile = load_profile()
    scenes = profile.setdefault("saved_scenes", [])
    target = None
    if scene_id:
        for scene in scenes:
            if scene.get("id") == scene_id:
                target = scene
                break
    if target is None:
        target = {
            "id": scene_id or _generate_profile_id({entry.get("id") for entry in scenes if entry.get("id")}),
            "name": "",
            "config": {},
        }
        scenes.append(target)
    target["name"] = (name or "Scene").strip() or "Scene"
    target["config"] = dict(config or {})
    target["updated_at"] = datetime.utcnow().isoformat()
    profile["saved_scenes"] = scenes
    save_profile(profile)
    return target


def delete_scene(scene_id: str) -> List[Dict[str, Any]]:
    profile = load_profile()
    scenes = profile.get("saved_scenes", [])
    filtered = [scene for scene in scenes if scene.get("id") != scene_id]
    profile["saved_scenes"] = filtered
    save_profile(profile)
    return filtered


__all__ = [
    "load_profile",
    "save_profile",
    "get_custom_bookmakers",
    "upsert_bookmaker",
    "delete_bookmaker",
    "aliases_map",
    "get_favorite_competitions",
    "add_favorite_competition",
    "remove_favorite_competition",
    "list_bankroll_profiles",
    "get_bankroll_settings",
    "save_bankroll_settings",
    "get_active_bankroll_profile",
    "set_active_bankroll_profile",
    "create_bankroll_profile",
    "rename_bankroll_profile",
    "delete_bankroll_profile",
    "DEFAULT_BANKROLL",
    "DEFAULT_BANKROLL_PROFILE",
    "get_intensity_weights",
    "save_intensity_weights",
    "DEFAULT_INTENSITY_WEIGHTS",
    "get_ui_defaults",
    "save_ui_defaults",
    "DEFAULT_UI_DEFAULTS",
    "get_ai_preferences",
    "save_ai_preferences",
    "DEFAULT_AI_PREFERENCES",
    "get_alert_settings",
    "save_alert_settings",
    "DEFAULT_ALERT_SETTINGS",
    "list_saved_scenes",
    "upsert_scene",
    "delete_scene",
]
def _normalize_intensity_weights(raw: Any) -> Dict[str, float]:
    normalized = DEFAULT_INTENSITY_WEIGHTS.copy()
    if isinstance(raw, dict):
        for key in normalized:
            try:
                value = float(raw.get(key, normalized[key]))
            except (TypeError, ValueError):
                value = normalized[key]
            normalized[key] = max(0.0, min(1.0, value))
    total = sum(normalized.values())
    if total <= 0:
        return DEFAULT_INTENSITY_WEIGHTS.copy()
    return {key: value / total for key, value in normalized.items()}
