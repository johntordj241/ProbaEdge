#!/usr/bin/env python3
"""Enrichit le dataset avec les Elo ratings et buts attendus (lambda)"""

import pandas as pd
import numpy as np
from pathlib import Path

df = pd.read_csv("data/prediction_dataset_enriched.csv")

print("=" * 80)
print("ENRICHISSEMENT DU DATASET")
print("=" * 80)

# ============================================================================
# 1. CALCULER LES RATINGS ELO
# ============================================================================
print("\n1️⃣  Calcul des ratings Elo...")


def calculate_elo(df):
    """Calcule les ratings Elo pour chaque équipe basé sur l'historique"""

    # Initialiser les ratings Elo
    elo_dict = {}
    default_elo = 1500.0

    # Trier par date pour traiter chronologiquement
    df_sorted = df.sort_values("fixture_date", na_position="last").copy()

    # Initialiser toutes les équipes
    for team in pd.concat([df_sorted["home_team"], df_sorted["away_team"]]).unique():
        if pd.notna(team):
            elo_dict[team] = default_elo

    # Parcourir les matchs chronologiquement
    elo_history = []

    for idx, row in df_sorted.iterrows():
        home = row["home_team"]
        away = row["away_team"]

        if pd.isna(home) or pd.isna(away):
            elo_history.append((np.nan, np.nan))
            continue

        # Elo avant le match
        elo_h_before = elo_dict.get(home, default_elo)
        elo_a_before = elo_dict.get(away, default_elo)

        elo_history.append((elo_h_before, elo_a_before))

        # Si résultat disponible, mettre à jour les Elo
        if pd.notna(row["result_winner"]):
            result = str(row["result_winner"]).lower()
            K = 32  # Facteur K pour la variation

            # Calcul des probabilités attendues
            elo_diff = elo_h_before - elo_a_before
            expected_h = 1 / (1 + 10 ** (-elo_diff / 400))
            expected_a = 1 - expected_h

            # Déterminer le résultat
            if result == "home":
                actual_h, actual_a = 1, 0
            elif result == "away":
                actual_h, actual_a = 0, 1
            elif result == "draw":
                actual_h, actual_a = 0.5, 0.5
            else:
                continue

            # Mettre à jour les Elo
            elo_dict[home] = elo_h_before + K * (actual_h - expected_h)
            elo_dict[away] = elo_a_before + K * (actual_a - expected_a)

    return elo_history, elo_dict


elo_history, final_elo = calculate_elo(df)
df["elo_home"] = [x[0] if x else np.nan for x in elo_history]
df["elo_away"] = [x[1] if x else np.nan for x in elo_history]

print(f"✅ Elo ratings calculés")
print(f"   Exemples Elo finaux: {list(final_elo.items())[:3]}")

# ============================================================================
# 2. CALCULER LES BUTS ATTENDUS (LAMBDA POISSON)
# ============================================================================
print("\n2️⃣  Calcul des buts attendus (lambda Poisson)...")


def estimate_lambda(df):
    """Estime les buts attendus (lambda) basé sur l'historique"""

    lambda_home_dict = {}
    lambda_away_dict = {}

    # Créer des statistiques par équipe
    df_completed = df[df["result_score"].notna()].copy()

    # Parser les scores
    def parse_score(score_str):
        try:
            parts = str(score_str).split("-")
            if len(parts) == 2:
                return int(parts[0]), int(parts[1])
        except:
            pass
        return None, None

    df_completed[["home_goals", "away_goals"]] = df_completed["result_score"].apply(
        lambda x: pd.Series(parse_score(x))
    )

    # Calculer les moyennes par équipe
    home_matches = (
        df_completed[df_completed["home_team"].notna()]
        .groupby("home_team")["home_goals"]
        .agg(["sum", "count"])
    )
    away_matches = (
        df_completed[df_completed["away_team"].notna()]
        .groupby("away_team")["away_goals"]
        .agg(["sum", "count"])
    )

    for team in home_matches.index:
        if home_matches.loc[team, "count"] > 0:
            lambda_home_dict[team] = (
                home_matches.loc[team, "sum"] / home_matches.loc[team, "count"]
            )
        else:
            lambda_home_dict[team] = 1.5

    for team in away_matches.index:
        if away_matches.loc[team, "count"] > 0:
            lambda_away_dict[team] = (
                away_matches.loc[team, "sum"] / away_matches.loc[team, "count"]
            )
        else:
            lambda_away_dict[team] = 1.0

    # Appliquer aux matchs
    lambda_home = []
    lambda_away = []

    for idx, row in df.iterrows():
        h = row["home_team"]
        a = row["away_team"]

        h_lambda = lambda_home_dict.get(h, 1.5) if pd.notna(h) else np.nan
        a_lambda = lambda_away_dict.get(a, 1.0) if pd.notna(a) else np.nan

        lambda_home.append(h_lambda)
        lambda_away.append(a_lambda)

    return lambda_home, lambda_away


df["feature_lambda_home"], df["feature_lambda_away"] = estimate_lambda(df)

print(f"✅ Lambda calculés")
print(f"   Domicile moyen: {df['feature_lambda_home'].mean():.2f}")
print(f"   Extérieur moyen: {df['feature_lambda_away'].mean():.2f}")

# ============================================================================
# 3. CALCULER DELTA_ELO
# ============================================================================
print("\n3️⃣  Calcul de delta_elo...")
df["delta_elo"] = df["elo_home"] - df["elo_away"]
print(f"✅ Delta Elo calculé")

# ============================================================================
# 4. SAUVEGARDER
# ============================================================================
print("\n4️⃣  Sauvegarde...")
df.to_csv("data/prediction_dataset_enriched_v2.csv", index=False)
print(f"✅ Sauvegardé: data/prediction_dataset_enriched_v2.csv")

# Vérifier
print("\n" + "=" * 80)
print("VÉRIFICATION")
print("=" * 80)
print(f"elo_home rempli:          {df['elo_home'].notna().sum()}/{len(df)}")
print(f"elo_away rempli:          {df['elo_away'].notna().sum()}/{len(df)}")
print(f"delta_elo rempli:         {df['delta_elo'].notna().sum()}/{len(df)}")
print(
    f"feature_lambda_home rempli: {df['feature_lambda_home'].notna().sum()}/{len(df)}"
)
print(
    f"feature_lambda_away rempli: {df['feature_lambda_away'].notna().sum()}/{len(df)}"
)

# Stats
print("\nStatistiques:")
print(f"Elo home: {df['elo_home'].describe()}")
print(f"Lambda home: {df['feature_lambda_home'].describe()}")
