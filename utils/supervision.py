from __future__ import annotations

import threading
import time
from collections import deque, defaultdict
from dataclasses import dataclass
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple

from .cache import cache_stats, purge_cache
from .notifications import notify_event


@dataclass
class APICallLog:
    timestamp: float
    endpoint: str
    params: Dict[str, Any]
    duration: float
    status_code: Optional[int]
    success: bool
    source: str
    error: Optional[str]
    cache_hit: bool
    quota_limit: Optional[int]
    quota_remaining: Optional[int]
    quota_reset: Optional[int]
    retries: int = 0


_LOCK = threading.Lock()
_CALLS: Deque[APICallLog] = deque(maxlen=400)
_ENDPOINT_STATS: Dict[str, Dict[str, Any]] = defaultdict(
    lambda: {
        "count": 0,
        "success": 0,
        "network_calls": 0,
        "cache_hits": 0,
        "total_duration": 0.0,
        "last_error": None,
        "last_status": None,
        "last_call": None,
        "retry_calls": 0,
        "max_retries": 0,
    }
)
_QUOTA: Dict[str, Optional[int]] = {
    "limit": None,
    "remaining": None,
    "reset": None,
    "updated_at": None,
}


def _to_int(value: Any) -> Optional[int]:
    if value in {None, "", "-"}:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def record_api_call(
    endpoint: str,
    *,
    params: Dict[str, Any],
    duration: float,
    status_code: Optional[int],
    success: bool,
    source: str,
    error: Optional[str] = None,
    cache_hit: bool = False,
    quota_limit: Optional[Any] = None,
    quota_remaining: Optional[Any] = None,
    quota_reset: Optional[Any] = None,
    retries: int = 0,
) -> None:
    """Persist a log entry and update aggregates."""
    if not endpoint:
        endpoint = "unknown"
    now = time.time()
    limit = _to_int(quota_limit)
    remaining = _to_int(quota_remaining)
    reset = _to_int(quota_reset)
    log = APICallLog(
        timestamp=now,
        endpoint=endpoint,
        params=dict(params or {}),
        duration=max(0.0, float(duration or 0.0)),
        status_code=status_code,
        success=bool(success),
        source=source or "unknown",
        error=error[:200] if isinstance(error, str) else error,
        cache_hit=bool(cache_hit),
        quota_limit=limit,
        quota_remaining=remaining,
        quota_reset=reset,
        retries=int(retries or 0),
    )
    with _LOCK:
        _CALLS.appendleft(log)
        stats = _ENDPOINT_STATS[endpoint]
        stats["count"] += 1
        stats["success"] += 1 if log.success else 0
        stats["total_duration"] += log.duration
        stats["last_status"] = log.status_code
        stats["last_call"] = log.timestamp
        stats["retry_calls"] += 1 if log.retries else 0
        if log.retries and log.retries > stats["max_retries"]:
            stats["max_retries"] = log.retries
        if log.cache_hit:
            stats["cache_hits"] += 1
        if log.source == "network":
            stats["network_calls"] += 1
        if not log.success:
            stats["last_error"] = log.error or f"HTTP {log.status_code}"

        if remaining is not None:
            _QUOTA["remaining"] = remaining
            _QUOTA["updated_at"] = now
        if limit is not None:
            _QUOTA["limit"] = limit
        if reset is not None:
            _QUOTA["reset"] = reset


def recent_calls(limit: int = 50, *, endpoint: Optional[str] = None) -> List[Dict[str, Any]]:
    with _LOCK:
        records: Iterable[APICallLog]
        if endpoint:
            records = (call for call in _CALLS if call.endpoint == endpoint)
        else:
            records = iter(_CALLS)
        selected: List[Dict[str, Any]] = []
        for call in records:
            selected.append(
                {
                    "Horodatage": time.strftime("%d/%m %H:%M:%S", time.localtime(call.timestamp)),
                    "Endpoint": call.endpoint,
                    "Duree (ms)": round(call.duration * 1000, 1),
                    "Statut": call.status_code or "-",
                    "Succes": "Oui" if call.success else "Non",
                    "Source": call.source,
                    "Cache": "Oui" if call.cache_hit else "Non",
                    "Params": call.params,
                    "Erreur": call.error or "",
                }
            )
            if len(selected) >= limit:
                break
        return selected


def endpoint_summary() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    now = time.time()
    with _LOCK:
        for endpoint, stats in _ENDPOINT_STATS.items():
            count = stats["count"] or 1
            success_rate = (stats["success"] / count) * 100.0
            avg_duration = (stats["total_duration"] / max(1, stats["network_calls"])) * 1000.0
            cache_ratio = (stats["cache_hits"] / count) * 100.0
            last_call = stats.get("last_call")
            rows.append(
                {
                    "Endpoint": endpoint,
                    "Appels": stats["count"],
                    "Succes %": round(success_rate, 1),
                    "Duree moy (ms)": round(avg_duration, 1),
                    "Cache %": round(cache_ratio, 1),
                    "Retries": stats.get("retry_calls", 0),
                    "Max retry": stats.get("max_retries", 0),
                    "Dernier statut": stats.get("last_status") or "-",
                    "Erreur recente": stats.get("last_error") or "",
                    "Dernier appel": time.strftime("%d/%m %H:%M:%S", time.localtime(last_call))
                    if last_call
                    else "-",
                }
            )
    rows.sort(key=lambda item: item["Endpoint"])
    return rows


def quota_status() -> Dict[str, Optional[int]]:
    with _LOCK:
        return dict(_QUOTA)


def health_snapshot() -> Dict[str, Any]:
    quota = quota_status()
    remaining = quota.get("remaining")
    limit = quota.get("limit")
    low_quota = False
    if remaining is not None and limit:
        low_quota = remaining <= max(int(0.1 * limit), 5)

    recent_failures = 0
    max_retry = 0
    with _LOCK:
        for entry in list(_CALLS)[:20]:
            if not entry.success and entry.source == "network":
                recent_failures += 1
        for entry in list(_CALLS)[:50]:
            if entry.retries and entry.retries > max_retry:
                max_retry = entry.retries

    cache_info = cache_stats()
    offline = bool(cache_info.get("offline"))
    reason = cache_info.get("offline_reason")

    return {
        "offline": offline,
        "offline_reason": reason,
        "low_quota": low_quota,
        "quota_remaining": remaining,
        "quota_limit": limit,
        "recent_failures": recent_failures,
        "max_retry": max_retry,
    }


def render_supervision_status(container: Any | None = None) -> None:
    try:
        import streamlit as st
    except ImportError:
        return

    target = container if container is not None else st.sidebar
    snapshot = health_snapshot()
    quota_remaining = snapshot.get("quota_remaining")
    quota_limit = snapshot.get("quota_limit")
    reason = snapshot.get("offline_reason")
    if snapshot.get("offline"):
        message = f"Mode hors ligne actif ({reason})" if reason else "Mode hors ligne actif"
        if reason == "user":
            target.info(message)
        else:
            target.error(message)
        notify_event(
            "Mode hors ligne detecte",
            message,
            severity="critical",
            tags=["supervision", "cache"],
            dedup_key=f"supervision_offline_{reason or 'auto'}",
            ttl_seconds=900,
            extra={"reason": reason},
        )
    elif snapshot.get("low_quota"):
        target.warning(
            f"Quota API faible : {quota_remaining}/{quota_limit}",
        )
        notify_event(
            "Quota API faible",
            f"Restant {quota_remaining}/{quota_limit}. Pensez a purger le cache ou a calmer les refresh.",
            severity="warning",
            tags=["supervision", "quota"],
            dedup_key="supervision_low_quota",
            ttl_seconds=1800,
            extra={"remaining": quota_remaining, "limit": quota_limit},
        )
    elif quota_remaining is not None and quota_limit:
        target.info(f"Quota API : {quota_remaining}/{quota_limit}")

    failures = snapshot.get("recent_failures", 0)
    if failures:
        target.warning(f"{failures} erreurs API sur les derniers appels.")
        notify_event(
            "Erreurs API repetees",
            f"{failures} appels recusent sur les 20 dernieres requetes.",
            severity="warning",
            tags=["supervision", "api"],
            dedup_key="supervision_errors",
            ttl_seconds=1200,
            extra={"recent_failures": failures},
        )
    max_retry = snapshot.get("max_retry", 0)
    if max_retry and max_retry >= 2:
        target.info(
            f"Retries automatiques actifs (max {max_retry}). Surveillez la latence et les quotas.",
        )
        notify_event(
            "Retries API eleves",
            f"Les retries automatiques montent a {max_retry}. Surveillez la latence / quotas.",
            severity="info",
            tags=["supervision", "api"],
            dedup_key="supervision_retries",
            ttl_seconds=1800,
            extra={"max_retry": max_retry},
        )


def purge_cache_via_supervision() -> int:
    return purge_cache(force=True)


__all__ = [
    "record_api_call",
    "recent_calls",
    "endpoint_summary",
    "quota_status",
    "health_snapshot",
    "render_supervision_status",
    "purge_cache_via_supervision",
]
