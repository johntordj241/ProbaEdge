from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from .api_calls import get_standings as fetch_standings
from .ui_helpers import select_league_and_season
from .widgets import render_widget
from .form_utils import render_form_table


def _extract_table(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(data, list) or not data:
        return []
    league_block = data[0].get("league", {})
    standings = league_block.get("standings")
    if not standings:
        return []
    return standings[0]


def show_standings(
    default_league_id: Optional[int] = None,
    default_season: Optional[int] = None,
) -> None:
    st.header("Classement du championnat")

    league_id, season, league_label = select_league_and_season(
        default_league_id=default_league_id,
        default_season=default_season,
    )
    st.caption(f"{league_label} - Saison {season}")

    scope = st.radio(
        "Vue",
        ("Tous", "Domicile", "Extérieur"),
        horizontal=True,
        help="Sélectionnez la vue globale ou uniquement les matches à domicile/à l'extérieur.",
    )
    scope_map = {"Tous": "all", "Domicile": "home", "Extérieur": "away"}
    scope_key = scope_map.get(scope, "all")

    with st.spinner("Chargement du classement..."):
        standings_data = fetch_standings(league_id, season)

    table = _extract_table(standings_data)
    if not table:
        st.warning("Pas de classement disponible pour cette sélection.")
        return

    rows: List[Dict[str, Any]] = []
    form_rows: List[Dict[str, Any]] = []
    form_scope_missing = False
    for entry in table:
        if not isinstance(entry, dict):
            continue
        team_info = entry.get("team") or {}
        stats = entry.get(scope_key) or entry.get("all") or {}
        goals = stats.get("goals") or {}
        wins = stats.get("win") or 0
        draws = stats.get("draw") or 0
        losses = stats.get("lose") or 0
        pts = entry.get("points")
        if scope_key != "all":
            pts = wins * 3 + draws
        rows.append(
            {
                "Pos": entry.get("rank"),
                "Equipe": team_info.get("name"),
                "J": stats.get("played"),
                "Pts": pts,
                "V": wins,
                "N": draws,
                "D": losses,
                "Buts +": goals.get("for"),
                "Buts -": goals.get("against"),
                "+/-": goals.get("for", 0) - goals.get("against", 0),
            }
        )
        form_value = ""
        if scope_key == "all":
            form_value = entry.get("form") or ""
        else:
            scoped_form = (entry.get(scope_key) or {}).get("form")
            if scoped_form:
                form_value = scoped_form
            else:
                form_value = entry.get("form") or ""
                form_scope_missing = True
        form_rows.append({"team": team_info.get("name", "?"), "form": form_value})

    if scope_key != "all":
        rows.sort(key=lambda item: (item["Pts"] or 0, item["+/-"] or 0, item["Buts +"] or 0), reverse=True)
        for idx, row in enumerate(rows, start=1):
            row["Pos"] = idx

    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, use_container_width=True)

    if form_rows:
        st.subheader("Forme visuelle (5 derniers matches)")
        st.markdown(render_form_table(form_rows), unsafe_allow_html=True)
        if form_scope_missing and scope_key != "all":
            st.info("Les données de forme domicile/extérieur ne sont pas fournies par l'API pour cette ligue. Affichage de la forme globale à la place.")

    st.markdown("---")
    st.subheader("Widget officiel - Classement")
    if scope_key != "all":
        st.info("Le widget officiel n'affiche que les stats globales. Sélectionnez 'Tous' pour le consulter.")
    else:
        render_widget("standings", height=720, league=league_id, season=season)

