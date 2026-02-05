#!/usr/bin/env python3
"""Analyse complète Europa League - Types de paris et combinés"""

import pandas as pd
import warnings

warnings.filterwarnings("ignore")

# Charger les données
try:
    df = pd.read_csv("data/prediction_dataset_enriched_v2.csv")
except:
    df = pd.read_csv("data/prediction_dataset_enriched.csv")

# Filtrer les données Europa valides (league_id = 4)
df_europa = df[(df["league_id"] == 4.0) & (df["success"].notna())].copy()

print("\n" + "=" * 100)
print("🎯 EUROPA LEAGUE - ANALYSE COMPLÈTE")
print("=" * 100)
print(f"\n📊 Total de paris Europa analysés: {len(df_europa)}")

if len(df_europa) == 0:
    print("\n❌ Pas assez de données pour Europa League dans le dataset actuel.")
    print("Les données disponibles sont probablement limitées à la LDC.")
    exit()


# Fonction pour catégoriser les types de paris
def get_bet_type(pick):
    if pd.isna(pick):
        return "Inconnu"

    p = str(pick).lower().strip()

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
    if "nul" in p or p == "x":
        return "Nul"
    if "victoire" in p or "1" in p or "2" in p:
        if "double" not in p:
            return "Victoire"
    if "double" in p:
        return "Double Chance"

    return "Autre"


df_europa["type"] = df_europa["main_pick"].apply(get_bet_type)

# ============================================================================
print("\n" + "=" * 100)
print("1️⃣ TAUX DE RÉUSSITE PAR TYPE DE PARI (SIMPLES)")
print("=" * 100)

bet_types = df_europa["type"].unique()
results = []

for bet_type in sorted(bet_types):
    sub = df_europa[df_europa["type"] == bet_type]
    if len(sub) >= 1:
        successes = sub["success"].astype(int).sum()
        total = len(sub)
        pct = (successes / total * 100) if total > 0 else 0
        results.append((bet_type, successes, total, pct))

results.sort(key=lambda x: x[3], reverse=True)

print(
    f"\n{'Type de Pari':<20} | {'Succès':<15} | {'Total':<10} | {'% Réussite':<12} | Visualisation"
)
print("-" * 100)

for bet_type, successes, total, pct in results:
    bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
    print(
        f"{bet_type:<20} | {successes:>3d}/{total:>3d} gagnés | {total:>6d} | {pct:>6.1f}%  | {bar}"
    )

# Résumé simples
print("\n" + "-" * 100)
if results:
    best = results[0]
    worst = results[-1]
    print(f"\n✅ MEILLEUR: {best[0]:20} → {best[3]:.1f}% ({best[1]}/{best[2]})")
    print(f"❌ PIRE:     {worst[0]:20} → {worst[3]:.1f}% ({worst[1]}/{worst[2]})")

    total_success = sum([r[1] for r in results])
    total_bets = sum([r[2] for r in results])
    avg_pct = (total_success / total_bets * 100) if total_bets > 0 else 0
    print(f"\n📊 MOYENNE GÉNÉRALE (EUROPA): {avg_pct:.1f}%")

# ============================================================================
print("\n" + "=" * 100)
print("2️⃣ ANALYSE DES PARIS COMBINÉS")
print("=" * 100)


# Identifier les combinés
def is_combo(row):
    main_pick = str(row["main_pick"]).strip() if pd.notna(row["main_pick"]) else ""
    bet_selection = (
        str(row["bet_selection"]).strip() if pd.notna(row["bet_selection"]) else ""
    )
    total_pick = str(row["total_pick"]).strip() if pd.notna(row["total_pick"]) else ""

    elements = sum(
        [
            len(main_pick) > 0 and main_pick != "nan",
            len(bet_selection) > 0 and bet_selection != "nan",
            len(total_pick) > 0 and total_pick != "nan",
        ]
    )
    return elements >= 2


df_europa["is_combo"] = df_europa.apply(is_combo, axis=1)
simples = df_europa[~df_europa["is_combo"]]
combos = df_europa[df_europa["is_combo"]]

print(f"\n📊 Distribution:")
print(f"   • Paris Simples:  {len(simples)} ({len(simples)/len(df_europa)*100:.1f}%)")
print(f"   • Paris Combinés: {len(combos)} ({len(combos)/len(df_europa)*100:.1f}%)")

# Performance simples vs combos
print("\n" + "-" * 100)
print("📈 PERFORMANCE")

if len(simples) > 0:
    simple_success = simples["success"].astype(int).sum()
    simple_pct = simple_success / len(simples) * 100
    print(f"\n📌 Paris Simples:  {simple_pct:.1f}% ({simple_success}/{len(simples)})")
else:
    simple_pct = 0
    print(f"\n📌 Paris Simples: Pas de données")

if len(combos) > 0:
    combo_success = combos["success"].astype(int).sum()
    combo_pct = combo_success / len(combos) * 100
    print(f"📌 Paris Combinés: {combo_pct:.1f}% ({combo_success}/{len(combos)})")
else:
    combo_pct = 0
    print(f"📌 Paris Combinés: Pas de données")

winner = "SIMPLES 🎯" if simple_pct > combo_pct else "COMBINÉS 🎯"
if len(combos) > 0 and len(simples) > 0:
    print(f"\n🏆 Le plus performant en Europa: {winner}")

# Analyse des combinés
if len(combos) > 0:
    print("\n" + "-" * 100)
    print("🔍 COMPOSITION DES COMBINÉS EUROPA")
    print("-" * 100)

    combos["main_type"] = combos["main_pick"].apply(get_bet_type)
    combos["bet_type"] = combos["bet_selection"].apply(get_bet_type)
    combos["total_type"] = combos["total_pick"].apply(get_bet_type)

    # Types les plus fréquents
    print("\nComme Premier pick (main_pick):")
    main_types = combos["main_type"].value_counts()
    for ptype, count in main_types.head(5).items():
        sub = combos[combos["main_type"] == ptype]
        success = sub["success"].astype(int).sum()
        pct = success / len(sub) * 100
        print(f"  {ptype:20} → {pct:5.1f}% ({success}/{len(sub)})")

    print("\nComme Deuxième pick (bet_selection):")
    bet_types_combo = combos["bet_type"].value_counts()
    for ptype, count in bet_types_combo.head(5).items():
        if ptype != "Inconnu":
            sub = combos[combos["bet_type"] == ptype]
            success = sub["success"].astype(int).sum()
            pct = success / len(sub) * 100
            print(f"  {ptype:20} → {pct:5.1f}% ({success}/{len(sub)})")

    print("\nComme Pick supplémentaire (total_pick):")
    total_types_combo = combos["total_type"].value_counts()
    for ptype, count in total_types_combo.head(5).items():
        if ptype != "Inconnu":
            sub = combos[combos["total_type"] == ptype]
            success = sub["success"].astype(int).sum()
            pct = success / len(sub) * 100
            print(f"  {ptype:20} → {pct:5.1f}% ({success}/{len(sub)})")

# ============================================================================
print("\n" + "=" * 100)
print("📊 RÉSUMÉ COMPARATIF: EUROPA vs LDC")
print("=" * 100)

# Charger aussi LDC pour comparaison
df_ldc = df[(df["league_id"] == 3.0) & (df["success"].notna())].copy()
ldc_success_rate = (
    (df_ldc["success"].astype(int).sum() / len(df_ldc) * 100) if len(df_ldc) > 0 else 0
)

europa_success_rate = (
    (df_europa["success"].astype(int).sum() / len(df_europa) * 100)
    if len(df_europa) > 0
    else 0
)

print(f"\n🏆 LDC:    {ldc_success_rate:.1f}%")
print(f"🎯 EUROPA: {europa_success_rate:.1f}%")

if europa_success_rate > ldc_success_rate:
    diff = europa_success_rate - ldc_success_rate
    print(f"\n✅ EUROPA est MEILLEURE que LDC (+{diff:.1f}%)")
elif europa_success_rate < ldc_success_rate:
    diff = ldc_success_rate - europa_success_rate
    print(f"\n⚠️ LDC est meilleure qu'EUROPA (-{diff:.1f}%)")
else:
    print(f"\n➡️ À égalité!")

print("\n" + "=" * 100)
