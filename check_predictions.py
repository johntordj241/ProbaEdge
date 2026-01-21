import pandas as pd

df = pd.read_csv("data/prediction_history.csv")

print("MAIN_PICK VALUE COUNTS:")
print(df["main_pick"].value_counts())
print("\n" + "=" * 80 + "\n")

print("BET_SELECTION VALUE COUNTS:")
print(df["bet_selection"].value_counts())
print("\n" + "=" * 80 + "\n")

print("Rows with 'over' or 'under':")
over_under = df[
    (df["main_pick"].astype(str).str.lower().str.contains("over|under", na=False))
    | (df["bet_selection"].astype(str).str.lower().str.contains("over|under", na=False))
]
print(f"Found {len(over_under)} Over/Under predictions")

print("\nColumn names:")
print(df.columns.tolist())
