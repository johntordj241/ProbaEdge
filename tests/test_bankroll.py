from utils.bankroll import BankrollSettings, suggest_stake


def build_settings(**overrides) -> BankrollSettings:
    base = {
        "amount": 200.0,
        "strategy": "percent",
        "flat_stake": 5.0,
        "percent": 5.0,
        "kelly_fraction": 0.5,
        "default_odds": 2.0,
        "min_stake": 0.0,
        "max_stake": 0.0,
    }
    base.update(overrides)
    return BankrollSettings.from_dict(base)


def test_negative_edge_returns_zero_stake() -> None:
    settings = build_settings(strategy="percent", percent=5.0)
    result = suggest_stake(0.4, 1.8, settings)  # edge < 0 => pas de mise
    assert result["stake"] == 0.0
    assert result["status"] == "negative_edge"
    assert result["expected_profit"] == 0.0


def test_positive_edge_with_no_bankroll_yields_zero() -> None:
    settings = build_settings(amount=0.0, strategy="kelly")
    result = suggest_stake(0.6, 2.0, settings)
    assert result["stake"] == 0.0
    assert result["status"] == "no_bankroll"


def test_max_stake_cap_is_reported() -> None:
    settings = build_settings(
        amount=500.0,
        strategy="kelly",
        kelly_fraction=1.0,
        max_stake=25.0,
    )
    result = suggest_stake(0.7, 2.5, settings)
    assert result["stake"] == 25.0
    assert result["status"] == "capped_max"
