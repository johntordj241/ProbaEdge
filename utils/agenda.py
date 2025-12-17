from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from .api_calls import get_fixtures_by_date
from .profile import list_saved_scenes
from .ui_helpers import load_leagues


def _build_agenda_rows(fixtures: List[Dict[str, Any]]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for item in fixtures:
        league = item.get("league") or {}
        fixture = item.get("fixture") or {}
        teams = item.get("teams") or {}
        home = teams.get("home", {}).get("name")
        away = teams.get("away", {}).get("name")
        kickoff = fixture.get("date")
        status = (fixture.get("status") or {}).get("long")
        rows.append(
            {
                "Match": f"{home} vs {away}",
                "Heure": kickoff,
                "Compétition": league.get("name"),
                "Pays": league.get("country"),
                "Statut": status,
            }
        )
    return pd.DataFrame(rows)


def show_agenda(default_date: Optional[date] = None) -> None:
    st.header("Agenda des matchs")
    st.caption("Vue transversale des rencontres du jour, tous championnats confondus.")

    target_date = default_date or date.today()
    selected_date = st.date_input("Date à afficher", value=target_date)

    st.subheader("Filtres")
    leagues = load_leagues()
    league_options = ["Tous"] + [entry["label"] for entry in leagues]
    selected_league = st.selectbox("Compétition", league_options)

    scenes = list_saved_scenes()
    if scenes:
        scene_options = ["Aucune"] + [scene["name"] for scene in scenes]
        st.selectbox("Scène rapide", scene_options)

    with st.spinner("Chargement de l'agenda..."):
        fixtures = get_fixtures_by_date(selected_date.isoformat()) or []

    if selected_league != "Tous":
        league_obj = next((entry for entry in leagues if entry["label"] == selected_league), None)
        if league_obj:
            fixtures = [
                fx for fx in fixtures if (fx.get("league") or {}).get("id") == league_obj["id"]
            ]

    df = _build_agenda_rows(fixtures)
    if df.empty:
        st.info("Aucun match trouvé pour cette sélection.")
    else:
        st.dataframe(df, hide_index=True, use_container_width=True)
