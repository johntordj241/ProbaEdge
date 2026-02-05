from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from .api_calls import get_topscorers
from .ui_helpers import select_league_and_season
from .profile import list_saved_scenes
from .widgets import render_widget


def show_topscorers(
    default_league_id: Optional[int] = None,
    default_season: Optional[int] = None,
) -> None:
    st.header("Meilleurs buteurs")

    saved_scenes = list_saved_scenes()
    scene_defaults_config = st.session_state.pop("_topscorers_scene_to_apply", None)
    sidebar_scene_options = [{"id": "", "name": "Aucune scène", "config": {}}] + saved_scenes
    sidebar_scene_labels = [entry["name"] or "Scène" for entry in sidebar_scene_options]
    current_sidebar_scene_id = st.session_state.get("_topscorers_scene_current", "")
    try:
        sidebar_default_index = next(
            idx for idx, entry in enumerate(sidebar_scene_options) if entry["id"] == current_sidebar_scene_id
        )
    except StopIteration:
        sidebar_default_index = 0
    sidebar_choice = st.sidebar.selectbox(
        "Scène rapide (buteurs)",
        options=list(range(len(sidebar_scene_options))),
        index=sidebar_default_index,
        format_func=lambda idx: sidebar_scene_labels[idx],
        key="topscorers_scene_select",
    )
    selected_sidebar_scene = sidebar_scene_options[sidebar_choice]
    if selected_sidebar_scene.get("id"):
        if selected_sidebar_scene["id"] != current_sidebar_scene_id:
            st.session_state["_topscorers_scene_to_apply"] = selected_sidebar_scene.get("config", {})
            st.session_state["_topscorers_scene_current"] = selected_sidebar_scene["id"]
            st.experimental_rerun()
    else:
        if current_sidebar_scene_id:
            st.session_state["_topscorers_scene_current"] = ""

    league_id, season, league_label = select_league_and_season(
        default_league_id=scene_defaults_config.get("league_id") if scene_defaults_config else default_league_id,
        default_season=scene_defaults_config.get("season") if scene_defaults_config else default_season,
        respect_user_defaults=False if scene_defaults_config else True,
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
