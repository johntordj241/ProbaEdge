import pandas as pd
from datetime import datetime

# Charger l'historique plus récent
df = pd.read_csv("data/prediction_history.csv")

# Convertir les dates
df["fixture_date"] = pd.to_datetime(df["fixture_date"], utc=True, errors="coerce")

# Date d'aujourd'hui: 30 janvier 2026
today = datetime(2026, 1, 30)

# Matchs du 30/01
matches_30_01 = df[df["fixture_date"].dt.date == today.date()].copy()
print(f"✅ Matchs trouvés le 30/01/2026: {len(matches_30_01)}")
print("\n" + "=" * 100)

if len(matches_30_01) > 0:
    matches_30_01 = matches_30_01.sort_values("fixture_date")
    for idx, row in matches_30_01.iterrows():
        print(f"\n⚽ {row['home_team']} vs {row['away_team']}")
        print(f"   ⏰ {row['fixture_date'].strftime('%H:%M')}")
        if "main_pick" in row and pd.notna(row["main_pick"]):
            print(f"   🎯 Prédiction: {row['main_pick']}")
        if "main_confidence" in row and pd.notna(row["main_confidence"]):
            print(f"   📊 Confiance: {row['main_confidence']*100:.1f}%")
        if "bet_odd" in row and pd.notna(row["bet_odd"]):
            print(f"   💰 Cote: {row['bet_odd']}")
else:
    print("❌ Pas de matchs trouvés le 30/01 dans l'historique")

# Chercher spécifiquement Cologne vs Wolfsburg
print(f"\n\n🔍 Recherche: Cologne vs Wolfsburg")
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

if len(cologne_wolfsburg) > 0:
    for idx, row in cologne_wolfsburg.iterrows():
        print(f"✅ TROUVÉ: {row['home_team']} vs {row['away_team']}")
        print(f"   Date: {row['fixture_date']}")
        if "main_pick" in row and pd.notna(row["main_pick"]):
            print(f"   Prédiction: {row['main_pick']}")
        if "main_confidence" in row and pd.notna(row["main_confidence"]):
            print(f"   Confiance: {row['main_confidence']*100:.1f}%")
else:
    print("❌ Cologne vs Wolfsburg NOT trouvé")

# Afficher les dates disponibles
print(f"\n\n📅 Dates disponibles dans l'historique:")
dates = df["fixture_date"].dt.date.unique()
print(sorted(dates)[-10:])
