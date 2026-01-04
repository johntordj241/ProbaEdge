from __future__ import annotations

import base64
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st

from utils.auth_ui import ensure_authenticated, render_account_sidebar
from utils.coach_ui import render_coach_widget
from utils.cards import show_cards
from utils.constants import DEFAULT_LEAGUE_ID, DEFAULT_SEASON, DEFAULT_TEAM_ID
from utils.chat_ui import show_chat_assistant
from utils.dashboard import show_dashboard
from utils.fixtures import show_matches
from utils.guides import show_guides
from utils.h2h import show_h2h
from utils.match_filter import show_bookmaker_availability
from utils.odds import show_odds
from utils.players_ui import show_players
from utils.prediction_history import training_progress
from utils.predictions import show_predictions
from utils.roadmap import show_roadmap
from utils.standings import show_standings
from utils.statistics import show_statistics
from utils.test_api_calls import run_all_tests
from utils.topassists import show_topassists
from utils.topscorers import show_topscorers
from utils.venues import show_venues
from utils.profile_ui import show_profile
from utils.analytics_ui import show_prediction_performance
from utils.admin_ui import show_admin
from utils.agenda import show_agenda
from utils.history_sync import update_history_view
from utils.performance_dashboard import show_performance_dashboard
from utils.cache import render_cache_controls
from utils.supervision import render_supervision_status
from utils.supervision_dashboard import show_supervision_dashboard
from utils.reports import show_reports
from utils.offers import show_offers
from utils.private_report import show_private_report
from utils.institutional import (
    show_access_governance,
    show_methodology_limits,
    show_security_data,
    show_legal_responsibility,
)
from utils.subscription import (
    plan_allows,
    menu_required_plan,
    plan_label,
    format_upgrade_hint,
    normalize_plan,
    COACH_MIN_PLAN,
)

st.set_page_config(
    page_title="Proba Edge",
    layout="wide",
    page_icon="assets/logo_proba_edge.png",
)

DEFAULT_LEAGUE_ID = 61
DEFAULT_SEASON = 2025
DEFAULT_TEAM_ID = 85
LOGO_PATH = ROOT_DIR / "assets" / "logo_proba_edge.svg"

if not ensure_authenticated():
    st.stop()

current_user = st.session_state.get("auth_user") or {}
CURRENT_PLAN = normalize_plan(current_user.get("plan"))

MENU_OPTIONS = [
    "Dashboard",
    "Assistant IA",
    "Agenda",
    "Roadmap",
    "Rapports",
    "Guides",
    "Offres & abonnements",
    "Audit interne",
    "Matchs",
    "Statistiques",
    "Classement",
    "Joueurs",
    "Predictions",
    "Buteurs",
    "Passeurs",
    "Cartons",
    "Cotes",
    "Bookmakers",
    "Profil",
    "Historique",
    "Performance IA",
    "Tableau IA",
    "Supervision",
    "Stades",
    "H2H",
    "Tester l'API",
    "Admin",
    "Acces & gouvernance",
    "Methodologie & limites",
    "Securite & donnees",
    "Mentions legales",
]

COACH_ALLOWED_PAGES = {
    "Cartons",
    "Cotes",
    "Bookmakers",
    "H2H",
    "Performance IA",
    "Tableau IA",
    "Supervision",
}

def _render_gate_message(menu_name: str, required_plan: str) -> None:
    st.error(f"Cette section requiert l'offre {plan_label(required_plan)}.")
    st.info(format_upgrade_hint(CURRENT_PLAN, required_plan))



if LOGO_PATH.exists():
    if LOGO_PATH.suffix.lower() == ".svg":
        svg_payload = base64.b64encode(LOGO_PATH.read_bytes()).decode("utf-8")
        st.sidebar.markdown(
            f"<img src='data:image/svg+xml;base64,{svg_payload}' "
            "style='width: 180px; display: block; margin: 0 auto;'/>",
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.image(str(LOGO_PATH), width=180)
    st.sidebar.markdown("---")

render_cache_controls(st.sidebar, key_prefix="main_")
st.sidebar.markdown("---")
render_supervision_status(st.sidebar)
st.sidebar.markdown("---")
render_account_sidebar(st.sidebar)

menu = st.sidebar.radio("Navigation", MENU_OPTIONS)

st.divider()

progress = training_progress(target=100)
ready = progress["ready"]
target = progress["target"]
remaining = progress["remaining"]
if remaining > 0:
    st.warning(f"Entrainement ML : {ready} / {target} matches finalises. Il en manque {remaining} pour lancer la mise a jour du modele.")
else:
    st.success("Entrainement ML : nous sommes pret a relancer l'entrainement (100/100).")

required_plan = menu_required_plan(menu)
access_granted = True
if required_plan and not plan_allows(CURRENT_PLAN, required_plan):
    _render_gate_message(menu, required_plan)
    access_granted = False
if access_granted and menu == "Admin" and CURRENT_PLAN != "elite":
    _render_gate_message(menu, "elite")
    access_granted = False

if access_granted:
    if menu == "Dashboard":
        show_dashboard(DEFAULT_LEAGUE_ID, DEFAULT_SEASON, DEFAULT_TEAM_ID)
    elif menu == "Assistant IA":
        show_chat_assistant()
    elif menu == "Agenda":
        show_agenda()
    elif menu == "Roadmap":
        show_roadmap()
    elif menu == "Rapports":
        show_reports()
    elif menu == "Guides":
        show_guides()
    elif menu == "Offres & abonnements":
        show_offers()
    elif menu == "Audit interne":
        show_private_report()
    elif menu == "Matchs":
        show_matches(DEFAULT_LEAGUE_ID, DEFAULT_SEASON)
    elif menu == "Statistiques":
        show_statistics(DEFAULT_LEAGUE_ID, DEFAULT_SEASON, DEFAULT_TEAM_ID)
    elif menu == "Classement":
        show_standings(DEFAULT_LEAGUE_ID, DEFAULT_SEASON)
    elif menu == "Joueurs":
        show_players(DEFAULT_LEAGUE_ID, DEFAULT_SEASON, DEFAULT_TEAM_ID)
    elif menu == "Predictions":
        show_predictions(DEFAULT_LEAGUE_ID, DEFAULT_SEASON)
    elif menu == "Buteurs":
        show_topscorers(DEFAULT_LEAGUE_ID, DEFAULT_SEASON)
    elif menu == "Passeurs":
        show_topassists(DEFAULT_LEAGUE_ID, DEFAULT_SEASON)
    elif menu == "Cartons":
        show_cards(DEFAULT_LEAGUE_ID, DEFAULT_SEASON)
    elif menu == "Cotes":
        show_odds(DEFAULT_LEAGUE_ID, DEFAULT_SEASON)
    elif menu == "Bookmakers":
        show_bookmaker_availability(DEFAULT_LEAGUE_ID, DEFAULT_SEASON)
    elif menu == "Profil":
        show_profile()
    elif menu == "Historique":
        update_history_view()
    elif menu == "Performance IA":
        show_performance_dashboard()
    elif menu == "Tableau IA":
        show_prediction_performance()
    elif menu == "Supervision":
        show_supervision_dashboard()
    elif menu == "Stades":
        show_venues()
    elif menu == "H2H":
        show_h2h(DEFAULT_LEAGUE_ID, DEFAULT_SEASON)
    elif menu == "Tester l'API":
        st.title("Tester l'API Football")
        if st.button("Lancer les tests API"):
            run_all_tests()
    elif menu == "Admin":
        show_admin()
    elif menu == "Acces & gouvernance":
        show_access_governance()
    elif menu == "Methodologie & limites":
        show_methodology_limits()
    elif menu == "Securite & donnees":
        show_security_data()
    elif menu == "Mentions legales":
        show_legal_responsibility()

if menu in COACH_ALLOWED_PAGES and plan_allows(CURRENT_PLAN, COACH_MIN_PLAN):
    render_coach_widget()

st.caption("Développé par **Tordjeman Labs** avec beaucoup d'amour ❤️")
