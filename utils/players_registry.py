from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .supabase_client import get_supabase_client

LOCAL_OVERRIDES_PATH = Path("data/players_overrides.json")
SUPABASE_ROSTER_TABLE = "players_overrides"


def _load_local_overrides() -> Dict[str, Any]:
    if not LOCAL_OVERRIDES_PATH.exists():
        return {}
    try:
        data = json.loads(LOCAL_OVERRIDES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _fetch_supabase_roster(team_id: int, season: int) -> List[Dict[str, Any]]:
    try:
        client = get_supabase_client()
    except Exception:
        return []
    try:
        response = (
            client.table(SUPABASE_ROSTER_TABLE)
            .select("players")
            .eq("team_id", team_id)
            .eq("season", season)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception:
        return []
    rows = response.data or []
    if not rows:
        return []
    payload = rows[0].get("players")
    return payload if isinstance(payload, list) else []


def _fetch_local_roster(team_id: int, season: int) -> List[Dict[str, Any]]:
    store = _load_local_overrides()
    key = f"{team_id}:{season}"
    payload = store.get(key)
    return payload if isinstance(payload, list) else []


def get_override_roster(team_id: int, season: int) -> List[Dict[str, Any]]:
    """
    Retourne les joueurs forces manuellement (Supabase > local JSON) si disponibles.
    """
    roster = _fetch_supabase_roster(team_id, season)
    if roster:
        return roster
    return _fetch_local_roster(team_id, season)


__all__ = ["get_override_roster"]
