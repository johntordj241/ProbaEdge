from __future__ import annotations

import pandas as pd
import pytest

from utils import chat_assistant as ca
from utils.bankroll import BankrollSettings


def _sample_bankroll() -> BankrollSettings:
    return BankrollSettings(
        amount=1000.0,
        strategy="percent",
        flat_stake=10.0,
        percent=2.0,
        kelly_fraction=0.5,
        default_odds=1.9,
        min_stake=5.0,
        max_stake=150.0,
    )


def test_compute_history_stats_handles_roi() -> None:
    df = pd.DataFrame(
        [
            {"result_status": "FT", "bet_stake": 100, "bet_return": 120, "bet_result": "win"},
            {"result_status": "FT", "bet_stake": 80, "bet_return": 0, "bet_result": "lose"},
        ]
    )
    stats = ca._compute_history_stats(df)
    assert stats["tracked_matches"] == 2
    assert pytest.approx(stats["roi_total"], rel=1e-9) == (120 - 180) / 180
    assert stats["win_rate_recent"] == pytest.approx(0.5)


def test_handle_chat_query_returns_answer_with_metadata(monkeypatch) -> None:
    df = pd.DataFrame(
        [
            {
                "result_status": "FT",
                "bet_stake": 100,
                "bet_return": 120,
                "bet_result": "win",
                "prob_home": 0.78,
                "prob_draw": 0.12,
                "prob_away": 0.10,
                "edge_comment": "Edge 8%",
                "home_team": "PSG",
                "away_team": "Lens",
                "bet_odd": 1.7,
                "league_id": 61,
                "fixture_id": 1,
            },
            {
                "result_status": "FT",
                "bet_stake": 80,
                "bet_return": 0,
                "bet_result": "lose",
                "prob_home": 0.45,
                "prob_draw": 0.30,
                "prob_away": 0.25,
                "edge_comment": "Edge 3%",
                "home_team": "Nice",
                "away_team": "OM",
                "bet_odd": 2.1,
                "league_id": 61,
                "fixture_id": 2,
            },
        ]
    )

    monkeypatch.setattr(ca, "_history_dataframe", lambda: df)
    monkeypatch.setattr(ca, "_call_openai_chat", lambda messages: "Analyse factuelle.")
    monkeypatch.setattr(ca, "_store_memory_entry", lambda *args, **kwargs: None)
    monkeypatch.setattr(ca, "_load_memory_entries", lambda user_id, limit=3: [])
    monkeypatch.setattr(ca, "_bankroll_settings", lambda: _sample_bankroll())

    result = ca.handle_chat_query("Quels matchs surperforment ?", context={"user_id": "test-user"})

    assert result["answer"] == "Analyse factuelle."
    metadata = result["metadata"]
    assert metadata["history_stats"]["tracked_matches"] == 2
    assert metadata["top_matches"], "au moins un match a forte proba doit etre retourne"
    assert metadata["kelly"]["stake"] >= 0
