import sys
import os

# Ajout du dossier parent pour que "utils" soit reconnu comme module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.data import league_mapping, seasons_available
from utils.api_calls import (
    get_fixtures,
    get_standings,
    get_statistics,
    get_players,
    get_cards,
    get_odds,
    get_venues,
    get_h2h,
)

def run_tests():
    season = seasons_available[-1]  # Dernière saison dispo
    league_name = "Ligue 1 (France)"  # Exemple
    league_id = league_mapping[league_name]

    print(f"=== 🔍 API Tests for {league_name} ({season}) ===")

    # Fixtures
    print("\n📅 Fixtures:")
    fixtures = get_fixtures(league_id, season)
    print(fixtures[:2] if fixtures else "❌ No fixtures")

    # Standings
    print("\n🏆 Standings:")
    standings = get_standings(league_id, season)
    print(standings[:2] if standings else "❌ No standings")

    # Statistics
    print("\n📊 Statistics:")
    stats = get_statistics(league_id, season)
    print(stats if stats else "❌ No statistics")

    # Players
    print("\n👥 Players:")
    players = get_players(league_id, season)
    print(players[:2] if players else "❌ No players")

    # Cards
    print("\n🟥🟨 Cards:")
    cards = get_cards(league_id, season)
    print(cards if cards else "❌ No cards")

    # Odds
    print("\n💰 Odds:")
    odds = get_odds(league_id, season)
    print(odds if odds else "❌ No odds")

    # Venues
    print("\n🏟️ Venues:")
    venues = get_venues(league_id)
    print(venues[:2] if venues else "❌ No venues")

    # H2H
    print("\n🔄 Head-to-Head:")
    h2h = get_h2h("Paris SG", "Lyon")
    print(h2h if h2h else "❌ No H2H data")


if __name__ == "__main__":
    run_tests()
