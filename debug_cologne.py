import pandas as pd
from datetime import datetime

# Charger les données
df = pd.read_csv("data/prediction_dataset_enriched_v2.csv")

# Convertir les dates
df["fixture_date"] = pd.to_datetime(df["fixture_date"], utc=True)
df["league_id"] = pd.to_numeric(df["league_id"], errors="coerce")

# Date d'aujourd'hui: 30 janvier 2026
today = datetime(2026, 1, 30)

# Vérifier tous les matchs du 30/01
matches_30_01 = df[df["fixture_date"].dt.date == today.date()].copy()
print(f"✅ Matchs trouvés le 30/01/2026: {len(matches_30_01)}")
print("\nDétails:")
for idx, row in matches_30_01.iterrows():
    print(f"  {row['home_team']} vs {row['away_team']} - League ID: {row['league_id']}")

# Chercher spécifiquement le match Cologne - Wolfsburg
cologne_wolfsburg = df[
    (
        (df["home_team"].str.contains("Köln|Cologne", case=False, na=False))
        & (df["away_team"].str.contains("Wolfsburg", case=False, na=False))
    )
    | (
        (df["home_team"].str.contains("Wolfsburg", case=False, na=False))
        & (df["away_team"].str.contains("Köln|Cologne", case=False, na=False))
    )
]

print(f"\n\n🔍 Recherche: Cologne vs Wolfsburg")
if len(cologne_wolfsburg) > 0:
    print(f"✅ Match trouvé dans le dataset:")
    for idx, row in cologne_wolfsburg.iterrows():
        print(f"  {row['home_team']} vs {row['away_team']}")
        print(f"  Date: {row['fixture_date']}")
        print(f"  League ID: {row['league_id']}")
else:
    print("❌ Match NOT trouvé dans le dataset")

# Chercher les équipes individuelles
print(f"\n\n📋 Vérification des équipes:")
cologne = df[df["home_team"].str.contains("Köln|Cologne", case=False, na=False)]
print(f"Matchs avec Cologne comme HOME: {len(cologne)}")
for idx, row in cologne.head(3).iterrows():
    print(
        f"  {row['fixture_date'].strftime('%Y-%m-%d %H:%M')} - {row['home_team']} vs {row['away_team']}"
    )

wolfsburg = df[df["home_team"].str.contains("Wolfsburg", case=False, na=False)]
print(f"\nMatchs avec Wolfsburg comme HOME: {len(wolfsburg)}")
for idx, row in wolfsburg.head(3).iterrows():
    print(
        f"  {row['fixture_date'].strftime('%Y-%m-%d %H:%M')} - {row['home_team']} vs {row['away_team']}"
    )
