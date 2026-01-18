#!/usr/bin/env python3
"""Analyse détaillée des paris: types, championnats, combinaisons"""

import pandas as pd
import numpy as np

df = pd.read_csv("data/prediction_dataset_enriched.csv")

print("=" * 100)
print("📊 ANALYSE DÉTAILLÉE DES PARIS & CHAMPIONNATS")
print("=" * 100)

# ============================================================================
# 1. TYPE DE PARIS
# ============================================================================
print("\n1️⃣  TYPES DE PARIS")
print("━" * 100)


# Parser les types de paris
def get_bet_type(main_pick):
    pick = str(main_pick).lower()
    if (
        "victoire" in pick
        or "domicile" in pick
        or "exterieur" in pick
        or any(x in pick for x in ["marseille", "paris", "lyon", "nice", "lens"])
    ):
        return "Victoire"
    if "nul" in pick or "x" in pick or "draw" in pick:
        return "Nul"
    if "over" in pick and "2.5" in pick:
        return "Over 2.5"
    if "under" in pick and "2.5" in pick:
        return "Under 2.5"
    if "over" in pick and "1.5" in pick:
        return "Over 1.5"
    if "under" in pick and "1.5" in pick:
        return "Under 1.5"
    if "btts" in pick or "deux équipes" in pick:
        return "BTTS"
    if "double" in pick and "1x" in pick:
        return "Double Chance 1X"
    if "double" in pick and "x2" in pick:
        return "Double Chance X2"
    if "double" in pick and "12" in pick:
        return "Double Chance 12"
    return "Autre"


df["bet_type"] = df["main_pick"].apply(get_bet_type)

# Analyser par type
bet_analysis = (
    df[df["success"].notna()]
    .groupby("bet_type")
    .agg({"success": ["sum", "count", "mean"]})
)

bet_analysis.columns = ["Succès", "Total", "Win Rate"]
bet_analysis["Succès"] = bet_analysis["Succès"].astype(int)
bet_analysis["Total"] = bet_analysis["Total"].astype(int)
bet_analysis["Win Rate %"] = (bet_analysis["Win Rate"] * 100).round(1)
bet_analysis = bet_analysis[["Succès", "Total", "Win Rate %"]]
bet_analysis = bet_analysis.sort_values("Win Rate %", ascending=False)

print(bet_analysis.to_string())
print(
    f"\n🏆 Meilleur type de pari: {bet_analysis.index[0]} ({bet_analysis.iloc[0]['Win Rate %']:.1f}%)"
)
print(
    f"❌ Pire type de pari: {bet_analysis.index[-1]} ({bet_analysis.iloc[-1]['Win Rate %']:.1f}%)"
)

# ============================================================================
# 2. CHAMPIONNATS
# ============================================================================
print("\n\n2️⃣  CHAMPIONNATS / LIGUES")
print("━" * 100)


def get_league_name(league_id):
    leagues = {
        61: "Ligue 1 (France)",
        62: "Ligue 2 (France)",
        39: "Premier League (Angleterre)",
        40: "Championship (Angleterre)",
        78: "Série A (Italie)",
        135: "Serie B (Italie)",
        140: "La Liga (Espagne)",
        141: "Segunda División (Espagne)",
        203: "Super Lig (Portugal)",
        3: "UEFA Champions League",
        5: "UEFA Nations League",
        32: "International Friendlies",
    }
    return (
        leagues.get(int(league_id), f"League {league_id}")
        if pd.notna(league_id)
        else "Unknown"
    )


df["league_name"] = df["league_id"].apply(get_league_name)

league_analysis = (
    df[df["success"].notna()]
    .groupby("league_name")
    .agg({"success": ["sum", "count", "mean"]})
    .round(3)
)

league_analysis.columns = ["Succès", "Total", "Win Rate %"]
league_analysis["Win Rate %"] = (league_analysis["Win Rate %"] * 100).round(1)
league_analysis = league_analysis[league_analysis["Total"] >= 5]  # Min 5 matchs
league_analysis = league_analysis.sort_values("Win Rate %", ascending=False)

print(league_analysis.to_string())
print(
    f"\n🏆 Meilleur championnat: {league_analysis.index[0]} ({league_analysis.iloc[0]['Win Rate %']:.1f}% sur {int(league_analysis.iloc[0]['Total'])} matchs)"
)
print(
    f"❌ Pire championnat: {league_analysis.index[-1]} ({league_analysis.iloc[-1]['Win Rate %']:.1f}%)"
)

# ============================================================================
# 3. PARIS COMBINÉS
# ============================================================================
print("\n\n3️⃣  PARIS COMBINÉS (Combos)")
print("━" * 100)

# Détecter les combos (si bet_selection ET total_pick sont remplis différemment)
df["is_combo"] = (
    df["bet_selection"].notna() & df["bet_selection"].astype(str).str.strip() != ""
) & (df["total_pick"].notna() & df["total_pick"].astype(str).str.strip() != "")

combo_data = df[df["success"].notna()]

combo_simple = combo_data[~combo_data["is_combo"]]
combo_double = combo_data[combo_data["is_combo"]]

print(f"\nParis SIMPLES:")
print(f"  Total: {len(combo_simple)}")
print(f"  Succès: {combo_simple['success'].sum()}")
print(f"  Win Rate: {combo_simple['success'].mean() * 100:.1f}%")

if len(combo_double) > 0:
    print(f"\nParis COMBINÉS:")
    print(f"  Total: {len(combo_double)}")
    print(f"  Succès: {combo_double['success'].sum()}")
    print(f"  Win Rate: {combo_double['success'].mean() * 100:.1f}%")

    print(f"\n📊 Comparaison:")
    print(f"  Simple: {combo_simple['success'].mean() * 100:.1f}%")
    print(f"  Combo:  {combo_double['success'].mean() * 100:.1f}%")
    print(
        f"  Différence: {(combo_double['success'].mean() - combo_simple['success'].mean()) * 100:+.1f}%"
    )
else:
    print(f"\nPas assez de paris combinés pour l'analyse")

# ============================================================================
# 4. CONFIANCE vs RÉSULTAT
# ============================================================================
print("\n\n4️⃣  CONFIANCE (main_confidence) vs RÉSULTAT")
print("━" * 100)

df_conf = df[df["success"].notna()].copy()
df_conf["confidence_bin"] = pd.cut(
    df_conf["main_confidence"],
    bins=[0, 50, 70, 85, 100],
    labels=["50-70%", "70-85%", "85-100%", "100%"],
)

confidence_analysis = (
    df_conf.groupby("confidence_bin", observed=True)
    .agg({"success": ["sum", "count", "mean"]})
    .round(3)
)

confidence_analysis.columns = ["Succès", "Total", "Win Rate %"]
confidence_analysis["Win Rate %"] = (confidence_analysis["Win Rate %"] * 100).round(1)

print(confidence_analysis.to_string())

# ============================================================================
# 5. RÉSUMÉ FINAL
# ============================================================================
print("\n\n" + "=" * 100)
print("📋 RÉSUMÉ DES FINDINGS")
print("=" * 100)

print(
    f"""
🎯 TOP PARIS
  • Type meilleur: {bet_analysis.index[0]} → {bet_analysis.iloc[0]['Win Rate %']:.1f}%
  • Championnat meilleur: {league_analysis.index[0]} → {league_analysis.iloc[0]['Win Rate %']:.1f}%
  
📊 COMPARAISON SIMPLE vs COMBO
  • Simple: {combo_simple['success'].mean() * 100:.1f}%
  • Combo: {combo_double['success'].mean() * 100 if len(combo_double) > 0 else 'N/A'}%
  
🔥 CONFIANCE
  • Meilleure confiance bin: 100% ({df_conf[df_conf['confidence_bin'] == '100%']['success'].mean() * 100:.1f}%)
  
💡 RECOMMENDATION
  Favorise: {bet_analysis.index[0]} en {league_analysis.index[0]} ✅
"""
)
