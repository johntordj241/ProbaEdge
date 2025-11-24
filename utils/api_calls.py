from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

import requests
import time
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



def get_fixture_details(fixture_id: int) -> Json:
    return _request("fixtures", {"id": fixture_id})


def get_fixture_statistics(fixture_id: int) -> Json:
    return _request("fixtures/statistics", {"fixture": fixture_id})


def get_fixture_events(fixture_id: int) -> Json:
    return _request("fixtures/events", {"fixture": fixture_id})


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
    return collected



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


__all__ = [
    "get_fixtures",
    "get_fixture_details",
    "get_fixture_statistics",
    "get_fixture_events",
    "get_leagues",
    "get_standings",
    "get_players",
    "get_players_for_team",
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



