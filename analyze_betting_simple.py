#!/usr/bin/env python3
"""Analyse détaillée des paris: types, championnats, combinaisons"""

import pandas as pd
import numpy as np

df = pd.read_csv("data/prediction_dataset_enriched.csv")

print("=" * 100)
print("📊 ANALYSE DÉTAILLÉE DES PARIS & CHAMPIONNATS")
print("=" * 100)


# Parser les types de paris
def get_bet_type(main_pick):
    pick = str(main_pick).lower()
    if "victoire" in pick or "domicile" in pick or "exterieur" in pick:
        return "Victoire"
    if "nul" in pick or "x" in pick:
        return "Nul"
    if "over" in pick and "2.5" in pick:
        return "Over 2.5"
    if "under" in pick and "2.5" in pick:
        return "Under 2.5"
    if "over" in pick and "1.5" in pick:
        return "Over 1.5"
    if "under" in pick and "1.5" in pick:
        return "Under 1.5"
    if "btts" in pick:
        return "BTTS"
    if "double" in pick and "1x" in pick:
        return "Double 1X"
    if "double" in pick and "x2" in pick:
        return "Double X2"
    if "double" in pick:
        return "Double Chance"
    return "Autre"


df["bet_type"] = df["main_pick"].apply(get_bet_type)

# ============================================================================
# 1. TYPE DE PARIS
# ============================================================================
print("\n1️⃣  TYPES DE PARIS - Performance")
print("━" * 100)

df_valid = df[df["success"].notna()].copy()

for bet_type in df_valid["bet_type"].unique():
    subset = df_valid[df_valid["bet_type"] == bet_type]
    total = len(subset)
    success = subset["success"].astype(int).sum()
    rate = (success / total * 100) if total > 0 else 0
    print(f"{bet_type:20s} | Succès: {success:3d}/{total:3d} | Win Rate: {rate:5.1f}%")

# ============================================================================
# 2. CHAMPIONNATS
# ============================================================================
print("\n\n2️⃣  CHAMPIONNATS - Performance")
print("━" * 100)


def get_league_name(league_id):
    leagues = {
        61: "Ligue 1 (France)",
        62: "Ligue 2 (France)",
        39: "Premier League",
        40: "Championship",
        78: "Serie A",
        140: "La Liga",
        3: "Champions League",
        5: "Nations League",
    }
    return (
        leagues.get(int(league_id), f"Other {league_id}")
        if pd.notna(league_id)
        else "Unknown"
    )


df["league_name"] = df["league_id"].apply(get_league_name)

for league in df_valid["league_name"].unique():
    subset = df_valid[df_valid["league_name"] == league]
    total = len(subset)
    if total >= 5:  # Min 5 matchs
        success = subset["success"].astype(int).sum()
        rate = success / total * 100
        print(
            f"{league:30s} | Succès: {success:3d}/{total:3d} | Win Rate: {rate:5.1f}%"
        )

# ============================================================================
# 3. COMBOS vs SIMPLE
# ============================================================================
print("\n\n3️⃣  PARIS SIMPLES vs COMBINÉS")
print("━" * 100)

df["is_combo"] = (
    df["bet_selection"].notna() & df["bet_selection"].astype(str).str.strip() != ""
) & (df["total_pick"].notna() & df["total_pick"].astype(str).str.strip() != "")

simple = df_valid[~df_valid["is_combo"]]
combo = df_valid[df_valid["is_combo"]]

if len(simple) > 0:
    s_rate = simple["success"].astype(int).sum() / len(simple) * 100
    print(
        f"SIMPLES      | Total: {len(simple):3d} | Succès: {simple['success'].astype(int).sum():3d} | Win Rate: {s_rate:5.1f}%"
    )

if len(combo) > 0:
    c_rate = combo["success"].astype(int).sum() / len(combo) * 100
    print(
        f"COMBINÉS     | Total: {len(combo):3d} | Succès: {combo['success'].astype(int).sum():3d} | Win Rate: {c_rate:5.1f}%"
    )

    if len(simple) > 0:
        diff = c_rate - s_rate
        print(f"\nDifférence: {diff:+.1f}%")

# ============================================================================
# 4. CONFIANCE
# ============================================================================
print("\n\n4️⃣  CONFIANCE - Win Rate par niveau")
print("━" * 100)

df_valid["confidence_level"] = pd.cut(
    df_valid["main_confidence"],
    bins=[0, 50, 70, 85, 100],
    labels=["50-70%", "70-85%", "85-100%", "100%"],
)

for conf_level in ["50-70%", "70-85%", "85-100%", "100%"]:
    subset = df_valid[df_valid["confidence_level"] == conf_level]
    if len(subset) > 0:
        success = subset["success"].astype(int).sum()
        total = len(subset)
        rate = success / total * 100
        print(
            f"Confiance {conf_level:8s} | Total: {total:3d} | Succès: {success:3d} | Win Rate: {rate:5.1f}%"
        )

# ============================================================================
# 5. TOP PERFORMERS
# ============================================================================
print("\n\n" + "=" * 100)
print("🏆 TOP PERFORMERS")
print("=" * 100)

# Meilleur type
bet_stats = []
for bet_type in df_valid["bet_type"].unique():
    subset = df_valid[df_valid["bet_type"] == bet_type]
    if len(subset) >= 5:
        rate = subset["success"].astype(int).mean() * 100
        bet_stats.append((bet_type, rate, len(subset)))
bet_stats.sort(key=lambda x: x[1], reverse=True)

print(f"\n🎯 Meilleur type de pari:")
print(
    f"   {bet_stats[0][0]:20s} → {bet_stats[0][1]:.1f}% ({int(bet_stats[0][2])} matchs)"
)

# Meilleur championnat
league_stats = []
for league in df_valid["league_name"].unique():
    subset = df_valid[df_valid["league_name"] == league]
    if len(subset) >= 5:
        rate = subset["success"].astype(int).mean() * 100
        league_stats.append((league, rate, len(subset)))
league_stats.sort(key=lambda x: x[1], reverse=True)

print(f"\n🏟️  Meilleur championnat:")
print(
    f"   {league_stats[0][0]:30s} → {league_stats[0][1]:.1f}% ({int(league_stats[0][2])} matchs)"
)

# Simple vs Combo
if len(combo) > 0:
    s_rate = simple["success"].astype(int).mean() * 100 if len(simple) > 0 else 0
    c_rate = combo["success"].astype(int).mean() * 100
    winner = "SIMPLES" if s_rate >= c_rate else "COMBINÉS"
    print(f"\n📊 Simple vs Combo:")
    print(f"   Gagnant: {winner}")
    print(f"   Simple: {s_rate:.1f}% | Combo: {c_rate:.1f}%")

print("\n" + "=" * 100)
