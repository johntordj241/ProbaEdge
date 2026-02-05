from utils.predictions import _statistics_dataframe


def test_statistics_dataframe_empty_payload_returns_empty_df():
    df = _statistics_dataframe([])
    assert df.empty


def test_statistics_dataframe_builds_columns_for_statistics():
    payload = [
        {
            "team": {"id": 10, "name": "Equipe A"},
            "statistics": [
                {"type": "Shots on Goal", "value": 3},
                {"type": "Ball Possession", "value": "55%"},
            ],
        }
    ]
    df = _statistics_dataframe(payload)
    assert not df.empty
    assert "Shots on Goal" in df.columns
    assert df.iloc[0]["Shots on Goal"] == 3
    assert df.iloc[0]["Ball Possession"] == "55%"
