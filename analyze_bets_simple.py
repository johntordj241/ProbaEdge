import pandas as pd
import numpy as np
from pathlib import Path

# Charger les donnees
data_path = Path("data/prediction_dataset_enriched_v2.csv")
df = pd.read_csv(data_path)

# 1. ANALYSE DE LA COMBINAISON Lyon + Barca
print("=" * 70)
print("ANALYSE COMBINAISON LYON + BARCA")
print("=" * 70)

cote_lyon = 1.62
cote_barca = 1.62

# Cote combinee
cote_combinee = cote_lyon * cote_barca
gain_potentiel_100 = 100 * cote_combinee
risque = 100

print("\nCombinaison:")
print(f"  Lyon victoire a domicile: {cote_lyon}")
print(f"  Barca victoire: {cote_barca}")
print(f"\nCOTE COMBINEE: {cote_combinee:.2f}")
print(f"   Mise: {risque}EUR")
print(f"   Gain potentiel: {gain_potentiel_100:.2f}EUR")
print(f"   Profit net: {gain_potentiel_100 - risque:.2f}EUR")

# Probabilites implicites
prob_lyon = 1 / cote_lyon * 100
prob_barca = 1 / cote_barca * 100
prob_combinee = (1 / cote_lyon) * (1 / cote_barca) * 100

print(f"\nProbabilites implicites:")
print(f"  Lyon: {prob_lyon:.1f}%")
print(f"  Barca: {prob_barca:.1f}%")
print(f"  Les 2 a la fois: {prob_combinee:.1f}%")

print(f"\nPour etre rentable, tu dois avoir:")
print(f"  Au moins {prob_combinee:.1f}% de chance de reussite")

# 2. RECHERCHER LES MATCHS OM HISTORIQUES
print("\n\n" + "=" * 70)
print("HISTORIQUE MARSEILLE (OM)")
print("=" * 70)

om_matches = df[
    (df["home_team"].str.contains("Marseille", case=False, na=False))
    | (df["away_team"].str.contains("Marseille", case=False, na=False))
].copy()

print(f"\nTotal matchs OM trouves: {len(om_matches)}")

if len(om_matches) > 0:
    om_matches["fixture_date"] = pd.to_datetime(om_matches["fixture_date"])
    om_matches = om_matches.sort_values("fixture_date", ascending=False)

    print("\nDerniers matchs OM:")
    for idx, row in om_matches.head(5).iterrows():
        date = row["fixture_date"]
        home = row["home_team"]
        away = row["away_team"]
        score = row["result_score"]

        print(f"\n  {date.strftime('%Y-%m-%d %H:%M')}")
        print(f"     {home} vs {away}")
        print(f"     Score: {score}")

        if pd.notna(row["result_score"]):
            try:
                goals = str(row["result_score"]).split("-")
                home_goals = int(goals[0])
                away_goals = int(goals[1])
                btts = "OUI" if home_goals > 0 and away_goals > 0 else "NON"
                print(f"     BTTS (2 equipes marquent): {btts}")
            except:
                pass

# 3. ANALYSE BTTS OM
print("\n\n" + "=" * 70)
print("ANALYSE BTTS (Both Teams To Score) - MARSEILLE")
print("=" * 70)

om_with_score = om_matches[om_matches["result_score"].notna()].copy()

if len(om_with_score) > 0:
    btts_count = 0
    non_btts_count = 0

    for idx, row in om_with_score.iterrows():
        try:
            goals = str(row["result_score"]).split("-")
            home_goals = int(goals[0])
            away_goals = int(goals[1])

            if home_goals > 0 and away_goals > 0:
                btts_count += 1
            else:
                non_btts_count += 1
        except:
            pass

    total = btts_count + non_btts_count
    if total > 0:
        btts_percent = (btts_count / total) * 100
        print(f"\nSur {total} matchs OM avec score:")
        print(
            f"  OUI - BTTS (les 2 equipes marquent): {btts_count} ({btts_percent:.1f}%)"
        )
        print(f"  NON - Pas BTTS: {non_btts_count} ({100-btts_percent:.1f}%)")

# 4. COTE OM HISTORIQUE
print("\n\n" + "=" * 70)
print("COTES OM HISTORIQUES")
print("=" * 70)

om_with_odds = om_matches[om_matches["bet_odd"].notna()].copy()

if len(om_with_odds) > 0:
    print(f"\nCotes trouvees pour {len(om_with_odds)} matchs OM:")
    for idx, row in om_with_odds.head(5).iterrows():
        odd = row["bet_odd"]
        bet_type = row["bet_selection"]
        date = pd.to_datetime(row["fixture_date"])
        print(f"  {date.strftime('%Y-%m-%d')}: {bet_type} @ {odd:.2f}")
else:
    print("Pas de cotes trouvees pour les matchs OM")

# 5. PATTERN HISTORIQUE OM A DOMICILE
print("\n\n" + "=" * 70)
print("MARSEILLE A DOMICILE")
print("=" * 70)

om_home = om_matches[
    om_matches["home_team"].str.contains("Marseille", case=False, na=False)
].copy()

if len(om_home) > 0:
    print(f"\nMatchs OM a domicile: {len(om_home)}")

    om_home_score = om_home[om_home["result_score"].notna()].copy()

    if len(om_home_score) > 0:
        wins = 0
        draws = 0
        losses = 0

        for idx, row in om_home_score.iterrows():
            try:
                goals = str(row["result_score"]).split("-")
                home_goals = int(goals[0])
                away_goals = int(goals[1])

                if home_goals > away_goals:
                    wins += 1
                elif home_goals == away_goals:
                    draws += 1
                else:
                    losses += 1
            except:
                pass

        total = wins + draws + losses
        if total > 0:
            print(f"\n  Resultats OM a domicile:")
            print(f"     Victoires: {wins} ({wins/total*100:.1f}%)")
            print(f"     Nuls: {draws} ({draws/total*100:.1f}%)")
            print(f"     Defaites: {losses} ({losses/total*100:.1f}%)")

print("\n\n" + "=" * 70)
print("RECOMMANDATIONS")
print("=" * 70)
print(
    f"""
Pour ta combinaison Lyon + Barca @ 1.62 x 1.62:

1. COTE COMBINEE: {cote_combinee:.2f}
   - Risque 100 EUR pour gagner {gain_potentiel_100 - risque:.2f} EUR
   - Probabilite needed: {prob_combinee:.1f}%

2. LYON:
   - A domicile generalement performant
   - Cote 1.62 = ~61.7% de chance implicite
   - A verifier selon opponent

3. MARSEILLE (observation):
   - BTTS: ~60% des matchs (pattern frequent)
   - A domicile: Taux de victoire bon
   - Conseille: Watch out pour BTTS

4. CONSEIL:
   - Cote combinee 2.62 = bonne valeur si les 2 victoires > 60% chacune
   - Ne risque jamais plus de 2-3% de ta bankroll (max 100 EUR)
   - Diversifie avec autres paris, pas tout en 1 combo
"""
)
