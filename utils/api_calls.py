from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

import requests
import time
import unicodedata
from random import uniform

from .config import BASE_URL, get_headers
from .cache import (
    load_cache,
    save_cache,
    CacheResult,
    is_offline_mode,
    set_offline_mode,
    maybe_auto_resume_offline,
)
from .supervision import record_api_call

Json = Union[Dict[str, Any], List[Dict[str, Any]], None]

MAX_RETRIES = 3
RETRYABLE_STATUS = {500, 502, 503, 504, 429}
BACKOFF_BASE = 0.6
BACKOFF_MAX_JITTER = 0.3

CACHE_TTL: Dict[str, int] = {
    "fixtures": 120,
    "fixtures/statistics": 45,
    "fixtures/events": 30,
    "fixtures/lineups": 45,
    "standings": 600,
    "teams/statistics": 600,
    "players": 600,
    "players/topscorers": 300,
    "players/topassists": 300,
    "players/topyellowcards": 300,
    "players/topredcards": 300,
    "odds": 60,
    "odds/live": 30,
    "odds/bookmakers": 7200,
    "fixtures/headtohead": 600,
    "predictions": 120,
    "leagues": 7200,
    "teams": 7200,
}



def _sleep_backoff(attempt: int) -> None:
    delay = BACKOFF_BASE * (2 ** (attempt - 1))
    jitter = uniform(0, BACKOFF_MAX_JITTER)
    time.sleep(delay + jitter)


def _request(path: str, params: Dict[str, Any], *, force_refresh: bool = False) -> Json:
    url = f"{BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    cleaned_params = {key: params[key] for key in params if params[key] is not None}
    start = time.perf_counter()

    maybe_auto_resume_offline()

    ttl = CACHE_TTL.get(path, 0)
    cache_entry: Optional[CacheResult] = None
    if ttl:
        cache_entry = load_cache(path, cleaned_params, ttl)
        if cache_entry and not cache_entry.is_expired and not force_refresh:
            duration = time.perf_counter() - start
            record_api_call(
                path,
                params=cleaned_params,
                duration=duration,
                status_code=200,
                success=True,
                source="cache",
                cache_hit=True,
            )
            return cache_entry.data

    offline = is_offline_mode()
    if offline:
        if cache_entry and cache_entry.data is not None:
            record_api_call(
                path,
                params=cleaned_params,
                duration=time.perf_counter() - start,
                status_code=200,
                success=True,
                source="offline-cache",
                cache_hit=True,
            )
            return cache_entry.data
        record_api_call(
            path,
            params=cleaned_params,
            duration=time.perf_counter() - start,
            status_code=None,
            success=False,
            source="offline",
            error="Mode hors ligne actif",
        )
        return None

    attempts = 0
    last_error: Optional[str] = None
    last_status: Optional[int] = None
    quota_limit = quota_remaining = quota_reset = None

    while attempts < MAX_RETRIES:
        attempts += 1
        try:
            resp = requests.get(
                url,
                headers=get_headers(),
                params=cleaned_params,
                timeout=20,
            )
            duration = time.perf_counter() - start
            quota_limit = resp.headers.get("x-ratelimit-requests-limit")
            quota_remaining = resp.headers.get("x-ratelimit-requests-remaining")
            quota_reset = resp.headers.get("x-ratelimit-requests-reset")

            if resp.status_code == 200:
                data = resp.json()
                response_payload = data.get("response", data)
                if ttl:
                    save_cache(path, cleaned_params, response_payload, ttl)
                try:
                    remaining_int = int(quota_remaining) if quota_remaining not in {None, ""} else None
                except (TypeError, ValueError):
                    remaining_int = None
                if remaining_int is not None and remaining_int <= 0:
                    set_offline_mode(True, reason="quota", resume_in=600)
                record_api_call(
                    path,
                    params=cleaned_params,
                    duration=duration,
                    status_code=resp.status_code,
                    success=True,
                    source="network",
                    cache_hit=False,
                    quota_limit=quota_limit,
                    quota_remaining=quota_remaining,
                    quota_reset=quota_reset,
                    retries=attempts - 1,
                )
                return response_payload

            last_status = resp.status_code
            should_retry = resp.status_code in RETRYABLE_STATUS and attempts < MAX_RETRIES
            if resp.status_code in {402, 403, 429} and not should_retry:
                set_offline_mode(True, reason="quota", resume_in=600)
            last_error = resp.text[:200]
            if should_retry:
                _sleep_backoff(attempts)
                continue

            record_api_call(
                path,
                params=cleaned_params,
                duration=duration,
                status_code=resp.status_code,
                success=False,
                source="network",
                error=last_error,
                quota_limit=quota_limit,
                quota_remaining=quota_remaining,
                quota_reset=quota_reset,
                retries=attempts - 1,
            )
            if cache_entry and cache_entry.data is not None:
                record_api_call(
                    path,
                    params=cleaned_params,
                    duration=0.0,
                    status_code=resp.status_code,
                    success=True,
                    source="cache-fallback",
                    cache_hit=True,
                    retries=attempts - 1,
                )
                return cache_entry.data
            return None
        except Exception as exc:  # pragma: no cover
            last_error = str(exc)
            if attempts < MAX_RETRIES:
                _sleep_backoff(attempts)
                continue
            duration = time.perf_counter() - start
            set_offline_mode(True, reason="network", resume_in=180)
            record_api_call(
                path,
                params=cleaned_params,
                duration=duration,
                status_code=last_status,
                success=False,
                source="network",
                error=last_error,
                quota_limit=quota_limit,
                quota_remaining=quota_remaining,
                quota_reset=quota_reset,
                retries=attempts - 1,
            )
            if cache_entry and cache_entry.data is not None:
                record_api_call(
                    path,
                    params=cleaned_params,
                    duration=0.0,
                    status_code=last_status,
                    success=True,
                    source="cache-fallback",
                    cache_hit=True,
                    retries=attempts - 1,
                )
                return cache_entry.data
            return None



def get_fixtures(
    league_id: int,
    season: int,
    team_id: Optional[int] = None,
    venue: Optional[str] = None,
    next_n: Optional[int] = None,
    last_n: Optional[int] = None,
    status: Optional[str] = None,
    live: Optional[str] = None,
) -> Json:
    params: Dict[str, Any] = {"league": league_id, "season": season}
    if team_id:
        params["team"] = team_id
    if venue in {"home", "away"}:
        params["venue"] = venue
    if next_n:
        params["next"] = next_n
    if last_n:
        params["last"] = last_n
    if status:
        params["status"] = status
    if live:
        params["live"] = live
    return _request("fixtures", params)


def get_fixtures_by_date(
    date: str,
    *,
    timezone: str = "UTC",
    league_id: Optional[int] = None,
) -> Json:
    params: Dict[str, Any] = {"date": date, "timezone": timezone}
    if league_id:
        params["league"] = league_id
    return _request("fixtures", params)



def get_fixture_details(fixture_id: int) -> Json:
    return _request("fixtures", {"id": fixture_id})


def get_fixture_statistics(fixture_id: int) -> Json:
    return _request("fixtures/statistics", {"fixture": fixture_id})


def get_fixture_events(fixture_id: int) -> Json:
    return _request("fixtures/events", {"fixture": fixture_id})


def get_lineups(fixture_id: int) -> Json:
    return _request("fixtures/lineups", {"fixture": fixture_id})


def get_leagues(
    country: Optional[str] = None,
    season: Optional[int] = None,
    current_only: bool = False,
) -> Json:
    params: Dict[str, Any] = {}
    if country:
        params["country"] = country
    if season:
        params["season"] = season
    if current_only:
        params["current"] = 1
    return _request("leagues", params)



def get_standings(league_id: int, season: int) -> Json:
    return _request("standings", {"league": league_id, "season": season})



def get_teams(league_id: int, season: int) -> Json:
    return _request("teams", {"league": league_id, "season": season})



def get_players(league_id: int, season: int, team_id: int, page: int = 1) -> Json:
    params = {"league": league_id, "season": season, "team": team_id, "page": page}
    return _request("players", params)



def get_players_for_team(
    league_id: int,
    season: int,
    team_id: Optional[int],
    *,
    max_pages: int = 3,
    include_lineup_roster: bool = True,
) -> List[Dict[str, Any]]:
    """Fetch players for a team across several pages (20 players per page)."""
    if not team_id:
        return []
    collected: List[Dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        chunk = get_players(league_id, season, team_id, page=page)
        if not isinstance(chunk, list) or not chunk:
            break
        collected.extend(chunk)
        if len(chunk) < 20:
            break
    if include_lineup_roster:
        try:
            lineup_players = _lineup_roster_for_team(league_id, season, team_id)
        except Exception:
            lineup_players = []
        if lineup_players:
            collected = _merge_rosters(collected, lineup_players)
    return collected


def get_team_squad(team_id: Optional[int]) -> Json:
    """
    Liste officielle des joueurs enregistres pour un club (endpoint players/squads).
    """
    if not team_id:
        return []
    return _request("players/squads", {"team": team_id})


def get_statistics(league_id: int, season: int, team_id: int) -> Json:
    params = {"league": league_id, "season": season, "team": team_id}
    return _request("teams/statistics", params)



def get_topscorers(league_id: int, season: int) -> Json:
    return _request("players/topscorers", {"league": league_id, "season": season})



def get_topassists(league_id: int, season: int) -> Json:
    return _request("players/topassists", {"league": league_id, "season": season})



def get_cards(league_id: int, season: int) -> Json:
    yellow = _request("players/topyellowcards", {"league": league_id, "season": season}) or []
    red = _request("players/topredcards", {"league": league_id, "season": season}) or []
    if isinstance(yellow, list) and isinstance(red, list):
        return yellow + red
    return yellow or red



def get_odds(league_id: int, season: int, date: Optional[str] = None, *, force_refresh: bool = False) -> Json:
    params = {"league": league_id, "season": season}
    if date:
        params["date"] = date
    return _request("odds", params, force_refresh=force_refresh)



def get_odds_by_fixture(fixture_id: int, *, force_refresh: bool = False) -> Json:
    return _request("odds", {"fixture": fixture_id}, force_refresh=force_refresh)


def get_odds_bookmakers(force_refresh: bool = False) -> Json:
    return _request("odds/bookmakers", {}, force_refresh=force_refresh)



def get_venues(country: Optional[str] = None, team_id: Optional[int] = None) -> Json:
    params: Dict[str, Any] = {}
    if country:
        params["country"] = country
    if team_id:
        params["team"] = team_id
    return _request("venues", params)



def get_injuries(league_id: int, season: int, team_id: Optional[int] = None) -> Json:
    params: Dict[str, Any] = {"league": league_id, "season": season}
    if team_id:
        params["team"] = team_id
    return _request("injuries", params)



def get_predictions(fixture_id: int) -> Json:
    return _request("predictions", {"fixture": fixture_id})



def get_h2h(team1_id: int, team2_id: int, last: int = 10) -> Json:
    params = {"h2h": f"{team1_id}-{team2_id}", "last": last}
    return _request("fixtures/headtohead", params)


def _normalize_player_name(value: Any) -> Optional[str]:
    if not value:
        return None
    text = unicodedata.normalize("NFKD", str(value).strip().lower())
    ascii_text = "".join(ch for ch in text if not unicodedata.combining(ch))
    normalized = "".join(ch for ch in ascii_text if ch.isalnum())
    return normalized or None


def _player_identity(entry: Dict[str, Any]) -> Optional[str]:
    player_block = (entry or {}).get("player") or {}
    player_id = player_block.get("id")
    if player_id is not None:
        return f"id:{player_id}"
    normalized = _normalize_player_name(player_block.get("name"))
    if normalized:
        return f"name:{normalized}"
    return None


def _build_lineup_player_entry(
    player_block: Dict[str, Any],
    team_block: Dict[str, Any],
    league_id: int,
    season: int,
    *,
    is_starter: bool,
    fixture_meta: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    name = player_block.get("name")
    if not name:
        return None
    minutes = 75 if is_starter else 25
    stats_block = {
        "team": {
            "id": team_block.get("id"),
            "name": team_block.get("name"),
            "logo": team_block.get("logo"),
        },
        "league": {"id": league_id, "season": season},
        "games": {
            "appearences": 1,
            "lineups": 1 if is_starter else 0,
            "minutes": minutes,
            "position": player_block.get("pos"),
            "number": player_block.get("number"),
        },
        "goals": {"total": player_block.get("goals") or 0, "assists": player_block.get("assists")},
        "shots": {"total": None, "on": None},
        "passes": {"total": None, "key": None, "accuracy": None},
        "tackles": {"total": None},
        "penalty": {"scored": None, "missed": None},
    }
    return {
        "player": {
            "id": player_block.get("id"),
            "name": name,
            "age": player_block.get("age"),
            "number": player_block.get("number"),
            "photo": player_block.get("photo"),
            "nationality": player_block.get("nationality"),
            "injured": bool(player_block.get("injured", False)),
        },
        "statistics": [stats_block],
        "meta": {
            "source": "lineup",
            "fixture_id": fixture_meta.get("id") if fixture_meta else None,
            "fixture_date": fixture_meta.get("date") if fixture_meta else None,
        },
    }


def _lineup_roster_for_team(
    league_id: int,
    season: int,
    team_id: int,
    *,
    lookback: int = 3,
) -> List[Dict[str, Any]]:
    roster: List[Dict[str, Any]] = []
    if not team_id:
        return roster
    fixtures = get_fixtures(league_id, season, team_id=team_id, last_n=lookback) or []
    if not fixtures:
        fixtures = get_fixtures(league_id, season, team_id=team_id, next_n=lookback) or []
    seen: set[str] = set()
    for fixture in fixtures:
        fixture_block = fixture.get("fixture") or {}
        fixture_id = fixture_block.get("id")
        if not fixture_id:
            continue
        try:
            lineups_payload = get_lineups(int(fixture_id)) or []
        except Exception:
            lineups_payload = []
        if not isinstance(lineups_payload, list):
            continue
        for lineup in lineups_payload:
            team_block = lineup.get("team") or {}
            if team_block.get("id") != team_id:
                continue
            entries: List[Dict[str, Any]] = []
            for block in lineup.get("startXI") or []:
                entry = _build_lineup_player_entry(
                    block.get("player") or {},
                    team_block,
                    league_id,
                    season,
                    is_starter=True,
                    fixture_meta=fixture_block,
                )
                if entry:
                    entries.append(entry)
            for block in lineup.get("substitutes") or []:
                entry = _build_lineup_player_entry(
                    block.get("player") or {},
                    team_block,
                    league_id,
                    season,
                    is_starter=False,
                    fixture_meta=fixture_block,
                )
                if entry:
                    entries.append(entry)
            if entries:
                for entry in entries:
                    identity = _player_identity(entry)
                    if not identity or identity in seen:
                        continue
                    seen.add(identity)
                    roster.append(entry)
                if roster:
                    return roster
    return roster


def _merge_rosters(
    primary: List[Dict[str, Any]],
    supplements: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not supplements:
        return primary
    merged = list(primary)
    seen = {identity for entry in primary if (identity := _player_identity(entry))}
    for entry in supplements:
        identity = _player_identity(entry)
        if not identity or identity in seen:
            continue
        merged.append(entry)
        seen.add(identity)
    return merged


__all__ = [
    "get_fixtures",
    "get_fixture_details",
    "get_fixture_statistics",
    "get_fixture_events",
    "get_lineups",
    "get_leagues",
    "get_standings",
    "get_players",
    "get_players_for_team",
    "get_team_squad",
    "get_statistics",
    "get_topscorers",
    "get_topassists",
    "get_cards",
    "get_odds",
    "get_odds_by_fixture",
    "get_venues",
    "get_injuries",
    "get_predictions",
    "get_h2h",
    "get_teams",
]
