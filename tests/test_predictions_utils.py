from types import SimpleNamespace

import utils.predictions as preds
from utils.bankroll import BankrollSettings


def _strength(name: str):
    return SimpleNamespace(
        name=name,
        lambda_value=1.2,
        attack=1.0,
        defense=1.0,
        elo_rating=1500.0,
        delta_elo=10.0,
        adjustments=[],
    )


def _context():
    return SimpleNamespace(
        weather="Sunny",
        referee="Ref",
        red_cards=["Player A"],
        injuries=["Player B"],
        fatigue_flags=[],
        adjustments_home=["Pression"],
        adjustments_away=[],
    )


def test_round_pct():
    assert preds._round_pct(0.1234) == 12.3
    assert preds._round_pct("0.5") == 50.0
    assert preds._round_pct(None) is None


def test_build_ai_match_payload_structure():
    fixture = {
        "fixture": {"date": "2025-11-23T15:00:00Z", "venue": {"name": "Stadium"}},
        "league": {"id": 61, "name": "Ligue 1", "season": 2025},
    }
    bank = BankrollSettings(
        amount=1000.0,
        strategy="percent",
        flat_stake=10.0,
        percent=2.0,
        kelly_fraction=0.5,
        default_odds=1.9,
        min_stake=5.0,
        max_stake=200.0,
    )
    payload = preds._build_ai_match_payload(
        fixture=fixture,
        fixture_id=123,
        league_id=61,
        season=2025,
        home_team={"name": "Home", "rank": 1},
        away_team={"name": "Away", "rank": 2},
        home_strength=_strength("Home"),
        away_strength=_strength("Away"),
        status={"label": "NS", "short": "NS", "elapsed": 0, "home_goals": 0, "away_goals": 0},
        projection_probs={"home": 0.55, "draw": 0.25, "away": 0.2},
        markets={"home": 0.55, "draw": 0.25, "away": 0.2},
        baseline_probs={"home": 0.5, "draw": 0.3, "away": 0.2},
        tips=[{"label": "Victoire Home", "probability": 0.55, "confidence": 80, "reason": "form"}],
        top_scores=[{"label": "2-1", "prob": 0.12}],
        intensity_snapshot={"score": 70, "label": "Haute", "comment": "match ouvert", "prob_over": 0.6, "prob_btts": 0.55, "total_xg": 2.8},
        pressure_metrics={"label": "Moderee", "score": 0.4, "shots_on_target_home": 3, "shots_on_target_away": 2},
        context=_context(),
        odds_map={"home": 1.9},
        bankroll_settings=bank,
    )
    assert payload["meta"]["fixture_id"] == 123
    assert payload["probabilities_pct"]["home"] == 55.0
    assert payload["teams"]["home"]["name"] == "Home"
    assert payload["bankroll"]["amount_eur"] == 1000.0


def test_note_ia_lines_outputs_disclaimer():
    bullets, disclaimer = preds._note_ia_lines(
        _strength("Home"),
        _strength("Away"),
        {"home": 0.6, "draw": 0.2, "away": 0.2},
        [{"label": "2-1", "prob": 0.1}],
        [{"label": "Victoire Home"}],
        {"label": "NS", "home_goals": 0, "away_goals": 0},
        _context(),
        {"ball_possession_home": 0.55, "ball_possession_away": 0.45},
        {"home": 0.5, "draw": 0.3, "away": 0.2},
    )
    assert bullets
    assert "Facteurs contextuels" in bullets[-1]
    assert "modeles statistiques" in disclaimer
