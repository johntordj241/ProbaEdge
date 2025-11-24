from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from .api_calls import get_standings as fetch_standings
from .ui_helpers import select_league_and_season
from .widgets import render_widget


def _extract_table(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(data, list) or not data:
        return []
    league_block = data[0].get("league", {})
    standings = league_block.get("standings")
    if not standings:
        return []
    return standings[0]


FORM_LABELS = {
    "W": "V",
    "L": "D",
    "D": "N",
    "V": "V",
    "N": "N",
}

FORM_CLASSES = {
    "W": "win",
    "V": "win",
    "L": "loss",
    "D": "loss",
    "N": "draw",
}


def _form_badges_html(form: Optional[str]) -> str:
    if not form:
        return "<span class='form-badge neutral'>-</span>"
    badges: list[str] = []
    cleaned = form.replace(" ", "").replace(",", "")
    for char in cleaned.strip():
        label = FORM_LABELS.get(char.upper(), char.upper())
        css_class = FORM_CLASSES.get(char.upper(), "neutral")
        badges.append(f"<span class='form-badge {css_class}'>{label}</span>")
    return "".join(badges)


def _render_form_table(teams: list[dict[str, Any]]) -> str:
    rows_html = []
    for entry in teams:
        rows_html.append(
            f"<tr><td class='team'>{entry['team']}</td><td>{_form_badges_html(entry['form'])}</td></tr>"
        )
    return f"""
    <style>
    .form-table {{
        border-collapse: collapse;
        width: 100%;
    }}
    .form-table td {{
        padding: 4px 8px;
        border-bottom: 1px solid rgba(255,255,255,0.1);
    }}
    .form-table td.team {{
        font-weight: 600;
        width: 30%;
    }}
    .form-badge {{
        display: inline-block;
        width: 22px;
        height: 22px;
        line-height: 22px;
        text-align: center;
        border-radius: 4px;
        margin-right: 4px;
        color: #fff;
        font-size: 0.8rem;
    }}
    .form-badge.win {{ background-color: #2ecc71; }}
    .form-badge.draw {{ background-color: #f1c40f; color: #111; }}
    .form-badge.loss {{ background-color: #e74c3c; }}
    .form-badge.neutral {{ background-color: #7f8c8d; }}
    </style>
    <table class="form-table">
        {''.join(rows_html)}
    </table>
    """


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
        st.markdown(_render_form_table(form_rows), unsafe_allow_html=True)
        if form_scope_missing and scope_key != "all":
            st.info("Les données de forme domicile/extérieur ne sont pas fournies par l'API pour cette ligue. Affichage de la forme globale à la place.")

    st.markdown("---")
    st.subheader("Widget officiel - Classement")
    if scope_key != "all":
        st.info("Le widget officiel n'affiche que les stats globales. Sélectionnez 'Tous' pour le consulter.")
    else:
        render_widget("standings", height=720, league=league_id, season=season)

