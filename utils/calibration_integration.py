"""
Integration du calibreur Over 2.5 dans le pipeline de prédictions
"""

import pandas as pd
import numpy as np
from utils.over_2_5_calibrator import Over25Calibrator

# Initialiser le calibreur au démarrage
calibrator = Over25Calibrator("isotonic")


def apply_calibration_to_dataframe(df, calibrator_obj=None):
    """
    Applique la calibration Over 2.5 à tous les matchs d'un dataframe

    Args:
        df: DataFrame avec colonne 'prob_over_2_5'
        calibrator_obj: Over25Calibrator instance

    Returns:
        DataFrame avec colonnes ajoutées
    """
    if calibrator_obj is None:
        calibrator_obj = calibrator

    df = df.copy()

    if calibrator_obj.model is None:
        print("⚠️ Calibreur non disponible - utilisant probas brutes")
        df["prob_over_2_5_calibrated"] = df["prob_over_2_5"]
        df["over_2_5_recommendation"] = df["prob_over_2_5"].apply(
            lambda x: "Over 2.5" if x >= 0.50 else "Under 2.5"
        )
        return df

    # Calibrer
    df["prob_over_2_5_calibrated"] = df["prob_over_2_5"].apply(
        lambda x: calibrator_obj.calibrate(float(x)) if pd.notna(x) else np.nan
    )

    # Recommandation (seuil 55% pour plus de confiance)
    df["over_2_5_recommendation"] = df["prob_over_2_5_calibrated"].apply(
        lambda x: "Over 2.5" if x >= 0.55 else "Under 2.5" if x < 0.45 else "Borderline"
    )

    # Confiance (0-100%)
    df["over_2_5_confidence"] = df["prob_over_2_5_calibrated"].apply(
        lambda x: abs(x - 0.5) * 2 * 100 if pd.notna(x) else np.nan
    )

    # Ajustement par rapport à la proba brute
    df["over_2_5_adjustment"] = (
        df["prob_over_2_5_calibrated"] - df["prob_over_2_5"]
    ) * 100

    return df


def get_calibrated_over_2_5(prob_over_2_5_brute, calibrator_obj=None):
    """
    Retourne la proba calibrée et la recommandation pour un match
    """
    if calibrator_obj is None:
        calibrator_obj = calibrator

    return calibrator_obj.get_recommendation(
        prob_over_2_5_brute, confidence_threshold=0.55
    )


def compare_before_after(df, calibrator_obj=None):
    """
    Affiche une comparaison avant/après calibration
    """
    if calibrator_obj is None:
        calibrator_obj = calibrator

    if calibrator_obj.model is None:
        print("Calibreur non disponible")
        return

    print("=" * 100)
    print("COMPARAISON AVANT/APRÈS CALIBRATION")
    print("=" * 100)

    # Appliquer calibration
    df_cal = apply_calibration_to_dataframe(df, calibrator_obj)

    # Avant
    accuracy_before = (
        df_cal["prob_over_2_5"].round() == (df_cal["total_goals"] > 2.5).astype(int)
    ).mean() * 100

    # Après
    accuracy_after = (
        df_cal["prob_over_2_5_calibrated"].round()
        == (df_cal["total_goals"] > 2.5).astype(int)
    ).mean() * 100

    print(f"\nAccuracy AVANT: {accuracy_before:.1f}%")
    print(f"Accuracy APRÈS: {accuracy_after:.1f}%")
    print(f"Amélioration: +{accuracy_after - accuracy_before:.1f}%")

    # Exemples
    print("\n--- EXEMPLES D'AJUSTEMENTS ---")
    sample = df_cal[df_cal["prob_over_2_5"].notna()].head(10)
    for idx, row in sample.iterrows():
        print(f"\n{row.get('home_team', '?')} vs {row.get('away_team', '?')}")
        print(f"  Proba brute:  {row['prob_over_2_5']*100:.1f}%")
        print(f"  Proba calibrée: {row['prob_over_2_5_calibrated']*100:.1f}%")
        print(f"  Ajustement: {row['over_2_5_adjustment']:+.1f} points")
        print(
            f"  Recommandation: {row['over_2_5_recommendation']} ({row['over_2_5_confidence']:.0f}% confiance)"
        )

    return df_cal


# Test
if __name__ == "__main__":
    # Charger données
    df = pd.read_csv("data/prediction_dataset_enriched_v2.csv")

    # Parser scores
    if "result_score" in df.columns:
        df[["goals_home", "goals_away"]] = df["result_score"].str.split(
            "-", expand=True
        )
        df["goals_home"] = pd.to_numeric(df["goals_home"], errors="coerce")
        df["goals_away"] = pd.to_numeric(df["goals_away"], errors="coerce")

    df["total_goals"] = df["goals_home"] + df["goals_away"]

    # Comparer
    compare_before_after(df, calibrator)
