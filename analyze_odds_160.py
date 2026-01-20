import pandas as pd
import numpy as np

# Charger les données
df = pd.read_csv("data/prediction_dataset_enriched_v2.csv")

# Filtrer les paris avec cotes entre 1.50 et 1.70 (proche de 1.60)
df["bet_odd"] = pd.to_numeric(df["bet_odd"], errors="coerce")
odds_range = df[(df["bet_odd"] >= 1.50) & (df["bet_odd"] <= 1.70)].copy()

print("=" * 70)
print("ANALYSE COTES PROCHES DE 1.60")
print("=" * 70)

if len(odds_range) == 0:
    print("\nPas de données avec cotes 1.50-1.70")
    # Essayer une gamme plus large
    odds_range = df[(df["bet_odd"] >= 1.40) & (df["bet_odd"] <= 1.80)].copy()
    print(f"Étendu à 1.40-1.80: {len(odds_range)} paris trouvés")

if len(odds_range) > 0:
    # Convertir le succès en booléen
    odds_range["success"] = pd.to_numeric(odds_range["success"], errors="coerce")

    total_bets = len(odds_range)
    winning_bets = odds_range["success"].sum()
    win_rate = (winning_bets / total_bets * 100) if total_bets > 0 else 0

    print(f"\nTotal paris avec cotes 1.50-1.70: {total_bets}")
    print(f"Paris gagnants: {int(winning_bets)}")
    print(f"Taux de réussite: {win_rate:.1f}%")

    # Rentabilité
    avg_odd = odds_range["bet_odd"].mean()
    expected_return = (win_rate / 100) * avg_odd
    profit_per_100 = (expected_return - 1) * 100

    print(f"\nCote moyenne: {avg_odd:.2f}")
    print(f"Retour attendu par 100€ misé: {expected_return:.2f}€")
    print(f"Profit/Perte net par 100€: {profit_per_100:+.1f}€")

    # Comparaison avec breakeven
    breakeven_rate = 100 / avg_odd
    print(f"\n📊 SEUIL DE RENTABILITÉ:")
    print(f"  Tu dois avoir {breakeven_rate:.1f}% de taux de réussite")
    print(f"  Tu as réellement: {win_rate:.1f}%")

    if win_rate > breakeven_rate:
        profit = win_rate - breakeven_rate
        print(f"  ✅ PROFIT de {profit:.1f}% par pari!")
    else:
        loss = breakeven_rate - win_rate
        print(f"  ❌ PERTE de {loss:.1f}% par pari")

    # Par type de pari
    print(f"\n\nPAR TYPE DE PARI:")
    bet_types = odds_range.groupby("bet_selection").agg({"success": ["count", "sum"]})

    for bet_type, row in bet_types.iterrows():
        total = int(row["success"]["count"])
        wins = int(row["success"]["sum"])
        rate = (wins / total * 100) if total > 0 else 0
        print(f"  {bet_type}: {wins}/{total} = {rate:.1f}%")

# Analyse plus large: cotes 1.50 à 2.50
print("\n\n" + "=" * 70)
print("SPECTRUM COMPLET: Cotes 1.50 à 2.50")
print("=" * 70)

broad_range = df[(df["bet_odd"] >= 1.50) & (df["bet_odd"] <= 2.50)].copy()

if len(broad_range) > 0:
    broad_range["success"] = pd.to_numeric(broad_range["success"], errors="coerce")

    # Segmenter par tranche de cotes
    bins = [1.50, 1.60, 1.70, 1.90, 2.50]
    labels = ["1.50-1.60", "1.60-1.70", "1.70-1.90", "1.90-2.50"]
    broad_range["odd_range"] = pd.cut(broad_range["bet_odd"], bins=bins, labels=labels)

    summary = broad_range.groupby("odd_range").agg(
        {"success": ["count", "sum", "mean"]}
    )

    print(f"\nCotes | Nb Paris | Gagnants | Taux")
    print("-" * 50)

    for range_label, row in summary.iterrows():
        if pd.notna(range_label):
            total = int(row["success"]["count"])
            wins = int(row["success"]["sum"])
            rate = row["success"]["mean"] * 100
            print(f"{range_label:12} | {total:8} | {wins:8} | {rate:5.1f}%")

print("\n\n" + "=" * 70)
print("CONCLUSION COTES 1.60")
print("=" * 70)

print(
    """
Cotes 1.60 = "Favoris modérés"

La probabilité implicite: 62.5%
= Le bookmaker pense que ça a 62.5% de chance

RÉALITÉ HISTORIQUE:
- Si mon taux réel = 60-62%: ✅ Neutre/Légèrement profitable
- Si mon taux réel < 55%: ❌ Perdant à long terme
- Si mon taux réel > 65%: ✅ Très profitable

CONSEIL:
Ne mise SUR cotes 1.60 que si tu es CONFIANT > 65%
Sinon: Cherche mieux ailleurs
"""
)
