import pandas as pd

df = pd.read_csv("data/prediction_history.csv")

# Chercher les colonnes avec 'success'
print(
    "Colonnes contenant 'success':", [c for c in df.columns if "success" in c.lower()]
)

# Essayer de la charger différemment
print("\nNom des colonnes exact:")
print(df.columns.tolist())

# Vérifier s'il y a une colonne non visible
print(f"\nTotal colonnes: {len(df.columns)}")

# Chercher manuellement
if "success" in df.columns:
    print("\n✅ Colonne 'success' trouvée!")
    completed = df[df["success"].notna()]
    print(f"Prédictions avec success: {len(completed)}")
    print(f"Win rate: {completed['success'].mean() * 100:.1f}%")
else:
    print("\n❌ Colonne 'success' NOT found")
    print("\nColonnes possibles de succès:")
    print(
        [
            c
            for c in df.columns
            if any(x in c.lower() for x in ["success", "win", "flag", "correct"])
        ]
    )
