from __future__ import annotations

from typing import Optional

import streamlit as st

from .api_calls import get_venues
from .ui_helpers import load_leagues, select_league_and_season, select_team


def _available_countries() -> list[str]:
    leagues = load_leagues()
    return sorted({entry["country"] for entry in leagues if entry["country"]})


def show_venues(
    default_league_id: Optional[int] = None,
    default_season: Optional[int] = None,
) -> None:
    st.header("Stades")

    mode = st.radio("Filtrer par", ["Pays", "Equipe"], horizontal=True)

    if mode == "Pays":
        countries = _available_countries()
        country = st.selectbox("Pays", options=["Tous"] + countries, index=0)
        country_param = None if country == "Tous" else country
        team_param = None
    else:
        league_id, season, league_label = select_league_and_season(
            default_league_id=default_league_id,
            default_season=default_season,
        )
        st.caption(f"{league_label} - Saison {season}")
        team_param = select_team(
            league_id,
            season,
            default_team_id=None,
            placeholder="Choisissez une équipe",
            key=f"venues_team_{league_id}_{season}",
        )
        if not team_param:
            st.info("Choisissez une équipe pour afficher son stade.")
            return
        country_param = None

    with st.spinner("Chargement des stades..."):
        venues = get_venues(country_param, team_param) or []

    if not venues:
        st.warning("Aucun stade trouvé pour cette sélection.")
        return

    for venue in venues[:20]:
        if not isinstance(venue, dict):
            continue
        name = venue.get("name", "Inconnu")
        city = venue.get("city", "Ville inconnue")
        capacity = venue.get("capacity")
        capacity_text = f"{capacity} places" if capacity else "Capacité inconnue"
        st.write(f"{name} - {city} ({capacity_text})")
