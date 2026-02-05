from typing import Any, Dict, Iterable, Optional

try:
    import streamlit as st
except ImportError:  # pragma: no cover
    st = None

from utils.api_calls import (
    get_cards,
    get_fixtures,
    get_fixture_details,
    get_fixture_events,
    get_fixture_statistics,
    get_h2h,
    get_injuries,
    get_leagues,
    get_odds,
    get_odds_by_fixture,
    get_players,
    get_statistics,
    get_standings,
    get_teams,
    get_topassists,
    get_topscorers,
    get_venues,
)
from utils.constants import DEFAULT_LEAGUE_ID, DEFAULT_SEASON, DEFAULT_TEAM_ID


LEAGUE_ID = DEFAULT_LEAGUE_ID  # Ligue 1 France
SEASON = DEFAULT_SEASON
TEAM_ID = DEFAULT_TEAM_ID  # PSG


def _preview(data: Any, limit: int = 2) -> Any:
    if isinstance(data, list):
        return data[:limit]
    return data


def print_result(title: str, data: Any) -> None:
    if not data:
        message = f"[WARN] {title} : aucun resultat"
        if st:
            st.warning(message)
        print(message)
    else:
        message = f"[OK] {title} : {_preview(data)}"
        if st:
            st.success(message)
        print(message)


def _first_fixture(fixtures: Optional[Iterable[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    if not fixtures:
        return None
    for entry in fixtures:
        if not isinstance(entry, dict):
            continue
        fixture_block = entry.get("fixture") or {}
        if fixture_block.get("id"):
            return entry
    return None


def _fixture_with_odds(league_id: int, season: int) -> Optional[int]:
    odds_payload = get_odds(league_id, season) or []
    for entry in odds_payload:
        try:
            fixture_id = entry.get("fixture", {}).get("id")
        except AttributeError:
            fixture_id = None
        bookmakers = entry.get("bookmakers") or []
        if fixture_id and bookmakers:
            return int(fixture_id)
    return None


def run_all_tests() -> None:
    print("\n===== TEST API FOOTBALL =====")
    if st:
        st.write("===== TEST API FOOTBALL =====")

    fixtures = get_fixtures(LEAGUE_ID, SEASON, next_n=10)
    print_result("Fixtures (next 10)", fixtures)

    sample_fixture = _first_fixture(fixtures)
    fixture_id = int(sample_fixture.get("fixture", {}).get("id")) if sample_fixture else None

    print_result("Standings", get_standings(LEAGUE_ID, SEASON))
    print_result("Teams", get_teams(LEAGUE_ID, SEASON))
    print_result("Standings", get_standings(LEAGUE_ID, SEASON))
    print_result("Players", get_players(LEAGUE_ID, SEASON, TEAM_ID))
    print_result("Statistics", get_statistics(LEAGUE_ID, SEASON, TEAM_ID))
    print_result("Top scorers", get_topscorers(LEAGUE_ID, SEASON))
    print_result("Top assists", get_topassists(LEAGUE_ID, SEASON))
    print_result("Cards", get_cards(LEAGUE_ID, SEASON))
    print_result("Odds", get_odds(LEAGUE_ID, SEASON))
    print_result("Venues", get_venues())
    print_result("Leagues (France)", get_leagues(country="France", season=SEASON))
    print_result("Injuries", get_injuries(LEAGUE_ID, SEASON, TEAM_ID))

    if fixture_id:
        print_result("Fixture details", get_fixture_details(fixture_id))
        print_result("Fixture statistics", get_fixture_statistics(fixture_id))
        print_result("Fixture events", get_fixture_events(fixture_id))

    fixture_with_odds = _fixture_with_odds(LEAGUE_ID, SEASON)
    if fixture_with_odds:
        print_result("Odds (fixture)", get_odds_by_fixture(fixture_with_odds))

    print_result("H2H PSG vs Lyon", get_h2h("Paris SG", "Lyon"))

    print("\n===== FIN DES TESTS =====\n")
    if st:
        st.write("===== FIN DES TESTS =====")


if __name__ == "__main__":
    run_all_tests()

