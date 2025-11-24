from utils.api_calls import get_standings
import json
league_id = 32
season = 2024
response = get_standings(league_id, season)
print(type(response), 'items' if isinstance(response, list) else '')
if isinstance(response, list) and response:
    league_block = response[0].get('league', {})
    print('name', league_block.get('name'), 'season', league_block.get('season'))
    standings = league_block.get('standings', [[]])[0]
    for row in standings[:4]:
        team = row.get('team', {}).get('name')
        stats_all = row.get('all', {})
        stats_home = row.get('home', {})
        stats_away = row.get('away', {})
        print(team, stats_all.get('played'), stats_all.get('win'), stats_home.get('win'), stats_away.get('win'))
