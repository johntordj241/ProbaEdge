#!/usr/bin/env python3
"""Analyse du taux de réussite par type de pari - LIGUE DES CHAMPIONS UNIQUEMENT"""

import pandas as pd
import warnings

warnings.filterwarnings("ignore")

# Charger les données
try:
    df = pd.read_csv("data/prediction_dataset_enriched_v2.csv")
except:
    df = pd.read_csv("data/prediction_dataset_enriched.csv")

# Filtrer les données valides
df_ldc = df[(df["league_id"] == 3.0) & (df["success"].notna())].copy()

print("\n" + "=" * 100)
print("🏆 LIGUE DES CHAMPIONS - TAUX DE RÉUSSITE PAR TYPE DE PARI")
print("=" * 100)
print(f"\n📊 Total de paris LDC analysés: {len(df_ldc)}")


# Fonction pour catégoriser les types de paris
def get_bet_type(pick):
    if pd.isna(pick):
        return "Inconnu"

    p = str(pick).lower().strip()

    # Over/Under
    if "over" in p and "2.5" in p:
        return "Over 2.5"
    if "under" in p and "2.5" in p:
        return "Under 2.5"
    if "over" in p and "1.5" in p:
        return "Over 1.5"
    if "under" in p and "1.5" in p:
        return "Under 1.5"

    # BTTS
    if "btts" in p:
        return "BTTS"

    # Nul
    if "nul" in p or p == "x":
        return "Nul"

    # Victoires
    if "victoire" in p or "1" in p or "2" in p:
        if "double" not in p:
            return "Victoire"

    # Double Chance
    if "double" in p:
        return "Double Chance"

    return "Autre"


df_ldc["type"] = df_ldc["main_pick"].apply(get_bet_type)

# Grouper par type de pari
bet_types = df_ldc["type"].unique()
results = []

for bet_type in sorted(bet_types):
    sub = df_ldc[df_ldc["type"] == bet_type]
    if len(sub) >= 1:
        successes = sub["success"].astype(int).sum()
        total = len(sub)
        pct = (successes / total * 100) if total > 0 else 0
        results.append((bet_type, successes, total, pct))

# Trier par taux de réussite (décroissant)
results.sort(key=lambda x: x[3], reverse=True)

print("\n" + "-" * 100)
print(
    f"{'Type de Pari':<20} | {'Succès':<15} | {'Total':<10} | {'% Réussite':<12} | Visualisation"
)
print("-" * 100)

for bet_type, successes, total, pct in results:
    bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
    print(
        f"{bet_type:<20} | {successes:>3d}/{total:>3d} gagnés | {total:>6d} | {pct:>6.1f}%  | {bar}"
    )

# Résumé
print("\n" + "=" * 100)
print("📈 RÉSUMÉ")
print("=" * 100)

if results:
    best = results[0]
    worst = results[-1]

    print(
        f"\n✅ MEILLEUR TYPE: {best[0]:20s} → {best[3]:.1f}% ({best[1]}/{best[2]} matchs)"
    )
    print(
        f"❌ PIRE TYPE:     {worst[0]:20s} → {worst[3]:.1f}% ({worst[1]}/{worst[2]} matchs)"
    )

    # Moyenne générale
    total_success = sum([r[1] for r in results])
    total_bets = sum([r[2] for r in results])
    avg_pct = (total_success / total_bets * 100) if total_bets > 0 else 0
    print(
        f"\n📊 MOYENNE GÉNÉRALE (LDC): {avg_pct:.1f}% ({total_success}/{total_bets} matchs)"
    )

print("\n" + "=" * 100)
