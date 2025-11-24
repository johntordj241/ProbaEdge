import pandas as pd

import utils.content_engine as ce


def test_content_payload_markdown_render():
    payload = ce.ContentPayload(
        title="Test Report",
        summary="Résumé des insights.",
        bullet_points=["Bullet A", "Bullet B"],
        highlights=[{"match": "Team A vs Team B", "edge_pct": 7.5, "bookmaker": "Bookie"}],
        tags=["test"],
        generated_at=pd.Timestamp("2025-11-23T10:00:00Z").to_pydatetime(),
    )
    markdown = payload.render_markdown()
    assert "# Test Report" in markdown
    assert "Bullet A" in markdown
    assert "Team A vs Team B" in markdown


def test_generate_payload_handles_empty_history(monkeypatch):
    monkeypatch.setattr(ce, "load_prediction_history", lambda: pd.DataFrame())
    monkeypatch.setattr(ce, "_match_gap_bullet", lambda: None)
    monkeypatch.setattr(ce, "_supervision_bullet", lambda: None)
    payload = ce.generate_content_payload()
    assert isinstance(payload.summary, str)
    assert payload.highlights == []


def test_match_gap_bullet_handles_errors(monkeypatch):
    def _fail(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(ce, "get_matches_over_horizon", _fail)
    assert ce._match_gap_bullet() is None
