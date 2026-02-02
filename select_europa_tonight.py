#!/usr/bin/env python3
"""Sélection des meilleurs matchs Europa du 29/01/2026"""

import pandas as pd
from datetime import datetime
import warnings

warnings.filterwarnings("ignore")

# Charger les données
try:
    df = pd.read_csv("data/prediction_dataset_enriched_v2.csv")
except:
    df = pd.read_csv("data/prediction_dataset_enriched.csv")

# Convertir les dates
df["fixture_date"] = pd.to_datetime(df["fixture_date"], utc=True, errors="coerce")

# Aujourd'hui: 29/01/2026
target_date = pd.Timestamp("2026-01-29", tz="UTC")

# Filtrer Europa League du 29/01/2026
europa_today = df[
    (df["league_id"] == 4.0) & (df["fixture_date"].dt.date == target_date.date())
].copy()

print("\n" + "=" * 120)
print("🎯 EUROPA LEAGUE - 29 JANVIER 2026")
print("=" * 120)
print(f"\n📊 Matchs trouvés: {len(europa_today)}")

if len(europa_today) == 0:
    print("\n⚠️ Pas de matchs Europa trouvés pour le 29/01/2026")
    print("\nVérification des matchs futurs disponibles...")

    future = df[(df["league_id"] == 4.0) & (df["fixture_date"] > target_date)].copy()

    if len(future) > 0:
        print(f"\n📅 Matchs Europa disponibles aux dates suivantes:")
        unique_dates = future["fixture_date"].dt.date.unique()
        for d in sorted(unique_dates)[:5]:
            count = len(future[future["fixture_date"].dt.date == d])
            print(f"   • {d}: {count} matchs")
    else:
        print("❌ Aucun match Europa trouvé dans le dataset.")
else:
    # Fonction pour obtenir le type de pari
    def get_bet_type(pick):
        if pd.isna(pick):
            return "?"

        p = str(pick).lower().strip()

        if "over" in p and "2.5" in p:
            return "Over 2.5"
        if "under" in p and "2.5" in p:
            return "Under 2.5"
        if "btts" in p:
            return "BTTS"
        if "nul" in p or p == "x":
            return "Nul"
        if "victoire" in p or ("1" in p or "2" in p) and "double" not in p:
            return "Victoire"
        if "double" in p:
            return "Double Chance"
        if "over" in p and "1.5" in p:
            return "Over 1.5"
        if "under" in p and "1.5" in p:
            return "Under 1.5"

        return "Autre"

    europa_today["main_type"] = europa_today["main_pick"].apply(get_bet_type)
    europa_today["bet_type"] = europa_today["bet_selection"].apply(get_bet_type)

    # Trier par probabilité de réussite (prob_home, prob_draw, prob_away, prob_over_2_5)
    europa_today["max_prob"] = europa_today[
        ["prob_home", "prob_draw", "prob_away", "prob_over_2_5"]
    ].max(axis=1)
    europa_today_sorted = europa_today.sort_values("max_prob", ascending=False)

    print("\n" + "=" * 120)
    print("🔥 SÉLECTION DES MEILLEURS MATCHS (TOP 5)")
    print("=" * 120)

    for idx, (i, row) in enumerate(europa_today_sorted.head(5).iterrows(), 1):
        print(f"\n{'=' * 120}")
        print(f"MATCH {idx}: {row['home_team']} vs {row['away_team']}")
        print(f"{'=' * 120}")

        time_str = (
            row["fixture_date"].strftime("%H:%M")
            if pd.notna(row["fixture_date"])
            else "?"
        )
        print(f"\n⏰ Heure: {time_str}")
        print(f"🎯 Main Pick: {row['main_pick']}")
        print(f"📊 Bet Selection: {row['bet_selection']}")
        print(f"📈 Total Pick: {row['total_pick']}")

        print(f"\n📉 Probabilités:")
        print(f"   • Home (1): {row['prob_home']*100:.1f}%")
        print(f"   • Draw (X): {row['prob_draw']*100:.1f}%")
        print(f"   • Away (2): {row['prob_away']*100:.1f}%")
        print(f"   • Over 2.5: {row['prob_over_2_5']*100:.1f}%")

        # Recommandations
        print(f"\n💡 RECOMMANDATION:")
        if pd.notna(row["main_pick"]):
            confidence = "🟢 CONFIANT" if row["max_prob"] > 0.65 else "🟡 MOYEN"
            print(
                f"   {confidence} - Main Pick: {row['main_pick']} ({row['main_type']})"
            )

        if pd.notna(row["bet_selection"]):
            print(f"   À combiner avec: {row['bet_selection']} ({row['bet_type']})")

        if pd.notna(row["total_pick"]):
            print(f"   Ajout: {row['total_pick']}")

# ============================================================================
print("\n" + "=" * 120)
print("💰 STRATÉGIE OPTIMALE POUR EUROPA")
print("=" * 120)

print(
    """
✅ BASÉ SUR L'ANALYSE EUROPA:

1. TYPES LES PLUS FIABLES EN EUROPA:
   → Privilégier: Nul, BTTS, Over 2.5
   → Éviter: Victoire simple (moins stable)

2. COMBINAISONS GAGNANTES:
   → Double Chance + Over 2.5 (très stable)
   → Nul + Over 2.5 (excellent en Europa)
   → BTTS + Double Chance (bon choix)

3. POUR CE SOIR (29/01):
   → Cherche les matchs équilibrés (probabilités proches)
   → Privilégie les nuls en Europa
   → Combine avec Over 2.5 ou BTTS
   → Mise: Préfère combinés aux simples

4. À ÉVITER:
   ❌ Victoires simples (seul)
   ❌ Under 2.5 trop souvent
   ❌ Matchs avec une grosse favorite (prob > 75%)
"""
)

print("\n" + "=" * 120)
