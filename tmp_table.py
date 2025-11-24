from utils.dashboard import _standings_table
from utils.api_calls import get_standings
standings_raw = get_standings(32, 2024) or []
standings = standings_raw[0]['league']['standings'][0]
df = _standings_table(standings)
print(df)
