import pandas as pd
from datetime import datetime
from pathlib import Path

# Paramètres
DATE = datetime.now().strftime("%Y-%m-%d")
MIN_ODDS = 1.40
MAX_STAKE = round(338.78 * 0.03, 2)  # 3% du solde

history_file = Path("data/prediction_history.csv")
if not history_file.exists():
    print("❌ prediction_history.csv not found")
    exit(1)

df = pd.read_csv(history_file)
df["fixture_date"] = pd.to_datetime(df["fixture_date"], errors="coerce", utc=True)
df = df[df["fixture_date"].notnull()]

# Filtrer les matchs du jour
mask = df["fixture_date"].dt.strftime("%Y-%m-%d") == DATE
matches_today = df[mask]

# On suppose que la colonne 'main_confidence' existe et que plus c'est haut, plus la proba est forte
if "main_confidence" in matches_today.columns:
    matches_today = matches_today.sort_values("main_confidence", ascending=False)

# Filtrer les paris avec une cote >= 1.40
matches_today["bet_odd"] = pd.to_numeric(matches_today["bet_odd"], errors="coerce")
recommandes = matches_today[matches_today["bet_odd"] >= MIN_ODDS]

if len(recommandes) == 0:
    print(f"Aucun pari recommandé aujourd'hui avec une cote >= {MIN_ODDS}")
    exit(0)

print(f"--- PARIS SIMPLES RECOMMANDÉS ({DATE}) ---")
for idx, row in recommandes.iterrows():
    print(
        f"{row['fixture_date'].strftime('%H:%M')} | {row['home_team']} - {row['away_team']} | {row['main_pick']} | Cote: {row['bet_odd']} | Mise max: {MAX_STAKE} €"
    )

# Générer un combiné sur les 2 ou 3 meilleures cotes (si dispo)
print(f"\n--- COMBINÉS À TENTER ---")
for n in [2, 3]:
    if len(recommandes) >= n:
        combi = recommandes.head(n)
        cote_combi = combi["bet_odd"].prod()
        print(f"Combiné {n} matchs :")
        for _, row in combi.iterrows():
            print(
                f"  - {row['home_team']} - {row['away_team']} | {row['main_pick']} | Cote: {row['bet_odd']}"
            )
        print(f"  Cote totale : {cote_combi:.2f} | Mise max: {MAX_STAKE} €\n")
