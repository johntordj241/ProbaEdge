import pandas as pd
import numpy as np

df = pd.read_csv("data/prediction_history.csv")

# Voir combien de prédictions avec résultats
completed = df[
    (df["success_flag"].notna()) & (df["success_flag"].astype(str).str.lower() != "nan")
]
print(f"✅ Prédictions complètes: {len(completed)}")
print(f"📊 Total prédictions: {len(df)}")

if len(completed) > 0:
    success_rate = completed["success_flag"].astype(bool).sum() / len(completed) * 100
    print(f"🎯 Win rate: {success_rate:.1f}%")

    # ROI si tu as des mises
    bet_mask = (
        (completed["bet_return"].notna())
        & (completed["bet_stake"].notna())
        & (completed["bet_stake"] > 0)
    )
    if bet_mask.any():
        total_staked = completed.loc[bet_mask, "bet_stake"].sum()
        total_return = completed.loc[bet_mask, "bet_return"].sum()
        roi = (
            (total_return - total_staked) / total_staked * 100
            if total_staked > 0
            else 0
        )
        print(f"💰 Total misé: {total_staked:.2f}")
        print(f"💵 Retour: {total_return:.2f}")
        print(f"📈 ROI: {roi:.1f}%")
else:
    print("❌ Aucune prédiction complète avec résultat")
