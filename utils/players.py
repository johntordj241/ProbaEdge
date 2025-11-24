from __future__ import annotations

from typing import Any, List

from .api_calls import get_players as api_get_players
from .models import normalize_player_list, PlayerInfo


def get_players(league_id: int, season: int, team_id: int, *, page: int = 1, normalized: bool = False) -> List[Any]:
    raw = api_get_players(league_id, season, team_id, page=page) or []
    if normalized:
        return normalize_player_list(raw if isinstance(raw, list) else [])
    return raw if isinstance(raw, list) else []


def get_players_normalized(league_id: int, season: int, team_id: int, *, page: int = 1) -> List[PlayerInfo]:
    return get_players(league_id, season, team_id, page=page, normalized=True)

__all__ = ["get_players", "get_players_normalized", "PlayerInfo"]
