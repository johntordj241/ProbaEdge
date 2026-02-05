#!/usr/bin/env python3
"""Cherche le match OM récent"""

import pandas as pd

df = pd.read_csv("data/prediction_dataset_enriched.csv")

# Chercher les matchs de l'OM (Marseille, OM, Olympique)
om_matches = df[
    (df["home_team"].str.contains("Marseille|OM|Olympique", case=False, na=False))
    | (df["away_team"].str.contains("Marseille|OM|Olympique", case=False, na=False))
]

print("=" * 100)
print(f"MATCHS TROUVÉS AVEC MARSEILLE: {len(om_matches)}")
print("=" * 100)

if len(om_matches) > 0:
    # Trier par date récente
    om_matches["fixture_date"] = pd.to_datetime(
        om_matches["fixture_date"], errors="coerce"
    )
    om_matches = om_matches.sort_values("fixture_date", ascending=False)

    print("\nLes 5 matchs les plus récents:")
    for idx, (_, row) in enumerate(om_matches.head(5).iterrows(), 1):
        print(f"\n{idx}. {row['home_team']} vs {row['away_team']}")
        print(f"   Date: {row['fixture_date']}")
        print(f"   Ligue: {int(row['league_id'])}")
        print(f"   Main pick: {row['main_pick']}")
        print(f"   Confiance: {row['main_confidence']:.1%}")
        print(f"   Résultat: {row['result_score']}")
        print(f"   Succès: {row['success']}")
        if pd.notna(row["bet_selection"]):
            print(f"   Bet selection: {str(row['bet_selection'])[:80]}")
        print(
            f"   Prob home/draw/away: {row['prob_home']:.1%} / {row['prob_draw']:.1%} / {row['prob_away']:.1%}"
        )
        print(f"   Over 2.5: {row['prob_over_2_5']:.1%}")
        print(f"   BTTS dans pick? {'BTTS' in str(row['main_pick']).lower()}")
else:
    print("\nAucun match de Marseille trouvé")

# Chercher aussi les matchs Ligue 1 récents
print("\n" + "=" * 100)
print("MATCHS LIGUE 1 RÉCENTS (L1 = league_id 61):")
print("=" * 100)

l1_matches = df[df["league_id"] == 61].copy()
l1_matches["fixture_date"] = pd.to_datetime(l1_matches["fixture_date"], errors="coerce")
l1_matches = l1_matches.sort_values("fixture_date", ascending=False)

print("\nTop 10 matchs les plus récents:")
for idx, (_, row) in enumerate(l1_matches.head(10).iterrows(), 1):
    print(
        f"{idx:2d}. {row['home_team']:20s} vs {row['away_team']:20s} | {row['fixture_date']} | Score: {row['result_score']:5s} | Pick: {str(row['main_pick'])[:30]}"
    )
