from __future__ import annotations

import textwrap

import streamlit as st

from .secrets import get_secret


PRIVATE_REPORT_CODE_ENV = "PRIVATE_REPORT_CODE"
DEFAULT_PRIVATE_CODE = "audit-2025"


def _authorized() -> bool:
    return bool(st.session_state.get("private_report_authorized"))


def _require_code() -> bool:
    required_code = get_secret(PRIVATE_REPORT_CODE_ENV) or DEFAULT_PRIVATE_CODE
    if _authorized():
        return True
    st.info("Cette page est réservée. Saisis le code privé pour continuer.")
    code = st.text_input("Code privé", type="password", key="private_report_code_input")
    if not code:
        return False
    if code.strip() != required_code:
        st.error("Code invalide.")
        return False
    st.session_state["private_report_authorized"] = True
    st.success("Accès accordé. Le rapport est disponible ci-dessous.")
    return True


def _section(title: str, body: str) -> None:
    st.subheader(title)
    st.markdown(textwrap.dedent(body).strip())


def show_private_report() -> None:
    st.header("Rapport d'audit interne – Décembre 2025")
    st.caption("Diffusion restreinte. Ne pas partager en dehors de l'équipe coeur.")

    if not _require_code():
        return

    _section(
        "1. Cartographie globale",
        """
        - **Frontend Streamlit** : `app.py` + modules `utils.*`. Navigation unique par `st.sidebar.radio`. Statut *stable*, couverture complète (Dashboard, Predictions, Admin, Offres, etc.).
        - **Moteur probabiliste** : `utils/prediction_model.py` (Poisson/Dixon-Coles, Markov, Elo) + calibration joblib. Implémenté, niveau *fonctionnel* (tombe en Poisson simple si les artefacts `.joblib` manquent).
        - **Collecte & cache** : `utils/api_calls.py`, `utils/cache.py`, `utils/supervision.py` – *fonctionnels* avec mode hors-ligne, quotas, purge. Dépendent d’API-Football + secrets.
        - **Historique/ROI** : `utils/prediction_history.py` – CSV complet, normalisation, export dataset. Implémenté.
        - **Alerting & Social** : `utils/notifications.py`, `utils/engagement.py`, `utils/content_engine.py`. Fonctionnels mais nécessitent Slack/Discord/SMTP/Supabase ; sinon dégradation silencieuse.
        - **IA & scénarios** : `utils/ai_.module.py`, `utils/ai_scenarios.py`, `utils/alt_predictor.py`. Implémentés, niveau *prototype/fonctionnel* (alt predictor heuristique).
        - **Offres & profil** : `utils/offers.py`, `utils/profile_ui.py`. Affichent les plans mais aucun contrôle d’accès réel.
        """,
    )

    _section(
        "2. Cerveau décisionnel",
        """
        - Modèle : Poisson/Dixon-Coles + calibration ML (`models/match_outcome_model.joblib`). Entrées : λ domicile/ext., Elo, pression, intensité, marchés Over/Under.
        - Sorties : probabilités 1X2, marchés agrégés, tips (`_betting_tips`) avec proba, raison, confiance. `suggest_stake` (flat/percent/Kelly) fournit mise/edge/expected profit.
        - Fallbacks : sans joblib, retour à Poisson de base. Moteur secondaire (`alt_predictor`) = simple rééquilibrage heuristique (pas de vrai deuxième modèle).
        """,
    )

    _section(
        "3. Module cotes & value",
        """
        - Cotes importées automatiquement via `get_odds_by_fixture` + `_best_fixture_odds` (meilleure cote par marché).
        - Normalisation partielle : double chances/handicaps convertis, mais aucune suppression explicite de marge bookmaker.
        - Value calculée réellement (`_probability_edge`, `over_bias_value`). Section “Belles cotes” exploite ce calcul.
        """,
    )

    _section(
        "4. Filtres & garde-fous",
        """
        - Filtres Over/Under configurables (probabilité min, intensité max). Bloquants : si non respectés, la page arrête le rendu du match.
        - Supervision/Offline : affichent des avertissements mais n’empêchent pas les actions.
        - Pas de veto automatique sur blessures/météo (informations uniquement).
        """,
    )

    _section(
        "5. Gestion de mise & risque",
        """
        - `suggest_stake` applique flat/percent/Kelly + clamp min/max + statuts (negative_edge, no_bankroll, etc.).
        - Cas limites couverts (proba nulle, edge négatif). Pas de débit automatique de la bankroll ni de suivi multi-profils (roadmap).
        """,
    )

    _section(
        "6. Journal & feedback",
        """
        - `prediction_history.csv` stocke paris, résultats, edge, intensité, etc. Scripts `backfill` / `export` disponibles.
        - `bet_return` souvent vide si l’utilisateur n’enregistre pas les paris : ROI exploitable seulement si la saisie est rigoureuse.
        - Feedback utilisateur stocké dans `data/feedback.csv`, affiché dans Profil.
        """,
    )

    _section(
        "7. Tests & dette technique",
        """
        - Tests unitaires présents (bankroll, content engine, notifications, prediction utils, supervision). Absents sur `prediction_history`, `prediction_model`, `alt_predictor`.
        - Erreurs non gérées : manque de secrets (Supabase/OpenAI) → RuntimeError dans admin/content ; pas de monitoring des dépendances externes.
        - Fichiers Word dans `utils/` sans usage applicatif → bruit documentaire.
        """,
    )

    _section(
        "8. Illusion de complétude",
        """
        - Moteur IA secondaire purement heuristique, malgré la communication “dual engine”.
        - Social Engine & diffusion nécessitent Supabase + webhooks : en absence de clés, les boutons semblent fonctionner mais rien n’est publié.
        - Plans d’abonnement : simple page marketing, aucune logique de facturation ni de gating.
        - Historique ROI incomplet sans saisie manuelle (cases `bet_return`, `bet_stake` souvent vides).
        """,
    )

    _section(
        "9. Verdict",
        """
        - Niveau global : **Produit utilisable** (app Streamlit exploitable avec moteur probabiliste, scripts, supervision, alerting).
        - Limitations majeures :
          1. **Dépendances externes** : sans API-Football/OpenAI/Supabase/Slack, plusieurs sections tombent en dégradation silencieuse.
          2. **Backtests disciplinés** : pas de pipeline de rejouage saison, couverture ROI dépendante de la saisie manuelle.
          3. **Industrialisation** : absence de gating licences, couverture de tests partielle, monitoring externe manquant.
        - Recommandation : réserver la communication “dual engine + diffusion auto” aux environnements où les secrets sont bien configurés et monitorés.
        """,
    )

    st.success("Rapport chargé. Réinitialise la session Streamlit pour verrouiller à nouveau l'accès.")


__all__ = ["show_private_report"]
