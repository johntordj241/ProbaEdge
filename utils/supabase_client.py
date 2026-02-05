from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, Optional

try:
    from supabase import Client, create_client  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    Client = Any  # type: ignore
    create_client = None

from .secrets import get_secret

SUPABASE_URL_ENV = "SUPABASE_URL"
SUPABASE_SERVICE_KEY_ENV = "SUPABASE_SERVICE_KEY"


def _missing_config_message() -> str:
    return (
        "Configuration Supabase manquante. "
        "Renseignez SUPABASE_URL et SUPABASE_SERVICE_KEY dans votre environnement "
        "ou dans le fichier .env."
    )


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    url = get_secret(SUPABASE_URL_ENV)
    key = get_secret(SUPABASE_SERVICE_KEY_ENV)
    if not url or not key:
        raise RuntimeError(_missing_config_message())
    if create_client is None:
        raise RuntimeError(
            "Le package `supabase` est requis pour utiliser get_supabase_client. "
            "Installez-le ou désactivez les fonctionnalités Social Engine."
        )
    return create_client(url, key)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def enqueue_social_post(
    *,
    channel: str,
    payload: Dict[str, Any],
    run_at: Optional[datetime] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Ajoute un message à publier dans la table social_queue.
    """
    client = get_supabase_client()
    row = {
        "channel": channel,
        "payload": payload,
        "metadata": metadata or {},
        "status": "pending",
        "run_at": (run_at or datetime.now(timezone.utc)).isoformat(),
        "created_at": _utc_now_iso(),
    }
    response = client.table("social_queue").insert(row).execute()
    return (response.data or [{}])[0]


def fetch_pending_social_posts(*, limit: int = 20) -> list[Dict[str, Any]]:
    """
    Récupère les messages à publier (status pending ou retry).
    """
    client = get_supabase_client()
    query = (
        client.table("social_queue")
        .select("*")
        .in_("status", ["pending", "retry"])
        .order("run_at", desc=False)
        .limit(limit)
    )
    response = query.execute()
    return response.data or []


def mark_social_post_status(
    queue_id: Any,
    *,
    status: str,
    error_message: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Met à jour le statut d'un message (success, failed, retry...).
    """
    client = get_supabase_client()
    update_payload: Dict[str, Any] = {
        "status": status,
        "updated_at": _utc_now_iso(),
    }
    if error_message is not None:
        update_payload["error_message"] = error_message
    if extra_metadata:
        update_payload["metadata"] = extra_metadata
    response = (
        client.table("social_queue")
        .update(update_payload)
        .eq("id", queue_id)
        .execute()
    )
    return (response.data or [{}])[0]


def store_report_metadata(entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enregistre dans la table reports la référence d'un rapport (PDF, statut...).
    """
    client = get_supabase_client()
    payload = {
        "title": entry.get("title"),
        "summary": entry.get("summary"),
        "tags": entry.get("tags", []),
        "pdf_path": entry.get("pdf_path"),
        "created_at": entry.get("created_at") or _utc_now_iso(),
        "author": entry.get("author"),
        "status": entry.get("status", "published"),
    }
    response = client.table("reports").insert(payload).execute()
    return (response.data or [{}])[0]


__all__ = [
    "get_supabase_client",
    "enqueue_social_post",
    "fetch_pending_social_posts",
    "mark_social_post_status",
    "store_report_metadata",
]
