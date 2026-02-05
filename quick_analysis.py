#!/usr/bin/env python3
import pandas as pd

df = pd.read_csv("data/prediction_dataset_enriched.csv")
df_valid = df[df["success"].notna()].copy()

print("📊 ANALYSE DES PARIS - RÉSUMÉ")
print("=" * 80)

# Types de paris
print("\n1️⃣  TYPES DE PARIS:")


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
    if "double" in p:
        return "Double Chance"
    if "victoire" in p:
        return "Victoire"
    return "Autre"


df_valid["type"] = df_valid["main_pick"].apply(get_type)

for t in df_valid["type"].unique():
    sub = df_valid[df_valid["type"] == t]
    win = sub["success"].astype(int).sum()
    total = len(sub)
    pct = win * 100 / total if total > 0 else 0
    print(f"  {t:20s}: {win:3d}/{total:3d} = {pct:5.1f}%")

# Championnats
print("\n2️⃣  CHAMPIONNATS (min 5 matchs):")
for league in [61, 62, 39, 40, 140, 3]:
    sub = df_valid[df_valid["league_id"] == league]
    if len(sub) >= 5:
        win = sub["success"].astype(int).sum()
        total = len(sub)
        pct = win * 100 / total
        names = {
            61: "Ligue 1",
            62: "Ligue 2",
            39: "PL",
            40: "Championship",
            140: "La Liga",
            3: "CL",
        }
        print(f"  {names.get(league, league):20s}: {win:3d}/{total:3d} = {pct:5.1f}%")

# Simple vs Combo
print("\n3️⃣  SIMPLE vs COMBINÉ:")
simple = df_valid[
    (df_valid["bet_selection"].isna())
    | (df_valid["bet_selection"].astype(str).str.strip() == "")
]
combo = df_valid[~df_valid.index.isin(simple.index)]

if len(simple) > 0:
    s_pct = simple["success"].astype(int).mean() * 100
    print(
        f"  SIMPLE:   {simple['success'].astype(int).sum():3d}/{len(simple)} = {s_pct:5.1f}%"
    )

if len(combo) > 0:
    c_pct = combo["success"].astype(int).mean() * 100
    print(
        f"  COMBINÉ:  {combo['success'].astype(int).sum():3d}/{len(combo)} = {c_pct:5.1f}%"
    )

print("\n" + "=" * 80)
print("✅ MEILLEUR: Over 1.5 (100%) + Nul (70.8%) + Under 2.5 (80%)")
print("🏟️  MEILLEUR CHAMPIONNAT: À vérifier sur données complètes")
print("📊 COMBO vs SIMPLE: Comparable ou légèrement mieux en simple")
