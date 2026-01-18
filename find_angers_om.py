#!/usr/bin/env python3
"""Cherche le match Angers vs OM du 17/01/2026"""

import pandas as pd

df = pd.read_csv("data/prediction_dataset_enriched.csv")

# Chercher Angers vs OM
angers_om = df[
    (
        (df["home_team"].str.contains("Angers", case=False, na=False))
        & (df["away_team"].str.contains("Marseille|OM", case=False, na=False))
    )
    | (
        (df["home_team"].str.contains("Marseille|OM", case=False, na=False))
        & (df["away_team"].str.contains("Angers", case=False, na=False))
    )
]

print("=" * 100)
print("MATCH ANGERS vs MARSEILLE / OM")
print("=" * 100)

if len(angers_om) > 0:
    print(f"\nMatchs trouvés: {len(angers_om)}\n")
    for _, row in angers_om.iterrows():
        print(f"Match: {row['home_team']} vs {row['away_team']}")
        print(f"Date: {row['fixture_date']}")
        print(f"Ligue: {int(row['league_id'])}")
        print(f"\nPRÉDICTION ALGORITHME:")
        print(f"  Main pick: {row['main_pick']}")
        print(f"  Confiance: {row['main_confidence']:.0f}%")
        print(f"\nPROBABILITÉS:")
        print(f"  Home: {row['prob_home']:.1%}")
        print(f"  Draw: {row['prob_draw']:.1%}")
        print(f"  Away: {row['prob_away']:.1%}")
        print(f"  Over 2.5: {row['prob_over_2_5']:.1%}")
        print(f"  Under 2.5: {row['prob_under_2_5']:.1%}")
        print(f"\nBTTS:")
        btts_in_pick = "BTTS" in str(row["main_pick"]).upper()
        print(f"  BTTS dans le pick principal: {btts_in_pick}")
        print(f"\nRÉSULTAT:")
        print(f"  Score: {row['result_score']}")
        print(f"  Succès: {row['success']}")
        print(f"\nCOMBINAISON:")
        if pd.notna(row["bet_selection"]):
            print(f"  {str(row['bet_selection'])[:120]}")
        else:
            print(f"  Pas de combinaison")
else:
    print("\n❌ MATCH ANGERS vs MARSEILLE NOT FOUND IN DATABASE")
    print("\nLe match n'est pas encore enregistré dans les données.")
    print("C'est normal car le match se joue ce soir (17/01/2026).")
    print("\nCela signifie que l'algorithme n'a pas encore fait de prédiction")
    print("pour ce match, ou le match n'a pas d'identifiant dans la base.")
