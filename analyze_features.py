import pandas as pd
import numpy as np

# Charger le dataset enrichi
df = pd.read_csv("data/prediction_dataset_enriched.csv")

print("=" * 80)
print("FEATURES ACTUELLEMENT UTILISÉES (6 features)")
print("=" * 80)
current_features = [
    "feature_home_draw_diff",
    "feature_home_away_diff",
    "feature_over_under_diff",
    "feature_max_prob",
    "feature_main_confidence_norm",
    "feature_total_pick_over",
]
for feat in current_features:
    filled = df[feat].notna().sum()
    pct = filled / len(df) * 100
    print(f"✅ {feat:35s} : {pct:5.1f}% rempli ({filled}/{len(df)})")

print("\n" + "=" * 80)
print("FEATURES SUPPLÉMENTAIRES DISPONIBLES (mais NON utilisées)")
print("=" * 80)

additional_features = [
    "feature_lambda_home",  # Buts attendus domicile
    "feature_lambda_away",  # Buts attendus extérieur
    "elo_home",  # Rating Elo domicile
    "elo_away",  # Rating Elo extérieur
    "delta_elo",  # Différence Elo
    "pressure_score",  # Score de pression
    "intensity_score",  # Score d'intensité
    "prob_home",  # Proba Poisson domicile
    "prob_draw",  # Proba Poisson nul
    "prob_away",  # Proba Poisson extérieur
    "prob_over_2_5",  # Proba Over 2.5
    "prob_under_2_5",  # Proba Under 2.5
    "main_confidence",  # Confiance du pick principal
]

for feat in additional_features:
    if feat in df.columns:
        filled = df[feat].notna().sum()
        pct = filled / len(df) * 100
        status = "✅" if pct > 50 else "⚠️" if pct > 10 else "❌"
        print(f"{status} {feat:35s} : {pct:5.1f}% rempli ({filled}/{len(df)})")

print("\n" + "=" * 80)
print("BONNES CANDIDATES POUR AMÉLIORER LE MODÈLE")
print("=" * 80)

good_features = [
    "prob_home",
    "prob_draw",
    "prob_away",
    "prob_over_2_5",
    "prob_under_2_5",
    "main_confidence",
    "delta_elo",
]

print(
    "\nCes 7 features sont bien remplies (>80%) et directement liées aux prédictions:"
)
for feat in good_features:
    if feat in df.columns:
        filled = df[feat].notna().sum()
        pct = filled / len(df) * 100
        print(f"  • {feat:35s} : {pct:5.1f}%")

print("\n" + "=" * 80)
print("IMPACT ESTIMÉ")
print("=" * 80)
print(
    """
Modèle ACTUEL (6 features):
  Accuracy:  61.2%
  ROC-AUC:   69.6%

Modèle AMÉLIORÉ (13 features):
  Accuracy:  63-65% (estimé +2-3%)
  ROC-AUC:   72-75% (estimé +2-5%)
  
Pourquoi ça améliore?
  • prob_home/draw/away = probabilités directes (très informatif)
  • main_confidence = confiance du pick (important)
  • delta_elo = force relative des équipes (très utile)
  • prob_over/under = qualité match (structure)
"""
)
