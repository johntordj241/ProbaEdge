from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from functools import lru_cache
from math import comb
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import unicodedata

import joblib
import numpy as np

from models.goal_models import (
    normalize_matrix as _normalize_score_matrix,
    poisson_probability as _goal_poisson_probability,
    scoreline_matrix as _scoreline_matrix,
)
from models.markov import MarkovContext, goal_prob_horizon
from models.ratings import DEFAULT_RATING, get_match_ratings

# Ce module décrit les 3 lois de probabilité utilisées par le moteur
# - Poisson : distribution des scores / marchés 1X2, over/under, BTTS
# - Binomiale : probabilité qu'un joueur marque selon son taux de réussite
# - Normale : comparaison de la forme (attaque/défense) par rapport à la ligue


# ---------------------------------------------------------------------------
# Helpers génériques
# ---------------------------------------------------------------------------
OUTCOME_MODEL_PATH = Path("models/match_outcome_model.joblib")
OUTCOME_FEATURE_COLUMNS = [
    "prob_home",
    "prob_draw",
    "prob_away",
    "feature_home_draw_diff",
    "feature_home_away_diff",
    "feature_over_under_diff",
    "feature_max_prob",
    "feature_main_confidence_norm",
    "feature_total_pick_over",
    "prob_over_2_5",
    "prob_under_2_5",
    "feature_lambda_home",
    "feature_lambda_away",
    "elo_home",
    "elo_away",
    "delta_elo",
    "pressure_score",
    "intensity_score",
]
PROBABILITY_KEYS = ("home", "draw", "away")
ELO_LAMBDA_ALPHA = 0.6
MIN_LAMBDA = 0.25
MAX_LAMBDA = 3.8
DEFAULT_SCORELINE_MODE = "dc"
DEFAULT_DC_TAU = 0.06
DEFAULT_BIVARIATE_RHO = 0.03


@lru_cache(maxsize=1)
def _load_outcome_model() -> Any:
    if not OUTCOME_MODEL_PATH.exists():
        return None
    try:
        return joblib.load(OUTCOME_MODEL_PATH)
    except Exception:
        return None


def _normalize_probability_map(
    values: Dict[str, float], fallback: Dict[str, float]
) -> Dict[str, float]:
    normalized: Dict[str, float] = {}
    for key in PROBABILITY_KEYS:
        normalized[key] = max(
            0.0, min(1.0, float(values.get(key, fallback.get(key, 0.0)) or 0.0))
        )
    total = sum(normalized.values())
    if total > 0:
        normalized = {key: val / total for key, val in normalized.items()}
    else:
        normalized = {
            key: float(fallback.get(key, 0.0) or 0.0) for key in PROBABILITY_KEYS
        }
    return normalized


def _ml_feature_vector(
    probs: Dict[str, float],
    markets: Dict[str, float],
    meta: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, float], np.ndarray]:
    meta = meta or {}
    prob_home = float(probs.get("home") or 0.0)
    prob_draw = float(probs.get("draw") or 0.0)
    prob_away = float(probs.get("away") or 0.0)

    prob_over = float(markets.get("over_2_5") or markets.get("over2_5") or 0.0)
    prob_under = float(markets.get("under_2_5") or markets.get("under2_5") or 0.0)

    max_prob = max(prob_home, prob_draw, prob_away)
    confidence_norm = max(0.3, min(1.0, max_prob))
    total_pick_over = 1.0 if prob_over >= prob_under else 0.0

    feature_map = {
        "prob_home": prob_home,
        "prob_draw": prob_draw,
        "prob_away": prob_away,
        "feature_home_draw_diff": prob_home - prob_draw,
        "feature_home_away_diff": prob_home - prob_away,
        "feature_over_under_diff": prob_over - prob_under,
        "feature_max_prob": max_prob,
        "feature_main_confidence_norm": confidence_norm,
        "feature_total_pick_over": total_pick_over,
        "prob_over_2_5": prob_over,
        "prob_under_2_5": prob_under,
        "feature_lambda_home": float(meta.get("lambda_home", 0.0)),
        "feature_lambda_away": float(meta.get("lambda_away", 0.0)),
        "elo_home": float(meta.get("elo_home", 0.0)),
        "elo_away": float(meta.get("elo_away", 0.0)),
        "delta_elo": float(meta.get("delta_elo", 0.0)),
        "pressure_score": float(meta.get("pressure_score", 0.0)),
        "intensity_score": float(meta.get("intensity_score", 0.0)),
    }
    vector = np.array(
        [[feature_map[name] for name in OUTCOME_FEATURE_COLUMNS]], dtype=float
    )
    return feature_map, vector


def calibrate_match_probabilities(
    probs: Dict[str, float],
    markets: Dict[str, float],
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    model = _load_outcome_model()
    if model is None:
        return probs
    try:
        _, features = _ml_feature_vector(probs, markets, meta=meta)
        predicted = model.predict_proba(features)[0]
        classes = getattr(model, "classes_", [])
        ml_map = {str(label): float(value) for label, value in zip(classes, predicted)}
        return _normalize_probability_map(ml_map, probs)
    except Exception:
        return probs


def _safe(d: Any, *keys: Any, default: Any = None) -> Any:
    cur = d
    try:
        for key in keys:
            if cur is None:
                return default
            cur = cur.get(key)
        return cur if cur is not None else default
    except Exception:
        return default


def _safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return fallback


# ---------------------------------------------------------------------------
# Modèles statistiques
# ---------------------------------------------------------------------------

# ---- Loi de Poisson & variantes ----


def poisson_probability(lmbda: float, k: int) -> float:
    return float(_goal_poisson_probability(lmbda, k))


def poisson_matrix(
    lambda_home: float,
    lambda_away: float,
    max_goals: int = 6,
    *,
    mode: Optional[str] = None,
    rho: Optional[float] = None,
    tau: Optional[float] = None,
) -> List[List[float]]:
    raw_matrix = _scoreline_matrix(
        max(lambda_home, 0.0),
        max(lambda_away, 0.0),
        max_goals=max_goals,
        mode=(mode or DEFAULT_SCORELINE_MODE),
        rho=rho if rho is not None else DEFAULT_BIVARIATE_RHO,
        tau=tau if tau is not None else DEFAULT_DC_TAU,
    )
    return _normalize_score_matrix(raw_matrix)


def aggregate_poisson_markets(
    matrix: Sequence[Sequence[float]],
    defense_home: Optional[float] = None,
    defense_away: Optional[float] = None,
    baseline_defense: Optional[float] = None,
) -> Dict[str, float]:
    """Agrège la matrice Poisson en marchés (1X2, Over/Under, BTTS).

    Args:
        matrix: Matrice Poisson de probabilités de scores
        defense_home: Buts encaissés/match de l'équipe à domicile (mesurant sa défense)
        defense_away: Buts encaissés/match de l'équipe en déplacement
        baseline_defense: Défense moyenne de la ligue (pour normalisation)
    """
    home = draw = away = over_1_5 = over_2_5 = btts_yes = 0.0
    for i, row in enumerate(matrix):
        for j, prob in enumerate(row):
            if i > j:
                home += prob
            elif i == j:
                draw += prob
            else:
                away += prob
            if i + j >= 2:
                over_1_5 += prob
            if i + j >= 3:
                over_2_5 += prob
            if i > 0 and j > 0:
                btts_yes += prob

    # Ajustement BTTS basé sur la qualité défensive réelle
    if (
        defense_home is not None
        and defense_away is not None
        and baseline_defense is not None
    ):
        baseline_defense = max(baseline_defense, 0.1)
        # Facteur de défense normalisé (1.0 = défense moyenne)
        # Si défense_home > baseline : mauvaise défense (encaisse plus)
        defense_factor_home = defense_home / baseline_defense
        defense_factor_away = defense_away / baseline_defense

        # Produit des facteurs défensifs : si l'un ou l'autre a une mauvaise défense, BTTS monte
        btts_adjustment = defense_factor_home * defense_factor_away

        # Appliquer l'ajustement (capped à 1.5x pour éviter distorsions extrêmes)
        adjustment_multiplier = min(1.5, max(0.7, btts_adjustment))
        btts_yes = min(1.0, btts_yes * adjustment_multiplier)

    return {
        "home": home,
        "draw": draw,
        "away": away,
        "over_1_5": over_1_5,
        "over_2_5": over_2_5,
        "btts_yes": btts_yes,
        "btts_no": 1 - btts_yes,
        # Double chance
        "double_chance_1X": home + draw,
        "double_chance_X2": away + draw,
        "double_chance_12": home + away,
    }


def top_scorelines(
    matrix: Sequence[Sequence[float]], home: str, away: str, limit: int = 5
) -> List[Dict[str, Any]]:
    scores: List[Dict[str, Any]] = []
    for i, row in enumerate(matrix):
        for j, prob in enumerate(row):
            scores.append(
                {
                    "score": (i, j),
                    "prob": prob,
                    "label": f"{home} {i}-{j} {away}",
                }
            )
    scores.sort(key=lambda item: item["prob"], reverse=True)
    return scores[:limit]


# ---- Loi Binomiale ----


def binomial_goal_probability(success_rate: float, attempts: float) -> float:
    """Probabilité qu'un joueur marque au moins un but sur 'attempts' opportunités."""
    if success_rate <= 0 or attempts <= 0:
        return 0.0
    # On borne pour éviter les excès (par ex. 10 tirs / 0.8 = 0.999)
    success_rate = min(max(success_rate, 0.02), 0.75)
    attempts = max(attempts, 1)
    # P(goal ≥1) = 1 - (1 - p)^n
    return 1 - (1 - success_rate) ** attempts


def binomial_probability(p: float, n: int, k: int) -> float:
    if p <= 0 or n <= 0 or k < 0:
        return 0.0
    p = min(max(p, 0.0), 1.0)
    return comb(n, k) * (p**k) * ((1 - p) ** (n - k))


# ---- Loi Normale ----


def z_score(value: float, mean_value: float, std_dev: float) -> float:
    if std_dev == 0:
        return 0.0
    return (value - mean_value) / std_dev


# ---------------------------------------------------------------------------
# Structures métiers
# ---------------------------------------------------------------------------


@dataclass
class TeamStrength:
    team_id: int
    name: str
    attack: float
    defense: float
    lambda_value: float
    z_score: float
    adjustments: List[str] = field(default_factory=list)
    elo_rating: float = DEFAULT_RATING
    delta_elo: float = 0.0


@dataclass
class LeagueBaseline:
    avg_attack: float
    avg_defense: float
    std_attack: float
    std_defense: float


@dataclass
class ContextAdjustments:
    halftime: bool = False
    halftime_message: Optional[str] = None
    red_cards: List[str] = field(default_factory=list)
    injuries: List[str] = field(default_factory=list)
    weather: Optional[str] = None
    referee: Optional[str] = None
    adjustments_home: List[str] = field(default_factory=list)
    adjustments_away: List[str] = field(default_factory=list)
    fatigue_flags: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Calcul des forces / λ attendus (Poisson + Normale)
# ---------------------------------------------------------------------------


def compute_league_baseline(standings: Iterable[Dict[str, Any]]) -> LeagueBaseline:
    attacks: List[float] = []
    defenses: List[float] = []
    for row in standings:
        played = _safe(row, "all", "played", default=0) or 0
        gf = _safe(
            row, "all", "goals", "for", default=_safe(row, "goals", "for", default=0)
        )
        ga = _safe(
            row,
            "all",
            "goals",
            "against",
            default=_safe(row, "goals", "against", default=0),
        )
        if played:
            attacks.append(gf / played)
            defenses.append(ga / played)
    if not attacks:
        # fallback typique Ligue 1
        return LeagueBaseline(
            avg_attack=1.45, avg_defense=1.35, std_attack=0.35, std_defense=0.3
        )
    return LeagueBaseline(
        avg_attack=mean(attacks),
        avg_defense=mean(defenses),
        std_attack=pstdev(attacks) if len(attacks) > 1 else 0.25,
        std_defense=pstdev(defenses) if len(defenses) > 1 else 0.25,
    )


def _goals_per_match(row: Dict[str, Any]) -> Tuple[float, float]:
    played = _safe(row, "all", "played", default=0) or 0
    if not played:
        return 1.4, 1.2
    gf = _safe(
        row, "all", "goals", "for", default=_safe(row, "goals", "for", default=0)
    )
    ga = _safe(
        row,
        "all",
        "goals",
        "against",
        default=_safe(row, "goals", "against", default=0),
    )
    return gf / played, ga / played


def compute_team_strength(
    row: Optional[Dict[str, Any]],
    team_id: int,
    team_name: str,
    baseline: LeagueBaseline,
    opponent_def: float,
    team_rating: float,
    delta_elo: float,
    *,
    home_advantage: float = 1.10,
    elo_alpha: float = ELO_LAMBDA_ALPHA,
) -> TeamStrength:
    if row:
        attack_pm, defense_pm = _goals_per_match(row)
    else:
        attack_pm, defense_pm = baseline.avg_attack, baseline.avg_defense

    baseline_def = baseline.avg_defense if baseline.avg_defense > 0 else 1.0
    opponent_def = max(opponent_def, 0.1)
    base_lambda = attack_pm * (opponent_def / baseline_def) * home_advantage
    lambda_value = max(MIN_LAMBDA, min(MAX_LAMBDA, base_lambda))

    if elo_alpha:
        lambda_value *= math.exp((elo_alpha * delta_elo) / 400.0)
        lambda_value = max(MIN_LAMBDA, min(MAX_LAMBDA, lambda_value))

    z = z_score(attack_pm, baseline.avg_attack, baseline.std_attack)
    return TeamStrength(
        team_id=team_id,
        name=team_name,
        attack=attack_pm,
        defense=defense_pm,
        lambda_value=lambda_value,
        z_score=z,
        elo_rating=team_rating,
        delta_elo=delta_elo,
    )


def expected_goals_from_standings(
    standings: List[Dict[str, Any]],
    home_id: int,
    away_id: int,
    home_name: str,
    away_name: str,
) -> Tuple[TeamStrength, TeamStrength, LeagueBaseline]:
    baseline = compute_league_baseline(standings)
    elo_home, elo_away, delta_home = get_match_ratings(
        home_id,
        away_id,
        home_name=home_name,
        away_name=away_name,
    )
    delta_away = -delta_home

    def row_for(team_id: int) -> Optional[Dict[str, Any]]:
        for entry in standings:
            if _safe(entry, "team", "id") == team_id:
                return entry
        return None

    home_row = row_for(home_id)
    away_row = row_for(away_id)

    def defensive_rate(row: Optional[Dict[str, Any]]) -> float:
        goals_against = baseline.avg_defense
        played = 1.0
        if row:
            goals_against = _safe(
                row,
                "all",
                "goals",
                "against",
                default=_safe(row, "goals", "against", default=baseline.avg_defense),
            )
            played = (
                _safe(row, "all", "played", default=_safe(row, "played", default=1.0))
                or 1.0
            )
        try:
            return max(float(goals_against) / float(played), 0.1)
        except (TypeError, ZeroDivisionError, ValueError):
            return max(baseline.avg_defense, 0.1)

    home_strength = compute_team_strength(
        home_row,
        home_id,
        home_name,
        baseline,
        opponent_def=defensive_rate(away_row),
        team_rating=elo_home,
        delta_elo=delta_home,
        home_advantage=1.10,
    )
    away_strength = compute_team_strength(
        away_row,
        away_id,
        away_name,
        baseline,
        opponent_def=defensive_rate(home_row),
        team_rating=elo_away,
        delta_elo=delta_away,
        home_advantage=1.00,
    )
    return home_strength, away_strength, baseline


# ---------------------------------------------------------------------------
# Ajustements contextuels (météo, fatigue, suspensions, mi-temps, live)
# ---------------------------------------------------------------------------


def adjust_lambdas_context(
    lambda_home: float,
    lambda_away: float,
    context: Optional[Dict[str, Any]],
) -> Tuple[float, float, List[str], List[str]]:
    if context is None:
        return (
            max(MIN_LAMBDA, min(MAX_LAMBDA, lambda_home)),
            max(MIN_LAMBDA, min(MAX_LAMBDA, lambda_away)),
            [],
            [],
        )

    context_map = context if isinstance(context, dict) else {}
    notes_home: List[str] = []
    notes_away: List[str] = []

    def clamp(value: float) -> float:
        return max(MIN_LAMBDA, min(MAX_LAMBDA, value))

    def apply_global(factor: float, reason: str) -> None:
        nonlocal lambda_home, lambda_away
        lambda_home *= factor
        lambda_away *= factor
        notes_home.append(reason)
        notes_away.append(reason)

    def apply_home(factor: float, reason: str) -> None:
        nonlocal lambda_home
        lambda_home *= factor
        notes_home.append(reason)

    def apply_away(factor: float, reason: str) -> None:
        nonlocal lambda_away
        lambda_away *= factor
        notes_away.append(reason)

    weather = context_map.get("weather")
    if isinstance(weather, dict):
        description = str(weather.get("description") or "").lower()
        wind = weather.get("wind")
        temperature = weather.get("temperature")
        if any(
            token in description
            for token in ("rain", "pluie", "shower", "orage", "storm", "neige", "snow")
        ):
            apply_global(0.95, "Météo défavorable (pluie/neige)")
        if isinstance(wind, (int, float)) and float(wind) >= 30.0:
            apply_global(0.93, "Vent fort (>30 km/h)")
        if isinstance(temperature, (int, float)):
            temp_val = float(temperature)
            if temp_val <= 0:
                apply_global(0.96, "Température basse (<=0°C)")
            elif temp_val >= 30:
                apply_global(0.97, "Température élevée (>=30°C)")

    susp_home = context_map.get("suspensions_home", 0)
    susp_away = context_map.get("suspensions_away", 0)
    inj_key_home = context_map.get("key_injuries_home", 0)
    inj_key_away = context_map.get("key_injuries_away", 0)

    if susp_home:
        apply_home(
            max(0.80, 1.0 - 0.07 * float(susp_home)), f"Suspensions clés ({susp_home})"
        )
    if susp_away:
        apply_away(
            max(0.80, 1.0 - 0.07 * float(susp_away)), f"Suspensions clés ({susp_away})"
        )
    if inj_key_home:
        apply_home(
            max(0.82, 1.0 - 0.05 * float(inj_key_home)),
            f"Blessures clés ({inj_key_home})",
        )
    if inj_key_away:
        apply_away(
            max(0.82, 1.0 - 0.05 * float(inj_key_away)),
            f"Blessures clés ({inj_key_away})",
        )

    rest_home = context_map.get("rest_hours_home")
    rest_away = context_map.get("rest_hours_away")

    if isinstance(rest_home, (int, float)):
        if rest_home < 48:
            apply_home(0.93, "Repos insuffisant (<48h)")
        elif rest_home < 72:
            apply_home(0.97, "Repos court (<72h)")
    if isinstance(rest_away, (int, float)):
        if rest_away < 48:
            apply_away(0.93, "Repos insuffisant (<48h)")
        elif rest_away < 72:
            apply_away(0.97, "Repos court (<72h)")

    fatigue_home = context_map.get("fatigue_home")
    fatigue_away = context_map.get("fatigue_away")
    if fatigue_home:
        apply_home(0.95, str(fatigue_home))
    if fatigue_away:
        apply_away(0.95, str(fatigue_away))

    ref_pen_rate = context_map.get("referee_penalty_rate")
    if isinstance(ref_pen_rate, (int, float)) and ref_pen_rate >= 0.25:
        apply_global(1.03, "Arbitre sanctionne souvent (pen/90 élevé)")

    lambda_home = clamp(lambda_home)
    lambda_away = clamp(lambda_away)
    return lambda_home, lambda_away, notes_home, notes_away


def adjust_lambdas_at_halftime(
    lambda_home: float,
    lambda_away: float,
    goals_ht_home: int,
    goals_ht_away: int,
    shots_ht_home: Optional[int] = None,
    shots_ht_away: Optional[int] = None,
    xg_ht_home: Optional[float] = None,
    xg_ht_away: Optional[float] = None,
) -> Tuple[float, float]:
    """Ajustement simple basé sur les signaux de la première mi-temps."""

    def signal(xg: Optional[float], shots: Optional[int], goals: int) -> float:
        if xg is not None:
            return max(xg, 0.05)
        if shots is not None:
            return max(shots * 0.11, 0.05)
        return max(goals * 0.9, 0.05)

    sig_home = signal(xg_ht_home, shots_ht_home, goals_ht_home)
    sig_away = signal(xg_ht_away, shots_ht_away, goals_ht_away)

    expected_home = max(lambda_home * 0.5, 0.05)
    expected_away = max(lambda_away * 0.5, 0.05)

    factor_home = max(0.45, min(1.9, sig_home / expected_home))
    factor_away = max(0.45, min(1.9, sig_away / expected_away))

    return lambda_home * 0.5 * factor_home, lambda_away * 0.5 * factor_away


def apply_context_adjustments(
    home: TeamStrength,
    away: TeamStrength,
    fixture: Dict[str, Any],
    *,
    injuries_home: Optional[List[Dict[str, Any]]] = None,
    injuries_away: Optional[List[Dict[str, Any]]] = None,
) -> ContextAdjustments:
    context = ContextAdjustments()
    status_short = _safe(fixture, "fixture", "status", "short", default="NS")
    teams_block = _safe(fixture, "teams", default={}) or {}
    context_payload: Dict[str, Any] = {}

    def _rest_hours(team_block: Dict[str, Any]) -> Optional[float]:
        rest = _safe(team_block, "fixtures", "last", "rest")
        if isinstance(rest, dict):
            hours = rest.get("hours")
            if isinstance(hours, (int, float)):
                return float(hours)
            days = rest.get("days")
            if isinstance(days, (int, float)):
                return float(days) * 24.0
        fallback = _safe(team_block, "rest_hours")
        if isinstance(fallback, (int, float)):
            return float(fallback)
        return None

    def _count_missing(team_block: Dict[str, Any], keyword: str) -> int:
        missing = _safe(team_block, "missing_players", default=[]) or []
        count = 0
        for entry in missing:
            reason = str(_safe(entry, "reason", default="")).lower()
            if keyword in reason:
                count += 1
        return count

    def _injury_notes(
        entries: Optional[List[Dict[str, Any]]], team_name: str
    ) -> List[str]:
        notes: List[str] = []
        seen: set[str] = set()
        for entry in entries or []:
            player_block = _safe(entry, "player", default={}) or {}
            name = player_block.get("name")
            if not name:
                continue
            detail = (
                player_block.get("type")
                or entry.get("type")
                or player_block.get("reason")
                or entry.get("reason")
            )
            label = f"{team_name} - {name}"
            if detail:
                label = f"{label} ({detail})"
            if label in seen:
                continue
            seen.add(label)
            notes.append(label)
        return notes

    # Mi-temps / live
    if status_short in {"HT", "1H", "LIVE", "2H"}:
        goals_home = _safe(fixture, "goals", "home", default=0) or 0
        goals_away = _safe(fixture, "goals", "away", default=0) or 0
        stats = _safe(fixture, "statistics") or []

        def shots_for(team_type: str) -> Optional[int]:
            for block in stats:
                if _safe(block, "team", "id") == (
                    home.team_id if team_type == "home" else away.team_id
                ):
                    for stat in block.get("statistics", []):
                        if stat.get("type") == "Shots on Goal":
                            return _safe(stat, "value", default=None)
            return None

        hom_l, awa_l = adjust_lambdas_at_halftime(
            home.lambda_value,
            away.lambda_value,
            goals_home,
            goals_away,
            shots_ht_home=shots_for("home"),
            shots_ht_away=shots_for("away"),
        )
        home.lambda_value = max(MIN_LAMBDA, hom_l)
        away.lambda_value = max(MIN_LAMBDA, awa_l)
        context.halftime = True
        context.halftime_message = (
            f"Réajusté à la mi-temps : {goals_home}-{goals_away}."
        )

    # Cartons rouges / blessures dans events
    weather_block = _safe(fixture, "fixture", "weather", default={})
    if weather_block:
        if isinstance(weather_block, dict):
            desc = weather_block.get("description") or weather_block.get("desc")
            temp = weather_block.get("temperature") or weather_block.get("temp")
            wind = weather_block.get("wind") or weather_block.get("wind_speed")
            parts = []
            if desc:
                parts.append(str(desc))
            if temp not in {None, ""}:
                parts.append(f"temp {temp}")
            if wind not in {None, ""}:
                parts.append(f"vent {wind}")
            if parts:
                context.weather = ", ".join(parts)
        else:
            context.weather = str(weather_block)
        context_payload["weather"] = (
            weather_block
            if isinstance(weather_block, dict)
            else {"description": weather_block}
        )

    referee_label = _safe(fixture, "fixture", "referee")
    if referee_label:
        context.referee = str(referee_label)
    referee_stats = _safe(fixture, "fixture", "referee_stats", default={})
    ref_pen_rate = None
    if isinstance(referee_stats, dict):
        raw_rate = referee_stats.get("penalties_per_game") or referee_stats.get(
            "penalties_per_90"
        )
        if isinstance(raw_rate, (int, float)):
            ref_pen_rate = float(raw_rate)
    context_payload["referee_penalty_rate"] = ref_pen_rate

    home_team_block = teams_block.get("home") or {}
    away_team_block = teams_block.get("away") or {}
    rest_home = _rest_hours(home_team_block)
    rest_away = _rest_hours(away_team_block)
    if rest_home is not None:
        context_payload["rest_hours_home"] = rest_home
        if rest_home < 72:
            context.fatigue_flags.append(f"{home.name} repos {rest_home:.0f}h")
            if rest_home < 48:
                context_payload["fatigue_home"] = "Repos <48h"
    if rest_away is not None:
        context_payload["rest_hours_away"] = rest_away
        if rest_away < 72:
            context.fatigue_flags.append(f"{away.name} repos {rest_away:.0f}h")
            if rest_away < 48:
                context_payload["fatigue_away"] = "Repos <48h"

    context_payload["suspensions_home"] = _count_missing(home_team_block, "suspens")
    context_payload["suspensions_away"] = _count_missing(away_team_block, "suspens")

    injury_notes_home = _injury_notes(injuries_home, home.name)
    injury_notes_away = _injury_notes(injuries_away, away.name)
    if injury_notes_home:
        context_payload["key_injuries_home"] = min(len(injury_notes_home), 3)
    if injury_notes_away:
        context_payload["key_injuries_away"] = min(len(injury_notes_away), 3)
    existing_injury_notes = set(context.injuries)
    for note in injury_notes_home + injury_notes_away:
        if note not in existing_injury_notes:
            context.injuries.append(note)
            existing_injury_notes.add(note)

    for event in _safe(fixture, "events", default=[]):
        detail = str(event.get("detail", ""))
        team_name = _safe(event, "team", "name", default="")
        team_id = _safe(event, "team", "id")
        if "red card" in detail.lower():
            if team_id == home.team_id:
                home.lambda_value = max(MIN_LAMBDA, home.lambda_value * 0.75)
                context.red_cards.append(f"{team_name} - carton rouge")
            elif team_id == away.team_id:
                away.lambda_value = max(MIN_LAMBDA, away.lambda_value * 0.75)
                context.red_cards.append(f"{team_name} - carton rouge")
        if "injury" in detail.lower():
            if team_id == home.team_id:
                home.lambda_value = max(MIN_LAMBDA, home.lambda_value * 0.85)
                context.injuries.append(f"{team_name} - blessure ({detail})")
            elif team_id == away.team_id:
                away.lambda_value = max(MIN_LAMBDA, away.lambda_value * 0.85)
                context.injuries.append(f"{team_name} - blessure ({detail})")

    lambda_home, lambda_away, notes_home, notes_away = adjust_lambdas_context(
        home.lambda_value,
        away.lambda_value,
        context_payload,
    )
    home.lambda_value = lambda_home
    away.lambda_value = lambda_away
    if notes_home:
        home.adjustments.extend(notes_home)
        context.adjustments_home.extend(notes_home)
    if notes_away:
        away.adjustments.extend(notes_away)
        context.adjustments_away.extend(notes_away)

    return context


# ---------------------------------------------------------------------------
# Buteurs probables (Poisson + Binomiale)
# ---------------------------------------------------------------------------


def probable_goalscorers(
    league_id: int,
    season: int,
    home_id: int,
    away_id: int,
    lambda_home: float,
    lambda_away: float,
    topscorers: List[Dict[str, Any]],
    players_home: List[Dict[str, Any]],
    players_away: List[Dict[str, Any]],
    topn: int = 6,
    *,
    injured_home: Optional[Iterable[str]] = None,
    injured_away: Optional[Iterable[str]] = None,
) -> List[Dict[str, Any]]:
    picks: List[Dict[str, Any]] = []

    def _normalize_name(name: Optional[str]) -> str:
        if not name:
            return ""
        normalized = unicodedata.normalize("NFKD", name)
        return (
            "".join(ch for ch in normalized if not unicodedata.combining(ch))
            .strip()
            .lower()
        )

    injured_home_set = {_normalize_name(name) for name in (injured_home or []) if name}
    injured_away_set = {_normalize_name(name) for name in (injured_away or []) if name}

    def _is_injured(candidate_name: str, team_id: int) -> bool:
        normalized = _normalize_name(candidate_name)
        if not normalized:
            return False
        if team_id == home_id:
            return normalized in injured_home_set
        if team_id == away_id:
            return normalized in injured_away_set
        return False

    def candidate_from_top(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        team_id = _safe(entry, "statistics", 0, "team", "id")
        if team_id not in {home_id, away_id}:
            return None
        goals = _safe(entry, "statistics", 0, "goals", "total", default=0)
        shots = _safe(entry, "statistics", 0, "shots", "total", default=0)
        apps = _safe(entry, "statistics", 0, "games", "appearences", default=1) or 1
        if goals == 0 and shots == 0:
            return None
        shots_per_match = shots / apps if shots else 2.2
        success_rate = goals / shots if shots else min(0.65, goals / apps)
        lambda_team = lambda_home if team_id == home_id else lambda_away
        prob = binomial_goal_probability(
            success_rate, max(shots_per_match, lambda_team * 2)
        )
        return {
            "team_id": team_id,
            "name": _safe(entry, "player", "name", default="Buteur"),
            "photo": _safe(entry, "player", "photo"),
            "prob": prob,
            "source": "topscorers",
        }

    for entry in topscorers or []:
        candidate = candidate_from_top(entry)
        if candidate and not _is_injured(candidate["name"], candidate["team_id"]):
            picks.append(candidate)

    def fill_from_squad(
        players: List[Dict[str, Any]], team_id: int, lambda_team: float
    ) -> None:
        def _player_position(entry: Dict[str, Any]) -> str:
            return str(
                _safe(entry, "statistics", 0, "games", "position", default="")
            ).lower()

        def _scoring_metric(entry: Dict[str, Any]) -> float:
            stats = _safe(entry, "statistics", 0, default={})
            goals = float(_safe(stats, "goals", "total", default=0) or 0)
            shots = float(_safe(stats, "shots", "total", default=0) or 0)
            minutes = float(_safe(stats, "games", "minutes", default=0) or 0)
            matches = max(minutes / 90.0, 1.0) if minutes else 1.0
            goals_per_90 = goals / matches
            shots_per_90 = shots / matches
            return (goals_per_90 * 0.7) + (shots_per_90 * 0.3)

        candidates = [p for p in players if not _player_position(p).startswith("gk")]
        if not candidates:
            candidates = players[:4]
        candidates.sort(key=_scoring_metric, reverse=True)
        base_prob = min(0.45, max(0.15, lambda_team / 2.5))

        for player in candidates[:3]:
            player_name = _safe(player, "player", "name", default="Buteur potentiel")
            if _is_injured(player_name, team_id):
                continue
            score = max(_scoring_metric(player), 0.05)
            prob = min(0.7, max(base_prob, score * 0.4 + base_prob * 0.6))
            picks.append(
                {
                    "team_id": team_id,
                    "name": player_name,
                    "photo": _safe(player, "player", "photo"),
                    "prob": prob,
                    "source": "squad",
                }
            )

    if sum(1 for p in picks if p["team_id"] == home_id) < 2:
        fill_from_squad(players_home or [], home_id, lambda_home)
    if sum(1 for p in picks if p["team_id"] == away_id) < 2:
        fill_from_squad(players_away or [], away_id, lambda_away)

    picks.sort(key=lambda item: item["prob"], reverse=True)
    return picks[:topn]


# ---------------------------------------------------------------------------
# Paris couverts / résumé éditorial
# ---------------------------------------------------------------------------

MARKETS_CATALOG = {
    "1X2": "Résultat du match",
    "Double chance": "1X, X2, 12",
    "Total buts": "Over/Under 1.5 & 2.5",
    "BTTS": "Les deux équipes marquent",
    "Score exact": "Score le plus probable",
    "Handicap +1": "Couverture simple par Poisson",
}


def available_markets_count() -> int:
    return len(MARKETS_CATALOG)


def editorial_summary(
    home: TeamStrength,
    away: TeamStrength,
    probs: Dict[str, float],
    context: ContextAdjustments,
    baseline: LeagueBaseline,
) -> str:
    sentences = []
    sentences.append(
        f"L'analyse Poisson projette {home.name} à {home.lambda_value:.2f} buts attendus contre {away.name} {away.lambda_value:.2f}."
    )
    sentences.append(
        f"Les formes normalisées (loi normale) confirment un z-score attaque de {home.name}: {home.z_score:+.2f} contre {away.name}: {away.z_score:+.2f}."
    )
    dominant = max(
        ("domicile", probs["home"]),
        ("nul", probs["draw"]),
        ("extérieur", probs["away"]),
        key=lambda x: x[1],
    )
    sentences.append(
        f"Le marché 1X2 penche vers {dominant[0]} ({dominant[1]*100:.1f}%)."
    )
    if context.red_cards or context.injuries:
        sentences.append(
            "Ajustements contextuels pris en compte : "
            + ", ".join(context.red_cards + context.injuries)
            + "."
        )
    elif context.halftime:
        sentences.append(context.halftime_message or "Réévaluation live appliquée.")
    sentences.append(
        "Le modèle reste purement statistique : il pondère les absences détectées (cartons/blessures dans le flux live) "
        "mais recommande de vérifier les informations tactiques avant de parier."
    )
    return " ".join(sentences)


def project_match_outcome(
    home: "TeamStrength",
    away: "TeamStrength",
    *,
    goals_home: int = 0,
    goals_away: int = 0,
    status_short: Optional[str] = None,
    elapsed: Optional[int] = None,
    max_goals: int = 6,
    context_adjustments: Optional[ContextAdjustments] = None,
    pressure_metrics: Optional[Dict[str, Any]] = None,
    matrix_mode: Optional[str] = None,
    markov_meta: Optional[Dict[str, Any]] = None,
) -> tuple[Dict[str, float], List[Dict[str, Any]], Optional[List[List[float]]]]:
    """Project outcome probabilities given live context (score & minute)."""
    goals_home = int(goals_home or 0)
    goals_away = int(goals_away or 0)
    status_short = (status_short or "NS").upper()

    if status_short in {"FT", "AET", "PEN"}:
        final_probs = {"home": 0.0, "draw": 0.0, "away": 0.0}
        if goals_home > goals_away:
            final_probs["home"] = 1.0
        elif goals_home == goals_away:
            final_probs["draw"] = 1.0
        else:
            final_probs["away"] = 1.0
        label = f"{home.name} {goals_home}-{goals_away} {away.name}"
        return (
            final_probs,
            [{"label": label, "prob": 1.0, "score": (goals_home, goals_away)}],
            None,
        )

    lambda_home = max(MIN_LAMBDA, float(home.lambda_value))
    lambda_away = max(MIN_LAMBDA, float(away.lambda_value))
    matrix_mode = matrix_mode or DEFAULT_SCORELINE_MODE

    is_live = (
        elapsed is not None
        and isinstance(elapsed, (int, float))
        and elapsed > 0
        and status_short not in {"NS", "TBD"}
    )
    if is_live:
        meta = markov_meta or {}
        pressure_score = 0.0
        if pressure_metrics:
            try:
                pressure_score = float(pressure_metrics.get("score", 0.0) or 0.0)
            except (TypeError, ValueError):
                pressure_score = 0.0
        ctx = MarkovContext(
            score_delta=goals_home - goals_away,
            red_cards_home=int(meta.get("red_cards_home", 0) or 0),
            red_cards_away=int(meta.get("red_cards_away", 0) or 0),
            pressure_score=max(0.0, min(1.0, pressure_score)),
            elapsed=float(elapsed or 0.0),
        )
        factor_home, factor_away = goal_prob_horizon(
            lambda_home,
            lambda_away,
            context=ctx,
            horizon_seconds=60.0,
        )
        lambda_home = max(MIN_LAMBDA, min(MAX_LAMBDA, lambda_home * factor_home))
        lambda_away = max(MIN_LAMBDA, min(MAX_LAMBDA, lambda_away * factor_away))

    if not is_live:
        base_matrix = poisson_matrix(
            lambda_home, lambda_away, max_goals=max_goals, mode=matrix_mode
        )
        # Créer une baseline par défaut pour l'ajustement BTTS
        default_baseline_defense = 1.35  # Valeur moyenne typique Ligue 1
        return (
            aggregate_poisson_markets(
                base_matrix,
                defense_home=home.defense,
                defense_away=away.defense,
                baseline_defense=default_baseline_defense,
            ),
            top_scorelines(base_matrix, home.name, away.name, limit=5),
            base_matrix,
        )

    total_minutes = 95.0
    elapsed = max(0.0, min(float(elapsed), total_minutes))
    remaining_ratio = max(0.05, (total_minutes - elapsed) / total_minutes)
    lambda_rem_home = max(0.05, lambda_home * remaining_ratio)
    lambda_rem_away = max(0.05, lambda_away * remaining_ratio)

    remaining_matrix = poisson_matrix(
        lambda_rem_home,
        lambda_rem_away,
        max_goals=max_goals,
        mode=matrix_mode,
    )

    probs = {"home": 0.0, "draw": 0.0, "away": 0.0}
    scorelines: List[Dict[str, Any]] = []

    for additional_home, row in enumerate(remaining_matrix):
        for additional_away, prob in enumerate(row):
            final_home = goals_home + additional_home
            final_away = goals_away + additional_away
            scorelines.append(
                {
                    "label": f"{home.name} {final_home}-{final_away} {away.name}",
                    "prob": prob,
                    "score": (final_home, final_away),
                }
            )
            if final_home > final_away:
                probs["home"] += prob
            elif final_home == final_away:
                probs["draw"] += prob
            else:
                probs["away"] += prob

    scorelines.sort(key=lambda item: item["prob"], reverse=True)
    return probs, scorelines[:5], remaining_matrix


def probability_confidence_interval(
    home: TeamStrength,
    away: TeamStrength,
    *,
    goals_home: int,
    goals_away: int,
    status_short: Optional[str],
    elapsed: Optional[int],
    context_adjustments: Optional[ContextAdjustments] = None,
    pressure_metrics: Optional[Dict[str, Any]] = None,
    matrix_mode: Optional[str] = None,
    markov_meta: Optional[Dict[str, Any]] = None,
    calibration_meta: Optional[Dict[str, Any]] = None,
    max_goals: int = 6,
) -> Dict[str, Tuple[float, float]]:
    """
    Compute a simple confidence interval on match outcome probabilities by perturbing lambdas by ±10%.
    """
    intervals: Dict[str, Tuple[float, float]] = {}
    scenarios: List[Dict[str, float]] = []
    matrix_mode = matrix_mode or DEFAULT_SCORELINE_MODE

    for scale in (0.9, 1.1):
        scaled_home = replace(
            home,
            lambda_value=max(MIN_LAMBDA, min(MAX_LAMBDA, home.lambda_value * scale)),
        )
        scaled_away = replace(
            away,
            lambda_value=max(MIN_LAMBDA, min(MAX_LAMBDA, away.lambda_value * scale)),
        )
        probs, _, matrix = project_match_outcome(
            scaled_home,
            scaled_away,
            goals_home=goals_home,
            goals_away=goals_away,
            status_short=status_short,
            elapsed=elapsed,
            max_goals=max_goals,
            context_adjustments=context_adjustments,
            pressure_metrics=pressure_metrics,
            matrix_mode=matrix_mode,
            markov_meta=markov_meta,
        )
        if matrix is None:
            matrix = poisson_matrix(
                scaled_home.lambda_value,
                scaled_away.lambda_value,
                max_goals=max_goals,
                mode=matrix_mode,
            )
        markets = aggregate_poisson_markets(matrix)
        markets.update(probs)
        if calibration_meta:
            meta_scaled = dict(calibration_meta)
            meta_scaled["lambda_home"] = scaled_home.lambda_value
            meta_scaled["lambda_away"] = scaled_away.lambda_value
            probs = calibrate_match_probabilities(probs, markets, meta=meta_scaled)
        scenarios.append(probs)

    for key in PROBABILITY_KEYS:
        low = min(scenario.get(key, 0.0) for scenario in scenarios)
        high = max(scenario.get(key, 0.0) for scenario in scenarios)
        intervals[key] = (max(0.0, low), min(1.0, high))
    return intervals


__all__ = [
    "TeamStrength",
    "LeagueBaseline",
    "ContextAdjustments",
    "poisson_probability",
    "poisson_matrix",
    "aggregate_poisson_markets",
    "top_scorelines",
    "binomial_goal_probability",
    "binomial_probability",
    "z_score",
    "expected_goals_from_standings",
    "adjust_lambdas_context",
    "apply_context_adjustments",
    "probable_goalscorers",
    "available_markets_count",
    "editorial_summary",
    "project_match_outcome",
    "probability_confidence_interval",
    "calibrate_match_probabilities",
]
