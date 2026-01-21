import pandas as pd
from pathlib import Path

history_file = Path("data/prediction_history.csv")
if not history_file.exists():
    print("❌ prediction_history.csv not found")
    exit(1)

df = pd.read_csv(history_file)

print("--- main_pick (20 premiers) ---")
print(df["main_pick"].dropna().unique()[:20])
print("\n--- bet_selection (20 premiers) ---")
print(df["bet_selection"].dropna().unique()[:20])

print("\n--- Extraits contenant 'buteur', 'topscorer', 'scorer' ---")
mask = df["main_pick"].astype(str).str.lower().str.contains(
    "buteur|topscorer|scorer", na=False
) | df["bet_selection"].astype(str).str.lower().str.contains(
    "buteur|topscorer|scorer", na=False
)
print(df[mask][["main_pick", "bet_selection"]].head(10))
