from __future__ import annotations

import requests
import streamlit as st

from utils.config import BASE_URL, get_headers


def get_odds(fixture_id: int):
    """Récupère les cotes pré-match pour une rencontre."""
    url = f"{BASE_URL}/odds"
    params = {"fixture": fixture_id}
    response = requests.get(url, headers=get_headers(), params=params)
    return response.json()


def get_live_odds(fixture_id: int):
    """Récupère les cotes live pendant le match."""
    url = f"{BASE_URL}/odds/live"
    params = {"fixture": fixture_id}
    response = requests.get(url, headers=get_headers(), params=params)
    return response.json()


def show_odds(odds_payload: dict[str, any]):
    """Affiche les cotes formatées dans Streamlit."""
    st.subheader("📊 Cotes disponibles")
    response = odds_payload.get("response") if isinstance(odds_payload, dict) else None
    if not response:
        st.warning("Pas de cotes disponibles.")
        return

    try:
        bookmakers = response[0].get("bookmakers", [])
        for bookmaker in bookmakers:
            st.markdown(f"### 💼 {bookmaker.get('name')}")
            for bet in bookmaker.get("bets", []):
                st.write(f"**{bet.get('name')}**")
                for value in bet.get("values", []):
                    st.write(f"- {value.get('value')} : {value.get('odd')}")
    except Exception as exc:  # pragma: no cover - affichage debug
        st.error(f"Erreur dans l'affichage des cotes : {exc}")
        st.json(odds_payload)
