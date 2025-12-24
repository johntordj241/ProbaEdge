from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

from .profile import DEFAULT_ALERT_SETTINGS, get_alert_settings
from .secrets import get_secret, PROJECT_ROOT

SEVERITY_BADGES = {
    "info": "[INFO]",
    "warning": "[WARN]",
    "critical": "[CRIT]",
}

DEFAULT_TTL_SECONDS = 900
LOG_FILE = PROJECT_ROOT / "data" / "notifications.log"
CHANNEL_FLAG_KEYS = (
    "channel_slack",
    "channel_discord",
    "channel_email",
    "channel_webhook",
    "channel_telegram",
    "channel_x",
)


def _ensure_log_file() -> Path:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    return LOG_FILE


def _channel_preferences() -> Dict[str, bool]:
    try:
        settings = get_alert_settings()
    except Exception:
        settings = {}
    prefs: Dict[str, bool] = {}
    for key in CHANNEL_FLAG_KEYS:
        default = DEFAULT_ALERT_SETTINGS.get(
            key,
            True if key in {"channel_slack", "channel_discord"} else False,
        )
        prefs[key] = bool(settings.get(key, default))
    return prefs


class NotificationManager:
    def __init__(self) -> None:
        self.slack_webhook = (get_secret("SLACK_WEBHOOK_URL") or "").strip()
        # Discord webhook compatible avec SOCIAL_DISCORD_TOKEN historique
        self.discord_webhook = (
            (get_secret("DISCORD_WEBHOOK_URL") or "") or (get_secret("SOCIAL_DISCORD_TOKEN") or "")
        ).strip()
        self._last_sent: Dict[str, float] = {}
        self._lock = threading.Lock()

    def has_channel(self) -> bool:
        return bool(self.slack_webhook or self.discord_webhook)

    def notify(
        self,
        title: str,
        message: str,
        *,
        severity: str = "info",
        tags: Optional[Iterable[str]] = None,
        dedup_key: Optional[str] = None,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        extra: Optional[Dict[str, Any]] = None,
    ) -> bool:
        severity = severity.lower()
        if severity not in SEVERITY_BADGES:
            severity = "info"
        if dedup_key and ttl_seconds > 0:
            with self._lock:
                last = self._last_sent.get(dedup_key)
                now = time.time()
                if last and (now - last) < ttl_seconds:
                    return False
                self._last_sent[dedup_key] = now

        timestamp = datetime.utcnow().isoformat()
        payload = {
            "title": title,
            "message": message,
            "severity": severity,
            "tags": list(tags or []),
            "timestamp": timestamp,
            "extra": extra or {},
        }
        self._log_locally(payload)
        channel_prefs = _channel_preferences()
        try:
            from .engagement import broadcast_notification_payload  # lazy import to avoid cycles
        except Exception:
            broadcast_notification_payload = None  # type: ignore

        has_primary_channel = (
            (self.slack_webhook and channel_prefs.get("channel_slack", True))
            or (self.discord_webhook and channel_prefs.get("channel_discord", True))
        )
        if not has_primary_channel:
            if broadcast_notification_payload:
                try:
                    return broadcast_notification_payload(payload, channels=channel_prefs)
                except Exception:
                    return False
            return False

        slack_ok = (
            self._send_slack(payload)
            if self.slack_webhook and channel_prefs.get("channel_slack", True)
            else False
        )
        discord_ok = (
            self._send_discord(payload)
            if self.discord_webhook and channel_prefs.get("channel_discord", True)
            else False
        )
        engagement_ok = False
        if broadcast_notification_payload:
            try:
                engagement_ok = broadcast_notification_payload(payload, channels=channel_prefs)
            except Exception:
                engagement_ok = False
        return slack_ok or discord_ok or engagement_ok

    def _send_slack(self, payload: Dict[str, Any]) -> bool:
        text = self._format_text(payload)
        body = {"text": text}
        return self._post(self.slack_webhook, body)

    def _send_discord(self, payload: Dict[str, Any]) -> bool:
        text = self._format_text(payload)
        body = {"content": text}
        return self._post(self.discord_webhook, body)

    def _post(self, url: str, body: Dict[str, Any]) -> bool:
        try:
            response = requests.post(url, json=body, timeout=6)
            response.raise_for_status()
            return True
        except Exception:
            return False

    def _format_text(self, payload: Dict[str, Any]) -> str:
        badge = SEVERITY_BADGES.get(payload["severity"], "[INFO]")
        tags = payload.get("tags") or []
        tags_suffix = f" [{' | '.join(tags)}]" if tags else ""
        return f"{badge} {payload['title']}{tags_suffix}\n{payload['message']}"

    def _log_locally(self, payload: Dict[str, Any]) -> None:
        try:
            log_file = _ensure_log_file()
            with log_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except OSError:
            pass


_MANAGER: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = NotificationManager()
    return _MANAGER


def notify_event(
    title: str,
    message: str,
    *,
    severity: str = "info",
    tags: Optional[Iterable[str]] = None,
    dedup_key: Optional[str] = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    extra: Optional[Dict[str, Any]] = None,
) -> bool:
    manager = get_notification_manager()
    try:
        return manager.notify(
            title,
            message,
            severity=severity,
            tags=tags,
            dedup_key=dedup_key,
            ttl_seconds=ttl_seconds,
            extra=extra,
        )
    except Exception:
        return False


__all__ = ["notify_event", "get_notification_manager", "NotificationManager"]
