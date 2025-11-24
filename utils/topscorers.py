from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from .api_calls import get_topscorers
from .ui_helpers import select_league_and_season
from .widgets import render_widget


def show_topscorers(
    default_league_id: Optional[int] = None,
    default_season: Optional[int] = None,
) -> None:
    st.header("Meilleurs buteurs")

    league_id, season, league_label = select_league_and_season(
        default_league_id=default_league_id,
        default_season=default_season,
    )
    st.caption(f"{league_label} - Saison {season}")

    with st.spinner("Chargement..."):
        scorers = get_topscorers(league_id, season) or []

    rows = []
    for rank, item in enumerate(scorers, start=1):
        if not isinstance(item, dict):
            continue
        player = item.get("player") or {}
        stats_list = item.get("statistics") or []
        stats = stats_list[0] if stats_list else {}
        goals_block = stats.get("goals") or {}
        shots_block = stats.get("shots") or {}
        rows.append(
            {
                "ID": player.get("id"),
                "Rang": rank,
                "Nom": player.get("name"),
                "Ã‚ge": player.get("age"),
                "Poste": stats.get("games", {}).get("position"),
                "Buts": goals_block.get("total"),
                "Buts sur penalty": goals_block.get("penalty"),
                "Tirs": shots_block.get("total"),
                "PrÃ©cision%": shots_block.get("on")
            }
        )
        if rank >= 20:
            break

    df = pd.DataFrame(rows)
    if df.empty:
        st.warning("Aucun buteur trouvÃ© pour cette sÃ©lection.")
        return

    st.dataframe(df.drop(columns=["ID"], errors="ignore"), hide_index=True, use_container_width=True)

    player_options = [
        (int(row.ID), row.Nom)
        for row in df.itertuples()
        if getattr(row, "ID", None)
    ]
    if player_options:
        selected_player = st.selectbox(
            "Widget officiel - Joueur",
            options=player_options,
            format_func=lambda item: item[1],
            key=f"topscorers_widget_{league_id}_{season}",
        )
        if selected_player:
            render_widget("player", height=720, player_id=int(selected_player[0]), season=season)

    st.markdown("---")
    st.subheader("Widget officiel - Buteurs")
    render_widget("topscorers", height=720, league=league_id, season=season)

