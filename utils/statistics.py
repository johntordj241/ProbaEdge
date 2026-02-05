from __future__ import annotations

from typing import Any, Dict, Optional

import altair as alt
import pandas as pd
import streamlit as st

from .api_calls import get_statistics
from .ui_helpers import select_league_and_season, select_team
from .profile import list_saved_scenes
from .widgets import render_widget


def _extract_stats(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list) and raw:
        return raw[0]
    return {}


def _minute_dataframe(goals_block: Dict[str, Any], side: str) -> pd.DataFrame:
    minute_data = goals_block.get(side, {}).get("minute") or {}
    records = []
    for interval, values in minute_data.items():
        if not isinstance(values, dict):
            continue
        total = values.get("total") or 0
        pct = values.get("percentage") or "0%"
        try:
            pct_value = float(str(pct).replace("%", "") or 0)
        except ValueError:
            pct_value = 0.0
        records.append({
            "Intervalle": interval,
            "Total": total,
            "Pourcentage": pct_value,
        })
    df = pd.DataFrame(records)
    if not df.empty:
        df = df.sort_values("Intervalle")
    return df


def show_statistics(
    default_league_id: Optional[int] = None,
    default_season: Optional[int] = None,
    default_team_id: Optional[int] = None,
) -> None:
    st.header("Statistiques d'équipe")

    saved_scenes = list_saved_scenes()
    scene_defaults_config = st.session_state.pop("_statistics_scene_to_apply", None)
    sidebar_scene_options = [{"id": "", "name": "Aucune scène", "config": {}}] + saved_scenes
    sidebar_scene_labels = [entry["name"] or "Scène" for entry in sidebar_scene_options]
    current_sidebar_scene_id = st.session_state.get("_statistics_scene_current", "")
    try:
        sidebar_default_index = next(
            idx for idx, entry in enumerate(sidebar_scene_options) if entry["id"] == current_sidebar_scene_id
        )
    except StopIteration:
        sidebar_default_index = 0
    sidebar_choice = st.sidebar.selectbox(
        "Scène rapide (stats)",
        options=list(range(len(sidebar_scene_options))),
        index=sidebar_default_index,
        format_func=lambda idx: sidebar_scene_labels[idx],
        key="statistics_scene_select",
    )
    selected_sidebar_scene = sidebar_scene_options[sidebar_choice]
    if selected_sidebar_scene.get("id"):
        if selected_sidebar_scene["id"] != current_sidebar_scene_id:
            st.session_state["_statistics_scene_to_apply"] = selected_sidebar_scene.get("config", {})
            st.session_state["_statistics_scene_current"] = selected_sidebar_scene["id"]
            st.experimental_rerun()
    else:
        if current_sidebar_scene_id:
            st.session_state["_statistics_scene_current"] = ""

    league_id, season, league_label = select_league_and_season(
        default_league_id=scene_defaults_config.get("league_id") if scene_defaults_config else default_league_id,
        default_season=scene_defaults_config.get("season") if scene_defaults_config else default_season,
        respect_user_defaults=False if scene_defaults_config else True,
    )
    st.caption(f"{league_label} - Saison {season}")

    team_id = select_team(
        league_id,
        season,
        default_team_id=scene_defaults_config.get("team_id") if scene_defaults_config else default_team_id,
        placeholder="Sélectionnez une équipe",
        key=f"stats_team_{league_id}_{season}",
    )
    if not team_id:
        st.info("Choisissez une équipe pour afficher les statistiques.")
        return

    with st.spinner("Chargement des statistiques..."):
        stats_raw = get_statistics(league_id, season, team_id)

    stats = _extract_stats(stats_raw)
    if not stats:
        st.warning("Aucune statistique disponible pour cette sélection.")
        return

    team = stats.get("team", {})
    fixtures = stats.get("fixtures", {})
    goals = stats.get("goals", {})

    total_played = fixtures.get("played", {}).get("total") or 0
    wins = fixtures.get("wins", {}).get("total") or 0
    draws = fixtures.get("draws", {}).get("total") or 0
    losses = fixtures.get("loses", {}).get("total") or 0

    goals_for = goals.get("for", {}).get("total", {}).get("total") or 0
    goals_against = goals.get("against", {}).get("total", {}).get("total") or 0
    avg_for = goals.get("for", {}).get("average", {}).get("total") or 0
    avg_against = goals.get("against", {}).get("average", {}).get("total") or 0

    st.subheader(team.get("name", "Équipe"))
    cols = st.columns(4)
    cols[0].metric("Matchs", total_played)
    cols[1].metric("Victoires", wins)
    cols[2].metric("Nuls", draws)
    cols[3].metric("Défaites", losses)

    cols = st.columns(4)
    cols[0].metric("Buts marqués", goals_for)
    cols[1].metric("Buts encaissés", goals_against)
    cols[2].metric("Moy. buts marqués", avg_for)
    cols[3].metric("Moy. buts encaissés", avg_against)

    st.divider()

    col_for, col_against = st.columns(2)
    df_for = _minute_dataframe(goals, "for")
    if not df_for.empty:
        chart_for = alt.Chart(df_for).mark_bar().encode(
            x="Intervalle",
            y=alt.Y("Total", title="Buts marqués"),
            color=alt.value("#2b8a3e"),
        )
        col_for.altair_chart(chart_for, use_container_width=True)
    else:
        col_for.info("Pas de répartition des buts marqués par intervalle.")

    df_against = _minute_dataframe(goals, "against")
    if not df_against.empty:
        chart_against = alt.Chart(df_against).mark_bar().encode(
            x="Intervalle",
            y=alt.Y("Total", title="Buts encaissés"),
            color=alt.value("#c92a2a"),
        )
        col_against.altair_chart(chart_against, use_container_width=True)
    else:
        col_against.info("Pas de répartition des buts encaissés par intervalle.")

    st.markdown("---")
    st.subheader("Widget officiel - �quipe")
    render_widget("team", height=680, team_id=int(team_id), league=league_id, season=season)
