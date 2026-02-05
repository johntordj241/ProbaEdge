import joblib
import pandas as pd
import numpy as np
import os


class Over25Calibrator:
    """Applique la calibration Over 2.5 aux prédictions"""

    def __init__(self, model_type="isotonic"):
        """
        Charge le modèle de calibration
        model_type: 'isotonic' ou 'logistic'
        """
        model_path = f"models/over_2_5_calibrator_{model_type}.joblib"

        if os.path.exists(model_path):
            self.model = joblib.load(model_path)
            self.model_type = model_type
            print(f"✅ Calibreur {model_type} chargé")
        else:
            self.model = None
            self.model_type = None
            print(f"⚠️ Calibreur {model_type} non trouvé - utilisant probas brutes")

    def calibrate(self, prob_over_2_5):
        """
        Calibre une probabilité Over 2.5

        Args:
            prob_over_2_5: float entre 0 et 1 (ou array)

        Returns:
            Probabilité calibrée
        """
        if self.model is None:
            return prob_over_2_5

        # Convertir en array si nécessaire
        is_scalar = np.isscalar(prob_over_2_5)
        probs = np.atleast_1d(prob_over_2_5).reshape(-1, 1)

        # Calibrer
        calibrated = self.model.predict(probs)

        # Retourner au format original
        if is_scalar:
            return float(calibrated[0])
        else:
            return calibrated.flatten()

    def get_recommendation(self, prob_over_2_5, confidence_threshold=0.55):
        """
        Donne une recommandation basée sur la proba calibrée

        Args:
            prob_over_2_5: probabilité brute
            confidence_threshold: seuil pour recommander

        Returns:
            dict avec recommendation et calibrated_prob
        """
        calibrated = self.calibrate(prob_over_2_5)

        return {
            "prob_brute": float(prob_over_2_5),
            "prob_calibree": float(calibrated),
            "recommendation": (
                "Over 2.5" if calibrated >= confidence_threshold else "Under 2.5"
            ),
            "confiance": float(abs(calibrated - 0.5) * 2 * 100),  # 0-100%
            "ajustement": float((calibrated - prob_over_2_5) * 100),  # +/- points
        }


# Tester
if __name__ == "__main__":
    calibrator = Over25Calibrator("isotonic")

    print("=" * 80)
    print("TEST CALIBREUR")
    print("=" * 80)

    test_probs = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

    for prob in test_probs:
        rec = calibrator.get_recommendation(prob)
        print(f"\nProba brute: {rec['prob_brute']:.1%}")
        print(f"  → Calibrée: {rec['prob_calibree']:.1%}")
        print(f"  → Recommandation: {rec['recommendation']}")
        print(f"  → Confiance: {rec['confiance']:.0f}%")
        print(f"  → Ajustement: {rec['ajustement']:+.1f} points")
