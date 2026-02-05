import pandas as pd
from datetime import datetime

# Charger les données
df = pd.read_csv("data/prediction_dataset_enriched_v2.csv")

# Convertir les dates
df["fixture_date"] = pd.to_datetime(df["fixture_date"], utc=True)
df["league_id"] = pd.to_numeric(df["league_id"], errors="coerce")

# Date d'aujourd'hui: 30 janvier 2026
today = datetime(2026, 1, 30)

# Championnat allemand = Bundesliga (league_id = 39)
german_today = df[
    (df["fixture_date"].dt.date == today.date()) & (df["league_id"] == 39.0)
].copy()

if len(german_today) > 0:
    print("=" * 100)
    print("MATCHS BUNDESLIGA - 30 JANVIER 2026")
    print("=" * 100)
    german_today = german_today.sort_values("prob_over_2_5", ascending=False)

    for idx, row in german_today.iterrows():
        print(f"\nℹ️ {row['home_team']} vs {row['away_team']}")
        print(f"   Heure: {row['fixture_date'].strftime('%H:%M')}")
        print(f"   🏠 Home: {row['prob_home']*100:.1f}%")
        print(f"   🤝 Draw: {row['prob_draw']*100:.1f}%")
        print(f"   🚀 Away: {row['prob_away']*100:.1f}%")
        print(f"   📊 Over 2.5: {row['prob_over_2_5']*100:.1f}%")
        print(f"   🎯 Under 2.5: {row['prob_under_2_5']*100:.1f}%")
else:
    print("❌ Aucun match Bundesliga aujourd'hui dans les données disponibles.")
