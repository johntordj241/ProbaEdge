#!/usr/bin/env python3
"""Importe les prédictions API-FOOTBALL pour des matches déjà disputés et les enregistre dans data/prediction_history.csv."""

from __future__ import annotations

import argparse
from datetime import datetime
from typing import Any, Dict, Iterable

from utils import api_calls
from utils.prediction_history import upsert_prediction, update_outcome


def _parse_percent(value: Any) -> float:
    if value in {None, ""}:
        return 0.0
    try:
        return float(str(value).replace("%", "").replace(",", ".")) / 100.0
    except (TypeError, ValueError):
        return 0.0


def _normalize_odds(prob: float) -> float:
    return max(0.0, min(1.0, float(prob or 0.0)))


def _target_fixtures(league_id: int, season: int, *, last: int) -> Iterable[Dict[str, Any]]:
    payload = api_calls.get_fixtures(league_id, season, last_n=last, status="FT") or []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        yield entry


def _winner_label(prediction: Dict[str, Any]) -> str:
    winner = prediction.get("winner") or {}
    name = winner.get("name")
    comment = winner.get("comment")
    if isinstance(name, str) and name:
        return name
    if isinstance(comment, str) and comment:
        return comment
    return ""


def _build_entry(
    fixture_id: int,
    league_id: int,
    season: int,
    home: Dict[str, Any],
    away: Dict[str, Any],
    fixture_date: str | None,
    api_prediction: Dict[str, Any],
) -> Dict[str, Any]:
    percent = api_prediction.get("percent") or {}
    probs_home = _parse_percent(percent.get("home"))
    probs_draw = _parse_percent(percent.get("draw"))
    probs_away = _parse_percent(percent.get("away"))
    over = _parse_percent(percent.get("over_25") or api_prediction.get("over_2_5"))
    under = 1.0 - over

    main_pick = _winner_label(api_prediction) or api_prediction.get("advice") or "Prediction API"
    main_confidence = int(round(max(probs_home, probs_draw, probs_away) * 100))
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "fixture_date": fixture_date or "",
        "fixture_id": str(fixture_id),
        "league_id": league_id,
        "season": season,
        "home_team": home.get("name", ""),
        "away_team": away.get("name", ""),
        "prob_home": _normalize_odds(probs_home),
        "prob_draw": _normalize_odds(probs_draw),
        "prob_away": _normalize_odds(probs_away),
        "prob_over_2_5": _normalize_odds(over),
        "prob_under_2_5": _normalize_odds(under),
        "main_pick": str(main_pick),
        "main_confidence": max(0, min(100, main_confidence)),
        "edge_comment": "Import auto depuis API-Football",
        "top_score": "",
        "total_pick": "Over 2.5 buts" if over >= 0.5 else "Under 2.5 buts",
        "status_snapshot": "FT",
    }
    return entry


def _update_result(fixture_id: int) -> None:
    details = api_calls.get_fixture_details(fixture_id) or []
    entry = details[0] if isinstance(details, list) and details else None
    if not isinstance(entry, dict):
        return
    fixture_block = entry.get("fixture") or {}
    teams = entry.get("teams") or {}
    status = fixture_block.get("status") or {}
    goals = entry.get("goals") or {}
    update_outcome(
        fixture_id,
        status=status.get("short", ""),
        goals_home=goals.get("home"),
        goals_away=goals.get("away"),
        winner=_winner_from_teams(teams),
    )


def _winner_from_teams(teams: Dict[str, Any]) -> str | None:
    home = teams.get("home") or {}
    away = teams.get("away") or {}
    if home.get("winner") is True:
        return "home"
    if away.get("winner") is True:
        return "away"
    if home.get("winner") is False and away.get("winner") is False:
        return "draw"
    return None


def backfill(league_id: int, season: int, *, last: int) -> int:
    inserted = 0
    for fixture in _target_fixtures(league_id, season, last=last):
        fixture_block = fixture.get("fixture") or {}
        fixture_id = fixture_block.get("id")
        if not fixture_id:
            continue
        predictions = api_calls.get_predictions(int(fixture_id)) or []
        horizon = predictions[0] if isinstance(predictions, list) and predictions else None
        if not isinstance(horizon, dict):
            continue
        ai_prediction = horizon.get("prediction") or {}
        if not isinstance(ai_prediction, dict) or not ai_prediction:
            continue
        teams = fixture.get("teams") or {}
        home = teams.get("home") or {}
        away = teams.get("away") or {}
        entry = _build_entry(
            int(fixture_id),
            league_id,
            season,
            home,
            away,
            fixture_block.get("date"),
            ai_prediction,
        )
        upsert_prediction(entry)
        _update_result(int(fixture_id))
        inserted += 1
        print(f"[OK] Fixture {fixture_id} importée")
    return inserted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill des prédictions API-Football dans prediction_history.csv")
    parser.add_argument("--league", type=int, required=True, help="ID de la ligue (ex: 61 pour Ligue 1)")
    parser.add_argument("--season", type=int, required=True, help="Saison cible (ex: 2025)")
    parser.add_argument("--last", type=int, default=20, help="Nombre de matches terminés à importer (default: 20)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    count = backfill(args.league, args.season, last=args.last)
    print(f"{count} prédiction(s) importée(s).")


if __name__ == "__main__":
    main()

