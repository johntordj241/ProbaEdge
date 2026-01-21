import pandas as pd
import numpy as np
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
df_scored = df.dropna(subset=["total_goals"]).copy()

print("=" * 80)
print("CALIBRATION OVER 2.5 - ÉCART D'ALGORITHME")
print("=" * 80)

# Grouper par résultat
under_25 = df_scored[df_scored["total_goals"] <= 2.5].copy()
over_25 = df_scored[df_scored["total_goals"] > 2.5].copy()

print(f"\nMatchs UNDER 2.5: {len(under_25)}")
print(f"Matchs OVER 2.5: {len(over_25)}")

# Analyser probas
print("\n--- CALIBRATION ACTUELLE ---")
avg_prob_under = under_25["prob_over_2_5"].mean() * 100
avg_prob_over = over_25["prob_over_2_5"].mean() * 100
ecart = avg_prob_over - avg_prob_under

print(f"Proba moyenne Over 2.5 pour matchs UNDER: {avg_prob_under:.1f}%")
print(f"Proba moyenne Over 2.5 pour matchs OVER: {avg_prob_over:.1f}%")
print(f"\n🎯 ÉCART ACTUEL: {ecart:.1f}%")
print(f"🎯 ÉCART IDÉAL: 30-40%")

if ecart < 10:
    print(f"\n❌ PROBLÈME: L'algo ne discrimine PAS bien")
    print(f"   Les 2 groupes ont presque la même proba → Mauvais calibrage")
elif ecart < 20:
    print(f"\n🟡 MOYEN: Discrimination faible")
    print(f"   L'algo hésite entre Under et Over")
else:
    print(f"\n✅ BON: Bonne discrimination")
    print(f"   L'algo sépare bien les 2 catégories")

# Quartiles pour voir la distribution
print("\n--- DISTRIBUTION DES PROBABILITÉS ---")
print("\nMatchs UNDER 2.5:")
print(f"  Min: {under_25['prob_over_2_5'].min()*100:.1f}%")
print(f"  Q1: {under_25['prob_over_2_5'].quantile(0.25)*100:.1f}%")
print(f"  Médiane: {under_25['prob_over_2_5'].median()*100:.1f}%")
print(f"  Q3: {under_25['prob_over_2_5'].quantile(0.75)*100:.1f}%")
print(f"  Max: {under_25['prob_over_2_5'].max()*100:.1f}%")

print("\nMatchs OVER 2.5:")
print(f"  Min: {over_25['prob_over_2_5'].min()*100:.1f}%")
print(f"  Q1: {over_25['prob_over_2_5'].quantile(0.25)*100:.1f}%")
print(f"  Médiane: {over_25['prob_over_2_5'].median()*100:.1f}%")
print(f"  Q3: {over_25['prob_over_2_5'].quantile(0.75)*100:.1f}%")
print(f"  Max: {over_25['prob_over_2_5'].max()*100:.1f}%")

# Overlap check
overlap_under = len(under_25[under_25["prob_over_2_5"] > 0.5])
overlap_over = len(over_25[over_25["prob_over_2_5"] < 0.5])

print(f"\n--- CHEVAUCHEMENT ---")
print(
    f"Matchs UNDER avec proba >50%: {overlap_under} ({overlap_under/len(under_25)*100:.1f}%)"
)
print(
    f"Matchs OVER avec proba <50%: {overlap_over} ({overlap_over/len(over_25)*100:.1f}%)"
)
print(
    f"\nChevauchement total: {(overlap_under + overlap_over) / (len(under_25) + len(over_25)) * 100:.1f}%"
)

if (overlap_under + overlap_over) / (len(under_25) + len(over_25)) > 0.3:
    print("⚠️ BEAUCOUP de chevauchement → Algo très mauvais")
elif (overlap_under + overlap_over) / (len(under_25) + len(over_25)) > 0.15:
    print("🟡 Chevauchement modéré → Algo imprécis")
else:
    print("✅ Peu de chevauchement → Algo bon")

# Courbe ROC simple
print("\n--- COURBE DE DISCRIMINATION ---")
print("\nSi tu defines un seuil de decision:")
for seuil in [0.25, 0.35, 0.45, 0.50, 0.55, 0.65]:
    tp = len(over_25[over_25["prob_over_2_5"] >= seuil])
    fp = len(under_25[under_25["prob_over_2_5"] >= seuil])
    precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
    recall = tp / len(over_25) * 100
    print(
        f"Seuil {seuil*100:.0f}%: Précision {precision:.1f}% | Rappel {recall:.1f}% | Taux faux positif {fp/len(under_25)*100:.1f}%"
    )
