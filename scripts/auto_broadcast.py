#!/usr/bin/env python3
"""
Diffuse automatiquement les templates (prÃ©-match, live, alerte edge) vers Telegram/X/Email/Webhook
en s'appuyant sur les derniÃ¨res entrÃ©es `data/prediction_history.csv`.

Usage basique :
    py -3.11 scripts/auto_broadcast.py --mode pre-match --channels telegram
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.engagement import TemplateError, get_engagement_service, render_template
from utils.secrets import get_secret
from utils.api_calls import get_fixtures_by_date

LOG_PATH = Path("data/auto_broadcast_log.jsonl")
PREDICTION_HISTORY_PATH = Path("data/prediction_history.csv")
APP_URL = (get_secret("PUBLIC_APP_URL") or "http://localhost:8501").rstrip("/")

LIVE_STATUS_CODES = {"LIVE", "1H", "2H", "ET", "P", "BT", "HT", "INT", "INP"}
FINISHED_STATUS_CODES = {"FT", "AET", "PEN", "CANC", "ABD", "AWD"}
PREMATCH_STATUS_CODES = {"NS", "TBD", "POST", "PST", "SCH"}

TEMPLATE_BY_MODE = {
    "pre-match": "pre_match",
    "live": "live_update",
    "edge": "edge_alert",
}


def _safe_float(value: Any) -> Optional[float]:
    if value in (None, "", "NaN"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    number = _safe_float(value)
    if number is None:
        return None
    try:
        return int(number)
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _edge_percent(raw: str) -> Optional[float]:
    if not raw:
        return None
    matches = re.findall(r"(-?\d+(?:\.\d+)?)%", raw)
    if not matches:
        return None
    try:
        return float(matches[-1])
    except ValueError:
        return None


def _prob_label(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def _scoreline(row: Dict[str, Any]) -> str:
    result = row.get("result_score")
    if result:
        return result
    top = row.get("top_score")
    if top:
        return top.replace(row.get("home_team", ""), "").replace(row.get("away_team", ""), "").strip() or "0-0"
    return "0-0"


def load_rows() -> List[Dict[str, Any]]:
    if not PREDICTION_HISTORY_PATH.exists():
        raise FileNotFoundError(f"Fichier introuvable : {PREDICTION_HISTORY_PATH}")
    with PREDICTION_HISTORY_PATH.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def _status_label(row: Dict[str, Any], kickoff: Optional[datetime]) -> str:
    status = (row.get("status_snapshot") or "").upper()
    if status in PREMATCH_STATUS_CODES:
        if kickoff:
            return f"Coup d'envoi prÃ©vu le {kickoff.strftime('%d/%m %H:%M')}"
        return "Match Ã  venir"
    if status in LIVE_STATUS_CODES:
        return f"Live ({status})"
    if status in FINISHED_STATUS_CODES:
        return f"TerminÃ© ({status})"
    return status or "Statut inconnu"


def build_share_context(row: Dict[str, Any]) -> Dict[str, Any]:
    fixture_id = _safe_int(row.get("fixture_id")) or 0
    home = row.get("home_team") or "Equipe A"
    away = row.get("away_team") or "Equipe B"
    kickoff = _parse_datetime(row.get("fixture_date"))
    status = _status_label(row, kickoff)
    edge_pct = _edge_percent(row.get("edge_comment", ""))
    bankroll_profile = row.get("bankroll_profile_name") or row.get("bankroll_profile_id")
    bankroll_label = f"Profil {bankroll_profile}" if bankroll_profile else "Profil principal"
    top_tip: Dict[str, Any] = {}
    if row.get("main_pick"):
        confidence = _safe_float(row.get("main_confidence"))
        prob_guess = confidence / 100.0 if confidence is not None else None
        top_tip = {
            "label": row["main_pick"],
            "probability": prob_guess,
            "confidence": confidence,
            "reason": row.get("edge_comment"),
        }
    kickoff_label = kickoff.strftime("%d/%m/%Y %H:%M") if kickoff else "N/A"
    intensity = _safe_float(row.get("intensity_score"))
    ai_clip = (row.get("ai_analysis") or "").strip()
    if ai_clip:
        ai_clip = ai_clip.splitlines()[0][:240]
    share_context = {
        "fixture_id": fixture_id,
        "match_label": f"{home} - {away}",
        "status_label": status,
        "scoreline": _scoreline(row),
        "kickoff_label": kickoff_label,
        "prob_home_pct": _prob_label(_safe_float(row.get("prob_home"))),
        "prob_draw_pct": _prob_label(_safe_float(row.get("prob_draw"))),
        "prob_away_pct": _prob_label(_safe_float(row.get("prob_away"))),
        "prob_over": _safe_float(row.get("prob_over_2_5")),
        "top_tip": top_tip,
        "edge_label": f"{edge_pct:.1f}%" if edge_pct is not None else (row.get("edge_comment") or "N/A"),
        "edge_value": edge_pct,
        "intensity_score": intensity,
        "ai_summary": ai_clip,
        "bankroll_label": bankroll_label,
        "app_url": APP_URL,
        "share_footer": "Diffusion automatique ProbaEdge",
    }
    return share_context


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _within_horizon(kickoff: Optional[datetime], horizon: timedelta) -> bool:
    if kickoff is None:
        return False
    now = _now()
    kickoff_utc = kickoff.astimezone(timezone.utc)
    return now <= kickoff_utc <= now + horizon


def _pick_rows(
    rows: Iterable[Dict[str, Any]],
    *,
    mode: str,
    limit: int,
    horizon: timedelta,
    min_edge: float,
    allowed_fixture_ids: Optional[Set[int]] = None,
) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    for row in sorted(rows, key=lambda r: r.get("fixture_date") or ""):
        status = (row.get("status_snapshot") or "").upper()
        if status in FINISHED_STATUS_CODES:
            continue
        fixture_id = _safe_int(row.get("fixture_id"))
        if allowed_fixture_ids is not None and (fixture_id not in allowed_fixture_ids):
            continue
        kickoff = _parse_datetime(row.get("fixture_date"))
        if mode == "pre-match":
            if status not in PREMATCH_STATUS_CODES:
                continue
            if not _within_horizon(kickoff, horizon):
                continue
        elif mode == "live":
            if status not in LIVE_STATUS_CODES:
                continue
        elif mode == "edge":
            edge_pct = _edge_percent(row.get("edge_comment", ""))
            if edge_pct is None or edge_pct < min_edge:
                continue
            if status not in PREMATCH_STATUS_CODES | LIVE_STATUS_CODES:
                continue
        else:
            continue
        selected.append(row)
        if len(selected) >= limit:
            break
    return selected


def _load_log() -> List[Dict[str, Any]]:
    if not LOG_PATH.exists():
        return []
    entries: List[Dict[str, Any]] = []
    with LOG_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _has_recent_entry(
    log_entries: Sequence[Dict[str, Any]],
    fixture_id: Optional[int],
    template_key: str,
    cooldown: timedelta,
) -> bool:
    if fixture_id is None:
        return False
    now = _now()
    for entry in log_entries:
        if entry.get("fixture_id") != fixture_id or entry.get("template") != template_key:
            continue
        ts_value = entry.get("timestamp")
        if not ts_value:
            continue
        try:
            ts = datetime.fromisoformat(ts_value)
        except ValueError:
            continue
        if now - ts <= cooldown:
            return True
    return False


def _record_entry(fixture_id: int, template_key: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "fixture_id": fixture_id,
        "template": template_key,
        "timestamp": _now().isoformat(),
    }
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _send_message(channels: Sequence[str], subject: str, body: str) -> Dict[str, Tuple[bool, Optional[str]]]:
    service = get_engagement_service()
    results: Dict[str, Tuple[bool, Optional[str]]] = {}
    payload_text = f"{subject}\n\n{body}".strip()
    for channel in channels:
        if channel == "telegram":
            if service.has_telegram():
                results[channel] = service.post_telegram(payload_text)
            else:
                results[channel] = (False, "Telegram non configurÃ©")
        elif channel == "email":
            if service.has_email():
                results[channel] = service.send_email(subject, body)
            else:
                results[channel] = (False, "Email non configurÃ©")
        elif channel == "webhook":
            if service.has_webhook():
                results[channel] = service.post_webhook(payload_text)
            else:
                results[channel] = (False, "Webhook non configurÃ©")
        elif channel == "x":
            if service.has_x():
                results[channel] = service.post_x(payload_text)
            else:
                results[channel] = (False, "X non configurÃ©")
        else:
            results[channel] = (False, "Canal inconnu")
    return results


def run_mode(
    mode: str,
    *,
    limit: int,
    horizon_minutes: int,
    min_edge: float,
    dry_run: bool,
    channels: Sequence[str],
    cooldown_hours: float,
    allowed_fixture_ids: Optional[Set[int]] = None,
) -> None:
    template_key = TEMPLATE_BY_MODE[mode]
    rows = load_rows()
    horizon = timedelta(minutes=horizon_minutes)
    selected = _pick_rows(
        rows,
        mode=mode,
        limit=limit,
        horizon=horizon,
        min_edge=min_edge,
        allowed_fixture_ids=allowed_fixture_ids,
    )
    if not selected:
        print(f"Aucune entrÃ©e Ã  diffuser pour le mode '{mode}'.")
        return
    log_entries = _load_log()
    cooldown = timedelta(hours=cooldown_hours)
    sent = 0
    for row in selected:
        fixture_id = _safe_int(row.get("fixture_id")) or 0
        if _has_recent_entry(log_entries, fixture_id, template_key, cooldown):
            continue
        context = build_share_context(row)
        try:
            rendered = render_template(template_key, context)
        except TemplateError as exc:
            print(f"[{mode}] Impossible de gÃ©nÃ©rer le template pour fixture {fixture_id}: {exc}")
            continue
        subject = rendered.get("subject", "ProbaEdge")
        body = rendered.get("body", "")
        if dry_run:
            print("=" * 60)
            print(subject)
            print(body)
            continue
        results = _send_message(channels, subject, body)
        for channel, (ok, err) in results.items():
            status = "OK" if ok else f"ECHEC ({err})"
            print(f"[{mode}] Fixture {fixture_id} -> {channel} : {status}")
            if ok:
                _record_entry(fixture_id, template_key)
                sent += 1
    if dry_run:
        print(f"[{mode}] AperÃ§u terminÃ© ({len(selected)} messages potentiels).")
    else:
        print(f"[{mode}] Diffusion terminÃ©e ({sent} messages envoyÃ©s).")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diffuser automatiquement les templates ProbaEdge.")
    parser.add_argument(
        "--mode",
        choices=["pre-match", "live", "edge", "all"],
        default="pre-match",
        help="Type de message Ã  diffuser.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Nombre maximum de matchs par mode.",
    )
    parser.add_argument(
        "--horizon-minutes",
        type=int,
        default=360,
        help="FenÃªtre temporelle max (prÃ©-match seulement).",
    )
    parser.add_argument(
        "--min-edge",
        type=float,
        default=15.0,
        help="Seuil d'edge (%) pour le mode alerte.",
    )
    parser.add_argument(
        "--channels",
        default="telegram,email",
        help="Liste de canaux sÃ©parÃ©s par des virgules (telegram,email,webhook,x).",
    )
    parser.add_argument(
        "--cooldown-hours",
        type=float,
        default=2.0,
        help="DÃ©lai minimum avant de renvoyer le mÃªme template sur un match.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche les messages sans envoyer.",
    )
    parser.add_argument(
        "--agenda-date",
        type=str,
        default=None,
        help="Filtre les matchs aux fixtures de l'agenda (format YYYY-MM-DD ou 'today').",
    )
    parser.add_argument(
        "--agenda-timezone",
        type=str,
        default="Europe/Paris",
        help="Fuseau horaire utilisÃ© pour l'agenda (si --agenda-date est dÃ©fini).",
    )
    return parser.parse_args()


def _agenda_fixture_ids(date_text: str, timezone: str) -> Set[int]:
    fixtures = get_fixtures_by_date(date_text, timezone=timezone) or []
    fixture_ids: Set[int] = set()
    for entry in fixtures:
        fixture = entry.get("fixture") or {}
        fixture_id = fixture.get("id")
        if fixture_id is None:
            continue
        try:
            fixture_ids.add(int(fixture_id))
        except (TypeError, ValueError):
            continue
    return fixture_ids


def main() -> None:
    args = parse_args()
    modes = ["pre-match", "live", "edge"] if args.mode == "all" else [args.mode]
    channels = [item.strip().lower() for item in args.channels.split(",") if item.strip()]
    agenda_fixture_ids: Optional[Set[int]] = None
    if args.agenda_date:
        agenda_date = args.agenda_date
        if agenda_date.lower() == "today":
            agenda_date = datetime.now().date().isoformat()
        try:
            agenda_fixture_ids = _agenda_fixture_ids(agenda_date, args.agenda_timezone)
            if not agenda_fixture_ids:
                print(f"[agenda] Aucun match trouvÃ© pour {agenda_date}.")
        except Exception as exc:
            print(f"[agenda] Impossible de charger les matchs ({agenda_date}) : {exc}")
            agenda_fixture_ids = set()
    for mode in modes:
        run_mode(
            mode,
            limit=args.limit,
            horizon_minutes=args.horizon_minutes,
            min_edge=args.min_edge,
            dry_run=args.dry_run,
            channels=channels,
            cooldown_hours=args.cooldown_hours,
            allowed_fixture_ids=agenda_fixture_ids,
        )


if __name__ == "__main__":
    main()
