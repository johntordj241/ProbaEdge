from __future__ import annotations

from typing import Optional

import streamlit as st

from .ui_helpers import select_league_and_season, load_leagues
from .widgets import render_widget


def show_leagues(
    default_league_id: Optional[int] = None,
    default_season: Optional[int] = None,
) -> None:
    st.header("Ligues & Compétitions")

    league_id, season, league_label = select_league_and_season(
        default_league_id=default_league_id,
        default_season=default_season,
    )
    st.caption(f"{league_label} - Saison {season}")

    st.subheader("Widget officiel - Ligue sélectionnée")
    render_widget("league", height=760, league=league_id, season=season)

    st.markdown("---")
    st.subheader("Widget officiel - Classement de la ligue")
    render_widget("standings", height=720, league=league_id, season=season)

    leagues = load_leagues()
    countries = sorted({entry.get("country") for entry in leagues if entry.get("country")})
    country = st.selectbox("Filtrer le widget global par pays", ["Tous"] + countries, index=0)

    widget_kwargs = {}
    if country != "Tous":
        widget_kwargs["country"] = country

    st.markdown("---")
    st.subheader("Widget officiel - Ligues (annuaire)")
    render_widget("leagues", height=760, **widget_kwargs)
