from __future__ import annotations

from pathlib import Path
import json
from typing import Any, Dict, List, Optional

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

DEFAULT_PROFILE: Dict[str, Any] = {
    "custom_bookmakers": [],
    "bankroll": DEFAULT_BANKROLL.copy(),
    "favorite_competitions": [],
    "intensity_weights": DEFAULT_INTENSITY_WEIGHTS.copy(),
    "ui_defaults": DEFAULT_UI_DEFAULTS.copy(),
}


def _ensure_file() -> None:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not PROFILE_PATH.exists():
        PROFILE_PATH.write_text(json.dumps(DEFAULT_PROFILE, indent=2), encoding="utf-8")


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
        data["intensity_weights"] = _normalize_intensity_weights(data.get("intensity_weights"))
        data["ui_defaults"] = _normalize_ui_defaults(data.get("ui_defaults"))
        return data
    except Exception:
        fallback = DEFAULT_PROFILE.copy()
        fallback["bankroll"] = DEFAULT_BANKROLL.copy()
        fallback["intensity_weights"] = DEFAULT_INTENSITY_WEIGHTS.copy()
        fallback["ui_defaults"] = DEFAULT_UI_DEFAULTS.copy()
        return fallback


def save_profile(profile: Dict[str, Any]) -> None:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    profile = dict(profile)
    profile["bankroll"] = _normalize_bankroll(profile.get("bankroll"))
    profile["favorite_competitions"] = _normalize_favorites(profile.get("favorite_competitions"))
    profile["intensity_weights"] = _normalize_intensity_weights(profile.get("intensity_weights"))
    profile["ui_defaults"] = _normalize_ui_defaults(profile.get("ui_defaults"))
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


def get_bankroll_settings() -> Dict[str, Any]:
    return load_profile().get("bankroll", DEFAULT_BANKROLL)


def save_bankroll_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    profile = load_profile()
    profile["bankroll"] = _normalize_bankroll(settings)
    save_profile(profile)
    return profile


def save_ui_defaults(defaults: Dict[str, Any]) -> Dict[str, Any]:
    profile = load_profile()
    profile["ui_defaults"] = _normalize_ui_defaults(defaults)
    save_profile(profile)
    return dict(profile["ui_defaults"])


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
    "get_bankroll_settings",
    "save_bankroll_settings",
    "DEFAULT_BANKROLL",
    "get_intensity_weights",
    "save_intensity_weights",
    "DEFAULT_INTENSITY_WEIGHTS",
    "get_ui_defaults",
    "save_ui_defaults",
    "DEFAULT_UI_DEFAULTS",
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
