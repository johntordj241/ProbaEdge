import utils.api_calls as api
import utils.players as players


def _base_player(player_id: int, name: str) -> dict:
    return {
        "player": {"id": player_id, "name": name},
        "statistics": [
            {
                "team": {"id": 123, "name": "Test FC"},
                "games": {"appearences": 1, "minutes": 90},
                "goals": {"total": 0},
            }
        ],
    }


def test_lineup_roster_collects_players_from_lineups(monkeypatch):
    base_players = [_base_player(10, "Existing Striker")]

    def fake_get_players(league, season, team_id, page=1):
        return base_players if page == 1 else []

    def fake_get_fixtures(*args, **kwargs):
        return [{"fixture": {"id": 999}}]

    def fake_get_lineups(fixture_id):
        return [
            {
                "team": {"id": 123, "name": "Test FC"},
                "startXI": [{"player": {"id": 77, "name": "Academy Star", "number": 19, "pos": "F"}}],
                "substitutes": [],
            }
        ]

    monkeypatch.setattr(api, "get_fixtures", fake_get_fixtures)
    monkeypatch.setattr(api, "get_lineups", fake_get_lineups)

    roster = api._lineup_roster_for_team(61, 2025, 123)

    assert any(entry["player"]["name"] == "Academy Star" for entry in roster)


def test_get_players_for_team_merges_lineup_players(monkeypatch):
    base_players = [_base_player(10, "Existing Striker")]

    def fake_get_players(league, season, team_id, page=1):
        return base_players if page == 1 else []

    def fake_lineup_roster(league, season, team_id, lookback=3):
        return [_base_player(77, "Academy Star")]

    monkeypatch.setattr(api, "get_players", fake_get_players)
    monkeypatch.setattr(api, "_lineup_roster_for_team", fake_lineup_roster)

    roster = api.get_players_for_team(61, 2025, 123, max_pages=1)

    assert any(entry["player"]["name"] == "Academy Star" for entry in roster)


def test_get_players_for_team_deduplicates_lineup(monkeypatch):
    base_players = [_base_player(99, "Captain Reliable")]

    def fake_get_players(league, season, team_id, page=1):
        return base_players if page == 1 else []

    monkeypatch.setattr(api, "get_players", fake_get_players)
    monkeypatch.setattr(api, "_lineup_roster_for_team", lambda *args, **kwargs: [_base_player(99, "Captain Reliable")])

    roster = api.get_players_for_team(61, 2025, 123, max_pages=1)

    names = [entry["player"]["name"] for entry in roster]
    assert names.count("Captain Reliable") == 1


def _override_entry(player_id: int, name: str) -> dict:
    return {
        "player": {"id": player_id, "name": name},
        "statistics": [
            {
                "team": {"id": 456, "name": "Future FC"},
                "games": {"position": "M", "number": 30},
                "goals": {"total": 0},
            }
        ],
    }


def test_get_players_enriched_merges_squad_payload(monkeypatch):
    base_players = [_base_player(10, "Existing Striker")]

    monkeypatch.setattr(players, "api_get_players_for_team", lambda *args, **kwargs: base_players)
    monkeypatch.setattr(
        players,
        "get_team_squad",
        lambda team_id: [
            {
                "team": {"id": team_id, "name": "Future FC"},
                "players": [{"id": 88, "name": "Squad Prospect", "number": 40, "position": "M"}],
            }
        ],
    )
    monkeypatch.setattr(players, "get_override_roster", lambda team_id, season: [])

    roster = players.get_players_enriched(61, 2025, 456)
    names = [player.name for player in roster]

    assert "Existing Striker" in names
    assert "Squad Prospect" in names


def test_get_players_enriched_uses_overrides(monkeypatch):
    monkeypatch.setattr(players, "api_get_players_for_team", lambda *args, **kwargs: [])
    monkeypatch.setattr(players, "get_team_squad", lambda team_id: [])
    monkeypatch.setattr(players, "get_override_roster", lambda team_id, season: [_override_entry(501, "Academy Kid")])

    roster = players.get_players_enriched(61, 2025, 456)
    assert any(player.name == "Academy Kid" for player in roster)
