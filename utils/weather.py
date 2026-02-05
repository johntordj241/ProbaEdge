from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, Optional, Tuple

import requests

from .cache import is_offline_mode
from .secrets import get_secret

OPENWEATHER_BASE = "https://api.openweathermap.org"
OPENWEATHER_API_KEY_ENV = "OPENWEATHER_API_KEY"


@lru_cache(maxsize=1)
def _get_openweather_api_key() -> Optional[str]:
    return get_secret(OPENWEATHER_API_KEY_ENV)


def _enabled() -> bool:
    return bool(_get_openweather_api_key())


def is_available() -> bool:
    return _enabled() and not is_offline_mode()


def _request_json(url: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if is_offline_mode() or not _enabled():
        return None
    try:
        response = requests.get(url, params=params, timeout=8)
        if response.status_code != 200:
            return None
        return response.json()
    except Exception:
        return None


@lru_cache(maxsize=128)
def _geocode(city: str, country: Optional[str]) -> Optional[Tuple[float, float]]:
    api_key = _get_openweather_api_key()
    if not api_key:
        return None
    params: Dict[str, Any] = {
        "q": f"{city},{country}" if country else city,
        "limit": 1,
        "appid": api_key,
    }
    payload = _request_json(f"{OPENWEATHER_BASE}/geo/1.0/direct", params)
    if not payload:
        return None
    try:
        entry = payload[0]
        return float(entry["lat"]), float(entry["lon"])
    except (IndexError, KeyError, TypeError, ValueError):
        return None


def _closest_forecast(entries: list[Dict[str, Any]], kickoff: datetime) -> Optional[Dict[str, Any]]:
    if not entries:
        return None
    kickoff_ts = kickoff.replace(tzinfo=timezone.utc).timestamp()
    best_entry = None
    best_delta = None
    for entry in entries:
        try:
            ts = float(entry.get("dt"))
        except (TypeError, ValueError):
            continue
        delta = abs(ts - kickoff_ts)
        if best_delta is None or delta < best_delta:
            best_entry = entry
            best_delta = delta
    return best_entry


def get_match_forecast(
    *,
    city: Optional[str],
    country: Optional[str],
    kickoff: Optional[datetime],
) -> Optional[Dict[str, Any]]:
    """
    Returns a compact OpenWeather forecast for a given city/country and kickoff datetime.
    """
    if not _enabled() or not city or not kickoff:
        return None
    api_key = _get_openweather_api_key()
    if not api_key:
        return None
    coords = _geocode(city, country)
    if not coords:
        return None
    lat, lon = coords
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric",
    }
    payload = _request_json(f"{OPENWEATHER_BASE}/data/2.5/forecast", params)
    if not payload:
        return None
    entry = _closest_forecast(payload.get("list") or [], kickoff)
    if not entry:
        return None
    weather_block = (entry.get("weather") or [{}])[0]
    main_block = entry.get("main") or {}
    wind_block = entry.get("wind") or {}
    return {
        "description": weather_block.get("description"),
        "temperature": main_block.get("temp"),
        "humidity": main_block.get("humidity"),
        "wind": wind_block.get("speed"),
        "source": "openweather",
    }


__all__ = [
    "get_match_forecast",
    "is_available",
]
