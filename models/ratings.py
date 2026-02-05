from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from datetime import datetime, timezone

import pandas as pd

DEFAULT_RATING: float = 1500.0
K_FACTOR: float = 20.0
RATINGS_PATH = Path("data/elo_table.parquet")

_CACHE: Optional[pd.DataFrame] = None
_COLUMNS = [
    "team_id",
    "team_name",
    "rating",
    "games_played",
    "last_season",
    "updated_at",
]


@dataclass
class EloUpdate:
    home_rating: float
    away_rating: float
    expected_home: float
    expected_away: float
    delta_home: float
    delta_away: float


def _ensure_table() -> pd.DataFrame:
    """Load the ratings table (parquet) into memory, creating it if missing/corrupted."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE.copy()

    if RATINGS_PATH.exists():
        try:
            table = pd.read_parquet(RATINGS_PATH)
        except Exception:
            table = pd.DataFrame(columns=_COLUMNS)
    else:
        table = pd.DataFrame(columns=_COLUMNS)

    # Guarantee expected columns
    for column in _COLUMNS:
        if column not in table.columns:
            table[column] = []

    if not pd.api.types.is_datetime64_any_dtype(table.get("updated_at")):
        try:
            table["updated_at"] = pd.to_datetime(table["updated_at"])
        except Exception:
            table["updated_at"] = pd.NaT

    _CACHE = table
    return table.copy()


def _persist_table(df: pd.DataFrame) -> None:
    RATINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(RATINGS_PATH, index=False)
    global _CACHE
    _CACHE = df.copy()


def load_ratings() -> pd.DataFrame:
    """Return the current Elo table (copy)."""
    return _ensure_table()


def _timestamp() -> datetime:
    return datetime.now(timezone.utc)


def get_team_rating(team_id: int, team_name: Optional[str] = None, default: float = DEFAULT_RATING) -> float:
    """
    Retrieve the rating for a team, creating an entry with the default rating when missing.
    """
    df = _ensure_table()
    mask = df["team_id"] == int(team_id)
    if mask.any():
        return float(df.loc[mask, "rating"].iloc[0])

    entry = pd.DataFrame(
        [
            {
                "team_id": int(team_id),
                "team_name": str(team_name or ""),
                "rating": float(default),
                "games_played": 0,
                "last_season": None,
                "updated_at": _timestamp(),
            }
        ]
    )
    df = pd.concat([df, entry], ignore_index=True)
    _persist_table(df)
    return float(default)


def register_team(team_id: int, team_name: Optional[str] = None, rating: float = DEFAULT_RATING) -> None:
    """Ensure an entry exists for the given team without altering existing ratings."""
    get_team_rating(team_id, team_name, rating)


def expected_score(rating_a: float, rating_b: float) -> float:
    """Expected game score of team A against team B."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def get_match_ratings(
    home_id: int,
    away_id: int,
    *,
    home_name: Optional[str] = None,
    away_name: Optional[str] = None,
) -> Tuple[float, float, float]:
    """
    Convenience helper returning (home_rating, away_rating, delta_home).
    """
    home_rating = get_team_rating(home_id, home_name)
    away_rating = get_team_rating(away_id, away_name)
    delta_home = home_rating - away_rating
    return home_rating, away_rating, delta_home


def _adjust_k(base_k: float, goal_diff: int) -> float:
    """
    Scale the K factor based on scoreline margin.
    Inspired by Elo soccer variants (small boost on large wins).
    """
    if goal_diff <= 1:
        return base_k
    if goal_diff == 2:
        return base_k * 1.1
    return base_k * (1.0 + min(goal_diff, 4) * 0.1)


def update_match(
    home_id: int,
    away_id: int,
    goals_home: int,
    goals_away: int,
    *,
    home_name: Optional[str] = None,
    away_name: Optional[str] = None,
    season: Optional[int] = None,
    k_factor: float = K_FACTOR,
) -> EloUpdate:
    """
    Update ratings after a finished match and persist the table.
    Returns information about the rating deltas applied.
    """
    df = _ensure_table()

    home_rating = get_team_rating(home_id, home_name)
    away_rating = get_team_rating(away_id, away_name)

    mask_home = df["team_id"] == int(home_id)
    mask_away = df["team_id"] == int(away_id)

    score_home = 1.0 if goals_home > goals_away else 0.0
    score_away = 1.0 - score_home
    if goals_home == goals_away:
        score_home = score_away = 0.5

    expected_home = expected_score(home_rating, away_rating)
    expected_away = expected_score(away_rating, home_rating)

    goal_diff = abs(int(goals_home) - int(goals_away))
    adjusted_k = _adjust_k(k_factor, goal_diff)

    new_home = home_rating + adjusted_k * (score_home - expected_home)
    new_away = away_rating + adjusted_k * (score_away - expected_away)

    ts = _timestamp()

    if mask_home.any():
        df.loc[mask_home, "rating"] = float(new_home)
        df.loc[mask_home, "games_played"] = df.loc[mask_home, "games_played"].fillna(0).astype(int) + 1
        if home_name:
            df.loc[mask_home, "team_name"] = str(home_name)
        if season is not None:
            df.loc[mask_home, "last_season"] = int(season)
        df.loc[mask_home, "updated_at"] = ts
    else:
        df = pd.concat(
            [
                df,
                pd.DataFrame(
                    [
                        {
                            "team_id": int(home_id),
                            "team_name": str(home_name or ""),
                            "rating": float(new_home),
                            "games_played": 1,
                            "last_season": int(season) if season is not None else None,
                            "updated_at": ts,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

    if mask_away.any():
        df.loc[mask_away, "rating"] = float(new_away)
        df.loc[mask_away, "games_played"] = df.loc[mask_away, "games_played"].fillna(0).astype(int) + 1
        if away_name:
            df.loc[mask_away, "team_name"] = str(away_name)
        if season is not None:
            df.loc[mask_away, "last_season"] = int(season)
        df.loc[mask_away, "updated_at"] = ts
    else:
        df = pd.concat(
            [
                df,
                pd.DataFrame(
                    [
                        {
                            "team_id": int(away_id),
                            "team_name": str(away_name or ""),
                            "rating": float(new_away),
                            "games_played": 1,
                            "last_season": int(season) if season is not None else None,
                            "updated_at": ts,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

    _persist_table(df)

    return EloUpdate(
        home_rating=new_home,
        away_rating=new_away,
        expected_home=expected_home,
        expected_away=expected_away,
        delta_home=new_home - home_rating,
        delta_away=new_away - away_rating,
    )


__all__ = [
    "DEFAULT_RATING",
    "K_FACTOR",
    "EloUpdate",
    "load_ratings",
    "register_team",
    "get_team_rating",
    "get_match_ratings",
    "expected_score",
    "update_match",
]
