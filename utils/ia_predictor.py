# utils/ia_predictor.py

import random

def predict_match(match):
    """
    Donne une prédiction simple sur un match basé sur une logique aléatoire (placeholder).
    match: dict contenant les infos du match (équipes, etc.)
    Retourne une chaîne de prédiction.
    """

    home = match["teams"]["home"]["name"]
    away = match["teams"]["away"]["name"]

    # Exemple de prédictions possibles
    predictions = [
        f"{home} gagne ✅",
        f"{away} gagne ✅",
        "Match nul ⚖️",
        "Plus de 2.5 buts ⚽⚽⚽",
        "Les deux équipes marquent 🔥"
    ]

    return random.choice(predictions)

