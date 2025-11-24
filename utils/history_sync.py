from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import streamlit as st

from .api_calls import get_fixtures
from .history import HEADER as HISTORY_HEADER
from .history import HISTORIQUE_PATH
from .history import load_history, save_history
from .models import normalize_team_list, normalize_team_entry
from .ui_helpers import select_league_and_season

REQUIRED_SEASONS = 3
PERSIST_COLUMNS = HISTORY_HEADER
STATUS_FINISHED = {"FT", "AET", "PEN"}


def _existing_fixture_ids(rows: Iterable[Dict[str, Any]]) -> set[int]:
    ids = set()
    for row in rows:
        try:
            ids.add(int(row.get("fixture_id")))
        except (TypeError, ValueError):
            continue
    return ids


def _append_new_rows(existing: List[Dict[str, Any]], new_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    combined = {int(row["fixture_id"]): row for row in existing if row.get("fixture_id")}
    for row in new_rows:
        fid = int(row["fixture_id"])
        combined[fid] = row
    return [combined[key] for key in sorted(combined.keys())]


def _normalize_fixture(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fixture_block = entry.get("fixture") if isinstance(entry.get("fixture"), dict) else {}
    league_block = entry.get("league") if isinstance(entry.get("league"), dict) else {}
    teams_block = entry.get("teams") if isinstance(entry.get("teams"), dict) else {}

    fixture_id = fixture_block.get("id")
    if fixture_id is None:
        return None

    date_value = fixture_block.get("date")
    try:
        date_iso = datetime.fromisoformat(date_value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S") if date_value else ""
    except Exception:
        date_iso = date_value or ""

    status_short = (fixture_block.get("status", {}) or {}).get("short", "")
    if status_short not in STATUS_FINISHED:
        return None

    home_block = teams_block.get("home") if isinstance(teams_block.get("home"), dict) else {}
    away_block = teams_block.get("away") if isinstance(teams_block.get("away"), dict) else {}

    goals_block = entry.get("goals") if isinstance(entry.get("goals"), dict) else {}

    return {
        "fixture_id": str(fixture_id),
        "league_id": str(league_block.get("id", "")),
        "season": str(league_block.get("season", "")),
        "date": date_iso,
        "home_team_id": str(home_block.get("id", "")),
        "home_team": home_block.get("name", ""),
        "away_team_id": str(away_block.get("id", "")),
        "away_team": away_block.get("name", ""),
        "status": status_short,
        "goals_home": str(goals_block.get("home", "")),
        "goals_away": str(goals_block.get("away", "")),
    }


def update_history_view() -> None:
    st.header("Historique matches")
    existing = load_history()
    st.caption(f"Entr?es existantes: {len(existing)}")
    st.write(HISTORIQUE_PATH)

    league_id, season, league_label = select_league_and_season()
    st.caption(f"{league_label} - Saison {season}")

    target_seasons = [season - offset for offset in range(REQUIRED_SEASONS)]
    st.write(f"Saisons cible: {target_seasons}")

    new_rows: List[Dict[str, Any]] = []
    existing_ids = _existing_fixture_ids(existing)

    for year in target_seasons:
        with st.spinner(f"R?cup?ration saison {year}..."):
            fixtures = get_fixtures(league_id, year, status="FT") or []
        for entry in fixtures:
            row = _normalize_fixture(entry) or None
            if not row:
                continue
            if int(row["fixture_id"]) in existing_ids:
                continue
            new_rows.append(row)

    if not new_rows:
        st.info("Aucun nouveau match fini ? ajouter.")
    else:
        st.success(f"{len(new_rows)} nouvelles entr?es.")
        combined = _append_new_rows(existing, new_rows)
        save_history(combined)
        st.caption(f"Total mis ? jour: {len(combined)}")

    if existing or new_rows:
        df = pd.DataFrame(existing + new_rows, columns=PERSIST_COLUMNS)
        st.dataframe(df.tail(200), hide_index=True, use_container_width=True)

__all__ = ["update_history_view", "_normalize_fixture"]
