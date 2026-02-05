import pandas as pd
import numpy as np

# Charger les données
df = pd.read_csv("data/prediction_dataset_enriched_v2.csv")

# Convertir les colonnes nécessaires
df["bet_odd"] = pd.to_numeric(df["bet_odd"], errors="coerce")
df["success"] = pd.to_numeric(df["success"], errors="coerce")

# Filtrer les paris avec cote >= 1.90
odds_190_plus = df[(df["bet_odd"] >= 1.90) & (df["bet_odd"].notna())].copy()

print("=" * 80)
print("PARIS AVEC COTE >= 1.90")
print("=" * 80)

if len(odds_190_plus) > 0:
    # Trier par cote décroissante
    odds_190_plus = odds_190_plus.sort_values("bet_odd", ascending=False)

    print(f"\nTotal de paris trouvés: {len(odds_190_plus)}\n")

    # Afficher chaque pari
    for idx, row in odds_190_plus.iterrows():
        home = row["home_team"]
        away = row["away_team"]
        odd = row["bet_odd"]
        bet_type = row["bet_selection"]
        success = row["success"]
        result_score = row["result_score"]
        date = row["fixture_date"]

        status = (
            "✅ GAGNE" if success == 1 else "❌ PERDU" if success == 0 else "❓ UNKNOWN"
        )

        print(f"{status} | Cote: {odd:.2f} | {home} vs {away}")
        print(f"       Type: {bet_type}")
        print(f"       Résultat: {result_score}")
        print(f"       Date: {date}")
        print()

    # Statistiques
    print("=" * 80)
    print("STATISTIQUES POUR COTES >= 1.90")
    print("=" * 80)

    gagnants = odds_190_plus[odds_190_plus["success"] == 1]
    perdants = odds_190_plus[odds_190_plus["success"] == 0]

    total = len(odds_190_plus)
    nb_gagnants = len(gagnants)
    nb_perdants = len(perdants)
    win_rate = (nb_gagnants / total * 100) if total > 0 else 0

    print(f"\nTotal: {total} paris")
    print(f"Gagnants: {nb_gagnants} ({win_rate:.1f}%)")
    print(f"Perdants: {nb_perdants} ({100-win_rate:.1f}%)")

    # Cotes moyennes
    avg_odd = odds_190_plus["bet_odd"].mean()
    print(f"\nCote moyenne: {avg_odd:.2f}")

    # Par type de pari
    print(f"\nPAR TYPE DE PARI:")
    by_type = odds_190_plus.groupby("bet_selection").agg({"success": ["count", "sum"]})

    for bet_type, row in by_type.iterrows():
        total_type = int(row["success"]["count"])
        wins = int(row["success"]["sum"])
        rate = (wins / total_type * 100) if total_type > 0 else 0
        print(f"  {bet_type}: {wins}/{total_type} = {rate:.1f}%")

else:
    print("Aucun pari trouvé avec cote >= 1.90")
