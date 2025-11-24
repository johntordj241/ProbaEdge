import datetime

import pytest

from utils import predictions as preds


@pytest.fixture(autouse=True)
def reset_fixture_cache():
    preds._LOCAL_FIXTURE_CACHE.clear()
    yield
    preds._LOCAL_FIXTURE_CACHE.clear()


def test_load_fixture_with_details_enriches_stats_and_events(monkeypatch):
    fixture_id = 999
    fallback = {"fixture": {"id": fixture_id}}

    detail_payload = [{
        "fixture": {
            "id": fixture_id,
            "update": "2025-10-21T20:15:00Z",
        }
    }]
    statistics_payload = [
        {
            "team": {"id": 1},
            "statistics": [
                {"type": "Shots on Goal", "value": 3},
                {"type": "Total Shots", "value": 8},
            ],
        }
    ]
    events_payload = [
        {
            "time": {"elapsed": 12},
            "type": "Goal",
            "detail": "Normal Goal",
        }
    ]

    monkeypatch.setattr(preds, "get_fixture_details", lambda fid: detail_payload)
    monkeypatch.setattr(preds, "get_fixture_statistics", lambda fid: statistics_payload)
    monkeypatch.setattr(preds, "get_fixture_events", lambda fid: events_payload)

    enriched, updated_at, source = preds._load_fixture_with_details(
        fixture_id,
        fallback,
        cache_ttl_seconds=300,
    )

    assert enriched["statistics"] == statistics_payload
    assert enriched["events"] == events_payload
    assert isinstance(updated_at, datetime.datetime)
    assert source == "api"

    # Second call should reuse cached data instead of hitting the API again.
    second, updated_at_cached, source_cached = preds._load_fixture_with_details(
        fixture_id,
        fallback,
        cache_ttl_seconds=300,
    )
    assert second["statistics"] == statistics_payload
    assert second["events"] == events_payload
    assert updated_at_cached == updated_at
    assert source_cached == "cache"

