import math

import pytest

from utils.prediction_model import (
    poisson_probability,
    poisson_matrix,
    aggregate_poisson_markets,
    top_scorelines,
)


def test_poisson_probability_matches_manual_formula():
    # Manual Poisson formula: e^{-λ} * λ^k / k!
    lam = 1.8
    k = 3
    expected = math.exp(-lam) * (lam**k) / math.factorial(k)
    assert poisson_probability(lam, k) == pytest.approx(expected)


def test_poisson_probability_handles_non_positive_lambda():
    assert poisson_probability(0, 2) == 0.0
    assert poisson_probability(-1, 1) == 0.0


def test_aggregate_poisson_markets_probabilities_sum_to_one():
    matrix = poisson_matrix(lambda_home=1.2, lambda_away=0.9, max_goals=6)
    markets = aggregate_poisson_markets(matrix)
    total = markets["home"] + markets["draw"] + markets["away"]
    # Truncation at max_goals can introduce a small residual mass.
    assert total == pytest.approx(1.0, abs=5e-4)


def test_top_scorelines_returns_ordered_scores():
    matrix = poisson_matrix(1.5, 1.0, max_goals=4)
    scores = top_scorelines(matrix, "Home", "Away", limit=3)
    # Probabilities should be sorted from highest to lowest
    probs = [entry["prob"] for entry in scores]
    assert probs == sorted(probs, reverse=True)
    # Returned labels should include the team names.
    assert all("Home" in entry["label"] and "Away" in entry["label"] for entry in scores)
