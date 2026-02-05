from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from .api_calls import get_topassists
from .ui_helpers import select_league_and_season
from .widgets import render_widget


def show_topassists(
    default_league_id: Optional[int] = None,
    default_season: Optional[int] = None,
) -> None:
    st.header("Meilleurs passeurs")

    league_id, season, league_label = select_league_and_season(
        default_league_id=default_league_id,
        default_season=default_season,
    )
    st.caption(f"{league_label} - Saison {season}")

    with st.spinner("Chargement..."):
        assists = get_topassists(league_id, season) or []

    rows = []
    for rank, item in enumerate(assists, start=1):
        if not isinstance(item, dict):
            continue
        player = item.get("player") or {}
        stats_list = item.get("statistics") or []
        stats = stats_list[0] if stats_list else {}
        goals_block = stats.get("goals") or {}
        passes_block = stats.get("passes") or {}
        rows.append(
            {
                "Rang": rank,
                "Nom": player.get("name"),
                "Ã‚ge": player.get("age"),
                "Poste": stats.get("games", {}).get("position"),
                "Passes": goals_block.get("assists"),
                "Passes clÃ©s": passes_block.get("key"),
                "Passes tentÃ©es": passes_block.get("total"),
                "PrÃ©cision%": passes_block.get("accuracy"),
            }
        )
        if rank >= 20:
            break

    df = pd.DataFrame(rows)
    if df.empty:
        st.warning("Aucun passeur trouvÃ© pour cette sÃ©lection.")
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
            key=f"topassists_widget_{league_id}_{season}",
        )
        if selected_player:
            render_widget("player", height=720, player_id=int(selected_player[0]), season=season)

    st.markdown("---")
    st.subheader("Widget officiel - Passeurs")
    render_widget("topassists", height=720, league=league_id, season=season)

