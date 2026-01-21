# 🤖 SMART BETTING RECOMMENDATIONS
# Filtres automatiques basés sur le ML model pour sélectionner les meilleurs paris

from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo

from .ml_prediction_engine import get_ml_confidence
from .prediction_model import project_match_outcome
from .calibration_integration import apply_calibration_to_dataframe, calibrator

PARIS_TZ = ZoneInfo("Europe/Paris")

# Thresholds pour déterminer les "bons" paris
CONFIDENCE_THRESHOLD = 65  # >=65% = high confidence
EDGE_THRESHOLD = 0.05  # >=5% edge = value bet
MIN_ODDS = 1.2
MAX_ODDS = 5.0


def score_match_for_recommendation(match: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score un match selon plusieurs critères pour le recommander automatiquement.

    Retourne un score de 0-100 et une raison.
    """

    try:
        # Récupérer la confiance du ML model
        ml_confidence = get_ml_confidence(match)

        if ml_confidence is None:
            return {"score": 0, "reason": "Pas de prédiction ML", "confidence": None}

        confidence_pct = ml_confidence * 100

        # Score de base: la confiance du modèle
        score = confidence_pct  # 0-100

        # Bonus si high confidence
        if confidence_pct >= CONFIDENCE_THRESHOLD:
            score = min(100, score + 10)

        # Malus si low confidence
        if confidence_pct < 40:
            score = max(0, score - 20)

        # Bonus si match proche (data fraîche = plus fiable)
        try:
            if match.get("kickoff_at"):
                kickoff = datetime.fromisoformat(
                    str(match["kickoff_at"]).replace("Z", "+00:00")
                ).astimezone(PARIS_TZ)
                now = datetime.now(PARIS_TZ)
                hours_until = (kickoff - now).total_seconds() / 3600

                # Bonus si match dans 12-48h (sweet spot)
                if 12 <= hours_until <= 48:
                    score = min(100, score + 5)
                elif hours_until < 2:
                    score = max(0, score - 10)  # Trop proche
                elif hours_until > 96:
                    score = max(0, score - 5)  # Trop loin
        except:
            pass

        # Déterminer la raison
        reason = f"Confiance: {confidence_pct:.1f}%"

        if score >= 75:
            reason += " 🟢 TOP PICK"
        elif score >= 60:
            reason += " 🟡 BON PICK"
        else:
            reason += " 🔴 À ÉVITER"

        return {
            "score": score,
            "reason": reason,
            "confidence": confidence_pct,
            "recommendation": (
                "TOP" if score >= 75 else ("GOOD" if score >= 60 else "SKIP")
            ),
        }

    except Exception as e:
        return {"score": 0, "reason": f"Erreur: {str(e)}", "confidence": None}


def get_top_recommendations(
    matches: List[Dict[str, Any]],
    top_n: int = 5,
    filter_type: str = "HIGH_CONFIDENCE",  # HIGH_CONFIDENCE | VALUE_BETS | ALL_RANKED
) -> Tuple[List[Dict[str, Any]], pd.DataFrame]:
    """
    Retourne les N meilleurs paris recommandés selon différents critères.

    Args:
        matches: Liste de tous les matchs
        top_n: Nombre de matchs à recommander
        filter_type:
            - HIGH_CONFIDENCE: Confiance >= 65%
            - VALUE_BETS: Edge >= 5% sur les cotes
            - ALL_RANKED: Tous, rankés par score

    Returns:
        (top_matches, dataframe_for_display)
    """

    # Scorer tous les matchs
    scored_matches = []
    for match in matches:
        match_copy = match.copy()
        score_info = score_match_for_recommendation(match)
        match_copy["_recommendation_score"] = score_info["score"]
        match_copy["_recommendation_reason"] = score_info["reason"]
        match_copy["_recommendation_type"] = score_info.get("recommendation", "SKIP")
        match_copy["_confidence_pct"] = score_info.get("confidence")
        scored_matches.append(match_copy)

    # Trier par score
    sorted_matches = sorted(
        scored_matches, key=lambda x: x["_recommendation_score"], reverse=True
    )

    # Appliquer le filtre
    if filter_type == "HIGH_CONFIDENCE":
        filtered = [
            m
            for m in sorted_matches
            if m["_confidence_pct"] and m["_confidence_pct"] >= CONFIDENCE_THRESHOLD
        ]
    elif filter_type == "VALUE_BETS":
        filtered = [m for m in sorted_matches if m["_recommendation_type"] == "TOP"]
    else:  # ALL_RANKED
        filtered = sorted_matches

    # Prendre le top N
    top_matches = filtered[:top_n]

    # Créer DataFrame pour affichage
    df_data = []
    for i, match in enumerate(top_matches, 1):
        df_data.append(
            {
                "#": i,
                "Match": f"{match.get('home_team', 'N/A')} vs {match.get('away_team', 'N/A')}",
                "Ligue": match.get("league_name", "N/A"),
                "Confiance ML": f"{match.get('_confidence_pct', 0):.1f}%",
                "Score": f"{match.get('_recommendation_score', 0):.0f}",
                "Recommandation": match.get("_recommendation_type", "?"),
                "Raison": match.get("_recommendation_reason", ""),
            }
        )

    df = pd.DataFrame(df_data)

    return top_matches, df


def render_smart_recommendations_ui(
    matches: List[Dict[str, Any]], key_prefix: str = "smart_rec_"
) -> Optional[Dict[str, Any]]:
    """
    Affiche l'UI Streamlit pour les recommandations intelligentes.

    Retourne le match sélectionné ou None.
    """

    st.markdown("---")
    st.subheader("🤖 Recommandations Intelligentes (basées sur ML)")

    col1, col2, col3 = st.columns(3)

    with col1:
        top_n = st.slider(
            "Nombre de recommandations",
            min_value=1,
            max_value=min(10, len(matches)),
            value=5,
            key=f"{key_prefix}top_n",
        )

    with col2:
        filter_type = st.selectbox(
            "Filtre",
            ["HIGH_CONFIDENCE", "VALUE_BETS", "ALL_RANKED"],
            format_func=lambda x: {
                "HIGH_CONFIDENCE": "🟢 Haute Confiance (≥65%)",
                "VALUE_BETS": "💎 Meilleures Cotes",
                "ALL_RANKED": "📊 Tous Rankés",
            }[x],
            key=f"{key_prefix}filter",
        )

    with col3:
        auto_select = st.checkbox(
            "Sélection auto du #1",
            value=False,
            key=f"{key_prefix}auto_select",
            help="Sélectionne automatiquement le meilleur match",
        )

    # Générer les recommandations
    try:
        top_matches, df = get_top_recommendations(
            matches, top_n=top_n, filter_type=filter_type
        )

        if len(top_matches) == 0:
            st.warning(f"⚠️ Pas de match trouvé avec le filtre: {filter_type}")
            return None

        # Afficher le tableau
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Sélection du match
        if auto_select and len(top_matches) > 0:
            selected_match = top_matches[0]
            st.success(
                f"✅ Auto-sélectionné: {selected_match.get('home_team')} vs {selected_match.get('away_team')}"
            )
            return selected_match
        else:
            match_options = [
                f"#{i+1}: {m.get('home_team')} vs {m.get('away_team')} ({m.get('_recommendation_type')})"
                for i, m in enumerate(top_matches)
            ]

            selected_idx = st.selectbox(
                "Sélectionner un match à analyser",
                range(len(top_matches)),
                format_func=lambda i: match_options[i],
                key=f"{key_prefix}select",
            )

            return top_matches[selected_idx] if selected_idx is not None else None

    except Exception as e:
        st.error(f"❌ Erreur lors de la génération des recommandations: {str(e)}")
        return None


def create_auto_betting_list(
    matches: List[Dict[str, Any]], confidence_min: float = 0.65, max_picks: int = 5
) -> pd.DataFrame:
    """
    Crée une liste de paris automatique à placer.

    Útile pour un mode "set and forget".
    """

    picked = []

    for match in matches:
        confidence = get_ml_confidence(match)

        if confidence and confidence >= confidence_min:
            picked.append(
                {
                    "Match": f"{match.get('home_team')} vs {match.get('away_team')}",
                    "Ligue": match.get("league_name"),
                    "Confiance": f"{confidence * 100:.1f}%",
                    "Prediction": match.get("predicted_outcome", "?"),
                    "Kickoff": match.get("kickoff_at", "?"),
                    "Status": "À placer",
                }
            )

    # Trier par confiance descendante
    picked_sorted = sorted(
        picked, key=lambda x: float(x["Confiance"].strip("%")), reverse=True
    )

    # Limiter au max_picks
    picked_limited = picked_sorted[:max_picks]

    return pd.DataFrame(picked_limited)
