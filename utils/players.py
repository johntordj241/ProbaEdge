from __future__ import annotations

from typing import Any, Dict, List, Optional

from .api_calls import (
    get_players as api_get_players,
    get_players_for_team as api_get_players_for_team,
    get_team_squad,
)
from .models import normalize_player_list, PlayerInfo
from .players_registry import get_override_roster


def _player_identity(entry: Dict[str, Any]) -> Optional[str]:
    player_block = (entry or {}).get("player") or {}
    player_id = player_block.get("id")
    if player_id is not None:
        return f"id:{player_id}"
    name = str(player_block.get("name") or "").strip().lower()
    if not name:
        return None
    number = player_block.get("number")
    return f"name:{name}|{number or ''}"


def _merge_entries(primary: List[Dict[str, Any]], supplements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not supplements:
        return primary
    merged = list(primary)
    seen = {identity for identity in (_player_identity(entry) for entry in merged) if identity}
    for entry in supplements:
        identity = _player_identity(entry)
        if not identity or identity in seen:
            continue
        merged.append(entry)
        seen.add(identity)
    return merged


def _squad_entries(team_id: int, payload: Any) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    if not payload:
        return entries
    blocks: List[Dict[str, Any]] = []
    if isinstance(payload, list):
        blocks = [block for block in payload if isinstance(block, dict)]
    elif isinstance(payload, dict):
        blocks = [payload]
    for block in blocks:
        team_block = block.get("team") or {}
        team_meta = {
            "id": team_block.get("id") or team_id,
            "name": team_block.get("name"),
        }
        for player in block.get("players") or []:
            if not isinstance(player, dict):
                continue
            stats_block = player.get("statistics") if isinstance(player.get("statistics"), dict) else {}
            goals_stats = stats_block.get("goals") if isinstance(stats_block, dict) else {}
            entries.append(
                {
                    "player": {
                        "id": player.get("id"),
                        "name": player.get("name"),
                        "age": player.get("age"),
                        "number": player.get("number"),
                        "nationality": player.get("nationality"),
                        "photo": player.get("photo"),
                        "injured": bool(player.get("injured", False)),
                    },
                    "statistics": [
                        {
                            "team": {"id": team_meta["id"], "name": team_meta["name"]},
                            "games": {
                                "appearences": stats_block.get("appearences")
                                if isinstance(stats_block, dict)
                                else player.get("appearences")
                                or player.get("appearances"),
                                "lineups": stats_block.get("lineups") if isinstance(stats_block, dict) else None,
                                "minutes": stats_block.get("minutes") if isinstance(stats_block, dict) else None,
                                "number": player.get("number"),
                                "position": player.get("position"),
                            },
                            "goals": {"total": goals_stats.get("total") if isinstance(goals_stats, dict) else None},
                            "shots": {},
                            "passes": {},
                            "tackles": {},
                            "duels": {},
                            "dribbles": {},
                            "fouls": {},
                            "cards": {},
                            "penalty": {},
                        }
                    ],
                    "meta": {"source": "squad"},
                }
            )
    return entries


def get_players(league_id: int, season: int, team_id: int, *, page: int = 1, normalized: bool = False) -> List[Any]:
    raw = api_get_players(league_id, season, team_id, page=page) or []
    if normalized:
        return normalize_player_list(raw if isinstance(raw, list) else [])
    return raw if isinstance(raw, list) else []


def get_players_normalized(league_id: int, season: int, team_id: int, *, page: int = 1) -> List[PlayerInfo]:
    return get_players(league_id, season, team_id, page=page, normalized=True)


def get_players_enriched(league_id: int, season: int, team_id: int, *, max_pages: int = 6) -> List[PlayerInfo]:
    raw_list = api_get_players_for_team(
        league_id,
        season,
        team_id,
        max_pages=max_pages,
        include_lineup_roster=True,
    )
    raw = raw_list if isinstance(raw_list, list) else []

    try:
        squad_payload = get_team_squad(team_id)
    except Exception:
        squad_payload = []
    if squad_payload:
        raw = _merge_entries(raw, _squad_entries(team_id, squad_payload))

    overrides = get_override_roster(team_id, season)
    if overrides:
        raw = _merge_entries(raw, overrides if isinstance(overrides, list) else [])

    return normalize_player_list(raw)


def get_full_roster(league_id: int, season: int, team_id: int, *, max_pages: int = 6) -> List[PlayerInfo]:
    return get_players_enriched(league_id, season, team_id, max_pages=max_pages)


__all__ = ["get_players", "get_players_normalized", "get_players_enriched", "get_full_roster", "PlayerInfo"]
