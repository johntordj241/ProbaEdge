#!/usr/bin/env python3
"""Analyse détaillée: Types de paris x Championnats"""

import pandas as pd

df = pd.read_csv("data/prediction_dataset_enriched.csv")
df_valid = df[df["success"].notna()].copy()

print("=" * 100)
print("📊 ANALYSE CROISÉE: TYPES DE PARIS × CHAMPIONNATS")
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

# Mapping des championnats
league_names = {
    61: "🇫🇷 Ligue 1",
    62: "🇫🇷 Ligue 2",
    39: "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
    40: "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Championship",
    140: "🇪🇸 La Liga",
    78: "🇩🇪 Bundesliga",
    3: "🏆 Ligue des Champions",
}

# Types de paris importants
important_types = ["Victoire", "Nul", "Over 2.5", "Under 2.5", "BTTS"]

print("\n1️⃣ VICTOIRES (Paris simples: Victoire Domicile ou Extérieur)")
print("-" * 100)
for league_id, league_name in sorted(league_names.items(), key=lambda x: x[1]):
    sub = df_valid[
        (df_valid["league_id"] == league_id) & (df_valid["type"] == "Victoire")
    ]
    if len(sub) >= 3:
        win = sub["success"].astype(int).sum()
        total = len(sub)
        pct = win * 100 / total
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  {league_name:25s} | {bar} {pct:5.1f}% | {win:2d}/{total:2d}")

print("\n2️⃣ NUL (Paris simples: Match nul)")
print("-" * 100)
for league_id, league_name in sorted(league_names.items(), key=lambda x: x[1]):
    sub = df_valid[(df_valid["league_id"] == league_id) & (df_valid["type"] == "Nul")]
    if len(sub) >= 3:
        win = sub["success"].astype(int).sum()
        total = len(sub)
        pct = win * 100 / total
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  {league_name:25s} | {bar} {pct:5.1f}% | {win:2d}/{total:2d}")

print("\n3️⃣ OVER 2.5 (Plus de 2.5 buts)")
print("-" * 100)
for league_id, league_name in sorted(league_names.items(), key=lambda x: x[1]):
    sub = df_valid[
        (df_valid["league_id"] == league_id) & (df_valid["type"] == "Over 2.5")
    ]
    if len(sub) >= 3:
        win = sub["success"].astype(int).sum()
        total = len(sub)
        pct = win * 100 / total
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  {league_name:25s} | {bar} {pct:5.1f}% | {win:2d}/{total:2d}")

print("\n4️⃣ UNDER 2.5 (Moins de 2.5 buts)")
print("-" * 100)
for league_id, league_name in sorted(league_names.items(), key=lambda x: x[1]):
    sub = df_valid[
        (df_valid["league_id"] == league_id) & (df_valid["type"] == "Under 2.5")
    ]
    if len(sub) >= 3:
        win = sub["success"].astype(int).sum()
        total = len(sub)
        pct = win * 100 / total
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  {league_name:25s} | {bar} {pct:5.1f}% | {win:2d}/{total:2d}")

print("\n5️⃣ BTTS (Les 2 équipes marquent)")
print("-" * 100)
for league_id, league_name in sorted(league_names.items(), key=lambda x: x[1]):
    sub = df_valid[(df_valid["league_id"] == league_id) & (df_valid["type"] == "BTTS")]
    if len(sub) >= 3:
        win = sub["success"].astype(int).sum()
        total = len(sub)
        pct = win * 100 / total
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  {league_name:25s} | {bar} {pct:5.1f}% | {win:2d}/{total:2d}")

print("\n" + "=" * 100)
print("📈 RÉSUMÉ - MEILLEURE COMBINAISON PAR CHAMPIONNAT")
print("=" * 100)

for league_id, league_name in sorted(league_names.items(), key=lambda x: x[1]):
    league_data = df_valid[df_valid["league_id"] == league_id]

    best_type = None
    best_pct = 0
    best_count = 0

    for ptype in important_types:
        sub = league_data[league_data["type"] == ptype]
        if len(sub) >= 2:  # Minimum 2 paris pour être considéré
            pct = sub["success"].astype(int).mean() * 100
            if pct > best_pct and len(sub) >= 3:
                best_pct = pct
                best_type = ptype
                best_count = len(sub)

    if best_type:
        print(f"\n{league_name}")
        print(
            f"  ✅ Meilleur type: {best_type:15s} à {best_pct:5.1f}% (n={best_count})"
        )

        # Afficher tous les types disponibles
        print(f"  Tous les types disponibles:")
        for ptype in important_types:
            sub = league_data[league_data["type"] == ptype]
            if len(sub) >= 2:
                pct = sub["success"].astype(int).mean() * 100
                print(f"    - {ptype:20s}: {pct:5.1f}% ({len(sub)} paris)")

print("\n" + "=" * 100)
print("🎯 CONCLUSIONS")
print("=" * 100)

# Victoire stats
print("\n1. VICTOIRES SIMPLES (Victoire Domicile ou Extérieur)")
victoire_by_league = {}
for league_id, league_name in league_names.items():
    sub = df_valid[
        (df_valid["league_id"] == league_id) & (df_valid["type"] == "Victoire")
    ]
    if len(sub) >= 3:
        pct = sub["success"].astype(int).mean() * 100
        victoire_by_league[league_name] = pct

best_vic = max(victoire_by_league.items(), key=lambda x: x[1])
worst_vic = min(victoire_by_league.items(), key=lambda x: x[1])
print(f"  🟢 MEILLEUR: {best_vic[0]} à {best_vic[1]:.1f}%")
print(f"  🔴 À ÉVITER: {worst_vic[0]} à {worst_vic[1]:.1f}%")

# Over 2.5
print("\n2. OVER 2.5 (Plus de 2.5 buts)")
over_by_league = {}
for league_id, league_name in league_names.items():
    sub = df_valid[
        (df_valid["league_id"] == league_id) & (df_valid["type"] == "Over 2.5")
    ]
    if len(sub) >= 3:
        pct = sub["success"].astype(int).mean() * 100
        over_by_league[league_name] = pct

if over_by_league:
    best_over = max(over_by_league.items(), key=lambda x: x[1])
    worst_over = min(over_by_league.items(), key=lambda x: x[1])
    print(f"  🟢 MEILLEUR: {best_over[0]} à {best_over[1]:.1f}%")
    print(f"  🔴 À ÉVITER: {worst_over[0]} à {worst_over[1]:.1f}%")

# Under 2.5
print("\n3. UNDER 2.5 (Moins de 2.5 buts)")
under_by_league = {}
for league_id, league_name in league_names.items():
    sub = df_valid[
        (df_valid["league_id"] == league_id) & (df_valid["type"] == "Under 2.5")
    ]
    if len(sub) >= 3:
        pct = sub["success"].astype(int).mean() * 100
        under_by_league[league_name] = pct

if under_by_league:
    best_under = max(under_by_league.items(), key=lambda x: x[1])
    worst_under = min(under_by_league.items(), key=lambda x: x[1])
    print(f"  🟢 MEILLEUR: {best_under[0]} à {best_under[1]:.1f}%")
    print(f"  🔴 À ÉVITER: {worst_under[0]} à {worst_under[1]:.1f}%")
