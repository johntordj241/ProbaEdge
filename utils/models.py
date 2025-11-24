from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


@dataclass
class TeamInfo:
    id: int
    name: str
    country: Optional[str]
    founded: Optional[int]
    code: Optional[str]
    logo: Optional[str]
    venue_name: Optional[str]
    venue_city: Optional[str]
    venue_capacity: Optional[int]
    raw: Dict[str, Any]


@dataclass
class PlayerInfo:
    id: int
    name: str
    age: Optional[int]
    nationality: Optional[str]
    team_id: Optional[int]
    team_name: Optional[str]
    position: Optional[str]
    number: Optional[int]
    appearances: Optional[int]
    lineups: Optional[int]
    minutes: Optional[int]
    rating: Optional[float]
    goals: Optional[int]
    assists: Optional[int]
    raw: Dict[str, Any]


def normalize_team_entry(entry: Dict[str, Any]) -> Optional[TeamInfo]:
    team_block = _safe_dict(entry.get("team"))
    venue_block = _safe_dict(entry.get("venue"))
    team_id = team_block.get("id")
    name = team_block.get("name")
    if team_id is None or name is None:
        return None
    return TeamInfo(
        id=int(team_id),
        name=str(name),
        country=team_block.get("country"),
        founded=team_block.get("founded"),
        code=team_block.get("code"),
        logo=team_block.get("logo"),
        venue_name=venue_block.get("name"),
        venue_city=venue_block.get("city"),
        venue_capacity=venue_block.get("capacity"),
        raw=entry,
    )


def normalize_team_list(entries: Iterable[Dict[str, Any]]) -> List[TeamInfo]:
    normalized: List[TeamInfo] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        team = normalize_team_entry(entry)
        if team:
            normalized.append(team)
    return normalized


def _parse_rating(raw_rating: Any) -> Optional[float]:
    if raw_rating in {None, ""}:
        return None
    try:
        return float(str(raw_rating))
    except (TypeError, ValueError):
        return None


def normalize_player_entry(entry: Dict[str, Any]) -> Optional[PlayerInfo]:
    player_block = _safe_dict(entry.get("player"))
    stats_list = entry.get("statistics") if isinstance(entry.get("statistics"), list) else []
    stats = stats_list[0] if stats_list else {}
    games = _safe_dict(stats.get("games"))
    goals = _safe_dict(stats.get("goals"))
    team_block = _safe_dict(stats.get("team"))

    player_id = player_block.get("id")
    name = player_block.get("name")
    if player_id is None or name is None:
        return None

    rating = _parse_rating(games.get("rating"))
    return PlayerInfo(
        id=int(player_id),
        name=str(name),
        age=player_block.get("age"),
        nationality=player_block.get("nationality"),
        team_id=team_block.get("id"),
        team_name=team_block.get("name"),
        position=games.get("position"),
        number=games.get("number"),
        appearances=games.get("appearences"),
        lineups=games.get("lineups"),
        minutes=games.get("minutes"),
        rating=rating,
        goals=goals.get("total"),
        assists=goals.get("assists"),
        raw=entry,
    )


def normalize_player_list(entries: Iterable[Dict[str, Any]]) -> List[PlayerInfo]:
    normalized: List[PlayerInfo] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        player = normalize_player_entry(entry)
        if player:
            normalized.append(player)
    return normalized

__all__ = [
    "TeamInfo",
    "PlayerInfo",
    "normalize_team_entry",
    "normalize_team_list",
    "normalize_player_entry",
    "normalize_player_list",
]
