# utils/test_api_runner.py

from utils.constants import DEFAULT_LEAGUE_ID, DEFAULT_SEASON, DEFAULT_TEAM_ID

from utils.api_calls import (

    get_fixtures,

    get_standings,

    get_players,

    get_statistics,

    get_topscorers,

    get_topassists,

    get_cards,

    get_odds,

    get_venues

)



LEAGUE_ID = 61   # Ligue 1 (France)

SEASON = 2025

TEAM_ID = 85     # PSG (modifiable)



def run_all_tests():

    results = {}



    try:

        results["fixtures"] = get_fixtures(LEAGUE_ID, SEASON)[:2]

    except Exception as e:

        results["fixtures"] = f"❌ Erreur: {e}"



    try:

        results["standings"] = get_standings(LEAGUE_ID, SEASON)[:2]

    except Exception as e:

        results["standings"] = f"❌ Erreur: {e}"



    try:

        results["players"] = get_players(LEAGUE_ID, SEASON, TEAM_ID)[:2]

    except Exception as e:

        results["players"] = f"❌ Erreur: {e}"



    try:

        results["statistics"] = get_statistics(LEAGUE_ID, SEASON, TEAM_ID)

    except Exception as e:

        results["statistics"] = f"❌ Erreur: {e}"



    try:

        results["topscorers"] = get_topscorers(LEAGUE_ID, SEASON)[:2]

    except Exception as e:

        results["topscorers"] = f"❌ Erreur: {e}"



    try:

        results["topassists"] = get_topassists(LEAGUE_ID, SEASON)[:2]

    except Exception as e:

        results["topassists"] = f"❌ Erreur: {e}"



    try:

        results["cards"] = get_cards(LEAGUE_ID, SEASON)[:2]

    except Exception as e:

        results["cards"] = f"❌ Erreur: {e}"



    try:

        results["odds"] = get_odds(LEAGUE_ID, SEASON)[:2]

    except Exception as e:

        results["odds"] = f"❌ Erreur: {e}"



    try:

        results["venues"] = get_venues()[:2]

    except Exception as e:

        results["venues"] = f"❌ Erreur: {e}"



    return results

