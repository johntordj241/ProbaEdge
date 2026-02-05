from __future__ import annotations

import json
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any, Dict, List, Optional, Tuple

import requests

from .secrets import get_secret


class TemplateError(RuntimeError):
    """Raised when a template cannot be rendered."""


ShareContext = Dict[str, Any]
RenderedTemplate = Dict[str, str]


def _pct(value: Optional[float]) -> str:
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "N/A"


def _top_tip_line(ctx: ShareContext) -> str:
    tip = ctx.get("top_tip") or {}
    if not tip:
        return "Aucun tip prioritaire."
    prob = tip.get("probability")
    confidence = tip.get("confidence")
    parts = [tip.get("label", "Sélection")]
    if prob is not None:
        parts.append(f"proba {_pct(prob)}")
    if confidence is not None:
        parts.append(f"confiance {confidence}/100")
    reason = tip.get("reason")
    line = " - ".join(parts)
    if reason:
        line += f" | {reason}"
    return line


def _base_context_lines(ctx: ShareContext) -> List[str]:
    lines = [
        f"{ctx.get('match_label', 'Match')} – {ctx.get('status_label', '')}",
        f"Probabilités : {ctx.get('prob_home_pct')} / {ctx.get('prob_draw_pct')} / {ctx.get('prob_away_pct')}",
        f"Indice IA : {ctx.get('intensity_score', 'N/A')} | Edge principal : {ctx.get('edge_label', 'n/a')}",
    ]
    top_tip = _top_tip_line(ctx)
    if top_tip:
        lines.append(f"Tip clé : {top_tip}")
    ai_clip = ctx.get("ai_summary")
    if ai_clip:
        lines.append(f"Résumé IA : {ai_clip}")
    return lines


def _render_pre_match(ctx: ShareContext) -> RenderedTemplate:
    subject = f"Prévision {ctx.get('match_label', '')}"
    body_lines = _base_context_lines(ctx)
    body_lines.append(f"Kick-off : {ctx.get('kickoff_label', '?')} | Lien : {ctx.get('app_url', '')}")
    return {"subject": subject, "body": "\n".join(body_lines)}


def _render_live_update(ctx: ShareContext) -> RenderedTemplate:
    subject = f"Live update {ctx.get('match_label', '')}"
    body_lines = [
        f"Score actuel {ctx.get('scoreline', '0-0')} ({ctx.get('status_label', '')})",
        f"Pression/intensité : {ctx.get('intensity_score', 'N/A')} | Over 2.5 : {_pct(ctx.get('prob_over'))}",
        _top_tip_line(ctx),
    ]
    ai_clip = ctx.get("ai_summary")
    if ai_clip:
        body_lines.append(ai_clip)
    body_lines.append(f"Rappel bankroll : {ctx.get('bankroll_label', '')}")
    body_lines.append(ctx.get("share_footer", ""))
    return {"subject": subject, "body": "\n".join(body_lines)}


def _render_edge_alert(ctx: ShareContext) -> RenderedTemplate:
    tip = ctx.get("top_tip") or {}
    label = tip.get("label", "Selection")
    subject = f"Edge détecté : {label}"
    body_lines = [
        f"Match : {ctx.get('match_label', '')} ({ctx.get('status_label', '')})",
        f"Selection : {label}",
        f"Probabilité {_pct(tip.get('probability'))} | Edge estimé {ctx.get('edge_value', 'N/A')} pts",
        f"Contexte : {tip.get('reason', 'Analyse IA disponible dans l’app.')}",
        f"Lien : {ctx.get('app_url', '')}",
    ]
    return {"subject": subject, "body": "\n".join(body_lines)}


TEMPLATES: Dict[str, Dict[str, Any]] = {
    "pre_match": {
        "label": "Pré-match complet",
        "description": "Résumé des probabilités et tip principal avant le coup d'envoi.",
        "builder": _render_pre_match,
    },
    "live_update": {
        "label": "Live update express",
        "description": "Score live + métriques intensité / over / tip en cours.",
        "builder": _render_live_update,
    },
    "edge_alert": {
        "label": "Alerte edge",
        "description": "Message court pour signaler une valeur détectée.",
        "builder": _render_edge_alert,
    },
}


def available_templates() -> List[Dict[str, str]]:
    return [
        {"key": key, "label": spec["label"], "description": spec.get("description", "")}
        for key, spec in TEMPLATES.items()
    ]


def render_template(template_key: str, context: ShareContext) -> RenderedTemplate:
    spec = TEMPLATES.get(template_key)
    if not spec:
        raise TemplateError(f"Template inconnu : {template_key}")
    builder = spec.get("builder")
    if not builder:
        raise TemplateError(f"Aucun builder pour le template {template_key}")
    return builder(context)


def _parse_recipients(raw: str) -> List[str]:
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


@dataclass
class EmailConnector:
    host: str
    port: int
    username: Optional[str]
    password: Optional[str]
    sender: str
    recipients: List[str]
    use_tls: bool = True

    def is_ready(self) -> bool:
        return bool(self.host and self.port and self.sender and self.recipients)

    def send(self, subject: str, body: str) -> Tuple[bool, Optional[str]]:
        if not self.is_ready():
            return False, "SMTP non configuré."
        message = EmailMessage()
        message["Subject"] = subject or "ProbaEdge"
        message["From"] = self.sender
        message["To"] = ", ".join(self.recipients)
        message.set_content(body, subtype="plain", charset="utf-8")
        try:
            with smtplib.SMTP(self.host, self.port, timeout=10) as server:
                if self.use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.send_message(message)
            return True, None
        except Exception as exc:
            return False, str(exc)


@dataclass
class WebhookConnector:
    url: str

    def is_ready(self) -> bool:
        return bool(self.url)

    def post(self, text: str) -> Tuple[bool, Optional[str]]:
        if not self.is_ready():
            return False, "Webhook social non configuré."
        try:
            resp = requests.post(self.url, json={"text": text}, timeout=6)
            resp.raise_for_status()
            return True, None
        except Exception as exc:
            return False, str(exc)


@dataclass
class TelegramConnector:
    token: str
    chat_id: str

    def is_ready(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, text: str) -> Tuple[bool, Optional[str]]:
        if not self.is_ready():
            return False, "Telegram non configuré."
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text}
        try:
            resp = requests.post(url, data=payload, timeout=6)
            resp.raise_for_status()
            return True, None
        except Exception as exc:
            return False, str(exc)


@dataclass
class XConnector:
    bearer_token: str

    def is_ready(self) -> bool:
        return bool(self.bearer_token)

    def post(self, text: str) -> Tuple[bool, Optional[str]]:
        if not self.is_ready():
            return False, "X (Twitter) non configuré."
        trimmed = text.strip()
        if len(trimmed) > 275:
            trimmed = trimmed[:272] + "..."
        try:
            resp = requests.post(
                "https://api.twitter.com/2/tweets",
                json={"text": trimmed},
                timeout=8,
                headers={"Authorization": f"Bearer {self.bearer_token}"},
            )
            resp.raise_for_status()
            return True, None
        except Exception as exc:
            return False, str(exc)


class EngagementService:
    def __init__(self) -> None:
        email_from = get_secret("ENGAGEMENT_EMAIL_FROM") or ""
        email_to = get_secret("ENGAGEMENT_EMAIL_TO") or ""
        smtp_host = get_secret("ENGAGEMENT_SMTP_HOST") or ""
        smtp_port = int(get_secret("ENGAGEMENT_SMTP_PORT") or "587")
        smtp_user = get_secret("ENGAGEMENT_SMTP_USERNAME")
        smtp_pass = get_secret("ENGAGEMENT_SMTP_PASSWORD")
        smtp_tls = (get_secret("ENGAGEMENT_SMTP_USE_TLS") or "true").lower() != "false"

        self.email_connector = EmailConnector(
            host=smtp_host,
            port=smtp_port,
            username=smtp_user,
            password=smtp_pass,
            sender=email_from,
            recipients=_parse_recipients(email_to),
            use_tls=smtp_tls,
        )
        webhook_url = get_secret("ENGAGEMENT_SOCIAL_WEBHOOK_URL") or ""
        self.webhook_connector = WebhookConnector(url=webhook_url)
        telegram_token = get_secret("TELEGRAM_BOT_TOKEN") or ""
        telegram_chat_id = get_secret("TELEGRAM_CHAT_ID") or ""
        self.telegram_connector = TelegramConnector(token=telegram_token, chat_id=telegram_chat_id)
        self.x_connector = XConnector(bearer_token=get_secret("X_BEARER_TOKEN") or "")

    def has_email(self) -> bool:
        return self.email_connector.is_ready()

    def has_webhook(self) -> bool:
        return self.webhook_connector.is_ready()

    def has_telegram(self) -> bool:
        return self.telegram_connector.is_ready()

    def has_x(self) -> bool:
        return self.x_connector.is_ready()

    def send_email(self, subject: str, body: str) -> Tuple[bool, Optional[str]]:
        return self.email_connector.send(subject, body)

    def post_webhook(self, body: str) -> Tuple[bool, Optional[str]]:
        return self.webhook_connector.post(body)

    def post_telegram(self, body: str) -> Tuple[bool, Optional[str]]:
        return self.telegram_connector.send(body)

    def post_x(self, body: str) -> Tuple[bool, Optional[str]]:
        return self.x_connector.post(body)

    def broadcast_notification(self, payload: Dict[str, Any], channels: Optional[Dict[str, bool]] = None) -> bool:
        text_lines = [payload.get("title", "Notification"), payload.get("message", "")]
        if payload.get("tags"):
            text_lines.append("#" + " #".join(payload["tags"]))
        text = "\n".join(line for line in text_lines if line).strip()
        if not text:
            return False
        flags = channels or {}
        success = False
        if flags.get("channel_email", True) and self.has_email():
            ok, _ = self.send_email(payload.get("title", "ProbaEdge"), text)
            success = success or ok
        if flags.get("channel_telegram", True) and self.has_telegram():
            ok, _ = self.post_telegram(text)
            success = success or ok
        if flags.get("channel_x", True) and self.has_x():
            ok, _ = self.post_x(text)
            success = success or ok
        if flags.get("channel_webhook", True) and self.has_webhook():
            ok, _ = self.post_webhook(text)
            success = success or ok
        return success


_SERVICE: Optional[EngagementService] = None


def get_engagement_service() -> EngagementService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = EngagementService()
    return _SERVICE


def broadcast_notification_payload(payload: Dict[str, Any], channels: Optional[Dict[str, bool]] = None) -> bool:
    service = get_engagement_service()
    return service.broadcast_notification(payload, channels=channels)


__all__ = [
    "available_templates",
    "render_template",
    "get_engagement_service",
    "broadcast_notification_payload",
    "TemplateError",
]
