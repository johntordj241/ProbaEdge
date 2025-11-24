from __future__ import annotations

from typing import List, Optional

import altair as alt
import pandas as pd
import streamlit as st

from .players import get_players_normalized
from .models import PlayerInfo
from .ui_helpers import select_league_and_season, select_team
from .widgets import render_widget


def _players_dataframe(players: List[PlayerInfo]) -> pd.DataFrame:
    rows = []
    for player in players:
        rows.append(
            {
                "ID": player.id,
                "Nom": player.name,
                "Age": player.age,
                "Poste": player.position,
                "Numero": player.number,
                "Matches": player.appearances,
                "Titularisations": player.lineups,
                "Minutes": player.minutes,
                "Buts": player.goals,
                "Passes": player.assists,
                "Nation": player.nationality,
                "Note": player.rating,
            }
        )
    return pd.DataFrame(rows)


def show_players(
    default_league_id: Optional[int] = None,
    default_season: Optional[int] = None,
    default_team_id: Optional[int] = None,
) -> None:
    st.header("Effectif")

    league_id, season, league_label = select_league_and_season(
        default_league_id=default_league_id,
        default_season=default_season,
    )
    st.caption(f"{league_label} - Saison {season}")

    team_id = select_team(
        league_id,
        season,
        default_team_id=default_team_id,
        placeholder="Selectionnez une equipe",
        key=f"players_team_{league_id}_{season}",
    )
    if not team_id:
        st.info("Choisissez une equipe pour afficher l'effectif.")
        return

    page = st.number_input(
        "Page API (20 joueurs par page)", min_value=1, max_value=50, value=1, step=1
    )

    with st.spinner("Chargement des joueurs..."):
        players = get_players_normalized(league_id, season, team_id, page=int(page))

    if not players:
        st.warning("Aucun joueur trouve pour cette selection.")
        return

    df = _players_dataframe(players)
    if df.empty:
        st.warning("Impossible de structurer les donnees joueurs.")
        return

    positions = sorted(df["Poste"].dropna().unique()) if "Poste" in df else []
    selected_positions = st.multiselect("Filtrer par poste", positions, default=positions)
    filtered_df = df[df["Poste"].isin(selected_positions)] if selected_positions else df

    st.dataframe(filtered_df.drop(columns=["ID"], errors="ignore"), hide_index=True, use_container_width=True)

    if not filtered_df.empty and "Minutes" in filtered_df:
        chart = alt.Chart(filtered_df).mark_bar().encode(
            x=alt.X("Nom", sort="-y"),
            y=alt.Y("Minutes", title="Minutes jouees"),
            color=alt.Color("Poste", legend=None),
            tooltip=["Nom", "Minutes", "Poste"],
        ).properties(height=320)
        st.altair_chart(chart, use_container_width=True)

    st.markdown("---")
    st.subheader("Widget officiel - equipe")
    render_widget("team", height=720, team_id=int(team_id), league=league_id, season=season)

    player_options = [
        (int(row["ID"]), row["Nom"])
        for _, row in df.iterrows()
        if row.get("ID")
    ]
    if player_options:
        selected_player = st.selectbox(
            "Widget officiel - Joueur",
            options=player_options,
            format_func=lambda item: item[1],
            key=f"player_widget_{league_id}_{season}_{team_id}",
        )
        if selected_player:
            render_widget(
                "player",
                height=720,
                player_id=int(selected_player[0]),
                season=season,
                player_statistics=True,
                player_trophies=True,
                player_injuries=True,
            )
