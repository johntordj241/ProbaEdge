import pandas as pd
from datetime import datetime
from pathlib import Path

DATE = datetime.now().strftime("%Y-%m-%d")
history_file = Path("data/prediction_history.csv")
if not history_file.exists():
    print("❌ prediction_history.csv not found")
    exit(1)

df = pd.read_csv(history_file)
df["fixture_date"] = pd.to_datetime(df["fixture_date"], errors="coerce", utc=True)
df = df[df["fixture_date"].notnull()]
mask = df["fixture_date"].dt.strftime("%Y-%m-%d") == DATE
matches_today = df[mask]

for col in ["league_id", "league_name", "bet_odd"]:
    if col in matches_today.columns:
        print(f"\n--- {col} ---")
        print(matches_today[col].unique())
