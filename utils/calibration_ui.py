"""
Fonctions pour afficher les Over 2.5 calibrés dans l'interface
"""

import streamlit as st
from utils.calibration_integration import calibrator


def display_calibrated_over_2_5(prob_over_2_5, home_team="", away_team=""):
    """
    Affiche une prédiction Over 2.5 calibrée avec des couleurs

    Args:
        prob_over_2_5: Probabilité brute
        home_team: Équipe domicile (optionnel, pour contexte)
        away_team: Équipe extérieur (optionnel, pour contexte)
    """
    if calibrator.model is None:
        # Fallback sans calibration
        st.warning("⚠️ Calibreur non disponible")
        return

    # Obtenir recommandation calibrée
    rec = calibrator.get_recommendation(prob_over_2_5, confidence_threshold=0.55)

    # Affichage avec couleurs
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Proba Brute", f"{rec['prob_brute']:.1%}")

    with col2:
        st.metric("Proba Calibrée", f"{rec['prob_calibree']:.1%}")

    with col3:
        # Couleur selon recommandation
        if rec["recommendation"] == "Over 2.5":
            st.success(f"✅ {rec['recommendation']}")
            st.caption(f"Confiance: {rec['confiance']:.0f}%")
        elif rec["recommendation"] == "Under 2.5":
            st.error(f"❌ {rec['recommendation']}")
            st.caption(f"Confiance: {rec['confiance']:.0f}%")
        else:
            st.info(f"⚠️ {rec['recommendation']}")
            st.caption(f"Confiance: {rec['confiance']:.0f}%")

    # Ajustement
    if rec["ajustement"] > 0:
        st.info(f"📈 Ajustement: +{rec['ajustement']:.1f} points (plus de Over)")
    elif rec["ajustement"] < 0:
        st.warning(f"📉 Ajustement: {rec['ajustement']:.1f} points (moins de Over)")


def get_over_2_5_badge(prob_over_2_5):
    """
    Retourne un badge pour Over 2.5 calibré (pour affichage dans tables)
    """
    if calibrator.model is None:
        return f"{prob_over_2_5:.1%}"

    rec = calibrator.get_recommendation(prob_over_2_5)

    if rec["recommendation"] == "Over 2.5":
        return f"✅ {rec['prob_calibree']:.1%}"
    elif rec["recommendation"] == "Under 2.5":
        return f"❌ {rec['prob_calibree']:.1%}"
    else:
        return f"⚠️ {rec['prob_calibree']:.1%}"


# Test
if __name__ == "__main__":
    import sys

    sys.path.append(".")

    print("Test affichage Over 2.5 calibré")
    test_probs = [0.2, 0.4, 0.6, 0.8]

    for prob in test_probs:
        rec = calibrator.get_recommendation(prob)
        print(f"\nProba {prob:.1%}:")
        print(f"  Calibrée: {rec['prob_calibree']:.1%}")
        print(f"  Recommandation: {rec['recommendation']}")
        print(f"  Badge: {get_over_2_5_badge(prob)}")
