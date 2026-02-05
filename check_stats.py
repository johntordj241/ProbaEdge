import pandas as pd

df = pd.read_csv("data/prediction_history.csv")
print("Colonnes:", df.columns.tolist()[:15])
print(f"Total: {len(df)}")

finalized = df[df["result_winner"].notna()]
print(f"Finalisées: {len(finalized)}")

if len(finalized) > 0:
    print(
        finalized[
            ["home_team", "away_team", "main_pick", "result_winner", "bet_result"]
        ].head(5)
    )
