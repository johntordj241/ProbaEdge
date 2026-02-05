import pandas as pd
from datetime import datetime

# Charger l'historique
df = pd.read_csv("data/prediction_history.csv")

# Convertir les dates
df["fixture_date"] = pd.to_datetime(df["fixture_date"], utc=True, errors="coerce")

# Date demain: 31 janvier 2026
tomorrow = datetime(2026, 1, 31)

# Matchs du 31/01
matches_31_01 = df[df["fixture_date"].dt.date == tomorrow.date()].copy()
print(f"✅ Matchs trouvés le 31/01/2026: {len(matches_31_01)}")
print("\n" + "=" * 120)

if len(matches_31_01) > 0:
    # Trier par confiance (confiance la plus élevée en premier)
    matches_31_01 = matches_31_01.sort_values(
        "main_confidence", ascending=False, na_position="last"
    )

    print("\n🎯 TOP MATCHS À JOUER LE 31/01/2026 (Triés par confiance)\n")

    for idx, row in matches_31_01.iterrows():
        confidence = row["main_confidence"] if pd.notna(row["main_confidence"]) else 0
        print(f"\n{'='*100}")
        print(f"⚽ {row['home_team']} vs {row['away_team']}")
        print(f"   ⏰ {row['fixture_date'].strftime('%H:%M')}")
        print(f"   🎯 Prédiction: {row['main_pick']}")
        print(f"   📊 Confiance: {confidence*100:.1f}%")
        if "bet_odd" in row and pd.notna(row["bet_odd"]):
            print(f"   💰 Cote recommandée: {row['bet_odd']:.2f}")
        if "edge_comment" in row and pd.notna(row["edge_comment"]):
            print(f"   💡 Analyse: {row['edge_comment']}")

        # Afficher les probas
        print(f"\n   Probabilités:")
        print(f"   • Home: {row['prob_home']*100:.1f}%")
        print(f"   • Draw: {row['prob_draw']*100:.1f}%")
        print(f"   • Away: {row['prob_away']*100:.1f}%")
        print(f"   • Over 2.5: {row['prob_over_2_5']*100:.1f}%")

    # Résumé
    print(f"\n\n{'='*100}")
    print("📋 RÉSUMÉ - MEILLEURES PARIS DEMAIN 31/01")
    print(f"{'='*100}\n")

    top_3 = matches_31_01.head(3)
    for i, (idx, row) in enumerate(top_3.iterrows(), 1):
        confidence = row["main_confidence"] if pd.notna(row["main_confidence"]) else 0
        print(
            f"{i}. {row['home_team']} vs {row['away_team']} | {row['main_pick']} | Confiance: {confidence*100:.0f}%"
        )

else:
    print("❌ Aucun match trouvé pour le 31/01/2026")

    # Afficher les dates disponibles
    print(f"\n📅 Dates disponibles:")
    dates = df["fixture_date"].dt.date.dropna().unique()
    dates_sorted = sorted(dates)
    for date in dates_sorted[-10:]:
        count = len(df[df["fixture_date"].dt.date == date])
        print(f"   {date}: {count} matchs")
