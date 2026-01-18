import pandas as pd

df = pd.read_csv("data/prediction_history.csv")

print("=" * 80)
print("TOUTES LES COLONNES DISPONIBLES:")
print("=" * 80)
for i, col in enumerate(df.columns, 1):
    print(f"{i:2d}. {col}")

print("\n" + "=" * 80)
print("COLONNES AVEC 'SUCCESS' OU 'FLAG':")
print("=" * 80)
success_cols = [
    col for col in df.columns if "success" in col.lower() or "flag" in col.lower()
]
print(success_cols)

print("\n" + "=" * 80)
print("COLONNES AVEC 'RESULT' OU 'WINNER':")
print("=" * 80)
result_cols = [
    col for col in df.columns if "result" in col.lower() or "winner" in col.lower()
]
print(result_cols)

# Vérifier si une colonne success existe
if success_cols:
    print(f"\n✅ Colonne trouvée: {success_cols[0]}")
    col = success_cols[0]
    df_valid = df[df[col].notna()]
    print(f"Prédictions complètes: {len(df_valid)}")
    print(f"Valeurs uniques: {df_valid[col].unique()[:10]}")

    # Calculer le taux
    if df_valid[col].dtype == "bool" or set(df_valid[col].unique()) == {
        True,
        False,
        0,
        1,
    }:
        rate = df_valid[col].astype(bool).sum() / len(df_valid) * 100
        print(f"📊 Win rate: {rate:.1f}%")
else:
    print("❌ Pas de colonne 'success' trouvée")

# Afficher les premières lignes
print("\n" + "=" * 80)
print("EXEMPLES DE DONNÉES:")
print("=" * 80)
print(
    df[
        [
            "home_team",
            "away_team",
            "main_pick",
            "result_winner",
            "result_score",
            "bet_result",
        ]
    ].head(10)
)
