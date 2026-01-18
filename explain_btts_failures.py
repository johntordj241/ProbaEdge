#!/usr/bin/env python3
"""Analyse: Pourquoi BTTS peut échouer même si une équipe faible défensivement prend un but"""

import pandas as pd
import re

df = pd.read_csv("data/prediction_dataset_enriched.csv")
df_valid = df[df["success"].notna()].copy()

print("=" * 100)
print(
    "🔍 ANALYSE: BTTS vs BUTS MARQUÉS - Pourquoi l'algorithme dit 'Non' mais il y a des buts?"
)
print("=" * 100)


# Fonction pour extraire le score final
def get_final_score(result_score):
    """Extrait le score du résultat (ex: '2-1' -> (2,1))"""
    if pd.isna(result_score):
        return None, None
    s = str(result_score).strip()
    if "-" in s:
        try:
            parts = s.split("-")
            return int(parts[0]), int(parts[1])
        except:
            return None, None
    return None, None


# Fonction pour identifier BTTS
def has_btts(home_score, away_score):
    """Les deux équipes marquent? (home > 0 AND away > 0)"""
    if home_score is None or away_score is None:
        return None
    return (home_score > 0) and (away_score > 0)


def get_type(pick):
    p = str(pick).lower()
    if "btts" in p:
        return "BTTS"
    if "over" in p and "2.5" in p:
        return "Over 2.5"
    if "nul" in p or "x" in p:
        return "Nul"
    return "Autre"


df_valid["type"] = df_valid["main_pick"].apply(get_type)

# Extraire les scores
df_valid[["home_score", "away_score"]] = df_valid["result_score"].apply(
    lambda x: pd.Series(get_final_score(x))
)

# Calculer le BTTS réel
df_valid["actual_btts"] = df_valid.apply(
    lambda row: has_btts(row["home_score"], row["away_score"]), axis=1
)

# Calculer le total de buts
df_valid["total_goals"] = df_valid["home_score"] + df_valid["away_score"]

print("\n1️⃣ PARIS BTTS - SUCCÈS vs ÉCHEC")
print("-" * 100)

btts_paris = df_valid[df_valid["type"] == "BTTS"].copy()
print(f"\nTotal de paris BTTS: {len(btts_paris)}")
print(f"  - Prédiction correcte (réussi): {btts_paris['success'].astype(int).sum()}")
print(
    f"  - Prédiction incorrecte (échoué): {(1 - btts_paris['success']).astype(int).sum()}"
)

print("\n" + "=" * 100)
print("2️⃣ ANALYSE DES PARIS BTTS ÉCHOUÉS - Pourquoi ont-ils échoué?")
print("=" * 100)

btts_failed = btts_paris[btts_paris["success"] == 0].copy()
print(f"\nTotal de paris BTTS ÉCHOUÉS: {len(btts_failed)}")

# Catégoriser les échecs
btts_failed["failure_reason"] = btts_failed.apply(
    lambda row: (
        "Équipe A 0 but"
        if row["home_score"] == 0
        else ("Équipe B 0 but" if row["away_score"] == 0 else "Autre")
    ),
    axis=1,
)

print("\nRaisons des ÉCHECS BTTS:")
for reason, count in btts_failed["failure_reason"].value_counts().items():
    pct = count / len(btts_failed) * 100
    print(f"  - {reason:20s}: {count:3d} matchs ({pct:5.1f}%)")

print("\nDétails des matchs où 0 but marqué:")
no_goal_matches = btts_failed[
    (btts_failed["home_score"] == 0) | (btts_failed["away_score"] == 0)
]

print(f"  Équipe à domicile 0 but: {(no_goal_matches['home_score'] == 0).sum()} matchs")
print(
    f"  Équipe à l'extérieur 0 but: {(no_goal_matches['away_score'] == 0).sum()} matchs"
)

# Total de buts dans les matchs échoués
avg_goals_failed = btts_failed["total_goals"].mean()
print(f"  Moyenne de buts dans les BTTS échoués: {avg_goals_failed:.2f}")

print("\n" + "=" * 100)
print("3️⃣ COMPARAISON: BTTS RÉUSSI vs ÉCHOUÉ")
print("=" * 100)

btts_success = btts_paris[btts_paris["success"] == 1].copy()

print(f"\nBTTS RÉUSSI ({len(btts_success)} matchs):")
print(f"  - Moyenne de buts: {btts_success['total_goals'].mean():.2f}")
print(f"  - Distribution des buts:")
for goals in sorted(btts_success["total_goals"].dropna().unique()):
    count = (btts_success["total_goals"] == goals).sum()
    pct = count / len(btts_success) * 100
    print(f"    * {int(goals)} buts: {count:2d} matchs ({pct:5.1f}%)")

print(f"\nBTTS ÉCHOUÉ ({len(btts_failed)} matchs):")
print(f"  - Moyenne de buts: {avg_goals_failed:.2f}")
print(f"  - Distribution des buts:")
for goals in sorted(btts_failed["total_goals"].dropna().unique()):
    count = (btts_failed["total_goals"] == goals).sum()
    pct = count / len(btts_failed) * 100
    print(f"    * {int(goals)} buts: {count:2d} matchs ({pct:5.1f}%)")

print("\n" + "=" * 100)
print("4️⃣ CAS CLÉS - Pourquoi une équipe faible défensivement ne marque pas?")
print("=" * 100)

# Cas où 0-X ou X-0
one_side_scored = btts_failed[
    (btts_failed["home_score"] == 0) | (btts_failed["away_score"] == 0)
].copy()

print(f"\nMatchs où UNE SEULE équipe a marqué: {len(one_side_scored)}")
print("\nExemples:")

for idx, (_, row) in enumerate(one_side_scored.head(15).iterrows(), 1):
    score = f"{int(row['home_score'])}-{int(row['away_score'])}"
    league_id = int(row["league_id"])
    league_map = {61: "L1", 62: "L2", 39: "PL", 3: "CL", 140: "LL", 78: "BL"}
    league = league_map.get(league_id, f"L{league_id}")
    print(
        f"  {idx:2d}. {league} Score {score:3s} - Une défense a bien tenu malgré la faiblesse"
    )

print("\n" + "=" * 100)
print("5️⃣ INSIGHT - Pourquoi l'algorithme dit NON BTTS mais il y a des buts?")
print("=" * 100)

print(
    """
✅ LA DIFFÉRENCE CLÉE:

  "Un but marqué" ≠ "BTTS (Les 2 équipes marquent)"

EXEMPLE:
  ❌ BTTS ÉCHOUE: 2-0 (Un gol défensif marque 2x, l'autre équipe ne marque PAS)
  ✅ BTTS RÉUSSIT: 2-1 (Les 2 défenses sont pénétrées)

WHY L'ALGORITHME DIT "NON":
  
  1. L'équipe A est défensive → Va prendre des buts
  2. MAIS l'équipe B peut être TRÈS OFFENSIVE
  3. Si équipe B ne marque pas → BTTS échoue MÊME SI équipe A prend 3 buts
  
EXEMPLE RÉEL:
  - Petit club (très faible défense) vs Grand club (très bonne attaque)
  - Résultat possible: 0-4
  - Un 4 buts marqués, mais 0 pour la petite équipe
  - ❌ BTTS échoue car une équipe n'a pas marqué

LA VRAIE QUESTION:
  Pour BTTS, tu dois compter sur:
    ✅ La faiblesse défensive de l'équipe A (elle prend des buts)
    ✅ ET la capacité offensive de l'équipe B (elle marque)
    
  Si l'une des deux conditions manque → BTTS échoue
  
  L'algorithme dit NON BTTS quand:
    - L'une des équipes est trop défensive aussi
    - Ou trop mauvaise offensivement
"""
)

print("\n" + "=" * 100)
print("6️⃣ STATISTIQUES - Quand BTTS échoue avec plusieurs buts")
print("=" * 100)

# Cas où il y a 2+ buts mais BTTS échoue
multi_goals_failed = btts_failed[btts_failed["total_goals"] >= 2]
print(f"\nBTTS échoués avec 2+ buts au total: {len(multi_goals_failed)}")
print(f"  → Pourquoi? Parce que UNE SEULE équipe a marqué les buts")
print(f"\nExemples de scores 'déséquilibrés':")

score_distribution = []
for _, row in multi_goals_failed.iterrows():
    h = int(row["home_score"])
    a = int(row["away_score"])
    score_distribution.append((h, a))

from collections import Counter

scores = Counter(score_distribution)
for (h, a), count in sorted(scores.items(), key=lambda x: -x[1])[:10]:
    total = h + a
    print(
        f"  - {h}-{a} ({total} buts): {count:2d} matchs - Une équipe a marqué tout seule"
    )

print("\n" + "=" * 100)
print("🎯 RÉSUMÉ - POURQUOI BTTS ÉCHOUE")
print("=" * 100)

print(
    f"""
RAISONS D'ÉCHEC BTTS (sur {len(btts_failed)} échecs):

1. ❌ UNE ÉQUIPE NE MARQUE PAS (domicile 0): {(btts_failed['home_score'] == 0).sum()} cas
   → Même si l'autre attaque bien, pas de BTTS

2. ❌ UNE ÉQUIPE NE MARQUE PAS (extérieur 0): {(btts_failed['away_score'] == 0).sum()} cas
   → Même si l'autre attaque bien, pas de BTTS

3. 💡 L'ALGORITHME FAIT BON:
   → Il dit NON BTTS quand il prévoit que UNE des deux équipes ne marquera PAS
   → Pas parce qu'il n'y aura pas de buts
   → Mais parce qu'une équipe sera trop défensive offensivement
   
LEÇON:
  ✅ BTTS n'est pas "un match avec buts"
  ✅ BTTS = "CHAQUE équipe marque AU MOINS 1 but"
  
  Si tu vois: 3-0, 4-0, 5-1 → BTTS ÉCHOUE
  Parce qu'une équipe n'a pas marqué!
"""
)
