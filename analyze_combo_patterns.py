#!/usr/bin/env python3
"""Analyse détaillée des COMBINAISONS - quels paris combinés ensemble passent le mieux"""

import pandas as pd
from itertools import combinations

df = pd.read_csv("data/prediction_dataset_enriched.csv")
df_valid = df[df["success"].notna()].copy()

print("=" * 100)
print("🎯 ANALYSE DES PARIS COMBINÉS - QUELLES COMBINAISONS PASSENT LE MIEUX?")
print("=" * 100)


def get_type(pick):
    p = str(pick).lower()
    if "over" in p and "2.5" in p:
        return "Over 2.5"
    if "under" in p and "2.5" in p:
        return "Under 2.5"
    if "over" in p and "1.5" in p:
        return "Over 1.5"
    if "under" in p and "1.5" in p:
        return "Under 1.5"
    if "btts" in p:
        return "BTTS"
    if "nul" in p or "x" in p:
        return "Nul"
    if "victoire" in p or "1" in p or "2" in p:
        if "double" not in p:
            return "Victoire"
    if "double" in p:
        return "Double Chance"
    return "Autre"


df_valid["type"] = df_valid["main_pick"].apply(get_type)

# Identifier les paris combinés
df_valid["is_combo"] = ~(
    (df_valid["bet_selection"].isna())
    | (df_valid["bet_selection"].astype(str).str.strip() == "")
)

print("\n1️⃣ STATISTIQUES GLOBALES DES COMBINAISONS")
print("-" * 100)

combos = df_valid[df_valid["is_combo"]]
simples = df_valid[~df_valid["is_combo"]]

print(f"\nParis SIMPLES:")
print(f"  - Total: {len(simples)}")
print(f"  - Gagnés: {simples['success'].astype(int).sum()}")
print(f"  - Taux: {simples['success'].astype(int).mean() * 100:.1f}%")

print(f"\nParis COMBINÉS:")
print(f"  - Total: {len(combos)}")
print(f"  - Gagnés: {combos['success'].astype(int).sum()}")
print(f"  - Taux: {combos['success'].astype(int).mean() * 100:.1f}%")

print("\n" + "=" * 100)
print("2️⃣ ANALYSE DES TYPES DE PARIS DANS LES COMBINAISONS")
print("=" * 100)

# Pour les paris combinés, regarder quels types sont les plus gagnants
combo_types = combos["type"].value_counts()
print("\nTypes de paris dans les COMBINÉS:")
for ptype, count in combo_types.items():
    sub = combos[combos["type"] == ptype]
    win_rate = sub["success"].astype(int).mean() * 100
    print(f"  {ptype:20s}: {count:3d} paris | {win_rate:5.1f}% de réussite")

print("\n" + "=" * 100)
print("3️⃣ ANALYSE PAR CHAMPIONNAT")
print("=" * 100)

league_names = {
    61: "🇫🇷 Ligue 1",
    62: "🇫🇷 Ligue 2",
    39: "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
    40: "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Championship",
    140: "🇪🇸 La Liga",
    78: "🇩🇪 Bundesliga",
    3: "🏆 Ligue des Champions",
}

print("\nCOMBINÉS par championnat:")
for league_id, league_name in sorted(league_names.items()):
    league_combos = combos[combos["league_id"] == league_id]
    if len(league_combos) > 0:
        win_rate = league_combos["success"].astype(int).mean() * 100
        bar = "█" * int(win_rate / 5) + "░" * (20 - int(win_rate / 5))
        print(
            f"  {league_name:25s} | {bar} {win_rate:5.1f}% | {league_combos['success'].astype(int).sum():2d}/{len(league_combos):2d}"
        )

print("\n" + "=" * 100)
print("4️⃣ TYPES DE PARIS GAGNANTS DANS LES COMBOS")
print("=" * 100)

# Les meilleurs types dans les combinés
print("\nMeilleurs types de paris DANS les combinaisons:")
for ptype in sorted(combo_types.index):
    sub = combos[combos["type"] == ptype]
    if len(sub) >= 2:
        win_rate = sub["success"].astype(int).mean() * 100
        wins = sub["success"].astype(int).sum()

        if win_rate >= 70:
            icon = "🟢🟢"
        elif win_rate >= 60:
            icon = "🟢"
        elif win_rate >= 50:
            icon = "🟡"
        else:
            icon = "🔴"

        print(f"  {icon} {ptype:20s}: {win_rate:5.1f}% ({wins}/{len(sub)})")

print("\n" + "=" * 100)
print("5️⃣ COMBINAISONS SPÉCIFIQUES - QUELS TYPES ENSEMBLE?")
print("=" * 100)

# Analyser bet_selection pour voir les combinaisons
print("\nExemples de combinaisons trouvées dans les données:")

combo_selections = combos[combos["bet_selection"].notna()]["bet_selection"].unique()
print(f"Total de patterns de combinaison différents: {len(combo_selections)}")

# Afficher les plus courants
combo_counts = combos[combos["bet_selection"].notna()]["bet_selection"].value_counts()
print("\nTop 10 des combinaisons les plus jouées:")
for idx, (combo_str, count) in enumerate(combo_counts.head(10).items(), 1):
    sub = combos[combos["bet_selection"] == combo_str]
    win_rate = sub["success"].astype(int).mean() * 100
    wins = sub["success"].astype(int).sum()

    if win_rate >= 70:
        icon = "🟢🟢"
    elif win_rate >= 60:
        icon = "🟢"
    elif win_rate >= 50:
        icon = "🟡"
    else:
        icon = "🔴"

    print(f"  {idx}. {icon} {combo_str[:60]:60s} | {win_rate:5.1f}% ({wins}/{count})")

print("\n" + "=" * 100)
print("6️⃣ RÉSUMÉ - MEILLEURE STRATÉGIE POUR LES COMBOS")
print("=" * 100)

# Comparer simple vs combo par type
print("\nPerformance SIMPLE vs COMBO par type de pari:")
important_types = ["Over 2.5", "Nul", "BTTS", "Under 2.5", "Victoire"]

for ptype in important_types:
    simple_type = simples[simples["type"] == ptype]
    combo_type = combos[combos["type"] == ptype]

    if len(simple_type) > 0 or len(combo_type) > 0:
        simple_rate = (
            simple_type["success"].astype(int).mean() * 100
            if len(simple_type) > 0
            else 0
        )
        combo_rate = (
            combo_type["success"].astype(int).mean() * 100 if len(combo_type) > 0 else 0
        )

        if len(simple_type) > 0:
            simple_str = f"{simple_rate:.1f}% ({len(simple_type)})"
        else:
            simple_str = "N/A"

        if len(combo_type) > 0:
            combo_str = f"{combo_rate:.1f}% ({len(combo_type)})"
        else:
            combo_str = "N/A"

        print(f"  {ptype:20s} | SIMPLE: {simple_str:15s} | COMBO: {combo_str:15s}")

print("\n" + "=" * 100)
print("🎯 CONCLUSIONS")
print("=" * 100)

# Stats finales
combo_win_rate = combos["success"].astype(int).mean() * 100
simple_win_rate = simples["success"].astype(int).mean() * 100
diff = simple_win_rate - combo_win_rate

print(f"\n1. GLOBAL:")
print(f"   - Paris SIMPLES: {simple_win_rate:.1f}%")
print(f"   - Paris COMBINÉS: {combo_win_rate:.1f}%")
print(f"   - Différence: {diff:+.1f}% (avantage aux SIMPLES)")

# Meilleur type en combo
best_combo_type = combos.groupby("type")["success"].agg(["sum", "count"])
best_combo_type["rate"] = best_combo_type["sum"] / best_combo_type["count"] * 100
best_combo_type = best_combo_type[best_combo_type["count"] >= 2].sort_values(
    "rate", ascending=False
)

if len(best_combo_type) > 0:
    top_type = best_combo_type.index[0]
    top_rate = best_combo_type.iloc[0]["rate"]
    top_count = int(best_combo_type.iloc[0]["count"])
    top_wins = int(best_combo_type.iloc[0]["sum"])
    print(f"\n2. MEILLEUR TYPE EN COMBINÉ:")
    print(f"   - {top_type}: {top_rate:.1f}% ({top_wins}/{top_count})")

print(f"\n3. RECOMMANDATION:")
if diff > 1:
    print(f"   ✅ Privilégie les PARIS SIMPLES (avantage de {diff:.1f}%)")
else:
    print(f"   ✅ Simple et Combiné sont équivalents - choisis selon ta stratégie")
