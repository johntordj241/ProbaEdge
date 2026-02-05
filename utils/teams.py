from __future__ import annotations

from typing import List, Dict, Any, Optional

from .api_calls import get_teams as api_get_teams
from .models import normalize_team_list, TeamInfo


def fetch_teams(league_id: int, season: int, *, normalized: bool = True) -> List[Any]:
    raw = api_get_teams(league_id, season) or []
    if not normalized:
        return raw if isinstance(raw, list) else []
    return normalize_team_list(raw if isinstance(raw, list) else [])


def show_teams(league_id: int, season: int) -> None:
    import streamlit as st

    st.subheader("Equipes")
    teams = fetch_teams(league_id, season, normalized=True)
    if not teams:
        st.warning("Aucune equipe trouvee.")
        return
    for team in teams:
        venue = team.venue_name or "Stade inconnu"
        st.write(f"**{team.name}** ? {venue}")

__all__ = ["fetch_teams", "show_teams", "TeamInfo"]
