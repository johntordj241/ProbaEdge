import pandas as pd

df = pd.read_csv("data/prediction_history.csv")

# Prédictions finalisées
finalized = df[df["result_winner"].notna()].copy()
print(f"📊 Total prédictions finalisées: {len(finalized)}")

# Vérifier les colonnes pour calculer le succès
print("\nAnalyse des picks principaux:")
print(finalized["main_pick"].value_counts().head(10))


# Essai simple: vérifier si home/away/draw match avec le résultat
def check_prediction_success(row):
    main_pick = str(row["main_pick"]).lower()
    result = str(row["result_winner"]).lower()

    # Cas simple : victoire domicile
    if "victoire" in main_pick and "home" in main_pick and result == "home":
        return True
    if (
        "victoire" in main_pick
        and any(x in main_pick for x in ["marseille", "paris", "lyon"])
        and result == "home"
    ):
        return True
    # Cas simple : défaite
    if "nul" in main_pick and result == "draw":
        return True
    if any(x in main_pick for x in ["x2", "extra"]) and result == "away":
        return True

    return None


finalized["simple_success"] = finalized.apply(check_prediction_success, axis=1)

success = finalized[finalized["simple_success"] == True]
print(f"\n✅ Prédictions réussies (détection simple): {len(success)}")
print(f"📈 Win rate (sample): {len(success) / len(finalized) * 100:.1f}%")

# Avec mises
with_bets = finalized[finalized["bet_result"].notna()]
print(f"\n💰 Prédictions avec mise: {len(with_bets)}")
if len(with_bets) > 0:
    wins = with_bets[with_bets["bet_result"].astype(str).str.lower() == "win"]
    print(f"🎯 Wins avec mise: {len(wins)}")
    print(f"ROI bet: {len(wins) / len(with_bets) * 100:.1f}%")
