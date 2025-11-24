from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

CACHE_DIR = Path("data/api_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

PURGE_INTERVAL_SECONDS = 2 * 3600  # 2 heures
FALLBACK_MAX_AGE = 7 * 24 * 3600   # 7 jours
PURGE_MARKER_FILE = CACHE_DIR / ".last_purge"

DEFAULT_PURGE_STRATEGY = {
    "interval": PURGE_INTERVAL_SECONDS,
    "force": False,
    "max_entries": 10000,
}
MAX_CACHE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


@dataclass
class CacheResult:
    data: Any
    timestamp: float
    ttl: Optional[float]
    age: float
    is_expired: bool


_STATS: Dict[str, Any] = {
    "hits": 0,
    "misses": 0,
    "expired": 0,
    "writes": 0,
    "purged": 0,
    "entries": 0,
    "size_bytes": 0,
    "last_purge": None,
}

_STATE: Dict[str, Any] = {
    "offline": False,
    "offline_reason": None,
    "last_purge_check": 0.0,
    "auto_resume_at": None,
    "auto_resume_reason": None,
}

_USAGE_LOCK = threading.Lock()
_USAGE: Dict[str, Dict[str, Any]] = defaultdict(
    lambda: {
        "hits": 0,
        "misses": 0,
        "expired": 0,
        "writes": 0,
        "last_access": 0.0,
    }
)


def _register_usage(endpoint: str, field: str) -> None:
    if not endpoint:
        endpoint = "unknown"
    with _USAGE_LOCK:
        stats = _USAGE[endpoint]
        stats[field] = stats.get(field, 0) + 1
        stats["last_access"] = time.time()


def cache_usage_snapshot() -> Dict[str, Dict[str, Any]]:
    with _USAGE_LOCK:
        return {endpoint: dict(values) for endpoint, values in _USAGE.items()}


def cache_usage_summary(limit: int = 10) -> List[Dict[str, Any]]:
    snapshot = cache_usage_snapshot()
    rows: List[Dict[str, Any]] = []
    for endpoint, stats in snapshot.items():
        hits = stats.get("hits", 0)
        misses = stats.get("misses", 0)
        expired = stats.get("expired", 0)
        total = hits + misses
        hit_ratio = (hits / total * 100.0) if total else 0.0
        rows.append(
            {
                "endpoint": endpoint,
                "hits": hits,
                "misses": misses,
                "expired": expired,
                "writes": stats.get("writes", 0),
                "hit_ratio": round(hit_ratio, 1),
                "last_access": stats.get("last_access"),
            }
        )
    rows.sort(key=lambda item: (item["hits"] + item["misses"]), reverse=True)
    return rows[:limit]


def _auto_resume_active() -> bool:
    return bool(
        _STATE.get("offline")
        and _STATE.get("offline_reason") not in {None, "user"}
        and _STATE.get("auto_resume_at")
    )


def auto_resume_remaining() -> Optional[float]:
    if not _auto_resume_active():
        return None
    remaining = float(_STATE.get("auto_resume_at") or 0.0) - time.time()
    return max(0.0, remaining)


def maybe_auto_resume_offline() -> None:
    if not _auto_resume_active():
        return
    remaining = auto_resume_remaining()
    if remaining is not None and remaining <= 0:
        set_offline_mode(False)


def _read_last_purge() -> Optional[float]:
    if not PURGE_MARKER_FILE.exists():
        return None
    try:
        return float(PURGE_MARKER_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _write_last_purge(timestamp: float) -> None:
    try:
        PURGE_MARKER_FILE.write_text(str(timestamp), encoding="utf-8")
    except Exception:
        pass


_STATS["last_purge"] = _read_last_purge()


def _update_storage_stats() -> None:
    entries = 0
    total_size = 0
    for file in CACHE_DIR.glob("*.json"):
        entries += 1
        try:
            total_size += file.stat().st_size
        except OSError:
            continue
    _STATS["entries"] = entries
    _STATS["size_bytes"] = total_size


_update_storage_stats()


def _canonical_key(path: str, params: Dict[str, Any]) -> str:
    normalized = "&".join(f"{key}={params[key]}" for key in sorted(params))
    raw = f"{path}?{normalized}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _cache_file(path: str, params: Dict[str, Any]) -> Path:
    key = _canonical_key(path, params)
    return CACHE_DIR / f"{key}.json"


def _should_remove(payload: Dict[str, Any], *, now: float, force: bool, older_than: Optional[float]) -> bool:
    timestamp = float(payload.get("timestamp", 0) or 0)
    ttl_value = payload.get("ttl")
    ttl_float = float(ttl_value) if ttl_value not in {None, ""} else 0.0
    age = now - timestamp if timestamp else 0.0

    if force:
        if older_than is None:
            return True
        return age > older_than

    if ttl_float > 0:
        return age > ttl_float

    fallback_limit = older_than if older_than is not None else FALLBACK_MAX_AGE
    return age > fallback_limit if fallback_limit else False


def purge_cache(*, force: bool = False, older_than: Optional[float] = None) -> int:
    now = time.time()
    purged = 0
    total_size = 0
    to_delete = []
    for file in CACHE_DIR.glob("*.json"):
        try:
            payload = json.loads(file.read_text(encoding="utf-8"))
            total_size += file.stat().st_size
        except Exception:
            try:
                file.unlink()
            except Exception:
                continue
            purged += 1
            continue
        if _should_remove(payload, now=now, force=force, older_than=older_than):
            try:
                file.unlink()
            except Exception:
                continue
            purged += 1
        else:
            to_delete.append((file, payload))
    # Enforce max cache size
    if not force and total_size > MAX_CACHE_SIZE_BYTES:
        to_delete.sort(key=lambda item: float(item[1].get("timestamp", 0) or 0))
        while total_size > MAX_CACHE_SIZE_BYTES and to_delete:
            file, payload = to_delete.pop(0)
            try:
                size = file.stat().st_size
                file.unlink()
                total_size -= size
                purged += 1
            except Exception:
                continue
    if purged:
        _STATS["purged"] += purged
    _STATS["last_purge"] = now
    _write_last_purge(now)
    _update_storage_stats()
    return purged


def maybe_purge_cache() -> int:
    now = time.time()
    last_check = _STATE.get("last_purge_check", 0.0)
    if now - last_check < 60:
        return 0
    _STATE["last_purge_check"] = now

    last_purge = _STATS.get("last_purge")
    if last_purge is None:
        last_purge = _read_last_purge()
        _STATS["last_purge"] = last_purge

    if last_purge is None or now - last_purge >= PURGE_INTERVAL_SECONDS:
        return purge_cache(force=False)
    return 0


def load_cache(path: str, params: Dict[str, Any], ttl: int) -> Optional[CacheResult]:
    maybe_purge_cache()
    file_path = _cache_file(path, params)
    if not file_path.exists():
        _STATS["misses"] += 1
        _register_usage(path, "misses")
        return None
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        try:
            file_path.unlink()
        except Exception:
            pass
        _update_storage_stats()
        _STATS["misses"] += 1
        _register_usage(path, "misses")
        return None

    timestamp = float(payload.get("timestamp", 0) or 0.0)
    stored_ttl = payload.get("ttl")
    effective_ttl = float(stored_ttl) if stored_ttl not in {None, ""} else float(ttl or 0)
    now = time.time()
    age = now - timestamp if timestamp else 0.0
    is_expired = bool(effective_ttl and age > effective_ttl)

    if is_expired:
        _STATS["expired"] += 1
        if not _STATE.get("offline"):
            _STATS["misses"] += 1
        else:
            _STATS["hits"] += 1
        _register_usage(path, "expired")
        if not _STATE.get("offline"):
            _register_usage(path, "misses")
        else:
            _register_usage(path, "hits")
    else:
        _STATS["hits"] += 1
        _register_usage(path, "hits")

    return CacheResult(
        data=payload.get("response"),
        timestamp=timestamp,
        ttl=effective_ttl if effective_ttl else None,
        age=age,
        is_expired=is_expired,
    )


def save_cache(path: str, params: Dict[str, Any], response: Any, ttl: int) -> None:
    maybe_purge_cache()
    file_path = _cache_file(path, params)
    payload = {
        "timestamp": time.time(),
        "ttl": float(ttl) if ttl else 0,
        "response": response,
    }
    file_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    _STATS["writes"] += 1
    _register_usage(path, "writes")
    _update_storage_stats()


def clear_cache() -> None:
    purged = 0
    for entry in CACHE_DIR.glob("*.json"):
        try:
            entry.unlink()
            purged += 1
        except Exception:
            continue
    if purged:
        _STATS["purged"] += purged
    _update_storage_stats()


def cache_stats() -> Dict[str, Any]:
    stats = dict(_STATS)
    stats["offline"] = bool(_STATE.get("offline"))
    stats["offline_reason"] = _STATE.get("offline_reason")
    stats["auto_resume_at"] = _STATE.get("auto_resume_at")
    stats["auto_resume_reason"] = _STATE.get("auto_resume_reason")
    stats["auto_resume_in"] = auto_resume_remaining()
    last_purge = stats.get("last_purge")
    if not last_purge:
        last_purge = _read_last_purge()
        stats["last_purge"] = last_purge
    stats["size_kb"] = round(stats.get("size_bytes", 0) / 1024, 2)
    total_requests = (stats.get("hits", 0) or 0) + (stats.get("misses", 0) or 0)
    stats["hit_ratio"] = round((stats.get("hits", 0) / total_requests) * 100.0, 1) if total_requests else 0.0
    stats["hits_per_endpoint"] = cache_usage_summary(limit=10)
    if last_purge:
        now = time.time()
        next_in = max(0.0, PURGE_INTERVAL_SECONDS - (now - last_purge))
        stats["next_purge_in"] = next_in
        stats["next_purge_eta"] = now + next_in
    else:
        stats["next_purge_in"] = None
        stats["next_purge_eta"] = None
    return stats


def set_offline_mode(enabled: bool, reason: Optional[str] = None, *, resume_in: Optional[float] = None) -> None:
    _STATE["offline"] = bool(enabled)
    if enabled:
        resolved_reason = reason or _STATE.get("offline_reason") or "inconnu"
        _STATE["offline_reason"] = resolved_reason
        if resolved_reason == "user":
            resume_in = None
        if resume_in:
            _STATE["auto_resume_at"] = time.time() + float(resume_in)
            _STATE["auto_resume_reason"] = resolved_reason
        else:
            _STATE["auto_resume_at"] = None
            _STATE["auto_resume_reason"] = None
    else:
        _STATE["offline_reason"] = None
        _STATE["auto_resume_at"] = None
        _STATE["auto_resume_reason"] = None


def is_offline_mode() -> bool:
    return bool(_STATE.get("offline"))


def offline_reason() -> Optional[str]:
    return _STATE.get("offline_reason")


def render_cache_controls(container: Any | None = None, key_prefix: str = "") -> None:
    try:
        import streamlit as st
    except ImportError:
        return

    target = container if container is not None else st.sidebar
    stats = cache_stats()
    offline = stats.get("offline", False)

    offline_reason_text = stats.get("offline_reason")
    if offline and offline_reason_text:
        target.info(f"Mode hors ligne ({offline_reason_text})")
        if stats.get("auto_resume_in") is not None and stats.get("auto_resume_reason") != "user":
            remaining = max(0.0, float(stats.get("auto_resume_in") or 0.0))
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            if minutes:
                resume_text = f"{minutes} min {seconds:02d}s"
            else:
                resume_text = f"{seconds}s"
            target.caption(f"Reprise automatique prevue dans ~{resume_text}")

    toggle_label = "Desactiver le mode hors ligne" if offline else "Activer le mode hors ligne"
    toggle_key = f"{key_prefix}cache_toggle_offline" if key_prefix else "cache_toggle_offline"
    if target.button(toggle_label, key=toggle_key):
        if offline:
            set_offline_mode(False)
        else:
            set_offline_mode(True, reason="user")
        st.experimental_rerun()

    cols = target.columns(3)
    cols[0].metric("Hits", stats.get("hits", 0))
    cols[1].metric("Misses", stats.get("misses", 0))
    cols[2].metric("Hit %", stats.get("hit_ratio", 0.0))

    target.caption(
        f"Cache : {stats.get('entries', 0)} fichiers | {stats.get('size_kb', 0.0)} KB"
    )
    last_purge = stats.get("last_purge")
    if last_purge:
        readable = time.strftime("%d/%m %H:%M", time.localtime(last_purge))
        target.caption(f"Derniere purge : {readable}")
    next_purge = stats.get("next_purge_in")
    if isinstance(next_purge, (int, float)):
        minutes = int(next_purge // 60)
        seconds = int(next_purge % 60)
        if minutes:
            eta_text = f"{minutes} min {seconds:02d}s"
        else:
            eta_text = f"{seconds}s"
        target.caption(f"Purge auto planifiee dans ~{eta_text}")

    purge_key = f"{key_prefix}cache_purge_now" if key_prefix else "cache_purge_now"
    if target.button("Purger le cache", key=purge_key):
        purged = purge_cache(force=True)
        target.success(f"{purged} fichiers supprimes.")
        st.experimental_rerun()

    top_usage = stats.get("hits_per_endpoint") or cache_usage_summary(limit=5)
    if top_usage:
        lines = "\n".join(
            f"- `{row['endpoint']}` : {row['hits']} hits / {row['misses']} misses ({row['hit_ratio']}% hits)"
            for row in top_usage
        )
        target.markdown("**Endpoints principaux**\n" + lines)


__all__ = [
    "load_cache",
    "save_cache",
    "clear_cache",
    "purge_cache",
    "maybe_purge_cache",
    "cache_stats",
    "cache_usage_snapshot",
    "cache_usage_summary",
    "auto_resume_remaining",
    "maybe_auto_resume_offline",
    "set_offline_mode",
    "is_offline_mode",
    "offline_reason",
    "render_cache_controls",
    "CacheResult",
]
