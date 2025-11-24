from __future__ import annotations

import math
from functools import lru_cache
from typing import List, Sequence


def _safe_factorial(k: int) -> float:
    if k < 0:
        return 1.0
    return math.factorial(k)


def poisson_probability(lmbda: float, k: int) -> float:
    if lmbda <= 0:
        return 0.0 if k > 0 else 1.0
    if k < 0:
        return 0.0
    return math.exp(-lmbda) * (lmbda**k) / _safe_factorial(k)


def poisson_bivariate_p(x: int, y: int, lam_home: float, lam_away: float, lambda_shared: float) -> float:
    """
    Bivariate Poisson probability as described by Karlis & Ntzoufras.
    lambda_shared models the covariance term (>= 0).
    """
    if min(x, y) < 0 or min(lam_home, lam_away) < 0 or lambda_shared < 0:
        return 0.0
    total = 0.0
    shared = min(x, y)
    for k in range(shared + 1):
        numerator = (
            (lam_home ** (x - k))
            * (lam_away ** (y - k))
            * (lambda_shared**k)
        )
        denominator = (
            _safe_factorial(x - k)
            * _safe_factorial(y - k)
            * _safe_factorial(k)
        )
        total += numerator / denominator
    base = math.exp(-(lam_home + lam_away + lambda_shared))
    return float(base * total)


def _dixon_coles_adjustment(x: int, y: int, lam_home: float, lam_away: float, tau: float) -> float:
    if tau == 0.0:
        return 1.0
    if x == 0 and y == 0:
        return 1.0 + (-lam_home - lam_away) * tau + lam_home * lam_away * (tau**2)
    if x == 0 and y == 1:
        return 1.0 + lam_home * tau
    if x == 1 and y == 0:
        return 1.0 + lam_away * tau
    if x == 1 and y == 1:
        return 1.0 - tau
    return 1.0


def dixon_coles_p(x: int, y: int, lam_home: float, lam_away: float, tau: float) -> float:
    base = poisson_probability(lam_home, x) * poisson_probability(lam_away, y)
    return float(base * _dixon_coles_adjustment(x, y, lam_home, lam_away, tau))


@lru_cache(maxsize=256)
def scoreline_matrix(
    lambda_home: float,
    lambda_away: float,
    *,
    max_goals: int = 6,
    mode: str = "dc",
    rho: float = 0.05,
    tau: float = 0.06,
) -> List[List[float]]:
    """
    Build a scoreline probability matrix using the requested mode:
        - "uni": independent Poisson
        - "dc": Dixon-Coles adjustment (default)
        - "bivariate": bivariate Poisson with shared lambda = rho
    """
    matrix: List[List[float]] = []
    lam_home = max(lambda_home, 0.0)
    lam_away = max(lambda_away, 0.0)
    mode_key = (mode or "dc").lower()
    for i in range(max_goals + 1):
        row: List[float] = []
        for j in range(max_goals + 1):
            if mode_key == "bivariate":
                prob = poisson_bivariate_p(i, j, lam_home, lam_away, max(rho, 0.0))
            elif mode_key == "uni":
                prob = poisson_probability(lam_home, i) * poisson_probability(lam_away, j)
            else:
                prob = dixon_coles_p(i, j, lam_home, lam_away, tau)
            row.append(prob)
        matrix.append(row)
    return matrix


def normalize_matrix(matrix: Sequence[Sequence[float]]) -> List[List[float]]:
    total = sum(sum(max(prob, 0.0) for prob in row) for row in matrix)
    if total <= 0.0:
        return [[0.0 for _ in row] for row in matrix]
    return [[max(prob, 0.0) / total for prob in row] for row in matrix]


__all__ = [
    "poisson_probability",
    "poisson_bivariate_p",
    "dixon_coles_p",
    "scoreline_matrix",
    "normalize_matrix",
]
