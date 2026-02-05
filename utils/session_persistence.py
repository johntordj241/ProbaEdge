"""
Session persistante - Stocke l'authentification localement pour que l'utilisateur reste connecté
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
import streamlit as st


SESSION_DIR = Path.home() / ".proba_edge_sessions"
SESSION_DIR.mkdir(exist_ok=True)


def get_session_file() -> Path:
    """Retourne le chemin du fichier de session"""
    # Utiliser un identifiant unique pour chaque utilisateur
    username = os.getenv("USERNAME", "user")
    return SESSION_DIR / f"{username}_session.json"


def save_session(user_data: Dict[str, Any]) -> None:
    """Sauvegarde les données de session localement"""
    try:
        session_file = get_session_file()
        with open(session_file, "w") as f:
            json.dump(user_data, f, indent=2)
        # Rendre le fichier lisible uniquement par l'utilisateur
        os.chmod(session_file, 0o600)
    except Exception as e:
        print(f"Erreur lors de la sauvegarde de session: {e}")


def load_session() -> Optional[Dict[str, Any]]:
    """Charge les données de session sauvegardées"""
    try:
        session_file = get_session_file()
        if session_file.exists():
            with open(session_file, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"Erreur lors du chargement de session: {e}")
    return None


def clear_session() -> None:
    """Efface les données de session sauvegardées"""
    try:
        session_file = get_session_file()
        if session_file.exists():
            session_file.unlink()
    except Exception as e:
        print(f"Erreur lors de l'effacement de session: {e}")


def init_session_state() -> None:
    """Initialise st.session_state avec les données sauvegardées si disponibles"""
    if "auth_user" not in st.session_state:
        # Essayer de charger la session sauvegardée
        saved_session = load_session()
        if saved_session and "auth_user" in saved_session:
            st.session_state["auth_user"] = saved_session["auth_user"]
            st.session_state["auth_token"] = saved_session.get("auth_token")
            st.toast("✅ Session retrouvée - Connecté automatiquement!", icon="🔓")


def update_session_state(
    user_data: Dict[str, Any], token: Optional[str] = None
) -> None:
    """Met à jour la session et la sauvegarde"""
    st.session_state["auth_user"] = user_data
    if token:
        st.session_state["auth_token"] = token

    # Sauvegarder localement
    session_data = {
        "auth_user": user_data,
        "auth_token": token,
    }
    save_session(session_data)
