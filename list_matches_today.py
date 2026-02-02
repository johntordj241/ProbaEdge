import pandas as pd
from datetime import datetime
from pathlib import Path

# Date du jour
DATE = datetime.now().strftime("%Y-%m-%d")

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

# Filtrer Ligue des Champions et FA Cup
ligue_champions_keywords = ["champions", "ldc", "uefa champions league"]
fa_cup_keywords = ["fa cup"]

# On cherche dans la colonne league_id, league_name ou bet_selection si dispo
league_cols = [
    col
    for col in ["league_id", "league_name", "bet_selection"]
    if col in matches_today.columns
]


def is_ligue_champions(row):
    for col in league_cols:
        val = str(row.get(col, "")).lower()
        if any(key in val for key in ligue_champions_keywords):
            return True
    return False


def is_fa_cup(row):
    for col in league_cols:
        val = str(row.get(col, "")).lower()
        if any(key in val for key in fa_cup_keywords):
            return True
    return False


filtered = matches_today[
    matches_today.apply(lambda row: is_ligue_champions(row) or is_fa_cup(row), axis=1)
]

if len(filtered) == 0:
    print(
        f"Aucun match de Ligue des Champions ou FA Cup trouvé pour aujourd'hui ({DATE})"
    )
    exit(0)

print(f"Matchs Ligue des Champions ou FA Cup du {DATE} :")
print(
    filtered[
        [
            "fixture_date",
            "home_team",
            "away_team",
            "main_pick",
            "bet_selection",
            "result_winner",
        ]
    ]
)
