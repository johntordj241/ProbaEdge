from __future__ import annotations

from typing import Dict, Optional

import streamlit as st

from .api_calls import get_h2h
from .ui_helpers import select_league_and_season, select_team
from .widgets import render_widget


def show_h2h(
    default_league_id: Optional[int] = None,
    default_season: Optional[int] = None,
) -> None:
    st.header("H2H (Confrontations directes)")

    league_id, season, league_label = select_league_and_season(
        default_league_id=default_league_id,
        default_season=default_season,
    )
    st.caption(f"{league_label} - Saison {season}")

    team1_id = select_team(
        league_id,
        season,
        default_team_id=None,
        placeholder="Equipe A",
        key=f"h2h_team_a_{league_id}_{season}",
    )
    if not team1_id:
        st.info("SÃ©lectionnez une Ã©quipe A.")
        return

    team2_id = select_team(
        league_id,
        season,
        default_team_id=None,
        placeholder="Equipe B",
        key=f"h2h_team_b_{league_id}_{season}",
    )
    if not team2_id or team2_id == team1_id:
        st.info("SÃ©lectionnez une Ã©quipe B diffÃ©rente.")
        return

    last_n = st.slider("Nombre de matchs", min_value=3, max_value=20, value=10, step=1)

    if st.button("Afficher les confrontations", use_container_width=True):
        with st.spinner("Chargement des confrontations..."):
            h2h = get_h2h(team1_id=team1_id, team2_id=team2_id, last=last_n)

        if not h2h:
            st.info("Aucune confrontation disponible pour ces Ã©quipes.")
            return

        for item in h2h:
            if not isinstance(item, dict):
                continue
            fixture = item.get("fixture") or {}
            league_info = item.get("league") or {}
            teams_info = item.get("teams") or {}
            goals = item.get("goals") or {}

            home = teams_info.get("home") or {}
            away = teams_info.get("away") or {}
            home_name = home.get("name", "?")
            away_name = away.get("name", "?")
            home_goals = goals.get("home", "-")
            away_goals = goals.get("away", "-")

            date_text = (fixture.get("date") or "")[:16].replace("T", " ")
            league_name = league_info.get("name", "")

            st.markdown(
                f"- **{home_name} {home_goals} - {away_goals} {away_name}** | {date_text} | {league_name}"
            )

        st.markdown("---")
        st.subheader("Widget officiel - H2H")
        render_widget("h2h", height=720, h2h=f"{team1_id}-{team2_id}")

