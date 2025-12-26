from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Set

import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_FOOTBALL_BASE_URL", "https://v3.football.api-sports.io").rstrip("/")
API_KEY = os.getenv("API_FOOTBALL_KEY")
DB_DSN = (
    os.getenv("SUPABASE_DB_DSN")
    or os.getenv("SUPABASE_DB_URL")
    or os.getenv("SUPABASE_CONNECTION")
    or os.getenv("SUPABASE_KEY")
)

HTTP_TIMEOUT = 30
DEFAULT_LAST_FIXTURES = 5


def _ensure_env() -> None:
    missing: List[str] = []
    if not API_KEY:
        missing.append("API_FOOTBALL_KEY")
    if not DB_DSN:
        missing.append("SUPABASE_DB_DSN (ou SUPABASE_KEY)")
    if missing:
        raise RuntimeError(
            f"Variables d'environnement manquantes pour la sync: {', '.join(missing)}"
        )


def api_get(endpoint: str, params: Optional[Dict[str, object]] = None) -> List[Dict[str, object]]:
    url = f"{API_URL}{endpoint}"
    headers = {"x-apisports-key": API_KEY}
    response = requests.get(url, headers=headers, params=params, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(f"API error on {endpoint}: {payload['errors']}")
    return payload.get("response") or []


def connect_db():
    return psycopg2.connect(DB_DSN)


def _collect_recent_participants(fixtures: Iterable[Dict[str, object]]) -> Set[int]:
    seen: Set[int] = set()
    fixture_ids = [
        (fixture.get("fixture") or {}).get("id")
        for fixture in fixtures
        if fixture.get("fixture")
    ]
    for fixture_id in filter(None, fixture_ids):
        lineups = api_get("/fixtures/lineups", {"fixture": fixture_id})
        for lineup in lineups:
            for bucket in ("startXI", "substitutes"):
                for entry in lineup.get(bucket, []):
                    player = entry.get("player") or {}
                    pid = player.get("id")
                    if pid:
                        seen.add(int(pid))
    return seen


def update_team(team_id: int, season: int, *, last_fixtures: int = DEFAULT_LAST_FIXTURES) -> int:
    _ensure_env()
    with connect_db() as conn, conn.cursor() as cur:
        players = api_get("/players", {"team": team_id, "season": season})
        injuries = api_get("/injuries", {"team": team_id, "season": season})
        transfers = api_get("/transfers", {"team": team_id})
        fixtures = api_get("/fixtures", {"team": team_id, "season": season, "last": last_fixtures})

        injured_ids = {entry["player"]["id"] for entry in injuries if entry.get("player")}
        transferred_out_ids = {
            entry["player"]["id"]
            for entry in transfers
            if entry.get("player")
            and entry.get("transfers")
            and entry["transfers"][-1]["teams"]["out"]
            and entry["transfers"][-1]["teams"]["out"]["id"] == team_id
        }

        recently_seen_ids = _collect_recent_participants(fixtures)
        today = datetime.now(timezone.utc)

        updated_rows = 0
        for player_entry in players:
            player = player_entry.get("player") or {}
            pid = player.get("id")
            if not pid:
                continue
            pid = int(pid)
            is_injured = pid in injured_ids
            is_transferred = pid in transferred_out_ids
            seen_recently = pid in recently_seen_ids

            score = 100
            if not seen_recently:
                score -= 50
            if is_injured:
                score -= 30
            if is_transferred:
                score -= 30
            score = max(score, 0)

            last_seen = today.date() if seen_recently else None

            cur.execute(
                """
                update players
                set
                    is_injured = %s,
                    is_transferred_out = %s,
                    last_seen_in_lineup = %s,
                    active_score = %s,
                    updated_at = %s
                where player_id = %s
                """,
                (
                    is_injured,
                    is_transferred,
                    last_seen,
                    score,
                    today,
                    pid,
                ),
            )
            updated_rows += cur.rowcount

        conn.commit()

    return updated_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synchronise l'effectif actif via API-Football.")
    parser.add_argument("--team", type=int, required=True, help="Identifiant equipe API-Football.")
    parser.add_argument("--season", type=int, default=2024, help="Saison (ex: 2024).")
    parser.add_argument(
        "--last-fixtures",
        type=int,
        default=DEFAULT_LAST_FIXTURES,
        help="Nombre de derniers matches a analyser (lineups).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    updated = update_team(team_id=args.team, season=args.season, last_fixtures=args.last_fixtures)
    print(f"Team {args.team} saison {args.season} : {updated} lignes mises a jour.")


if __name__ == "__main__":
    main()
