import requests
import streamlit as st

from utils.config import BASE_URL, get_headers


def get_injuries(league_id, season):
    """Récupère les joueurs blessés via l'API Football."""
    url = f"{BASE_URL}/injuries"
    params = {"league": league_id, "season": season}
    response = requests.get(url, headers=get_headers(), params=params)
    if response.status_code == 200:
        return response.json()
    return {"response": []}


def show_injuries(league_id, season):
    """Affiche les blessures pour la ligue/ saison sélectionnée."""
    injuries = get_injuries(league_id, season)
    if not injuries or "response" not in injuries:
        st.warning("Aucun blessé trouvé.")
        return

    st.subheader("🩺 Joueurs blessés")
    for entry in injuries["response"]:
        player = entry.get("player", {})
        team = entry.get("team", {})
        st.write(
            f"**{player.get('name')}** - {team.get('name')} - {player.get('type', 'inconnu')}"
        )
