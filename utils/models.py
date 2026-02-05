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
    shots_total: Optional[float]
    shots_on: Optional[float]
    passes_total: Optional[float]
    passes_key: Optional[float]
    passes_accuracy: Optional[float]
    tackles_total: Optional[float]
    interceptions: Optional[float]
    duels_total: Optional[float]
    duels_won: Optional[float]
    dribbles_attempts: Optional[float]
    dribbles_success: Optional[float]
    fouls_drawn: Optional[float]
    fouls_committed: Optional[float]
    yellow_cards: Optional[int]
    red_cards: Optional[int]
    saves: Optional[float]
    penalties_scored: Optional[float]
    penalties_missed: Optional[float]
    injured: bool
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


def _safe_float(value: Any) -> Optional[float]:
    if value in {None, "", "-", "null"}:
        return None
    try:
        text = str(value).strip().replace(",", ".")
        if text.endswith("%"):
            text = text[:-1]
        return float(text)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value in {None, "", "-", "null"}:
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def normalize_player_entry(entry: Dict[str, Any]) -> Optional[PlayerInfo]:
    player_block = _safe_dict(entry.get("player"))
    stats_list = entry.get("statistics") if isinstance(entry.get("statistics"), list) else []
    stats = stats_list[0] if stats_list else {}
    games = _safe_dict(stats.get("games"))
    goals = _safe_dict(stats.get("goals"))
    team_block = _safe_dict(stats.get("team"))
    shots = _safe_dict(stats.get("shots"))
    passes = _safe_dict(stats.get("passes"))
    tackles = _safe_dict(stats.get("tackles"))
    duels = _safe_dict(stats.get("duels"))
    dribbles = _safe_dict(stats.get("dribbles"))
    fouls = _safe_dict(stats.get("fouls"))
    cards = _safe_dict(stats.get("cards"))
    penalty = _safe_dict(stats.get("penalty"))

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
        shots_total=_safe_float(shots.get("total")),
        shots_on=_safe_float(shots.get("on")),
        passes_total=_safe_float(passes.get("total")),
        passes_key=_safe_float(passes.get("key")),
        passes_accuracy=_safe_float(passes.get("accuracy")),
        tackles_total=_safe_float(tackles.get("total")),
        interceptions=_safe_float(tackles.get("interceptions")),
        duels_total=_safe_float(duels.get("total")),
        duels_won=_safe_float(duels.get("won")),
        dribbles_attempts=_safe_float(dribbles.get("attempts")),
        dribbles_success=_safe_float(dribbles.get("success")),
        fouls_drawn=_safe_float(fouls.get("drawn")),
        fouls_committed=_safe_float(fouls.get("committed")),
        yellow_cards=_safe_int(cards.get("yellow")),
        red_cards=_safe_int(cards.get("red") or cards.get("yellowred")),
        saves=_safe_float(goals.get("saves")),
        penalties_scored=_safe_float(penalty.get("scored")),
        penalties_missed=_safe_float(penalty.get("missed")),
        injured=bool(player_block.get("injured")),
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
