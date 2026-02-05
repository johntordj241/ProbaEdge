from utils.api_calls import get_leagues
leagues = get_leagues()
for league in leagues:
    if league.get('league', {}).get('id') == 32:
        seasons = league.get('seasons', [])
        for entry in seasons[:5]:
            print(entry.get('year'), entry.get('current'))
