from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from .api_calls import get_cards
from .ui_helpers import select_league_and_season
from .widgets import render_widget


def show_cards(
    default_league_id: Optional[int] = None,
    default_season: Optional[int] = None,
) -> None:
    st.header("Classement des cartons")

    league_id, season, league_label = select_league_and_season(
        default_league_id=default_league_id,
        default_season=default_season,
        key_prefix="cards_",
    )
    st.caption(f"{league_label} - Saison {season}")

    with st.spinner("Chargement..."):
        cards = get_cards(league_id, season) or []

    rows = []
    for rank, item in enumerate(cards, start=1):
        if not isinstance(item, dict):
            continue
        player = item.get("player") or {}
        stats_list = item.get("statistics") or []
        stats = stats_list[0] if stats_list else {}
        cards_block = stats.get("cards") or {}
        rows.append(
            {
                "ID": player.get("id"),
                "Rang": rank,
                "Nom": player.get("name"),
                "�ge": player.get("age"),
                "Poste": stats.get("games", {}).get("position"),
                "Jaunes": cards_block.get("yellow"),
                "Jaunes (2�me)": cards_block.get("yellowred"),
                "Rouges": cards_block.get("red"),
            }
        )
        if rank >= 30:
            break

    df = pd.DataFrame(rows)
    if df.empty:
        st.warning("Aucun joueur trouv� avec des cartons pour cette s�lection.")
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
            key=f"cards_widget_{league_id}_{season}",
        )
        if selected_player:
            render_widget("player", height=720, player_id=int(selected_player[0]), season=season)


