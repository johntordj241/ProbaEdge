import pandas as pd
import warnings

warnings.filterwarnings("ignore")

# Charger les données
df = pd.read_csv("data/prediction_dataset_enriched_v2.csv")

# Convertir dates
df["fixture_date"] = pd.to_datetime(df["fixture_date"], utc=True, errors="coerce")

# Chercher le match
match = df[
    (df["home_team"].str.contains("Sporting", case=False, na=False))
    & (df["away_team"].str.contains("Paris|PSG|Saint Germain", case=False, na=False))
]

if len(match) == 0:
    print("Match non trouvé. Cherche alternatives...")
    match = df[
        (df["home_team"].str.contains("Sporting|Paris", case=False, na=False))
        & (
            df["away_team"].str.contains(
                "Paris|PSG|Saint Germain|Sporting", case=False, na=False
            )
        )
    ]

print("=" * 80)
print("ANALYSE SPORTING CP vs PARIS SAINT GERMAIN")
print("=" * 80)

if len(match) > 0:
    row = match.iloc[0]

    print(f"\n{row['home_team']} vs {row['away_team']}")
    print(f"Date: {row['fixture_date']}")

    # Probas disponibles
    print(f"\n--- PROBAS BUTS ---")
    print(f"Over 2.5: {row.get('prob_over_2_5', 'N/A')}")
    print(f"Under 2.5: {row.get('prob_under_2_5', 'N/A')}")

    # Colonnes contenant 3.5
    cols_35 = [col for col in row.index if "3.5" in col.lower() or "35" in col]
    print(f"\nColonnes avec 3.5: {cols_35}")

    if cols_35:
        for col in cols_35:
            print(f"  {col}: {row[col]}")
    else:
        print("  ❌ Pas de colonne Over 3.5 détectée")

    # xG
    print(f"\n--- xG PROJETE ---")
    if "feature_total_pick_over" in row.index:
        print(f"Feature total_pick_over: {row['feature_total_pick_over']}")

    # Main pick
    print(f"\nMain pick: {row['main_pick']}")
    print(f"Main confidence: {row['main_confidence']*100:.1f}%")

    # Commentaire
    if "edge_comment" in row.index:
        print(f"Edge comment: {row['edge_comment']}")

    print("\n--- RECOMMANDATION ---")
    print("Le modèle propose Over 2.5 mais pas Over 3.5 spécifiquement")
    print("Raison: Over 3.5 exige une proba > 71.4% pour rentabiliser à 1.40")
    print(
        f"Proba estimée Over 3.5: ~{row.get('prob_over_2_5', 0) * 0.8 * 100:.0f}% (moins que Over 2.5)"
    )

else:
    print("❌ Match non trouvé dans la base de données")
    print("\nVérification des dates disponibles...")
    recent = df.sort_values("fixture_date", ascending=False).head(5)
    for idx, r in recent.iterrows():
        print(f"  {r['fixture_date']} | {r['home_team']} vs {r['away_team']}")
