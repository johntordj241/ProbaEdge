from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from .notifications import notify_event
from .prediction_history import load_prediction_history
from .supabase_client import enqueue_social_post, store_report_metadata
from .supervision import health_snapshot
from .match_filter import get_matches_over_horizon

REPORTS_DIR = Path("docs/reports")
TEMPLATES_DIR = Path("supabase/templates")
SOCIAL_QUEUE_TABLE = "social_queue"
MAX_HIGHLIGHTS = 5


@dataclass
class ContentPayload:
    title: str
    summary: str
    bullet_points: List[str]
    highlights: List[Dict[str, Any]]
    tags: List[str]
    generated_at: datetime

    def render_markdown(self) -> str:
        lines = [f"# {self.title}", ""]
        lines.append(self.summary)
        lines.append("")
        if self.bullet_points:
            for bullet in self.bullet_points:
                lines.append(f"- {bullet}")
            lines.append("")
        if self.highlights:
            lines.append("## Highlights")
            for item in self.highlights:
                match = item.get("match")
                edge = item.get("edge_pct")
                bookmaker = item.get("bookmaker")
                lines.append(f"- **{match}** : edge {edge:.1f}% ({bookmaker})")
            lines.append("")
        lines.append(f"_Généré le {self.generated_at.strftime('%d/%m/%Y %H:%M')}._")
        return "\n".join(lines)

    def to_social_caption(self) -> str:
        highlights = ", ".join(
            f"{item['match']} ({item['edge_pct']:.1f}% @ {item['bookmaker']})"
            for item in self.highlights[:3]
        )
        return f"{self.title} — {self.summary}\nHighlights: {highlights}"


def _load_prediction_df() -> pd.DataFrame:
    try:
        df = load_prediction_history()
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df.get("timestamp"), errors="coerce", utc=True)
    df["edge_pct"] = df.get("edge_comment")
    if "edge_pct" in df:
        df["edge_pct"] = pd.to_numeric(df["edge_pct"], errors="coerce")
    return df


def _recent_highlights(df: pd.DataFrame, *, limit: int = MAX_HIGHLIGHTS) -> List[Dict[str, Any]]:
    if df.empty:
        return []
    if "edge_pct" not in df:
        df["edge_pct"] = pd.NA
    df = df.dropna(subset=["edge_pct", "home_team", "away_team"])
    if df.empty:
        return []
    df = df.sort_values("edge_pct", ascending=False).head(limit)
    highlights = []
    for _, row in df.iterrows():
        highlights.append(
            {
                "match": f"{row['home_team']} vs {row['away_team']}",
                "edge_pct": float(row["edge_pct"]),
                "bookmaker": row.get("bet_bookmaker") or "n/a",
                "fixture_id": row.get("fixture_id"),
            }
        )
    return highlights


def _match_gap_bullet() -> Optional[str]:
    try:
        matches = get_matches_over_horizon(date.today(), days=1)
    except Exception:
        return None
    if not matches:
        return None
    missing = [match for match in matches if not match.bookmakers]
    if not missing:
        return None
    first = min(missing, key=lambda m: m.kickoff_utc or datetime.max)
    kickoff = first.kickoff_local_text
    return (
        f"{len(missing)} matchs sur {len(matches)} sans offre bookmaker pour les prochaines 24h "
        f"(ex : {first.label} le {kickoff})."
    )


def _supervision_bullet() -> Optional[str]:
    snapshot = health_snapshot()
    if snapshot.get("offline"):
        reason = snapshot.get("offline_reason") or "raison inconnue"
        return f"Mode hors ligne actif ({reason}) : relancer les fetchs une fois le quota rétabli."
    if snapshot.get("low_quota"):
        remaining = snapshot.get("quota_remaining")
        limit = snapshot.get("quota_limit")
        return f"Quota API faible ({remaining}/{limit}). Prévoir un rafraîchissement léger."
    failures = snapshot.get("recent_failures")
    if failures:
        return f"{failures} erreurs réseau consécutives détectées sur l’API Football."
    return None


def generate_content_payload() -> ContentPayload:
    df = _load_prediction_df()
    highlights = _recent_highlights(df)
    total_predictions = len(df)
    if "result_winner" in df:
        result_series = df["result_winner"]
    else:
        result_series = pd.Series([pd.NA] * len(df), index=df.index)
    finished = df[result_series.notna()]
    win_rate = float(finished["success_flag"].mean() * 100) if not finished.empty else None
    title = "Résumé IA Proba Edge"
    summary_bits = []
    if total_predictions:
        summary_bits.append(f"{total_predictions} prédictions suivies")
    if win_rate is not None:
        summary_bits.append(f"Win rate {win_rate:.1f}% sur les matches finalisés")
    summary = " | ".join(summary_bits) or "Pas de nouvel insight enregistré."
    bullet_points = []
    if highlights:
        top = highlights[0]
        bullet_points.append(
            f"Edge max sur {top['match']} ({top['edge_pct']:.1f}% chez {top['bookmaker']})."
        )
    pending = df[result_series.isna()]
    if not pending.empty:
        next_kickoff = pending.get("fixture_date").dropna().min()
        if pd.notna(next_kickoff):
            bullet_points.append(f"Prochain match en attente : {next_kickoff.strftime('%d/%m %H:%M')}.")
    match_gap_msg = _match_gap_bullet()
    if match_gap_msg:
        bullet_points.append(match_gap_msg)
    supervision_msg = _supervision_bullet()
    if supervision_msg:
        bullet_points.append(supervision_msg)
    generated_at = datetime.now(timezone.utc)
    return ContentPayload(
        title=title,
        summary=summary,
        bullet_points=bullet_points,
        highlights=highlights,
        tags=["social", "predictions"],
        generated_at=generated_at,
    )


def save_report_markdown(payload: ContentPayload, filename: Optional[str] = None) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if not filename:
        filename = f"rapport-{payload.generated_at.strftime('%Y%m%d-%H%M')}.md"
    path = REPORTS_DIR / filename
    path.write_text(payload.render_markdown(), encoding="utf-8")
    return path


def queue_social_post(payload: ContentPayload) -> Dict[str, Any]:
    caption = payload.to_social_caption()
    request = enqueue_social_post(
        channel="discord",
        payload={
            "caption": caption,
            "highlights": payload.highlights,
        },
        metadata={"tags": payload.tags},
    )
    return request


def log_report_metadata(payload: ContentPayload, markdown_path: Path, pdf_path: Optional[Path] = None) -> Dict[str, Any]:
    entry = {
        "title": payload.title,
        "summary": payload.summary,
        "tags": payload.tags,
        "pdf_path": str(pdf_path or markdown_path),
        "created_at": payload.generated_at.isoformat(),
        "author": "Proba Edge Bot",
        "status": "draft",
    }
    return store_report_metadata(entry)


def broadcast_content(payload: ContentPayload, *, notify: bool = True) -> None:
    caption = payload.to_social_caption()
    notify_event(
        payload.title,
        caption,
        severity="info",
        tags=payload.tags,
        dedup_key="content_engine_last",
        ttl_seconds=600,
    )
    queue_social_post(payload)


__all__ = [
    "ContentPayload",
    "generate_content_payload",
    "save_report_markdown",
    "queue_social_post",
    "log_report_metadata",
    "broadcast_content",
]
