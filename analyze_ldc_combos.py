#!/usr/bin/env python3
"""Analyse des combinés (paris combinés) - LIGUE DES CHAMPIONS"""

import pandas as pd
import warnings

warnings.filterwarnings("ignore")

# Charger les données
try:
    df = pd.read_csv("data/prediction_dataset_enriched_v2.csv")
except:
    df = pd.read_csv("data/prediction_dataset_enriched.csv")

# Filtrer les données LDC valides
df_ldc = df[(df["league_id"] == 3.0) & (df["success"].notna())].copy()

print("\n" + "=" * 100)
print("🏆 LIGUE DES CHAMPIONS - ANALYSE DES PARIS COMBINÉS")
print("=" * 100)


# Fonction pour identifier les combinés
def is_combo(row):
    """Identifie si c'est un pari combiné (2 sélections ou plus)"""
    main_pick = str(row["main_pick"]).strip() if pd.notna(row["main_pick"]) else ""
    bet_selection = (
        str(row["bet_selection"]).strip() if pd.notna(row["bet_selection"]) else ""
    )
    total_pick = str(row["total_pick"]).strip() if pd.notna(row["total_pick"]) else ""

    # Un combo a au moins 2 éléments parmi main_pick, bet_selection, total_pick
    elements = sum(
        [
            len(main_pick) > 0 and main_pick != "nan",
            len(bet_selection) > 0 and bet_selection != "nan",
            len(total_pick) > 0 and total_pick != "nan",
        ]
    )
    return elements >= 2


df_ldc["is_combo"] = df_ldc.apply(is_combo, axis=1)

# Séparer simples et combinés
simples = df_ldc[~df_ldc["is_combo"]]
combos = df_ldc[df_ldc["is_combo"]]

print(f"\n📊 Total LDC: {len(df_ldc)} matchs")
print(f"   • Paris Simples: {len(simples)} ({len(simples)/len(df_ldc)*100:.1f}%)")
print(f"   • Paris Combinés: {len(combos)} ({len(combos)/len(df_ldc)*100:.1f}%)")


# Fonction pour obtenir le type de pari
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


if len(combos) > 0:
    print("\n" + "=" * 100)
    print("🎯 PERFORMANCE DES COMBINÉS")
    print("=" * 100)

    combo_success = combos["success"].astype(int).sum()
    combo_total = len(combos)
    combo_pct = (combo_success / combo_total * 100) if combo_total > 0 else 0

    print(
        f"\n📈 TAUX DE RÉUSSITE COMBINÉ LDC: {combo_pct:.1f}% ({combo_success}/{combo_total} matchs)"
    )

    # Analyse par composition de combo
    print("\n" + "-" * 100)
    print("🔍 COMPOSITION DES COMBINÉS LDC")
    print("-" * 100)

    # Checker les combinaisons principales
    combos["main_type"] = combos["main_pick"].apply(get_bet_type)
    combos["bet_type"] = combos["bet_selection"].apply(get_bet_type)
    combos["total_type"] = combos["total_pick"].apply(get_bet_type)

    # Combinaisons avec main_pick + bet_selection
    with_main_bet = combos[
        (combos["main_pick"].notna()) & (combos["bet_selection"].notna())
    ]
    if len(with_main_bet) > 0:
        success = with_main_bet["success"].astype(int).sum()
        pct = success / len(with_main_bet) * 100
        print(
            f"\n  Main Pick + Bet Selection: {pct:.1f}% ({success}/{len(with_main_bet)})"
        )
        for idx, row in with_main_bet.head(3).iterrows():
            print(
                f"    • {row['main_type']:15} + {row['bet_type']:15} → {'✅' if row['success'] == 1 else '❌'}"
            )

    # Combinaisons avec main_pick + total_pick
    with_main_total = combos[
        (combos["main_pick"].notna()) & (combos["total_pick"].notna())
    ]
    if len(with_main_total) > 0:
        success = with_main_total["success"].astype(int).sum()
        pct = success / len(with_main_total) * 100
        print(
            f"\n  Main Pick + Total Pick: {pct:.1f}% ({success}/{len(with_main_total)})"
        )
        for idx, row in with_main_total.head(3).iterrows():
            print(
                f"    • {row['main_type']:15} + {row['total_type']:15} → {'✅' if row['success'] == 1 else '❌'}"
            )

    # Types les plus fréquents dans les combinés
    print("\n" + "-" * 100)
    print("📊 TYPES LES PLUS FRÉQUENTS DANS LES COMBINÉS LDC")
    print("-" * 100)

    main_types = combos["main_type"].value_counts()
    print("\nComme Premier pick (main_pick):")
    for ptype, count in main_types.head(5).items():
        sub = combos[combos["main_type"] == ptype]
        success = sub["success"].astype(int).sum()
        pct = success / len(sub) * 100
        print(f"  {ptype:20} → {pct:5.1f}% ({success}/{len(sub)})")

    bet_types = combos["bet_type"].value_counts()
    print("\nComme Deuxième pick (bet_selection):")
    for ptype, count in bet_types.head(5).items():
        if ptype != "Inconnu":
            sub = combos[combos["bet_type"] == ptype]
            success = sub["success"].astype(int).sum()
            pct = success / len(sub) * 100
            print(f"  {ptype:20} → {pct:5.1f}% ({success}/{len(sub)})")

    total_types = combos["total_type"].value_counts()
    print("\nComme Pick supplémentaire (total_pick):")
    for ptype, count in total_types.head(5).items():
        if ptype != "Inconnu":
            sub = combos[combos["total_type"] == ptype]
            success = sub["success"].astype(int).sum()
            pct = success / len(sub) * 100
            print(f"  {ptype:20} → {pct:5.1f}% ({success}/{len(sub)})")

# Comparaison Simple vs Combo
print("\n" + "=" * 100)
print("📊 COMPARAISON SIMPLE vs COMBINÉ")
print("=" * 100)

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
print(f"\n🏆 Le plus performant en LDC: {winner}")

print("\n" + "=" * 100)
