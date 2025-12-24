#!/usr/bin/env python3
"""
Envoyer par email la liste des matchs du jour.

Usage:
    python scripts/email_daily_matches.py --date 2025-12-14 --leagues 39 61 --email john@example.com

Le script s'appuie sur les secrets SMTP configurés pour l'EngagementService
(`ENGAGEMENT_SMTP_*`, `ENGAGEMENT_EMAIL_FROM`, `ENGAGEMENT_EMAIL_TO`).
"""
from __future__ import annotations

import argparse
from datetime import datetime, date
from typing import Iterable, List, Dict, Any, Optional

from utils.api_calls import get_fixtures_by_date
from utils.engagement import get_engagement_service


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Envoyer par email les matchs du jour.")
    parser.add_argument(
        "--date",
        type=str,
        default=date.today().isoformat(),
        help="Date cible au format YYYY-MM-DD (défaut : aujourd'hui).",
    )
    parser.add_argument(
        "--timezone",
        type=str,
        default="Europe/Paris",
        help="Fuseau horaire désiré (transmis à l'API).",
    )
    parser.add_argument(
        "--leagues",
        type=int,
        nargs="*",
        help="Identifiants de ligues à inclure (défaut : toutes les compétitions retournées par l'API).",
    )
    parser.add_argument(
        "--email",
        type=str,
        help="Adresse email de destination (écrase ENGAGEMENT_EMAIL_TO).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="N'envoie pas d'email, affiche simplement le contenu.",
    )
    return parser.parse_args()


def _collect_fixtures(target_date: str, timezone: str, leagues: Optional[Iterable[int]]) -> List[Dict[str, Any]]:
    fixtures: List[Dict[str, Any]] = []
    if leagues:
        for league_id in leagues:
            chunk = get_fixtures_by_date(target_date, timezone=timezone, league_id=league_id) or []
            fixtures.extend(chunk if isinstance(chunk, list) else [])
    else:
        chunk = get_fixtures_by_date(target_date, timezone=timezone) or []
        fixtures.extend(chunk if isinstance(chunk, list) else [])
    return fixtures


def _format_fixture(entry: Dict[str, Any]) -> str:
    fixture_block = entry.get("fixture") or {}
    league_block = entry.get("league") or {}
    teams_block = entry.get("teams") or {}

    league = league_block.get("name", "Compétition inconnue")
    kickoff_iso = fixture_block.get("date")
    kickoff_display = kickoff_iso or "N/C"
    try:
        if kickoff_iso:
            kickoff_dt = datetime.fromisoformat(kickoff_iso.replace("Z", "+00:00"))
            kickoff_display = kickoff_dt.strftime("%d/%m %H:%M")
    except ValueError:
        pass

    home = (teams_block.get("home") or {}).get("name", "?")
    away = (teams_block.get("away") or {}).get("name", "?")
    venue = (fixture_block.get("venue") or {}).get("name")
    venue_txt = f" | {venue}" if venue else ""
    return f"- [{league}] {home} vs {away} – {kickoff_display}{venue_txt}"


def _build_email_body(fixtures: List[Dict[str, Any]], target_date: str, timezone: str) -> str:
    if not fixtures:
        return f"Aucun match enregistré pour la date {target_date} ({timezone})."
    lines = [
        f"Matches du {target_date} ({timezone})",
        "",
        *( _format_fixture(entry) for entry in sorted(fixtures, key=lambda e: (e.get('fixture') or {}).get('date') or '') ),
    ]
    lines.append("")
    lines.append("— ProbaEdge")
    return "\n".join(lines)


def main() -> None:
    args = _parse_args()
    fixtures = _collect_fixtures(args.date, args.timezone, args.leagues)
    body = _build_email_body(fixtures, args.date, args.timezone)
    subject = f"Matches du {args.date}"

    if args.dry_run:
        print(body)
        return

    service = get_engagement_service()
    if args.email:
        service.email_connector.recipients = [args.email]
    ok, error = service.send_email(subject, body)
    if ok:
        print(f"Email envoyé ({len(fixtures)} matchs).")
    else:
        print("Échec de l'envoi email :", error or "connecteur indisponible")
        print("Contenu :\n", body)


if __name__ == "__main__":
    main()
