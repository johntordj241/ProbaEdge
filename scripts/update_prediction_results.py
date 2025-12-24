#!/usr/bin/env python3
"""
Met à jour les entrées de data/prediction_history.csv en allant chercher le score
et le statut final des matches encore marqués comme pendants.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from utils import api_calls
from utils.prediction_history import FINISHED_STATUS, update_outcome

MAX_FIXTURES = 200


def _winner_from_payload(entry: dict) -> Optional[str]:
    teams = entry.get("teams") or {}
    goals = entry.get("goals") or {}
    home = teams.get("home") or {}
    away = teams.get("away") or {}
    if home.get("winner") is True:
        return "home"
    if away.get("winner") is True:
        return "away"
    if goals.get("home") is not None and goals.get("home") == goals.get("away"):
        return "draw"
    return None


def update_missing_results(limit: int = MAX_FIXTURES) -> int:
    df = pd.read_csv("data/prediction_history.csv")
    missing = df[
        (df["fixture_id"].notna())
        & (
            df["result_status"].isna()
            | (~df["result_status"].astype(str).str.upper().isin(FINISHED_STATUS))
        )
    ]
    processed = 0
    for fixture_id in missing["fixture_id"].unique():
        if pd.isna(fixture_id):
            continue
        try:
            fixture_int = int(float(fixture_id))
        except (TypeError, ValueError):
            continue
        payload = api_calls.get_fixture_details(fixture_int) or []
        match = payload[0] if isinstance(payload, list) and payload else None
        if not isinstance(match, dict):
            continue
        status_block = (match.get("fixture") or {}).get("status") or {}
        short = (status_block.get("short") or "").upper()
        if short not in FINISHED_STATUS:
            continue
        goals = match.get("goals") or {}
        update_outcome(
            fixture_int,
            status=short,
            goals_home=goals.get("home"),
            goals_away=goals.get("away"),
            winner=_winner_from_payload(match),
        )
        processed += 1
        print(f"[OK] Fixture {fixture_int} mis à jour ({short})")
        if processed >= limit:
            break
    return processed


def main() -> None:
    updated = update_missing_results()
    print(f"{updated} fixture(s) mis(es) à jour.")


if __name__ == "__main__":
    main()
