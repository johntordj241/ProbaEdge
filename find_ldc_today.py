import pandas as pd
from datetime import datetime

# Charger les données
df = pd.read_csv("data/prediction_dataset_enriched_v2.csv")

# Convertir les dates
df["fixture_date"] = pd.to_datetime(df["fixture_date"])

# Aujourd'hui
today = pd.Timestamp("2026-01-19")

# Matchs Ligue des Champions aujourd'hui (league_id = 3)
ldc_today = df[
    (df["fixture_date"].dt.date == today.date()) & (df["league_id"] == 3.0)
].copy()

print("=" * 80)
print("MATCHS LIGUE DES CHAMPIONS - 19 JANVIER 2026")
print("=" * 80)

if len(ldc_today) > 0:
    for idx, row in ldc_today.iterrows():
        print(f"\n{row['home_team']} vs {row['away_team']}")
        print(f"Heure: {row['fixture_date'].strftime('%H:%M')}")
        print(f"Proba Home: {row['prob_home']*100:.1f}%")
        print(f"Proba Draw: {row['prob_draw']*100:.1f}%")
        print(f"Proba Away: {row['prob_away']*100:.1f}%")
        print(f"Over 2.5: {row['prob_over_2_5']*100:.1f}%")
else:
    print("\nPas de matchs LDC aujourd'hui dans les données.")

    # Chercher les matchs futurs en général
    print("\n" + "=" * 80)
    print("MATCHS FUTURS DISPONIBLES")
    print("=" * 80)

    future_matches = df[df["fixture_date"] > today].copy()
    future_matches = future_matches.drop_duplicates(subset=["fixture_id"])
    future_matches = future_matches.sort_values("fixture_date")

    for idx, row in future_matches.head(20).iterrows():
        league_name = {
            1: "Angleterre",
            2: "L1",
            3: "LDC",
            78: "Bundesliga",
            140: "La Liga",
            206: "Ligue 2",
        }.get(int(row["league_id"]), "Autre")

        print(
            f"{row['fixture_date'].strftime('%Y-%m-%d %H:%M')} | {league_name:12} | {row['home_team']:20} vs {row['away_team']}"
        )
