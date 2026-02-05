from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import math
import numpy as np

STATE_INDEX = {
    "neutral": 0,
    "press_home": 1,
    "press_away": 2,
    "cpa_home": 3,
    "cpa_away": 4,
    "shot_home": 5,
    "shot_away": 6,
    "goal_home": 7,
    "goal_away": 8,
}

GOAL_STATES = (STATE_INDEX["goal_home"], STATE_INDEX["goal_away"])
STEP_SECONDS = 15.0


@dataclass(frozen=True)
class MarkovContext:
    score_delta: int = 0
    red_cards_home: int = 0
    red_cards_away: int = 0
    pressure_score: float = 0.0
    elapsed: float = 0.0


def _base_matrix() -> np.ndarray:
    mat = np.array(
        [
            # neutral, press_h, press_a, cpa_h, cpa_a, shot_h, shot_a, goal_h, goal_a
            [0.60, 0.14, 0.14, 0.02, 0.02, 0.04, 0.04, 0.00, 0.00],  # neutral
            [0.35, 0.30, 0.10, 0.05, 0.02, 0.12, 0.02, 0.02, 0.02],  # press_home
            [0.35, 0.10, 0.30, 0.02, 0.05, 0.02, 0.12, 0.02, 0.02],  # press_away
            [0.25, 0.18, 0.05, 0.20, 0.05, 0.15, 0.03, 0.07, 0.02],  # cpa_home
            [0.25, 0.05, 0.18, 0.05, 0.20, 0.03, 0.15, 0.02, 0.07],  # cpa_away
            [0.45, 0.12, 0.05, 0.04, 0.02, 0.18, 0.05, 0.07, 0.02],  # shot_home
            [0.45, 0.05, 0.12, 0.02, 0.04, 0.05, 0.18, 0.02, 0.07],  # shot_away
            [1.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00],  # goal_home absorbing proxy
            [1.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00],  # goal_away absorbing proxy
        ],
        dtype=float,
    )
    return mat


def _regime_adjustments(ctx: MarkovContext) -> Tuple[float, float]:
    delta = ctx.score_delta
    pressure = max(0.0, min(1.0, ctx.pressure_score))
    if delta == 0:
        return 1.0 + 0.1 * pressure, 1.0 + 0.1 * pressure
    if delta > 0:
        # home leading, away pushing
        return 1.0 - 0.05 * min(delta, 2) - 0.05 * ctx.red_cards_home, 1.0 + 0.12 * min(delta, 2) + 0.05 * pressure
    # away leading, home pushing
    return 1.0 + 0.12 * min(-delta, 2) + 0.05 * pressure, 1.0 - 0.05 * min(-delta, 2) - 0.05 * ctx.red_cards_away


def _transition_matrix(ctx: MarkovContext) -> np.ndarray:
    base = _base_matrix().copy()
    home_boost, away_boost = _regime_adjustments(ctx)
    # pressure adjustments
    base[STATE_INDEX["neutral"], STATE_INDEX["press_home"]] *= home_boost
    base[STATE_INDEX["neutral"], STATE_INDEX["press_away"]] *= away_boost
    base[STATE_INDEX["neutral"], STATE_INDEX["shot_home"]] *= home_boost
    base[STATE_INDEX["neutral"], STATE_INDEX["shot_away"]] *= away_boost
    if ctx.red_cards_home:
        base[:, STATE_INDEX["press_home"]] *= 0.85
        base[:, STATE_INDEX["shot_home"]] *= 0.85
        base[:, STATE_INDEX["goal_home"]] *= 0.9
    if ctx.red_cards_away:
        base[:, STATE_INDEX["press_away"]] *= 0.85
        base[:, STATE_INDEX["shot_away"]] *= 0.85
        base[:, STATE_INDEX["goal_away"]] *= 0.9

    # normalise rows
    row_sums = base.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0.0] = 1.0
    base /= row_sums
    return base


def goal_prob_horizon(
    lambda_home: float,
    lambda_away: float,
    *,
    context: MarkovContext,
    horizon_seconds: float = 60.0,
) -> Tuple[float, float]:
    """
    Estimate the goal probability for each side within the provided horizon using a simple Markov model.
    """
    steps = max(1, int(math.ceil(horizon_seconds / STEP_SECONDS)))
    matrix = _transition_matrix(context)
    pressure = max(0.0, min(1.0, context.pressure_score))
    initial = np.zeros(len(STATE_INDEX), dtype=float)
    initial[STATE_INDEX["neutral"]] = max(0.2, 1.0 - pressure)
    initial[STATE_INDEX["press_home"]] = 0.4 * pressure
    initial[STATE_INDEX["press_away"]] = 0.4 * pressure
    initial /= initial.sum()

    dist = initial
    for _ in range(steps):
        dist = dist @ matrix

    prob_home = float(dist[STATE_INDEX["goal_home"]])
    prob_away = float(dist[STATE_INDEX["goal_away"]])

    total_minutes = 95.0
    baseline_home = 1.0 - math.exp(-max(lambda_home, 0.0) * horizon_seconds / (total_minutes * 60.0))
    baseline_away = 1.0 - math.exp(-max(lambda_away, 0.0) * horizon_seconds / (total_minutes * 60.0))
    baseline_home = max(1e-6, baseline_home)
    baseline_away = max(1e-6, baseline_away)

    factor_home = max(0.5, min(1.8, prob_home / baseline_home))
    factor_away = max(0.5, min(1.8, prob_away / baseline_away))

    return factor_home, factor_away


__all__ = [
    "MarkovContext",
    "goal_prob_horizon",
]
