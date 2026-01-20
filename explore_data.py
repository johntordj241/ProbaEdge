import pandas as pd
import warnings

warnings.filterwarnings("ignore")

# Charger les données
df = pd.read_csv("data/prediction_dataset_enriched_v2.csv")

print("=" * 80)
print("EXPLORATION DES DONNÉES")
print("=" * 80)

# Infos générales
print(f"\nTotal de lignes: {len(df)}")
print(f"Colonnes: {list(df.columns)}")

# Examiner la colonne fixture_date
print(f"\n--- FIXTURE_DATE ---")
print(f"Type: {df['fixture_date'].dtype}")
print(f"Premiers 5 éléments:")
print(df["fixture_date"].head())

# Convertir les dates
df["fixture_date"] = pd.to_datetime(df["fixture_date"], utc=True, errors="coerce")
df = df.dropna(subset=["fixture_date"])

# Plage de dates
print(f"\nDate min: {df['fixture_date'].min()}")
print(f"Date max: {df['fixture_date'].max()}")

# Dates uniques
df["date_str"] = df["fixture_date"].dt.strftime("%Y-%m-%d")
unique_dates = sorted(df["date_str"].unique())
print(f"\n--- DATES DISPONIBLES ---")
for d in unique_dates[-30:]:  # Dernières 30 dates
    count = len(df[df["date_str"] == d])
    print(f"{d}: {count} matchs")

# Chercher Barça
print(f"\n--- RECHERCHE BARCELONA ---")
barca_refs = df[
    (df["home_team"].str.contains("Barcelona", case=False, na=False))
    | (df["away_team"].str.contains("Barcelona", case=False, na=False))
].copy()

if len(barca_refs) > 0:
    print(f"Trouvé {len(barca_refs)} matches avec Barcelona")
    print("\nDerniers matchs Barcelona:")
    for idx, row in barca_refs.tail(10).iterrows():
        score = row["result_score"] if pd.notna(row["result_score"]) else "N/A"
        print(
            f"{row['date_str']} | {row['home_team']:25} vs {row['away_team']:25} | Score: {score}"
        )
else:
    print("❌ Aucun match Barça trouvé!")

    # Afficher tous les noms d'équipes uniques
    print(f"\nTous les noms d'équipes (premiers 50):")
    teams = set(df["home_team"].unique().tolist() + df["away_team"].unique().tolist())
    teams_with_bar = [t for t in teams if "bar" in t.lower()]
    print(f"\nÉquipes contenant 'bar': {teams_with_bar}")

    all_teams = sorted(list(teams))
    for i, team in enumerate(all_teams[:50]):
        print(f"{team}")
