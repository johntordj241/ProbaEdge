from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

MONITOR_PATH = Path("data/api_monitor.json")
MONITOR_PATH.parent.mkdir(parents=True, exist_ok=True)

MAX_EVENTS = 200
DEFAULT_QUOTA_WINDOW_HOURS = 24

DEFAULT_STATE: Dict[str, Any] = {
    "events": [],
    "stats": {
        "total": 0,
        "success": 0,
        "failures": 0,
        "offline": 0,
        "cache_hits": 0,
        "fallbacks": 0,
        "last_error": None,
        "last_error_at": None,
    },
    "quota": {
        "limit": None,
        "window_hours": DEFAULT_QUOTA_WINDOW_HOURS,
        "used": 0,
        "reset_at": None,
        "last_call_at": None,
        "over_limit": False,
    },
}


@dataclass
class ApiEvent:
    endpoint: str
    params: Dict[str, Any]
    outcome: str
    timestamp: str
    duration_ms: Optional[float]
    status_code: Optional[int]
    message: Optional[str]
    cache_fallback: bool

    def as_dict(self) -> Dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "params": self.params,
            "outcome": self.outcome,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "status_code": self.status_code,
            "message": self.message,
            "cache_fallback": self.cache_fallback,
        }


def _deepcopy_default(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


def _normalize_state(state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(state, dict):
        state = {}
    if not isinstance(state.get("events"), list):
        state["events"] = []

    stats_defaults = _deepcopy_default(DEFAULT_STATE["stats"])
    stats = state.get("stats")
    if not isinstance(stats, dict):
        stats = {}
    for key, default_value in stats_defaults.items():
        stats.setdefault(key, default_value)
    state["stats"] = stats

    quota_defaults = _deepcopy_default(DEFAULT_STATE["quota"])
    quota = state.get("quota")
    if not isinstance(quota, dict):
        quota = {}
    for key, default_value in quota_defaults.items():
        quota.setdefault(key, default_value)
    state["quota"] = quota
    return state


def _load_state() -> Dict[str, Any]:
    if not MONITOR_PATH.exists():
        return _normalize_state(_deepcopy_default(DEFAULT_STATE))
    try:
        data = json.loads(MONITOR_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return _normalize_state(data)


def _save_state(state: Dict[str, Any]) -> None:
    try:
        MONITOR_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def _update_quota_usage(state: Dict[str, Any], now: datetime) -> None:
    quota = state.setdefault("quota", _deepcopy_default(DEFAULT_STATE["quota"]))

    window_hours = quota.get("window_hours") or DEFAULT_QUOTA_WINDOW_HOURS
    try:
        window_hours = int(window_hours)
    except (TypeError, ValueError):
        window_hours = DEFAULT_QUOTA_WINDOW_HOURS
    window_hours = max(window_hours, 1)

    reset_at = _parse_datetime(quota.get("reset_at"))
    if reset_at is None or now >= reset_at:
        quota["used"] = 0
        quota["reset_at"] = (now + timedelta(hours=window_hours)).isoformat()

    used = int(quota.get("used", 0)) + 1
    quota["used"] = used
    quota["window_hours"] = window_hours
    quota["last_call_at"] = now.isoformat()

    limit = quota.get("limit")
    if limit in {None, ""}:
        quota["limit"] = None
    else:
        try:
            quota_limit = max(int(limit), 0)
        except (TypeError, ValueError):
            quota_limit = 0
        quota["limit"] = quota_limit or None

    limit_value = quota.get("limit")
    quota["over_limit"] = bool(limit_value and used > limit_value)
    state["quota"] = quota


def record_api_call(
    endpoint: str,
    params: Dict[str, Any],
    *,
    outcome: str,
    duration_ms: Optional[float] = None,
    status_code: Optional[int] = None,
    message: Optional[str] = None,
    cache_fallback: bool = False,
) -> None:
    state = _load_state()
    events: List[Dict[str, Any]] = state.get("events", [])
    stats: Dict[str, Any] = state.setdefault("stats", {}).copy()

    now = datetime.now(timezone.utc)
    event = ApiEvent(
        endpoint=endpoint,
        params=params,
        outcome=outcome,
        timestamp=now.isoformat(),
        duration_ms=round(duration_ms, 2) if duration_ms is not None else None,
        status_code=status_code,
        message=message[:200] if isinstance(message, str) else message,
        cache_fallback=cache_fallback,
    )

    events.append(event.as_dict())
    if len(events) > MAX_EVENTS:
        events = events[-MAX_EVENTS:]
    state["events"] = events

    stats.setdefault("total", 0)
    stats.setdefault("success", 0)
    stats.setdefault("failures", 0)
    stats.setdefault("offline", 0)
    stats.setdefault("cache_hits", 0)
    stats.setdefault("fallbacks", 0)

    stats["total"] += 1
    if outcome == "success":
        stats["success"] += 1
    elif outcome == "cache_hit":
        stats["cache_hits"] += 1
    else:
        if outcome in {"offline_cache", "offline_failed"}:
            stats["offline"] += 1
        if cache_fallback:
            stats["fallbacks"] += 1
        stats["failures"] += 1
        stats["last_error"] = event.as_dict()
        stats["last_error_at"] = event.timestamp

    state["stats"] = stats
    _update_quota_usage(state, now)
    _save_state(state)


def get_api_monitor_state() -> Dict[str, Any]:
    state = _load_state()
    stats = state.get("stats", {})
    total = stats.get("total", 0) or 1
    failures = stats.get("failures", 0)
    stats["error_rate"] = round((failures / total) * 100, 2)
    state["stats"] = stats
    return state


def get_recent_events(limit: int = 50) -> List[Dict[str, Any]]:
    state = _load_state()
    events = state.get("events", [])
    return list(reversed(events[-limit:]))


def clear_api_monitor() -> None:
    _save_state(_normalize_state(_deepcopy_default(DEFAULT_STATE)))


def get_quota_status() -> Dict[str, Any]:
    state = _load_state()
    quota = state.get("quota", _deepcopy_default(DEFAULT_STATE["quota"]))
    now = datetime.now(timezone.utc)
    limit = quota.get("limit")
    used = int(quota.get("used", 0))
    limit_value = int(limit) if isinstance(limit, int) else None

    if limit_value is None and isinstance(limit, str) and limit.isdigit():
        limit_value = int(limit)

    remaining: Optional[int] = None
    percent: Optional[float] = None
    if limit_value:
        remaining = max(limit_value - used, 0)
        percent = round(min((used / limit_value) * 100, 999.99), 2)

    reset_at_dt = _parse_datetime(quota.get("reset_at"))
    reset_in_minutes: Optional[int] = None
    if reset_at_dt:
        delta = reset_at_dt - now
        reset_in_minutes = max(int(delta.total_seconds() // 60), 0)

    return {
        "limit": limit_value,
        "used": used,
        "remaining": remaining,
        "window_hours": int(quota.get("window_hours") or DEFAULT_QUOTA_WINDOW_HOURS),
        "reset_at": reset_at_dt.isoformat() if reset_at_dt else None,
        "reset_in_minutes": reset_in_minutes,
        "over_limit": bool(quota.get("over_limit")) or bool(limit_value and used > limit_value),
        "percent": percent,
        "last_call_at": quota.get("last_call_at"),
    }


def update_quota_settings(limit: Optional[int], window_hours: Optional[int] = None) -> Dict[str, Any]:
    state = _load_state()
    quota = state.get("quota", _deepcopy_default(DEFAULT_STATE["quota"]))

    if limit in {None, "", 0}:
        quota["limit"] = None
    else:
        try:
            quota["limit"] = max(int(limit), 0) or None
        except (TypeError, ValueError):
            quota["limit"] = None

    if window_hours is not None:
        try:
            quota["window_hours"] = max(int(window_hours), 1)
        except (TypeError, ValueError):
            quota["window_hours"] = DEFAULT_QUOTA_WINDOW_HOURS

    now = datetime.now(timezone.utc)
    window_hours_value = quota.get("window_hours") or DEFAULT_QUOTA_WINDOW_HOURS
    try:
        window_hours_value = max(int(window_hours_value), 1)
    except (TypeError, ValueError):
        window_hours_value = DEFAULT_QUOTA_WINDOW_HOURS

    quota["used"] = 0
    quota["reset_at"] = (now + timedelta(hours=window_hours_value)).isoformat()
    quota["last_call_at"] = None
    quota["over_limit"] = False

    state["quota"] = quota
    _save_state(state)
    return quota


def reset_quota_usage() -> Dict[str, Any]:
    state = _load_state()
    quota = state.get("quota", _deepcopy_default(DEFAULT_STATE["quota"]))
    now = datetime.now(timezone.utc)

    window_hours = quota.get("window_hours") or DEFAULT_QUOTA_WINDOW_HOURS
    try:
        window_hours = max(int(window_hours), 1)
    except (TypeError, ValueError):
        window_hours = DEFAULT_QUOTA_WINDOW_HOURS

    quota["used"] = 0
    quota["reset_at"] = (now + timedelta(hours=window_hours)).isoformat()
    quota["over_limit"] = False

    state["quota"] = quota
    _save_state(state)
    return quota


__all__ = [
    "record_api_call",
    "get_api_monitor_state",
    "get_recent_events",
    "clear_api_monitor",
    "get_quota_status",
    "update_quota_settings",
    "reset_quota_usage",
]
