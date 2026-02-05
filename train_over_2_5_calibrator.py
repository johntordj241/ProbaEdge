import pandas as pd
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
import joblib
import warnings

warnings.filterwarnings("ignore")

# Charger
df = pd.read_csv("data/prediction_dataset_enriched_v2.csv")
df["fixture_date"] = pd.to_datetime(df["fixture_date"], utc=True, errors="coerce")

# Parser scores
if "result_score" in df.columns:
    df[["goals_home", "goals_away"]] = df["result_score"].str.split("-", expand=True)
    df["goals_home"] = pd.to_numeric(df["goals_home"], errors="coerce")
    df["goals_away"] = pd.to_numeric(df["goals_away"], errors="coerce")

df["total_goals"] = df["goals_home"] + df["goals_away"]
df_scored = df.dropna(subset=["total_goals", "prob_over_2_5"]).copy()

# Target: 1 si Over 2.5, 0 si Under 2.5
df_scored["over_2_5_actual"] = (df_scored["total_goals"] > 2.5).astype(int)

print("=" * 80)
print("CRÉATION DU RECALIBREUR OVER/UNDER 2.5")
print("=" * 80)

# Features pour recalibrage
features_to_use = ["prob_over_2_5"]
X = df_scored[features_to_use].values
y = df_scored["over_2_5_actual"].values

print(f"\nDonnées d'entraînement: {len(X)} matchs")
print(f"Ratio Over/Under: {y.sum()} / {len(y) - y.sum()}")

# Méthode 1: Isotonic Regression (meilleur pour calibrage)
print("\n--- ISOTONIC REGRESSION ---")
iso_reg = IsotonicRegression(out_of_bounds="clip")
iso_reg.fit(X, y)

# Tester
y_pred_iso = iso_reg.predict(X)
accuracy_iso = np.mean((y_pred_iso.round() == y))
print(f"Accuracy (Isotonic): {accuracy_iso*100:.1f}%")

# Méthode 2: Logistic Regression (meilleur pour calibrage probabiliste)
print("\n--- LOGISTIC REGRESSION ---")
log_reg = LogisticRegression(max_iter=1000)
log_reg.fit(X, y)

y_pred_log = log_reg.predict_proba(X)[:, 1]
accuracy_log = np.mean((y_pred_log.round() == y))
print(f"Accuracy (Logistic): {accuracy_log*100:.1f}%")

# Comparer avant/après
print("\n--- COMPARAISON ---")
print(f"Accuracy AVANT recalibrage: {np.mean((X.round() == y))*100:.1f}%")
print(f"Accuracy APRÈS (Isotonic): {accuracy_iso*100:.1f}%")
print(f"Accuracy APRÈS (Logistic): {accuracy_log*100:.1f}%")

# Vérifier calibrage
print("\n--- VÉRIFICATION DE CALIBRAGE ---")
proba_bins = np.arange(0, 1.1, 0.1)
for i in range(len(proba_bins) - 1):
    mask = (X.flatten() >= proba_bins[i]) & (X.flatten() < proba_bins[i + 1])
    if mask.sum() > 0:
        actual_rate = y[mask].mean()
        print(
            f"Proba [{proba_bins[i]:.1f}-{proba_bins[i+1]:.1f}]: {mask.sum():3d} matchs → Réel: {actual_rate*100:.1f}% (Idéal: ~{(proba_bins[i]+proba_bins[i+1])/2*100:.1f}%)"
        )

# Sauvegarder les 2 modèles
print("\n--- SAUVEGARDE ---")
joblib.dump(iso_reg, "models/over_2_5_calibrator_isotonic.joblib")
joblib.dump(log_reg, "models/over_2_5_calibrator_logistic.joblib")
print("✅ Modèles sauvegardés:")
print("   - models/over_2_5_calibrator_isotonic.joblib")
print("   - models/over_2_5_calibrator_logistic.joblib")

# Créer courbe d'ajustement
print("\n--- COURBE D'AJUSTEMENT ---")
test_probes = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]).reshape(-1, 1)
adjusted_iso = iso_reg.predict(test_probes)
adjusted_log = log_reg.predict_proba(test_probes)[:, 1]

print("\nProba Brute → Proba Calibrée (Isotonic) → Calibrée (Logistic)")
for i, pb in enumerate(test_probes.flatten()):
    print(
        f"{pb:.1f}       →    {adjusted_iso[i]:.3f}          →    {adjusted_log[i]:.3f}"
    )

# Recommandation
print("\n--- RECOMMANDATION ---")
if accuracy_log > accuracy_iso:
    print("✅ Utiliser LOGISTIC REGRESSION")
    print("   Elle donne des probabilités mieux calibrées")
    model_to_use = "logistic"
else:
    print("✅ Utiliser ISOTONIC REGRESSION")
    print("   Elle préserve mieux la forme originale")
    model_to_use = "isotonic"

# Sauvegarder le choix
with open("models/over_2_5_calibrator_choice.txt", "w") as f:
    f.write(model_to_use)
print(f"\nChoix sauvegardé: {model_to_use}")
