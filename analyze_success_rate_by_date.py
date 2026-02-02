import pandas as pd
from pathlib import Path

# Paramètres
DATE = "2026-01-20"

history_file = Path("data/prediction_history.csv")
if not history_file.exists():
    print("❌ prediction_history.csv not found")
    exit(1)

df = pd.read_csv(history_file)

# Conversion robuste des dates
df["fixture_date"] = pd.to_datetime(df["fixture_date"], errors="coerce", utc=True)
# On garde uniquement les lignes où la date est valide
df = df[df["fixture_date"].notnull()]

# Filtrer la date
mask = df["fixture_date"].dt.strftime("%Y-%m-%d") == DATE
filtered = df[mask]

if len(filtered) == 0:
    print(f"Aucun pari trouvé pour la date {DATE}")
    exit(0)

# Taux de réussite
won = filtered[
    filtered["result_winner"]
    .astype(str)
    .str.lower()
    .isin(["yes", "win", "correct", "home", "away", "draw"])
]
total = len(filtered)
success_rate = len(won) / total * 100

print(f"Date : {DATE}")
print(f"Total paris : {total}")
print(f"Paris gagnés : {len(won)}")
print(f"Taux de réussite : {success_rate:.1f}%")

# Détail
print("\nDétail des paris :")
print(
    filtered[["fixture_date", "home_team", "away_team", "main_pick", "result_winner"]]
)
