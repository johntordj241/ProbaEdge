from __future__ import annotations

from typing import Dict, Mapping, Optional

from .ai_scenarios import scenario_probability_factors


def _normalize_probabilities(probs: Mapping[str, float]) -> Dict[str, float]:
    total = sum(max(float(value), 0.0) for value in probs.values())
    if total <= 0:
        return {key: 1.0 / len(probs) if probs else 0.0 for key in probs}
    return {key: max(float(value), 0.0) / total for key, value in probs.items()}


def _base_map(projection: Mapping[str, float]) -> Dict[str, float]:
    return {
        "home": float(projection.get("home") or 0.0),
        "draw": float(projection.get("draw") or 0.0),
        "away": float(projection.get("away") or 0.0),
    }


def _apply_factor_map(probs: Dict[str, float], factors: Mapping[str, float]) -> Dict[str, float]:
    adjusted = {}
    for key, value in probs.items():
        factor = float(factors.get(key, 1.0) or 1.0)
        adjusted[key] = value * factor
    return _normalize_probabilities(adjusted)


def alt_projection_snapshot(
    projection_probs: Mapping[str, float],
    *,
    intensity_score: Optional[float] = None,
    pressure_score: Optional[float] = None,
    scenario_key: Optional[str] = None,
) -> Dict[str, float]:
    """
    Simple heuristics-based projection used comme moteur local.
    """
    working = _base_map(projection_probs)
    factors: Dict[str, float] = {"home": 1.0, "draw": 1.0, "away": 1.0}

    if scenario_key:
        scenario_factors = scenario_probability_factors(scenario_key)
        for key, value in scenario_factors.items():
            factors[key] = factors.get(key, 1.0) * float(value or 1.0)

    if intensity_score is not None:
        if intensity_score >= 75:
            factors["draw"] *= 0.85
            factors["home"] *= 1.05
            factors["away"] *= 1.05
        elif intensity_score <= 40:
            factors["draw"] *= 1.1

    if pressure_score is not None:
        if pressure_score >= 65:
            factors["home"] *= 1.05
            factors["away"] *= 1.05
        elif pressure_score <= 35:
            factors["draw"] *= 1.08

    return _apply_factor_map(working, factors)


def probability_delta(
    base: Mapping[str, float],
    alternative: Mapping[str, float],
) -> Dict[str, float]:
    return {
        "home": float(alternative.get("home", 0.0)) - float(base.get("home", 0.0)),
        "draw": float(alternative.get("draw", 0.0)) - float(base.get("draw", 0.0)),
        "away": float(alternative.get("away", 0.0)) - float(base.get("away", 0.0)),
    }


__all__ = ["alt_projection_snapshot", "probability_delta"]

