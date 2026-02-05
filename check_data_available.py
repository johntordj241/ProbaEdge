#!/usr/bin/env python3
"""Vérifier les données disponibles"""

import pandas as pd

df = pd.read_csv("data/prediction_dataset_enriched_v2.csv")
df["fixture_date"] = pd.to_datetime(df["fixture_date"], utc=True, errors="coerce")

print("\n" + "=" * 80)
print("VÉRIFICATION DES DONNÉES DISPONIBLES")
print("=" * 80)

# Vérifier les dates disponibles
print("\nPlage de dates dans les données:")
print(f'  Min: {df["fixture_date"].min()}')
print(f'  Max: {df["fixture_date"].max()}')

# Vérifier les ligues
print(f"\nCompositions de league_id:")
print(df["league_id"].value_counts().sort_index())

# Vérifier Europa (4)
europa = df[df["league_id"] == 4.0]
print(f"\nMatchs Europa disponibles: {len(europa)}")
if len(europa) > 0:
    dates = sorted(europa["fixture_date"].dt.date.unique())
    print(f"Dates Europa: {dates}")

# Pour LDC (3)
ldc = df[df["league_id"] == 3.0]
print(f"\nMatchs LDC disponibles: {len(ldc)}")
if len(ldc) > 0:
    dates = sorted(ldc["fixture_date"].dt.date.unique())
    print(f"Dates LDC: {dates}")

print("\n" + "=" * 80)
