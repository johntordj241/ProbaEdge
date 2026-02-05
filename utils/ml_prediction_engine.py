"""
ML Prediction Engine - Intégration du modèle scikit-learn
Fournit la prédiction de confiance pour les paris utilisant le modèle entraîné
"""

import joblib
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Any
import streamlit as st


MODEL_PATH = Path("models/prediction_success_model_v2.joblib")

# Les 6 features optimales du modèle
REQUIRED_FEATURES = [
    "feature_max_prob",
    "feature_total_pick_over",
    "feature_over_under_diff",
    "feature_home_draw_diff",
    "feature_main_confidence_norm",
    "feature_home_away_diff",
]


@st.cache_resource
def load_model():
    """Charge le modèle ML entraîné"""
    try:
        if MODEL_PATH.exists():
            model = joblib.load(str(MODEL_PATH))
            return model
    except Exception as e:
        print(f"Erreur lors du chargement du modèle: {e}")
    return None


def get_ml_confidence(features: Dict[str, float]) -> Optional[float]:
    """
    Retourne la confiance du modèle ML pour un pari

    Args:
        features: Dict avec les 6 features requises

    Returns:
        Confiance en % (0-100) ou None si le modèle ne peut pas prédire
    """
    model = load_model()
    if model is None:
        return None

    try:
        # Vérifier que toutes les features sont présentes
        missing = [f for f in REQUIRED_FEATURES if f not in features]
        if missing:
            print(f"Features manquantes: {missing}")
            return None

        # Créer le DataFrame avec les features dans le bon ordre
        df_features = pd.DataFrame([{f: features[f] for f in REQUIRED_FEATURES}])

        # Prédiction: probabilité de succès
        probas = model.predict_proba(df_features)[0]  # [prob_fail, prob_success]
        confidence = probas[1] * 100  # Convertir en %

        return round(confidence, 1)

    except Exception as e:
        print(f"Erreur lors de la prédiction ML: {e}")
        return None


def format_ml_confidence_ui(confidence: Optional[float]) -> str:
    """Formate la confiance ML pour l'affichage"""
    if confidence is None:
        return "❓ N/A"

    if confidence >= 70:
        return f"🟢 {confidence}%"
    elif confidence >= 60:
        return f"🟡 {confidence}%"
    else:
        return f"🔴 {confidence}%"


# Statistiques d'entraînement du modèle
MODEL_STATS = {
    "accuracy": 0.612,
    "roc_auc": 0.696,
    "win_rate": 0.606,
    "valid_predictions": 411,
    "features": 6,
    "model_version": "v2",
}

# Meilleur types de paris selon l'analyse
BEST_BET_TYPES = {
    "Over 1.5": {"win_rate": 1.0, "count": 9},
    "Under 2.5": {"win_rate": 0.80, "count": 10},
    "Nul": {"win_rate": 0.678, "count": 146},
    "BTTS": {"win_rate": 0.66, "count": 47},
    "Over 2.5": {"win_rate": 0.59, "count": 122},
}

# Meilleur championnats selon l'analyse
BEST_LEAGUES = {
    3: {"name": "Ligue des Champions", "win_rate": 0.794, "count": 34},
    39: {"name": "Premier League", "win_rate": 0.661, "count": 59},
    62: {"name": "Ligue 2", "win_rate": 0.556, "count": 9},
    61: {"name": "Ligue 1", "win_rate": 0.525, "count": 139},
}

# Types de paris simples vs combinés
SIMPLE_VS_COMBO = {
    "simple": {"win_rate": 0.609, "count": 307},
    "combo": {"win_rate": 0.596, "count": 104},
}


def get_league_performance(league_id: int) -> Optional[Dict[str, Any]]:
    """Retourne la performance historique d'une ligue"""
    return BEST_LEAGUES.get(league_id)


def get_bet_type_performance(bet_type: str) -> Optional[Dict[str, Any]]:
    """Retourne la performance historique d'un type de pari"""
    return BEST_BET_TYPES.get(bet_type)


def get_simple_vs_combo_stats() -> Dict[str, Any]:
    """Retourne les stats simples vs combinés"""
    return SIMPLE_VS_COMBO
