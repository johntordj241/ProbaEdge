#!/usr/bin/env python3
"""Cherche la fiche exacte du match Angers vs OM 17/01/2026"""

import pandas as pd

df = pd.read_csv("data/prediction_dataset_enriched.csv")

# Convertir la date
df["fixture_date"] = pd.to_datetime(df["fixture_date"], errors="coerce", utc=True)

# Chercher les matchs autour du 17/01/2026
recent = df[df["fixture_date"] >= "2026-01-15"].sort_values(
    "fixture_date", ascending=False
)

print("=" * 120)
print("MATCHS DU 15-20 JANVIER 2026")
print("=" * 120)

print(f"\nTotal matchs trouvés: {len(recent)}\n")

for idx, (_, row) in enumerate(recent.head(20).iterrows(), 1):
    date_str = (
        row["fixture_date"].strftime("%Y-%m-%d %H:%M")
        if pd.notna(row["fixture_date"])
        else "N/A"
    )
    league = int(row["league_id"]) if pd.notna(row["league_id"]) else "?"
    print(
        f"{idx:2d}. {date_str} | {row['home_team']:20s} vs {row['away_team']:20s} | L{league}"
    )

# Chercher spécifiquement Angers
print("\n" + "=" * 120)
print("RECHERCHE SPÉCIFIQUE ANGERS")
print("=" * 120)

angers = df[
    (df["home_team"].str.contains("Angers", case=False, na=False))
    | (df["away_team"].str.contains("Angers", case=False, na=False))
]

if len(angers) > 0:
    angers_sorted = angers.sort_values("fixture_date", ascending=False)
    print(f"\nMatchs avec Angers trouvés: {len(angers)}\n")
    for _, row in angers_sorted.head(5).iterrows():
        print(f"\n{'=' * 120}")
        print(f"MATCH: {row['home_team']} vs {row['away_team']}")
        print(f"{'=' * 120}")
        print(f"Date: {row['fixture_date']}")
        print(f"Ligue ID: {int(row['league_id'])}")
        print(f"\nPRÉDICTION:")
        print(f"  Main pick: {row['main_pick']}")
        print(f"  Confiance: {row['main_confidence']:.0f}%")
        print(f"\nPROBABILITÉS:")
        print(f"  Home: {row['prob_home']:.1%}")
        print(f"  Draw: {row['prob_draw']:.1%}")
        print(f"  Away: {row['prob_away']:.1%}")
        print(f"  Over 2.5: {row['prob_over_2_5']:.1%}")
        print(f"  Under 2.5: {row['prob_under_2_5']:.1%}")
        print(f"\nRÉSULTAT:")
        print(f"  Score: {row['result_score']}")
        print(f"  Succès: {row['success']}")
        print(f"  Détails du pari: {row['bet_result']}")
        print(f"\nBET SELECTION (Combinaison):")
        if pd.notna(row["bet_selection"]):
            print(f"  {row['bet_selection']}")
        else:
            print(f"  Aucun pari en combinaison")
else:
    print("\n❌ Aucun match avec Angers trouvé")
    print("\nLe match n'a peut-être pas encore été enregistré dans la base de données.")
