import pandas as pd
import warnings

warnings.filterwarnings("ignore")

# Charger les données
df = pd.read_csv("data/prediction_dataset_enriched_v2.csv")

# Convertir et nettoyer
df["fixture_date"] = pd.to_datetime(df["fixture_date"], utc=True, errors="coerce")
df = df.dropna(subset=["fixture_date"])

# Chercher les colonnes de buts
goals_cols = [
    col for col in df.columns if "goals" in col.lower() or "score" in col.lower()
]
print(f"Colonnes trouvées: {goals_cols}")

# Si result_score existe, parser
if "result_score" in df.columns:
    df[["goals_home", "goals_away"]] = df["result_score"].str.split("-", expand=True)
    df["goals_home"] = pd.to_numeric(df["goals_home"], errors="coerce")
    df["goals_away"] = pd.to_numeric(df["goals_away"], errors="coerce")

# Calculer total de buts
df["total_goals"] = df["goals_home"] + df["goals_away"]

# Filtrer les matchs terminés avec un score
df_with_score = df.dropna(subset=["total_goals"]).copy()

print("=" * 80)
print("ANALYSE MATCHS PROCHES DU SEUIL 2.5 BUTS")
print("=" * 80)

# Grouper par zones
near_threshold = df_with_score[
    (df_with_score["total_goals"] >= 1.0) & (df_with_score["total_goals"] <= 4.0)
].copy()

print(f"\nTotal matchs près du seuil 2.5: {len(near_threshold)}")

# Analyser par nombre de buts
print("\n--- DISTRIBUTION ---")
for total in sorted(near_threshold["total_goals"].unique()):
    count = len(near_threshold[near_threshold["total_goals"] == total])
    pct = (count / len(near_threshold)) * 100
    over_under = "OVER 2.5 ✅" if total > 2.5 else "UNDER 2.5 ❌"
    print(f"{total:.0f} buts: {count:3d} matchs ({pct:5.1f}%) → {over_under}")

# Analyse détaillée des 2.x et 3.x
print("\n--- DÉTAIL CRITIQUE (2-3 buts) ---")
critical = near_threshold[near_threshold["total_goals"].isin([2.0, 3.0])]
print(
    f"Total 2 buts: {len(near_threshold[near_threshold['total_goals'] == 2.0])} matchs → UNDER 2.5"
)
print(
    f"Total 3 buts: {len(near_threshold[near_threshold['total_goals'] == 3.0])} matchs → OVER 2.5"
)

# Ratio
two_goals = len(near_threshold[near_threshold["total_goals"] == 2.0])
three_goals = len(near_threshold[near_threshold["total_goals"] == 3.0])
if two_goals + three_goals > 0:
    ratio = (three_goals / (two_goals + three_goals)) * 100
    print(f"\nChances OVER 2.5 si seuil 2.5: {ratio:.1f}%")
    print(f"Chances UNDER 2.5 si seuil 2.5: {100-ratio:.1f}%")

# Matchs spécifiques
print("\n--- TOP MATCHS À 2 BUTS (PERTES si Over 2.5) ---")
two_goal_matches = (
    near_threshold[near_threshold["total_goals"] == 2.0]
    .sort_values("fixture_date", ascending=False)
    .head(10)
)
for idx, row in two_goal_matches.iterrows():
    print(
        f"{row['fixture_date'].strftime('%d/%m')} | {row['home_team']:20} {row['goals_home']:.0f}-{row['goals_away']:.0f} {row['away_team']:20}"
    )

print("\n--- TOP MATCHS À 3 BUTS (GAINS si Over 2.5) ---")
three_goal_matches = (
    near_threshold[near_threshold["total_goals"] == 3.0]
    .sort_values("fixture_date", ascending=False)
    .head(10)
)
for idx, row in three_goal_matches.iterrows():
    print(
        f"{row['fixture_date'].strftime('%d/%m')} | {row['home_team']:20} {row['goals_home']:.0f}-{row['goals_away']:.0f} {row['away_team']:20}"
    )

# Analyse par proba
print("\n--- PROBA MOYENNE PAR GROUPE ---")
if "prob_over_2_5" in df_with_score.columns:
    avg_over_2b = (
        near_threshold[near_threshold["total_goals"] == 2.0]["prob_over_2_5"].mean()
        * 100
    )
    avg_over_3b = (
        near_threshold[near_threshold["total_goals"] == 3.0]["prob_over_2_5"].mean()
        * 100
    )
    print(f"Prob moyenne Over 2.5 pour matchs 2 buts: {avg_over_2b:.1f}%")
    print(f"Prob moyenne Over 2.5 pour matchs 3 buts: {avg_over_3b:.1f}%")
    print(
        f"\n⚠️ INSIGHT: {two_goals} matchs à 2 buts ont eu proba Over moyenne de {avg_over_2b:.1f}%"
    )
    print(f"             Ça montre un biais: l'algo surévalue Over 2.5 sur ces matchs")
