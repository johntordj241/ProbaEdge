import json
import requests

from utils.config import BASE_URL, get_headers


def fetch_all_leagues():
    url = f"{BASE_URL}/leagues"
    response = requests.get(url, headers=get_headers())
    data = response.json()

    leagues = {}
    for item in data.get("response", []):
        league = item.get("league", {})
        country = item.get("country", {})
        name = f"{league.get('name')} ({country.get('name')})"
        if name:
            leagues[name] = league.get("id")
    return leagues


if __name__ == "__main__":
    leagues = fetch_all_leagues()
    with open("leagues.json", "w", encoding="utf-8") as handle:
        json.dump(leagues, handle, indent=4, ensure_ascii=False)
    print(f"{len(leagues)} compétitions enregistrées dans leagues.json")
