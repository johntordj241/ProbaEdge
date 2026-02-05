from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from .api_calls import get_fixtures_by_date
from .profile import list_saved_scenes
from .ui_helpers import load_leagues


def _format_kickoff(value: Any) -> str:
    if not value:
        return ""
    try:
        dt = pd.to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.tz_localize("UTC")
        dt_paris = dt.tz_convert("Europe/Paris")
        return dt_paris.strftime("%d/%m %H:%M")
    except Exception:
        return str(value)


def _fixture_meta(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fixture = entry.get("fixture") or {}
    teams = entry.get("teams") or {}
    league = entry.get("league") or {}
    fixture_id = fixture.get("id")
    home = teams.get("home", {}).get("name", "?")
    away = teams.get("away", {}).get("name", "?")
    kickoff = _format_kickoff(fixture.get("date"))
    if not fixture_id:
        return None
    label = f"{kickoff} · {home} vs {away} ({league.get('name','competition inconnue')})"
    snippet = f"{fixture_id} | {home} vs {away} | {kickoff}"
    return {"id": fixture_id, "label": label, "snippet": snippet}


def _build_agenda_rows(fixtures: List[Dict[str, Any]]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for item in fixtures:
        league = item.get("league") or {}
        fixture = item.get("fixture") or {}
        teams = item.get("teams") or {}
        home = teams.get("home", {}).get("name")
        away = teams.get("away", {}).get("name")
        kickoff = _format_kickoff(fixture.get("date"))
        status = (fixture.get("status") or {}).get("long")
        rows.append(
            {
                "Fixture ID": fixture.get("id"),
                "Match": f"{home} vs {away}",
                "Heure (Paris)": kickoff,
                "Competition": league.get("name"),
                "Pays": league.get("country"),
                "Statut": status,
            }
        )
    return pd.DataFrame(rows)


def show_agenda(default_date: Optional[date] = None) -> None:
    st.header("Agenda des matchs")
    st.caption("Vue transversale des rencontres du jour, tous championnats confondus.")

    target_date = default_date or date.today()
    selected_date = st.date_input("Date a afficher", value=target_date)

    with st.spinner("Chargement des matchs du jour..."):
        fixtures_all = get_fixtures_by_date(selected_date.isoformat(), timezone="Europe/Paris") or []

    quick_options = [meta for meta in (_fixture_meta(entry) for entry in fixtures_all) if meta]
    if quick_options:
        st.subheader("Actions rapides")
        selected_meta = st.selectbox(
            "Choisir un match pour copier ou envoyer vers d'autres modules",
            quick_options,
            format_func=lambda item: item["label"],
        )
        st.text_input(
            "Copier / coller ce repere",
            value=selected_meta["snippet"],
            key=f"agenda_copy_{selected_meta['id']}",
        )
        col_pred, col_coach = st.columns(2)
        if col_pred.button("Preparer l'onglet Predictions", key=f"agenda_to_predictions_{selected_meta['id']}"):
            st.session_state["preferred_fixture_id"] = str(selected_meta["id"])
            st.success("Ouvrez l'onglet Predictions : le match sera pre-selectionne.")
        if col_coach.button("Envoyer au Coach IA", key=f"agenda_to_coach_{selected_meta['id']}"):
            st.session_state["coach_prefill"] = (
                f"Peux-tu analyser {selected_meta['label']} "
                f"(fixture {selected_meta['id']}) et qualifier le signal et son incertitude ?"
            )
            st.success("Ouvrez l'Assistant IA pour poursuivre la discussion.")

    tabs = st.tabs(["Panorama mondial", "Par competition API"])

    with tabs[0]:
        world_df = _build_agenda_rows(fixtures_all)
        search = st.text_input("Filtrer (club, competition, pays)", placeholder="Premier League, Real Madrid...")
        if not world_df.empty and search:
            needle = search.lower()
            mask = world_df.apply(
                lambda row: any(needle in str(value).lower() for value in row.values if value), axis=1
            )
            world_df = world_df[mask]
        if world_df.empty:
            st.info("Aucun match trouve pour cette date.")
        else:
            st.dataframe(world_df, hide_index=True, use_container_width=True)

    with tabs[1]:
        st.subheader("Filtres API Football")
        leagues = load_leagues()
        league_options = ["Tous"] + [entry["label"] for entry in leagues]
        selected_league = st.selectbox("Competition", league_options, key="agenda_league_select")

        scenes = list_saved_scenes()
        if scenes:
            scene_options = ["Aucune"] + [scene["name"] for scene in scenes]
            st.selectbox("Scene rapide", scene_options, key="agenda_scene_select")

        fixtures = list(fixtures_all)

        if selected_league != "Tous":
            league_obj = next((entry for entry in leagues if entry["label"] == selected_league), None)
            if league_obj:
                fixtures = [
                    fx for fx in fixtures if (fx.get("league") or {}).get("id") == league_obj["id"]
                ]

        df = _build_agenda_rows(fixtures)
        if df.empty:
            st.info("Aucun match trouve pour cette selection via API Football.")
        else:
            st.dataframe(df, hide_index=True, use_container_width=True)
