from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


def compute_roi(probability: float, odd: float) -> Optional[float]:
    try:
        p = float(probability)
        o = float(odd)
    except (TypeError, ValueError):
        return None
    if o <= 1 or p < 0:
        return None
    edge = o * p - 1
    return edge


def outcome_result(probability: float, won: bool) -> float:
    return probability if won else 1 - probability


@dataclass
class PredictionOutcome:
    fixture_id: str
    main_pick: str
    probability: float
    real_winner: str
    success: bool
    roi: Optional[float]

__all__ = ["compute_roi", "outcome_result", "PredictionOutcome"]
