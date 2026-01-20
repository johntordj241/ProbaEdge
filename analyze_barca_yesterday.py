import pandas as pd
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings("ignore")

# Charger les données
df = pd.read_csv("data/prediction_dataset_enriched_v2.csv")

# Convertir les dates de manière robuste
df["fixture_date"] = pd.to_datetime(df["fixture_date"], utc=True, errors="coerce")
df = df.dropna(subset=["fixture_date"])

# Hier (18 janvier 2026)
yesterday_str = "2026-01-18"
df["date_str"] = df["fixture_date"].dt.strftime("%Y-%m-%d")

print("=" * 80)
print("ANALYSE MATCH BARÇA - 18 JANVIER 2026")
print("=" * 80)

# Trouver les matchs du Barça hier
barca_matches = df[
    (df["date_str"] == yesterday_str)
    & (
        (df["home_team"].str.contains("Barça|Barcelona", case=False, na=False))
        | (df["away_team"].str.contains("Barça|Barcelona", case=False, na=False))
    )
].copy()

if len(barca_matches) > 0:
    for idx, row in barca_matches.iterrows():
        print(f"\n{row['home_team']} vs {row['away_team']}")
        print(f"Date: {row['fixture_date']}")
        print(f"Score final: {row['goals_home']} - {row['goals_away']}")
        print(f"Total buts: {row['goals_home'] + row['goals_away']}")
        print(f"\n--- PRÉDICTIONS ---")
        print(f"Prob Over 2.5: {row['prob_over_2_5']*100:.1f}%")
        print(f"Prob Under 2.5: {row['prob_under_2_5']*100:.1f}%")
        print(f"Over 2.5 Confidence: {row.get('over_2_5_confidence', 'N/A')}")
        print(f"Over 2.5 dans top recommandations: {row.get('over_2_5_rank', 'N/A')}")
        print(f"\n--- RÉSULTAT ---")
        if row["goals_home"] + row["goals_away"] > 2.5:
            print("✅ Over 2.5 GAGNÉ")
        else:
            print("❌ Over 2.5 PERDU")
else:
    print("\n❌ Pas de match Barça hier trouvé.")

    # Chercher tous les matchs d'hier
    print("\n" + "=" * 80)
    print("TOUS LES MATCHS D'HIER (18/01/2026)")
    print("=" * 80)

    yesterday_all = df[df["date_str"] == yesterday_str].drop_duplicates(
        subset=["fixture_id"]
    )

    if len(yesterday_all) > 0:
        for idx, row in yesterday_all.iterrows():
            league = {
                1.0: "PL",
                2.0: "L1",
                3.0: "LDC",
                78.0: "Bundesliga",
                140.0: "La Liga",
            }.get(row.get("league_id"), "?")
            goals = row["goals_home"] + row["goals_away"]
            print(
                f"{league:5} | {row['home_team']:25} {row['goals_home']} - {row['goals_away']} {row['away_team']:25} ({goals} buts)"
            )
    else:
        print("Aucun match trouvé pour cette date.")
