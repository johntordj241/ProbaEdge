from __future__ import annotations

from datetime import date
from typing import Optional

DEFAULT_LEAGUE_ID = 61
DEFAULT_TEAM_ID = 85


def compute_default_season(today: Optional[date] = None) -> int:
    """Return the most relevant season for European leagues (July to June)."""
    today = today or date.today()
    return today.year if today.month >= 7 else today.year - 1


DEFAULT_SEASON = compute_default_season()

__all__ = [
    "DEFAULT_LEAGUE_ID",
    "DEFAULT_TEAM_ID",
    "DEFAULT_SEASON",
    "compute_default_season",
]
