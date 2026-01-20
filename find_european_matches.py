import pandas as pd
import warnings

warnings.filterwarnings("ignore")

# Charger les données
df = pd.read_csv("data/prediction_dataset_enriched_v2.csv")

# Convertir les dates
df["fixture_date"] = pd.to_datetime(df["fixture_date"], utc=True, errors="coerce")
df = df.dropna(subset=["fixture_date"])
df["date_str"] = df["fixture_date"].dt.strftime("%Y-%m-%d")

# Filtrer LDC (3) et Europa (4) - Matchs futurs SEULEMENT
today = pd.Timestamp("2026-01-19", tz='UTC')
european = df[
    (df["league_id"].isin([3.0, 4.0])) &
    (df["fixture_date"] >= today)
].copy()

european = european.drop_duplicates(subset=["fixture_id"]).sort_values("fixture_date")

league_names = {3.0: "🏆 LDC", 4.0: "🎯 EUROPA"}

print("=" * 100)
print(f"MATCHS LDC & EUROPA À VENIR ({len(european)} matchs futurs)")
print("=" * 100)

if len(european) > 0:
    current_date = None
    for idx, row in european.iterrows():
        row_date = row["fixture_date"].strftime("%d/%m/%Y")
        
        # Afficher un séparateur de date si elle change
        if row_date != current_date:
            if current_date is not None:
                print()
            print(f"\n📅 {row_date}")
            print("-" * 100)
            current_date = row_date
        
        league_name = league_names.get(row["league_id"], "?")
        time = row["fixture_date"].strftime("%H:%M")

        print(
            f"{league_name} | {time:5} | {row['home_team']:20} vs {row['away_team']:20}"
        )
        print(
            f"       → Home {row['prob_home']*100:.0f}% | Draw {row['prob_draw']*100:.0f}% | Away {row['prob_away']*100:.0f}%"
        )
        print(
            f"       → Over 2.5: {row['prob_over_2_5']*100:.0f}% | Main pick: {row['main_pick']}"
        )
else:
    print("\n❌ Aucun match LDC/Europa à venir trouvé.")
    print("\n📊 ANALYSE DISPONIBILITÉ DONNÉES:")
    unique_dates = sorted(df["date_str"].unique())
    print(f"Plage des données: {unique_dates[0]} → {unique_dates[-1]}")
    ldc_europa = df[df["league_id"].isin([3.0, 4.0])]["date_str"].unique()
    print(f"Matchs LDC/Europa disponibles aux dates: {sorted(ldc_europa)}")
        print(f"  {d}: {count} matchs")
