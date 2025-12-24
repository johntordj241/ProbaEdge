from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional, Tuple, Mapping, Sequence
from copy import deepcopy

import json
import math
import re
import unicodedata

PARIS_TZ = ZoneInfo("Europe/Paris")

import pandas as pd
import streamlit as st

from .bankroll import BankrollSettings, suggest_stake
from .ai_ import analyse_match_with_ai, commentate_match_with_ai, is_openai_configured, AIAnalysisError
from .ai_scenarios import (
    DEFAULT_AI_SCENARIOS,
    available_scenarios,
    build_scenario_payload,
    scenario_instruction,
)
from .alt_predictor import alt_projection_snapshot, probability_delta
from .notifications import notify_event
from .profile import (
    get_bankroll_settings,
    get_intensity_weights,
    get_favorite_competitions,
    get_ai_preferences,
    get_alert_settings,
    list_saved_scenes,
    upsert_scene,
    delete_scene,
)
from .cache import render_cache_controls, cache_stats, is_offline_mode
from .api_calls import (
    get_fixtures,
    get_fixture_details,
    get_fixture_events,
    get_fixture_statistics,
    get_players_for_team,
    get_predictions,
    get_standings,
    get_topscorers,
    get_odds_by_fixture,
    get_injuries,
)
from .prediction_history import (
    load_prediction_history,
    upsert_prediction,
    update_outcome,
    normalize_prediction_history,
    over_under_bias,
    record_bet,
)
from .supervision import health_snapshot
from .prediction_model import (
    apply_context_adjustments,
    calibrate_match_probabilities,
    editorial_summary,
    expected_goals_from_standings,
    probable_goalscorers,
    project_match_outcome,
    probability_confidence_interval,
    poisson_probability,
)
from .ui_helpers import select_league_and_season, select_team
from . import weather
from .widgets import render_widget
from .events import load_fixture_events, format_event_line
from .engagement import (
    available_templates,
    render_template,
    get_engagement_service,
    TemplateError,
)
from .secrets import get_secret

STRATEGY_LABELS = {
    "flat": "Mise fixe",
    "percent": "Pourcentage fixe",
    "kelly": "Kelly simplifie",
}

OPPORTUNITY_EDGE_THRESHOLD = 0.04


def _seed_scene_state(config: Optional[Dict[str, Any]]) -> None:
    if not config:
        return

    def _set_state(key: str, value: Any) -> None:
        if value is not None:
            st.session_state[key] = value

    highlight = int(config.get("highlight_threshold_pts", int(OPPORTUNITY_EDGE_THRESHOLD * 100)))
    highlight = min(30, max(1, highlight))
    _set_state("predictions_highlight_threshold", highlight)
    _set_state("predictions_scope_select", config.get("scope"))
    limit_val = int(config.get("limit", 30))
    limit_val = min(60, max(5, limit_val))
    _set_state("predictions_limit_slider", limit_val)
    _set_state("over_filters_enabled", bool(config.get("over_filters_enabled")))
    thresholds = config.get("over_thresholds") or {}
    _set_state("over_threshold_1_5", int(thresholds.get("over_1_5", 55)))
    _set_state("over_threshold_2_5", int(thresholds.get("over_2_5", 60)))
    _set_state("over_threshold_3_5", int(thresholds.get("over_3_5", 45)))
    _set_state("under_filters_enabled", bool(config.get("under_filters_enabled")))
    min_prob = config.get("under_min_prob")
    if min_prob is not None:
        _set_state("under_min_prob_slider", int(min_prob))
    _set_state("under_intensity_lock", bool(config.get("under_limit_intensity")))
    _set_state("under_intensity_cap_slider", int(config.get("under_max_intensity", 65)))


def _compose_scene_config(
    *,
    league_id: int,
    season: int,
    team_id: Optional[int],
    scope: str,
    limit: int,
    highlight_points: int,
    over_under_filters: Dict[str, Any],
) -> Dict[str, Any]:
    over_settings = over_under_filters.get("over", {})
    under_settings = over_under_filters.get("under", {})
    over_thresholds = {
        key: int(value)
        for key, value in (over_settings.get("thresholds") or {}).items()
        if value is not None
    }
    return {
        "league_id": int(league_id) if league_id is not None else None,
        "season": int(season) if season is not None else None,
        "team_id": int(team_id) if team_id is not None else None,
        "scope": scope,
        "limit": int(limit),
        "highlight_threshold_pts": int(highlight_points),
        "over_filters_enabled": bool(over_settings.get("enabled")),
        "over_thresholds": over_thresholds,
        "under_filters_enabled": bool(under_settings.get("enabled")),
        "under_min_prob": (
            int(under_settings.get("min_prob")) if under_settings.get("min_prob") is not None else None
        ),
        "under_limit_intensity": bool(under_settings.get("limit_intensity")),
        "under_max_intensity": int(under_settings.get("max_intensity", 65)),
    }


def _stake_comment(suggestion: Dict[str, Any], settings: BankrollSettings) -> str:
    status = suggestion.get("status")
    if status == "negative_edge":
        return "Edge negatif : ne pas engager ce pari."
    if status == "no_bankroll":
        return "Capital indisponible ou mise minimale trop elevee."
    if status == "capped_max":
        return "Plafond de mise atteint."
    if status == "all_bankroll":
        return "Attention : tout le capital serait engage."
    if status == "min_enforced":
        return "Application de la mise minimale."
    if status == "zero_probability":
        return "Probabilite nulle estimee pour cette selection."
    return ""


def _store_tip_meta(
    tip_meta: Dict[str, Dict[str, Any]],
    label: str,
    odd: float,
    suggestion: Dict[str, Any],
    settings: BankrollSettings,
) -> Dict[str, Any]:
    entry = tip_meta.setdefault(label, {})
    entry["odd"] = odd
    entry["stake"] = suggestion["stake"]
    entry["edge"] = suggestion["edge"]
    entry["expected_profit"] = suggestion["expected_profit"]
    status = suggestion.get("status")
    if status is not None:
        entry["status"] = status
    comment = _stake_comment(suggestion, settings)
    if comment:
        entry["comment"] = comment
    else:
        entry.pop("comment", None)
    return entry


def _top_value_opportunities(
    tips: Sequence[Dict[str, Any]],
    *,
    odds_map: Mapping[str, float],
    bankroll: BankrollSettings,
    home_name: str,
    away_name: str,
    max_items: int = 4,
    edge_threshold: float = OPPORTUNITY_EDGE_THRESHOLD,
) -> List[Dict[str, Any]]:
    """Return the highest value picks based on model probability vs available odds."""
    highlights: List[Dict[str, Any]] = []
    if not tips:
        return highlights
    for tip in tips:
        probability = tip.get("probability")
        if probability in (None, ""):
            continue
        odds = _odds_for_tip(tip, odds_map, home_name, away_name) or bankroll.default_odds
        suggestion = suggest_stake(probability, odds, bankroll)
        edge = suggestion.get("edge")
        if edge is None or edge < edge_threshold:
            continue
        highlights.append(
            {
                "label": tip.get("label", "Selection"),
                "odd": suggestion.get("odds", odds),
                "edge_pct": float(edge) * 100.0,
                "stake": suggestion.get("stake", 0.0),
                "confidence": tip.get("confidence"),
                "reason": tip.get("reason", ""),
            }
        )
    highlights.sort(key=lambda item: (item["edge_pct"], item.get("confidence") or 0), reverse=True)
    return highlights[:max_items]


LIVE_STATUS_CODES = {"LIVE", "1H", "2H", "ET", "P", "BT", "HT", "INT", "INP"}
UPCOMING_STATUS_CODES = {"NS", "TBD", "PST"}
FINISHED_STATUS_CODES = {"FT", "AET", "PEN", "CANC", "ABD", "AWD"}
EVENT_STATUS_CODES = LIVE_STATUS_CODES | FINISHED_STATUS_CODES

AI_MARKET_KEYS: Tuple[str, ...] = (
    "home",
    "draw",
    "away",
    "over_1_5",
    "over_2_5",
    "under_2_5",
    "over_3_5",
    "under_3_5",
    "btts_yes",
    "btts_no",
)

AI_PRESSURE_FIELDS: Tuple[str, ...] = (
    "label",
    "score",
    "shots_on_target_home",
    "shots_on_target_away",
    "total_shots_home",
    "total_shots_away",
    "xg_home",
    "xg_away",
    "ball_possession_home",
    "ball_possession_away",
    "dangerous_attacks",
    "yellow_cards_home",
    "yellow_cards_away",
    "fouls_home",
    "fouls_away",
    "corners_home",
    "corners_away",
    "big_chances_home",
    "big_chances_away",
    "recent_events",
)


_LOCAL_FIXTURE_CACHE: Dict[int, Dict[str, Any]] = {}


def _topscorers_best_effort(league_id: int, season: int) -> tuple[list[dict[str, Any]], Optional[int]]:
    current = get_topscorers(league_id, season) or []
    if current:
        return current, None
    previous = season - 1 if season and season > 2000 else None
    if not previous:
        return [], None
    fallback = get_topscorers(league_id, previous) or []
    if fallback:
        return fallback, previous
    return [], None


def _players_best_effort(league_id: int, season: int, team_id: Optional[int]) -> list[dict[str, Any]]:
    if not team_id:
        return []
    return get_players_for_team(league_id, season, team_id)


def _injured_name_set(entries: Optional[List[Dict[str, Any]]]) -> set[str]:
    names: set[str] = set()
    for entry in entries or []:
        player = entry.get("player") or {}
        name = player.get("name")
        if name:
            names.add(name)
    return names


def _parse_datetime(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        dt_obj = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    try:
        return dt_obj.astimezone(PARIS_TZ)
    except Exception:
        return dt_obj


def _format_datetime(raw: Optional[str]) -> str:
    dt_obj = _parse_datetime(raw)
    if not dt_obj:
        return "Date inconnue"
    return dt_obj.strftime("%d/%m/%Y %H:%M")


def _status_details(fixture: Dict[str, Any]) -> Dict[str, Any]:
    fixture_info = fixture.get("fixture") or {}
    status_block = fixture_info.get("status") or {}
    goals_block = fixture.get("goals") or {}
    short = (status_block.get("short") or "NS").upper()
    elapsed = status_block.get("elapsed")
    home_goals = goals_block.get("home") or 0
    away_goals = goals_block.get("away") or 0

    if short in LIVE_STATUS_CODES:
        elapsed_str = f"{elapsed}'" if elapsed is not None else "Live"
        label = f"Situation live {elapsed_str} : {home_goals}-{away_goals}"
    elif short in FINISHED_STATUS_CODES:
        label = f"Score final {home_goals}-{away_goals} ({short})"
    else:
        label = f"Coup d'envoi prevu le {_format_datetime(fixture_info.get('date'))}"

    return {
        "short": short,
        "elapsed": elapsed,
        "home_goals": int(home_goals or 0),
        "away_goals": int(away_goals or 0),
        "label": label,
    }


def _match_summary_lines(
    fixture: Dict[str, Any],
    home_strength: Any,
    away_strength: Any,
    status: Dict[str, Any],
    context: Optional[Any] = None,
) -> List[str]:
    fixture_info = fixture.get("fixture") or {}
    venue = (fixture_info.get("venue") or {}).get("name")
    teams = fixture.get("teams") or {}
    home = teams.get("home") or {}
    away = teams.get("away") or {}
    home_name = home.get("name", "?")
    away_name = away.get("name", "?")
    delta = home_strength.lambda_value - away_strength.lambda_value
    lines = [
        f":soccer: {home_name} vs {away_name}",
        f":clock1: {status['label']}",
        f":bar_chart: Ecart attendu : {delta:+.2f} xG",
    ]
    lines.append(
        f":dna: xG prevus - {home_name}: {home_strength.lambda_value:.2f} | {away_name}: {away_strength.lambda_value:.2f}"
    )
    if venue:
        lines.append(f":stadium: {venue}")
    if context:
        weather_desc = getattr(context, "weather", None)
        if weather_desc:
            lines.append(f":cloud: Meteo : {weather_desc}")
        elif not weather.is_available():
            lines.append(":cloud: Meteo : non disponible (ajoutez OPENWEATHER_API_KEY).")
    return lines


MAX_WEATHER_FORECAST_DAYS = 5


def _attach_weather_to_fixture(fixture: Dict[str, Any]) -> None:
    fixture_block = fixture.get("fixture")
    if not isinstance(fixture_block, dict):
        return
    if fixture_block.get("weather"):
        return
    venue = fixture_block.get("venue") or {}
    city = venue.get("city")
    league_block = fixture.get("league") or {}
    country = league_block.get("country")
    kickoff = _parse_datetime(fixture_block.get("date"))
    if not city or not kickoff:
        return
    horizon = kickoff - datetime.now(PARIS_TZ)
    if horizon > timedelta(days=MAX_WEATHER_FORECAST_DAYS):
        fixture_block["weather"] = {
            "description": f"Prevision indisponible (match trop eloigne > {MAX_WEATHER_FORECAST_DAYS} jours pour OpenWeather).",
            "source": "openweather",
        }
        fixture["fixture"] = fixture_block
        return
    forecast = weather.get_match_forecast(
        city=city,
        country=country,
        kickoff=kickoff,
    )
    if forecast:
        fixture_block["weather"] = forecast
        fixture["fixture"] = fixture_block


def _load_fixture_with_details(
    fixture_id: int,
    fallback: Dict[str, Any],
    *,
    cache_ttl_seconds: int = 45,
) -> Tuple[Dict[str, Any], Optional[datetime], str]:
    try:
        cache_store = st.session_state.setdefault("_fixture_details_cache", {})
    except Exception:
        cache_store = _LOCAL_FIXTURE_CACHE
    now = datetime.now(PARIS_TZ)
    cache_entry = cache_store.get(fixture_id)
    if not cache_entry:
        cache_entry = _LOCAL_FIXTURE_CACHE.get(fixture_id)
    if cache_entry:
        fetched_at = cache_entry.get("fetched_at")
        if isinstance(fetched_at, datetime) and (now - fetched_at).total_seconds() <= cache_ttl_seconds:
            origin = cache_entry.get("source", "cache")
            source_label = "cache" if origin == "api" else origin
            return deepcopy(cache_entry["data"]), cache_entry.get("updated_at"), source_label
    try:
        details = get_fixture_details(int(fixture_id)) or []
    except Exception:
        merged = deepcopy(fallback)
        cache_store[fixture_id] = {
            "data": merged,
            "fetched_at": now,
            "updated_at": None,
            "source": "error",
        }
        return merged, None, "error"
    entry = details[0] if isinstance(details, list) and details else details
    if not isinstance(entry, dict):
        merged = deepcopy(fallback)
        cache_store[fixture_id] = {
            "data": merged,
            "fetched_at": now,
            "updated_at": None,
            "source": "fallback",
        }
        return merged, None, "fallback"
    merged = deepcopy(fallback)
    for key, value in entry.items():
        if value not in (None, [], {}):
            merged[key] = value
    if not merged.get("statistics"):
        try:
            stats_payload = get_fixture_statistics(fixture_id) or []
        except Exception:
            stats_payload = []
        if isinstance(stats_payload, list) and stats_payload:
            merged["statistics"] = stats_payload
    if not merged.get("events"):
        try:
            events_payload = get_fixture_events(fixture_id) or []
        except Exception:
            events_payload = []
        if isinstance(events_payload, list) and events_payload:
            merged["events"] = events_payload
    fixture_block = merged.get("fixture") or {}
    updated_raw = (
        fixture_block.get("update")
        or fixture_block.get("updated_at")
        or fixture_block.get("updated")
        or fixture_block.get("lastUpdate")
    )
    updated_at = _parse_datetime(updated_raw) if updated_raw else None
    cache_entry = {
        "data": merged,
        "fetched_at": now,
        "updated_at": updated_at,
        "source": "api",
    }
    cache_store[fixture_id] = cache_entry
    _LOCAL_FIXTURE_CACHE[fixture_id] = cache_entry
    return deepcopy(merged), updated_at, "api"


def _normalize_stat_label(raw: Any) -> str:
    text = unicodedata.normalize("NFKD", str(raw or "").strip())
    ascii_text = "".join(ch for ch in text if ord(ch) < 128)
    return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())


STAT_LABEL_ALIASES: Dict[str, set[str]] = {
    "shots on goal": {
        "shots on goal",
        "shots on target",
        "tir cadre",
        "tirs cadres",
        "tirs au but",
        "tirs cadres",
    },
    "total shots": {
        "total shots",
        "shots total",
        "tirs totaux",
        "tirs",
    },
    "dangerous attacks": {
        "dangerous attacks",
        "attaques dangereuses",
    },
    "attacks": {
        "attacks",
        "attaques",
    },
    "expected goals": {
        "expected goals",
        "xg",
        "x.g",
        "buts attendus",
    },
    "ball possession": {
        "ball possession",
        "possession",
        "possession de balle",
    },
    "passes accurate": {
        "passes accurate",
        "passes precises",
        "passes precis",
        "passes reussies",
        "passes rÃ©ussies",
        "passes reussies",
        "passes completed",
    },
    "fouls": {
        "fouls",
        "fautes",
    },
    "corner kicks": {
        "corner kicks",
        "corners",
        "coups de coin",
    },
    "yellow cards": {
        "yellow cards",
        "cartons jaunes",
    },
    "red cards": {
        "red cards",
        "cartons rouges",
    },
    "big chances": {
        "big chances",
        "grosses occasions",
    },
    "shots inside box": {
        "shots inside box",
        "tirs dans la surface",
    },
    "shots outside box": {
        "shots outside box",
        "tirs hors de la surface",
    },
    "goalkeeper saves": {
        "goalkeeper saves",
        "arrets gardien",
        "arrets du gardien",
        "arrÃªts gardien",
    },
}


def _stat_label_variants(label: str) -> set[str]:
    normalized = _normalize_stat_label(label)
    variants = {normalized}
    for base_label, options in STAT_LABEL_ALIASES.items():
        normalized_options = {_normalize_stat_label(opt) for opt in {base_label, *options}}
        if normalized in normalized_options:
            variants.update(normalized_options)
            break
    return variants


def _stat_value(statistics: List[Dict[str, Any]], team_id: int, label: str) -> Optional[float]:
    targets = _stat_label_variants(label)
    for block in statistics or []:
        team_block = block.get("team") or {}
        if team_block.get("id") != team_id:
            continue
        for stat in block.get("statistics") or []:
            stat_label = stat.get("type")
            if _normalize_stat_label(stat_label) not in targets:
                continue
            value = stat.get("value")
            if value in {None, "", "-"}:
                return None
            try:
                raw = str(value).strip()
                if raw.endswith("%"):
                    return float(raw.replace("%", "").replace(",", ".")) / 100.0
                return float(raw.replace(",", "."))
            except (TypeError, ValueError):
                return None
    return None


def _live_match_pressure(
    fixture: Dict[str, Any],
    home_id: int,
    away_id: int,
    elapsed: Optional[Any],
) -> Dict[str, Any]:
    statistics = fixture.get("statistics") or []
    events = fixture.get("events") or []
    try:
        elapsed_val = float(elapsed) if elapsed is not None else None
    except (TypeError, ValueError):
        elapsed_val = None

    home_shots_on = _stat_value(statistics, home_id, "Shots on Goal") or 0.0
    away_shots_on = _stat_value(statistics, away_id, "Shots on Goal") or 0.0
    home_total_shots = _stat_value(statistics, home_id, "Total Shots") or 0.0
    away_total_shots = _stat_value(statistics, away_id, "Total Shots") or 0.0
    home_dangerous = _stat_value(statistics, home_id, "Dangerous Attacks") or 0.0
    away_dangerous = _stat_value(statistics, away_id, "Dangerous Attacks") or 0.0
    home_attacks = _stat_value(statistics, home_id, "Attacks") or 0.0
    away_attacks = _stat_value(statistics, away_id, "Attacks") or 0.0
    home_xg = (
        _stat_value(statistics, home_id, "Expected Goals")
        or _stat_value(statistics, home_id, "xG")
        or 0.0
    )
    away_xg = (
        _stat_value(statistics, away_id, "Expected Goals")
        or _stat_value(statistics, away_id, "xG")
        or 0.0
    )
    home_possession = _stat_value(statistics, home_id, "Ball Possession")
    away_possession = _stat_value(statistics, away_id, "Ball Possession")
    home_passes = _stat_value(statistics, home_id, "Passes accurate")
    away_passes = _stat_value(statistics, away_id, "Passes accurate")
    home_corners = _stat_value(statistics, home_id, "Corner Kicks")
    away_corners = _stat_value(statistics, away_id, "Corner Kicks")
    home_fouls = _stat_value(statistics, home_id, "Fouls")
    away_fouls = _stat_value(statistics, away_id, "Fouls")
    home_yellow = _stat_value(statistics, home_id, "Yellow Cards")
    away_yellow = _stat_value(statistics, away_id, "Yellow Cards")
    home_big_chances = _stat_value(statistics, home_id, "Big Chances")
    away_big_chances = _stat_value(statistics, away_id, "Big Chances")

    total_shots_on = home_shots_on + away_shots_on
    total_shots = home_total_shots + away_total_shots
    total_dangerous = home_dangerous + away_dangerous
    total_attacks = home_attacks + away_attacks
    total_xg = home_xg + away_xg

    recent_events = 0
    last_event_elapsed: Optional[float] = None
    if elapsed_val is not None:
        threshold = max(0.0, elapsed_val - 10.0)
        for event in events:
            time_block = event.get("time") or {}
            try:
                event_minute = float(time_block.get("elapsed") or 0)
            except (TypeError, ValueError):
                continue
            if last_event_elapsed is None or event_minute > last_event_elapsed:
                last_event_elapsed = event_minute
            if event_minute >= threshold:
                event_type = str(event.get("type") or "").lower()
                detail = str(event.get("detail") or "").lower()
                if event_type in {"goal", "shot", "dangerous attack"} or "shot" in detail:
                    recent_events += 1

    pressure_score = 0.0
    if total_shots_on >= 7:
        pressure_score += 0.25
    if total_shots >= 18:
        pressure_score += 0.20
    if total_dangerous >= 45 or total_attacks >= 140:
        pressure_score += 0.20
    if total_xg >= 2.4:
        pressure_score += 0.20
    if recent_events >= 4:
        pressure_score += 0.15
    if elapsed_val is not None and elapsed_val >= 75 and total_shots_on >= 5:
        pressure_score += 0.10
    pressure_score = max(0.0, min(1.0, pressure_score))

    if pressure_score >= 0.75:
        label = "Tres elevee"
    elif pressure_score >= 0.5:
        label = "Elevee"
    elif pressure_score >= 0.3:
        label = "Moderee"
    else:
        label = "Calme"

    return {
        "score": pressure_score,
        "label": label,
        "shots_on_target": int(total_shots_on),
        "total_shots": int(total_shots),
        "dangerous_attacks": int(total_dangerous),
        "recent_events": recent_events,
        "xg_total": round(total_xg, 2),
        "shots_on_target_home": int(home_shots_on),
        "shots_on_target_away": int(away_shots_on),
        "total_shots_home": int(home_total_shots),
        "total_shots_away": int(away_total_shots),
        "ball_possession_home": home_possession,
        "ball_possession_away": away_possession,
        "passes_accurate_home": home_passes,
        "passes_accurate_away": away_passes,
        "corners_home": home_corners,
        "corners_away": away_corners,
        "fouls_home": home_fouls,
        "fouls_away": away_fouls,
        "yellow_cards_home": home_yellow,
        "yellow_cards_away": away_yellow,
        "big_chances_home": home_big_chances,
        "big_chances_away": away_big_chances,
        "xg_home": round(home_xg, 2),
        "xg_away": round(away_xg, 2),
        "last_event_elapsed": last_event_elapsed,
    }


def _statistics_dataframe(stats_payload: List[Dict[str, Any]]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for entry in stats_payload or []:
        if not isinstance(entry, dict):
            continue
        team = entry.get("team") or {}
        team_name = team.get("name", "Equipe")
        row: Dict[str, Any] = {"Equipe": team_name}
        for item in entry.get("statistics") or []:
            if not isinstance(item, dict):
                continue
            stat_name = str(item.get("type") or "").strip()
            if not stat_name:
                continue
            value = item.get("value")
            if value in {None, "", "-"}:
                row[stat_name] = "-"
            else:
                row[stat_name] = value
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    cols = ["Equipe"] + [col for col in df.columns if col != "Equipe"]
    df = df[cols]
    return df


def _core_live_stat_rows(
    statistics: List[Dict[str, Any]],
    home_id: Optional[Any],
    away_id: Optional[Any],
    home_label: str,
    away_label: str,
) -> List[Dict[str, str]]:
    metrics = [
        ("Tirs cadrés", "Shots on Goal", "int"),
        ("Tirs totaux", "Total Shots", "int"),
        ("xG cumulés", "Expected Goals", "float"),
        ("Passes réussies", "Passes accurate", "int"),
        ("Possession", "Ball Possession", "pct"),
        ("Corners", "Corner Kicks", "int"),
        ("Fautes", "Fouls", "int"),
        ("Cartons jaunes", "Yellow Cards", "int"),
        ("Big chances", "Big Chances", "int"),
    ]

    def _safe_team_id(raw: Optional[Any]) -> Optional[int]:
        try:
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    home_team_id = _safe_team_id(home_id)
    away_team_id = _safe_team_id(away_id)

    def _format(value: Optional[float], kind: str) -> str:
        if value is None:
            return "-"
        if kind == "pct":
            return f"{value * 100:.0f}%"
        if kind == "float":
            return f"{value:.2f}"
        if abs(value - int(value)) < 1e-6:
            return str(int(value))
        return f"{value:.2f}"

    rows: List[Dict[str, str]] = []
    for label, stat_key, kind in metrics:
        home_value = _stat_value(statistics, home_team_id, stat_key) if home_team_id is not None else None
        away_value = _stat_value(statistics, away_team_id, stat_key) if away_team_id is not None else None
        if home_value is None and away_value is None:
            continue
        rows.append(
            {
                "Statistique": label,
                home_label: _format(home_value, kind),
                away_label: _format(away_value, kind),
            }
        )
    return rows


def _format_delta(seconds: float) -> str:
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def _api_probability_snapshot(fixture_id: int) -> Dict[str, float]:
    try:
        predictions = get_predictions(int(fixture_id)) or []
    except Exception:
        return {}
    if not predictions:
        return {}
    entry = predictions[0] if isinstance(predictions, list) else predictions
    prediction = entry.get("prediction") or {}
    percent = prediction.get("percent") or {}
    return {
        "home": _percent_to_float(percent.get("home")),
        "draw": _percent_to_float(percent.get("draw")),
        "away": _percent_to_float(percent.get("away")),
    }


def _percent_to_float(value: Any) -> float:
    if value in {None, ""}:
        return 0.0
    try:
        return float(str(value).replace("%", "").replace(",", ".")) / 100.0
    except (TypeError, ValueError):
        return 0.0


def _confidence_from_probability(prob: float) -> int:
    return max(30, min(100, int(round(prob * 100))))


def _format_percentage(prob: float) -> str:
    return f"{prob * 100:.0f}%"


def _recent_bet_streak(
    *,
    loss_threshold: int = 4,
    win_threshold: int = 5,
) -> Optional[Tuple[str, int]]:
    try:
        history = load_prediction_history()
    except Exception:
        return None
    if history.empty:
        return None
    df = history.copy()
    mask = df.get("bet_selection", pd.Series(dtype=str)).fillna("").astype(str).str.strip() != ""
    confirmed = df[mask]
    if confirmed.empty:
        return None
    ts_series = confirmed.get("bet_timestamp")
    if ts_series is None:
        ts_series = pd.Series(index=confirmed.index, dtype=object)
    for column in ("fixture_date", "timestamp"):
        candidate = confirmed.get(column)
        if candidate is None:
            continue
        ts_series = ts_series.fillna(candidate)
    confirmed = confirmed.assign(__ts=pd.to_datetime(ts_series, errors="coerce"))
    confirmed["__ts"] = confirmed["__ts"].fillna(pd.Timestamp.utcnow())
    confirmed.sort_values("__ts", inplace=True)
    results: List[str] = []
    for _, row in confirmed.iterrows():
        result = str(row.get("bet_result") or "").strip().lower()
        if not result:
            success_value = row.get("success")
            if pd.notna(success_value):
                result = "win" if bool(success_value) else "loss"
        if result in {"win", "loss"}:
            results.append(result)
        elif result == "void":
            continue
    if not results:
        return None
    current = results[-1]
    count = 1
    for previous in reversed(results[:-1]):
        if previous == current:
            count += 1
        else:
            break
    if current == "loss" and count >= loss_threshold:
        return ("loss", count)
    if current == "win" and count >= win_threshold:
        return ("win", count)
    return None


def _evaluate_over_under_filters(
    filters: Dict[str, Any],
    markets: Mapping[str, Any],
    intensity_snapshot: Mapping[str, Any],
) -> List[str]:
    messages: List[str] = []
    over_cfg = filters.get("over") or {}
    if over_cfg.get("enabled"):
        thresholds: Dict[str, float] = over_cfg.get("thresholds", {})
        label_map = {
            "over_1_5": "Over 1.5",
            "over_2_5": "Over 2.5",
            "over_3_5": "Over 3.5",
        }
        for key, min_pct in thresholds.items():
            if min_pct is None:
                continue
            prob = float(markets.get(key, 0.0) or 0.0) * 100.0
            if prob < float(min_pct):
                label = label_map.get(key, key.replace("_", " ").title())
                messages.append(f"{label} estimé à {prob:.1f}% (< {min_pct}%).")
    under_cfg = filters.get("under") or {}
    if under_cfg.get("enabled"):
        min_prob = under_cfg.get("min_prob")
        prob_under = float(markets.get("under_2_5", max(0.0, 1.0 - float(markets.get("over_2_5", 0.0) or 0.0)))) * 100.0
        if min_prob is not None and prob_under < float(min_prob):
            messages.append(f"Under 2.5 estimé à {prob_under:.1f}% (< {min_prob}%).")
        if under_cfg.get("limit_intensity"):
            max_intensity = float(under_cfg.get("max_intensity", 65))
            current_intensity = float(intensity_snapshot.get("score") or 0.0)
            if current_intensity > max_intensity:
                messages.append(
                    f"Intensité {current_intensity:.0f}/100 supérieure au plafond {max_intensity:.0f}/100 pour jouer un Under."
                )
    return messages


def _bet_state_key(fixture_id: Any, label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or "selection"
    return f"bet_{fixture_id}_{slug}"


def _bet_tracker() -> Dict[str, bool]:
    storage = st.session_state.setdefault("bet_tracker", {})
    if not isinstance(storage, dict):
        storage = {}
        st.session_state["bet_tracker"] = storage
    return storage


def _combo_cart() -> Dict[str, Dict[str, Any]]:
    cart = st.session_state.setdefault("combo_cart", {})
    if not isinstance(cart, dict):
        cart = {}
        st.session_state["combo_cart"] = cart
    return cart


def _combo_state_key(fixture_id: Any, label: str) -> str:
    slug = _bet_state_key(fixture_id, label).replace("bet_", "", 1)
    return f"combo_{slug}"


def _add_to_combo(selection_key: str, entry: Dict[str, Any]) -> None:
    cart = _combo_cart()
    cart[selection_key] = entry
    st.session_state["combo_cart"] = cart


def _remove_from_combo(selection_key: str) -> None:
    cart = _combo_cart()
    if selection_key in cart:
        del cart[selection_key]
        st.session_state["combo_cart"] = cart
    if selection_key in st.session_state:
        st.session_state.pop(selection_key, None)


def _render_combo_cart(bankroll_settings: BankrollSettings) -> None:
    cart = _combo_cart()
    st.subheader("Panier combinÃ©")
    if not cart:
        st.caption("Ajoute des paris depuis les matches pour construire un ticket combinÃ©.")
        return

    selections = list(cart.items())
    odds = [entry["odd"] for _, entry in selections if entry.get("odd")]
    probs = [entry["probability"] for _, entry in selections if entry.get("probability") is not None]

    combined_odd = math.prod(odds) if odds else None
    combined_prob = math.prod(probs) if probs else None
    combined_prob_pct = combined_prob * 100 if combined_prob is not None else None

    metric_cols = st.columns(3)
    if combined_odd is not None:
        metric_cols[0].metric("Cote combinÃ©e", f"{combined_odd:.2f}")
    if combined_prob_pct is not None:
        metric_cols[1].metric("ProbabilitÃ© estimÃ©e", f"{combined_prob_pct:.1f}%")
    if combined_prob is not None and combined_odd is not None:
        staking = suggest_stake(combined_prob, combined_odd, bankroll_settings)
        metric_cols[2].metric(
            "Mise suggÃ©rÃ©e",
            f"{staking['stake']:.2f} EUR",
            help="Calcul basÃ© sur ta stratÃ©gie bankroll.",
        )

        combo_comment = _stake_comment(staking, bankroll_settings)
        if combo_comment:
            metric_cols[2].caption(combo_comment)
    for selection_key, entry in selections:
        cols = st.columns([3, 1, 1])
        with cols[0]:
            st.markdown(f"**{entry.get('match_label', 'Match')}**")
            prob_value = entry.get("probability")
            prob_text = f"{prob_value * 100:.1f}%" if prob_value is not None else "-"
            meta = f"Cote {entry.get('odd', 1.0):.2f} | Proba {prob_text}"
            kickoff = entry.get("fixture_date")
            if kickoff:
                meta += f" | {kickoff}"
            st.caption(f"{entry['label']} â€” {meta}")
        with cols[2]:
            if st.button("Retirer", key=f"remove_{selection_key}"):
                _remove_from_combo(selection_key)
                st.experimental_rerun()

    if st.button("Vider le combinÃ©", key="combo_reset"):
        for selection_key, _ in list(selections):
            _remove_from_combo(selection_key)
        st.experimental_rerun()


def _tip_outcome_state(
    label: str,
    status: Dict[str, Any],
    home_name: str,
    away_name: str,
) -> str:
    label_low = (label or "").lower()
    home_low = (home_name or "").lower()
    away_low = (away_name or "").lower()
    home_goals = int(status.get("home_goals") or 0)
    away_goals = int(status.get("away_goals") or 0)
    total_goals = home_goals + away_goals

    def _home_victory_state() -> str:
        if home_goals > away_goals:
            return "winning"
        if home_goals < away_goals:
            return "losing"
        return "open"

    def _away_victory_state() -> str:
        if away_goals > home_goals:
            return "winning"
        if away_goals < home_goals:
            return "losing"
        return "open"

    if label_low.startswith("victoire "):
        if home_low and home_low in label_low:
            return _home_victory_state()
        if away_low and away_low in label_low:
            return _away_victory_state()

    if label_low.startswith("double chance"):
        if "1x" in label_low:
            if home_goals >= away_goals:
                return "winning"
            return "losing"
        if "x2" in label_low:
            if away_goals >= home_goals:
                return "winning"
            return "losing"
        if "12" in label_low:
            if home_goals != away_goals:
                return "winning"
            return "open"

    if label_low.startswith("draw no bet"):
        if home_low and home_low in label_low:
            return _home_victory_state()
        if away_low and away_low in label_low:
            return _away_victory_state()

    over_match = re.search(r"over\s+([0-9]+(?:\.[0-9])?)", label_low)
    if over_match:
        threshold = float(over_match.group(1))
        if total_goals > threshold:
            return "winning"
        return "open"

    under_match = re.search(r"under\s+([0-9]+(?:\.[0-9])?)", label_low)
    if under_match:
        threshold = float(under_match.group(1))
        if total_goals > threshold:
            return "losing"
        return "open"

    if "btts : non" in label_low:
        if home_goals > 0 and away_goals > 0:
            return "losing"
        return "open"
    if "les deux equipes marquent" in label_low or ("btts" in label_low and "non" not in label_low):
        if home_goals > 0 and away_goals > 0:
            return "winning"
        return "open"

    if label_low.startswith("mi-temps : victoire"):
        if home_low and home_low in label_low:
            return _home_victory_state()
        if away_low and away_low in label_low:
            return _away_victory_state()
        return "open"

    if label_low.startswith("mi-temps : match nul"):
        if home_goals == away_goals:
            return "winning"
        return "losing"

    return "open"


def _scoreline_probability(
    projection_matrix: Optional[List[List[float]]],
    status: Dict[str, Any],
    final_home: int,
    final_away: int,
) -> Optional[float]:
    if projection_matrix is None:
        return None
    try:
        current_home = int(status.get("home_goals", 0) or 0)
        current_away = int(status.get("away_goals", 0) or 0)
    except Exception:
        current_home = current_away = 0
    add_home = final_home - current_home
    add_away = final_away - current_away
    if add_home < 0 or add_away < 0:
        return 0.0
    if add_home >= len(projection_matrix):
        return None
    row = projection_matrix[add_home]
    if add_away >= len(row):
        return None
    try:
        return float(row[add_away])
    except (TypeError, ValueError):
        return None


def _live_probability_for_tip(
    tip: Dict[str, Any],
    markets: Dict[str, Any],
    status: Dict[str, Any],
    projection_matrix: Optional[List[List[float]]],
    home_name: str,
    away_name: str,
) -> Tuple[Optional[float], str]:
    label = (tip.get("label") or "").strip()
    if not label:
        return None, "unknown"
    label_low = label.lower()
    home_low = (home_name or "").lower()
    away_low = (away_name or "").lower()

    def market_prob(key: str) -> Optional[float]:
        try:
            value = markets.get(key)
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None

    if label_low.startswith("victoire "):
        if home_low and home_low in label_low:
            return market_prob("home"), "1x2"
        if away_low and away_low in label_low:
            return market_prob("away"), "1x2"
    if label_low.startswith("match nul") or label_low == "nul":
        return market_prob("draw"), "1x2"

    if label_low.startswith("double chance 1x"):
        prob_home = market_prob("home") or 0.0
        prob_draw = market_prob("draw") or 0.0
        return prob_home + prob_draw, "double_chance"
    if label_low.startswith("double chance x2"):
        prob_away = market_prob("away") or 0.0
        prob_draw = market_prob("draw") or 0.0
        return prob_away + prob_draw, "double_chance"
    if label_low.startswith("double chance 12"):
        prob_home = market_prob("home") or 0.0
        prob_away = market_prob("away") or 0.0
        return prob_home + prob_away, "double_chance"

    if label_low.startswith("draw no bet"):
        if home_low and home_low in label_low:
            return market_prob("home"), "dnb"
        if away_low and away_low in label_low:
            return market_prob("away"), "dnb"

    over_match = re.search(r"over\s+([0-9]+(?:\.[0-9])?)", label_low)
    if over_match:
        threshold = over_match.group(1).replace(".", "_")
        prob = market_prob(f"over_{threshold}")
        if prob is not None:
            return prob, "over"
    under_match = re.search(r"under\s+([0-9]+(?:\.[0-9])?)", label_low)
    if under_match:
        threshold = under_match.group(1).replace(".", "_")
        prob = market_prob(f"under_{threshold}")
        if prob is not None:
            return prob, "under"

    if label_low.startswith("over 1.5 buts "):
        if home_low and home_low in label_low:
            return market_prob("home_over_1_5"), "team_total"
        if away_low and away_low in label_low:
            return market_prob("away_over_1_5"), "team_total"

    if "les deux equipes marquent" in label_low or ("btts" in label_low and "non" not in label_low):
        prob = market_prob("btts_yes")
        if prob is not None:
            return prob, "btts_yes"
    if label_low.startswith("btts : non") or "btts : non" in label_low:
        prob = market_prob("btts_no")
        if prob is not None:
            return prob, "btts_no"
    if "btts + over 2.5" in label_low or "btts & over 2.5" in label_low:
        prob = market_prob("btts_yes_over_2_5")
        if prob is not None:
            return prob, "combo"

    if "handicap -1" in label_low:
        if home_low and home_low in label_low:
            return market_prob("home_win_by_2"), "handicap"
        if away_low and away_low in label_low:
            return market_prob("away_win_by_2"), "handicap"

    if label_low.startswith("mi-temps/fin"):
        suffix = label[len("Mi-temps/Fin"):].strip()
        if "/" in suffix:
            ht_part, ft_part = [part.strip().lower() for part in suffix.split("/", 1)]

            def resolve(segment: str) -> Optional[str]:
                if not segment:
                    return None
                if segment.startswith("nul") or segment.startswith("draw"):
                    return "N"
                if home_low and (segment.startswith(home_low) or home_low.startswith(segment)):
                    return "1"
                if away_low and (segment.startswith(away_low) or away_low.startswith(segment)):
                    return "2"
                return None

            ht_token = resolve(ht_part)
            ft_token = resolve(ft_part)
            if ht_token and ft_token:
                prob = market_prob(f"htft_{ht_token}/{ft_token}")
                if prob is not None:
                    return prob, "htft"

    if label_low.startswith("score exact"):
        match = re.search(r"(\d+)\s*[-â€“]\s*(\d+)", label_low)
        if match:
            final_home = int(match.group(1))
            final_away = int(match.group(2))
            prob = _scoreline_probability(projection_matrix, status, final_home, final_away)
            if prob is not None:
                return prob, "score_exact"

    return None, "unknown"


def _cashout_recommendations(
    tips: List[Dict[str, Any]],
    tip_meta: Dict[str, Dict[str, Any]],
    status: Dict[str, Any],
    home_name: str,
    away_name: str,
    markets: Dict[str, Any],
    projection_matrix: Optional[List[List[float]]],
    pressure: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    if status.get("short") not in LIVE_STATUS_CODES:
        return []
    recommendations: List[Dict[str, Any]] = []
    elapsed_raw = status.get("elapsed")
    try:
        elapsed = float(elapsed_raw) if elapsed_raw is not None else 0.0
    except (TypeError, ValueError):
        elapsed = 0.0
    pressure_score = 0.0
    pressure_label = ""
    if pressure:
        try:
            pressure_score = float(pressure.get("score", 0.0) or 0.0)
        except (TypeError, ValueError):
            pressure_score = 0.0
        pressure_label = str(pressure.get("label") or "")

    for tip in tips[:8]:
        meta = tip_meta.get(tip["label"])
        if not meta:
            continue
        odd = float(meta.get("odd") or 1.0)
        base_prob = float(tip.get("probability", 0.0) or 0.0)
        live_prob, tip_kind = _live_probability_for_tip(
            tip,
            markets,
            status,
            projection_matrix,
            home_name,
            away_name,
        )
        prob = live_prob if live_prob is not None else base_prob
        prob = max(0.0, min(1.0, prob))
        outcome = _tip_outcome_state(tip["label"], status, home_name, away_name)
        expected_ev = prob * (odd - 1.0) - (1.0 - prob)
        risk_remaining = max(0.0, 1.0 - prob)
        if pressure_score > 0 and tip_kind == "under":
            prob = max(0.0, min(1.0, prob * (1.0 - 0.25 * pressure_score)))
            expected_ev = prob * (odd - 1.0) - (1.0 - prob)

        action = "hold"
        reason = (
            f"Probabilite live {prob * 100:.1f}% | cote {odd:.2f} | minute {int(elapsed)}."
        )
        if pressure_score >= 0.6:
            reason += f" Pression {pressure_label or 'elevee'}."

        if outcome == "losing":
            action = "cashout"
            reason += " Score contraire : limiter la casse."
        elif expected_ev < -0.05:
            action = "cashout"
            reason += f" Valeur attendue negative ({expected_ev * 100:.1f}%)."
        elif prob < 0.35:
            action = "cashout"
            reason += " Probabilite < 35%, mieux vaut encaisser."
        else:
            decisive_cashout = False
            if elapsed >= 80:
                if tip_kind in {"under", "score_exact"} and risk_remaining > 0.08:
                    action = "cashout"
                    reason += (
                        f" Dernieres minutes : risque residuel {risk_remaining * 100:.1f}%."
                    )
                    decisive_cashout = True
                elif odd >= 3.0 and prob > 0.6:
                    action = "cashout"
                    reason += " Fin de match : securise un gain important."
                    decisive_cashout = True
            if (
                not decisive_cashout
                and tip_kind == "score_exact"
                and elapsed >= 70
                and odd >= 4.0
                and prob > 0.5
            ):
                action = "cashout"
                reason += " Score exact fragile : encaisse le profit."
                decisive_cashout = True
            if (
                not decisive_cashout
                and tip_kind == "under"
                and elapsed >= 80
                and prob > 0.6
                and odd >= 2.0
            ):
                action = "cashout"
                reason += " Under en jeu : un but tardif annulerait le pari."
                decisive_cashout = True
            if (
                not decisive_cashout
                and tip_kind == "under"
                and pressure_score >= 0.6
                and elapsed >= 70
            ):
                action = "cashout"
                reason += " Pression offensive tres elevee, la securite prime."
                decisive_cashout = True
            if not decisive_cashout and expected_ev >= -0.05:
                reason += " Maintien recommande."

        recommendations.append(
            {
                "label": tip["label"],
                "action": action,
                "reason": reason,
            }
        )
    return recommendations

def _match_intensity_score_with_weights(
    home_lambda: float,
    away_lambda: float,
    markets: Dict[str, float],
    *,
    weights: Optional[Dict[str, float]],
    is_live: bool = False,
) -> Dict[str, Any]:
    total_xg = max(home_lambda + away_lambda, 0.0)
    prob_over = float(markets.get("over_2_5", 0.0) or 0.0)
    prob_btts = float(markets.get("btts_yes", 0.0) or 0.0)
    pace_factor = min(total_xg / 3.2, 1.0)
    weights = weights or {"xg": 0.45, "over": 0.35, "btts": 0.20}
    total_weight = sum(weights.values()) or 1.0
    normalized = {key: max(0.0, value) / total_weight for key, value in weights.items()}
    raw = (
        (pace_factor * normalized.get("xg", 0.45))
        + (prob_over * normalized.get("over", 0.35))
        + (prob_btts * normalized.get("btts", 0.20))
    )
    if is_live:
        raw = min(raw + 0.05, 1.0)
    clamped = max(0.0, min(raw, 1.0))
    score = int(round(clamped * 100))
    if score >= 75:
        label = "Tres eleve"
        comment = "Rythme attendu tres fort, nombreuses occasions."
    elif score >= 55:
        label = "Eleve"
        comment = "Match qui devrait generer des opportunites."
    elif score >= 40:
        label = "Modere"
        comment = "Intensite moyenne, variance moderee."
    else:
        label = "Faible"
        comment = "Profil prudent ou defenses solides."
    return {
        "score": score,
        "label": label,
        "total_xg": total_xg,
        "prob_over": prob_over,
        "prob_btts": prob_btts,
        "comment": comment,
    }


def _match_intensity_score(
    home_lambda: float,
    away_lambda: float,
    markets: Dict[str, float],
    *,
    is_live: bool = False,
) -> Dict[str, Any]:
    return _match_intensity_score_with_weights(
        home_lambda,
        away_lambda,
        markets,
        weights=None,
        is_live=is_live,
    )

ODDS_MARKET_MAIN = {"1x2", "match winner", "match result", "fulltime result"}
ODDS_MARKET_DOUBLE = {"double chance"}
ODDS_MARKET_TOTAL = {"over/under", "over under", "total goals"}
ODDS_MARKET_BTTS = {"both teams to score", "btts"}
ODDS_MARKET_BTTS_TOTAL = {"both teams to score & total goals", "btts & total", "btts and total goals"}
ODDS_MARKET_DRAW_NO_BET = {"draw no bet", "dnb"}
ODDS_MARKET_HANDICAP = {"handicap", "asian handicap", "handicap result"}
ODDS_MARKET_TEAM_TOTAL = {"team total goals", "team goals", "goals over/under"}
ODDS_MARKET_CLEAN_SHEET = {"clean sheet", "to keep a clean sheet", "team clean sheet"}
ODDS_MARKET_EXACT_SCORE = {"exact score", "correct score", "score exact"}


def _normalize_odds_key(market: str, label: str) -> Optional[str]:
    market = (market or "").lower()
    label = (label or "").lower()
    normalized = label.replace(",", ".")
    compressed = normalized.replace(" ", "")
    tokens = {token for token in re.split(r"[^a-z0-9]+", normalized) if token}

    def has_threshold(value: str) -> bool:
        return value in normalized
    has_over = bool({"over", "plus", "sup"} & tokens) or "over" in normalized
    has_under = bool({"under", "moins", "inf"} & tokens) or "under" in normalized
    if market in ODDS_MARKET_MAIN:
        if {"1", "home", "local", "w1"} & tokens:
            return "1"
        if tokens & {"x", "draw", "tie", "d"}:
            return "x"
        if {"2", "away", "visitor", "w2"} & tokens:
            return "2"
    if market in ODDS_MARKET_DOUBLE:
        if compressed in {"1x", "1/x", "1-x"}:
            return "1x"
        if compressed in {"x2", "x/2", "x-2"}:
            return "x2"
        if compressed in {"12", "1/2", "1-2"}:
            return "12"
    if market in ODDS_MARKET_TOTAL or market in ODDS_MARKET_TEAM_TOTAL:
        if has_over:
            if has_threshold("1.5"):
                if market in ODDS_MARKET_TEAM_TOTAL:
                    if {"home", "1", "w1"} & tokens:
                        return "home_over_1_5"
                    if {"away", "2", "w2"} & tokens:
                        return "away_over_1_5"
                return "over_1_5"
            if has_threshold("2.5"):
                return "over_2_5"
            if has_threshold("3.5"):
                return "over_3_5"
        if has_under:
            if has_threshold("1.5"):
                return "under_1_5"
            if has_threshold("2.5"):
                return "under_2_5"
            if has_threshold("3.5"):
                return "under_3_5"
    if market in ODDS_MARKET_BTTS:
        if {"yes", "oui"} & tokens:
            return "btts_yes"
        if {"no", "non"} & tokens:
            return "btts_no"
    if market in ODDS_MARKET_BTTS_TOTAL:
        if has_threshold("2.5") and ({"yes", "oui"} & tokens):
            return "btts_yes_over_2_5"
    if market in ODDS_MARKET_DRAW_NO_BET or "drawnobet" in compressed or tokens & {"dnb"}:
        if {"1", "home", "w1"} & tokens:
            return "home_draw_no_bet"
        if {"2", "away", "w2"} & tokens:
            return "away_draw_no_bet"
    if market in ODDS_MARKET_HANDICAP and any(edge in compressed for edge in {"-1", "-1.0"}):
        if {"1", "home", "w1"} & tokens:
            return "home_win_by_2"
        if {"2", "away", "w2"} & tokens:
            return "away_win_by_2"
    if market in ODDS_MARKET_CLEAN_SHEET or "cleansheet" in compressed:
        if not ({"yes", "oui"} & tokens):
            return None
        if {"1", "home", "w1"} & tokens or "home" in normalized:
            return "clean_sheet_home"
        if {"2", "away", "w2"} & tokens or "away" in normalized:
            return "clean_sheet_away"
    if ("btts" in normalized or "both teams" in normalized) and "over" in normalized and has_threshold("2.5"):
        return "btts_yes_over_2_5"
    if "half time" in normalized or "mi-temps" in normalized or "ht/ft" in normalized:
        tokens = normalized.split()
        ht = ft = None
        if "1/1" in raw_label or "home/home" in normalized:
            ht, ft = "1", "1"
        elif "1/x" in normalized or "home/draw" in normalized:
            ht, ft = "1", "N"
        elif "1/2" in normalized or "home/away" in normalized:
            ht, ft = "1", "2"
        elif "x/1" in normalized or "draw/home" in normalized or "n/1" in normalized:
            ht, ft = "N", "1"
        elif ("x/x" in normalized or "draw/draw" in normalized or "n/n" in normalized):
            ht, ft = "N", "N"
        elif ("x/2" in normalized or "draw/away" in normalized or "n/2" in normalized):
            ht, ft = "N", "2"
        elif "2/1" in normalized or "away/home" in normalized:
            ht, ft = "2", "1"
        elif "2/x" in normalized or "away/draw" in normalized:
            ht, ft = "2", "N"
        elif "2/2" in normalized or "away/away" in normalized:
            ht, ft = "2", "2"
        if ht and ft:
            return f"htft_{ht}/{ft}"
    if any(tag in market for tag in ODDS_MARKET_EXACT_SCORE):
        if any(segment in market for segment in {"first half", "1st half", "second half", "2nd half"}):
            return None
        match = re.search(r"(\d+)\s*[:\-\u2013\u2014]\s*(\d+)", normalized)
        if match:
            home_score = match.group(1)
            away_score = match.group(2)
            return f"score_exact_{home_score}_{away_score}"
    return None


def _best_fixture_odds(fixture_id: int) -> Dict[str, float]:
    payload = get_odds_by_fixture(fixture_id) or []
    best: Dict[str, float] = {}
    entries = payload if isinstance(payload, list) else [payload]
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for bookmaker in entry.get("bookmakers") or []:
            if not isinstance(bookmaker, dict):
                continue
            for bet in bookmaker.get("bets") or []:
                if not isinstance(bet, dict):
                    continue
                market = str(bet.get("name", "")).strip().lower()
                for value in bet.get("values") or []:
                    raw_label = str(value.get("value", "")).strip()
                    key = _normalize_odds_key(market, raw_label)
                    if not key:
                        continue
                    try:
                        odd = float(value.get("odd"))
                    except (TypeError, ValueError):
                        continue
                    current = best.get(key)
                    if current is None or odd > current:
                        best[key] = odd
    home_odd = best.get("1")
    draw_odd = best.get("x")
    away_odd = best.get("2")

    def implied(odd: Optional[float]) -> Optional[float]:
        if odd is None:
            return None
        try:
            odd_f = float(odd)
        except (TypeError, ValueError):
            return None
        if odd_f <= 0:
            return None
        return 1.0 / odd_f

    ph = implied(home_odd)
    pd = implied(draw_odd)
    pa = implied(away_odd)

    def add_combined(key: str, value: Optional[float]) -> None:
        if key in best:
            return
        if value is None or value <= 0:
            return
        best[key] = round(value, 4)

    if ph and pd:
        add_combined("1x", 1.0 / (ph + pd))
    if pd and pa:
        add_combined("x2", 1.0 / (pd + pa))
    if ph and pa:
        add_combined("12", 1.0 / (ph + pa))
        add_combined("home_draw_no_bet", (ph + pa) / ph)
        add_combined("away_draw_no_bet", (ph + pa) / pa)
    return best


def _odds_for_tip(
    tip: Dict[str, Any],
    odds_map: Dict[str, float],
    home_name: str,
    away_name: str,
) -> Optional[float]:
    label = (tip.get("label", "") or "").lower()
    normalized = label.replace("ï¿½", "e")
    home_name = (home_name or "").lower()
    away_name = (away_name or "").lower()

    def matches_team(team: str) -> bool:
        team = (team or "").lower()
        return bool(team and team in normalized)

    if label.startswith("victoire ") and "double" not in label:
        if matches_team(home_name):
            return odds_map.get("1")
        if matches_team(away_name):
            return odds_map.get("2")
    if label.startswith("match nul") or label == "nul":
        return odds_map.get("x")
    if label.startswith("double chance 1x"):
        return odds_map.get("1x")
    if label.startswith("double chance x2"):
        return odds_map.get("x2")
    if label.startswith("double chance 12"):
        return odds_map.get("12")
    if label.startswith("draw no bet"):
        if matches_team(home_name) or label.rstrip().endswith("1"):
            return odds_map.get("home_draw_no_bet")
        if matches_team(away_name) or label.rstrip().endswith("2"):
            return odds_map.get("away_draw_no_bet")
    if label.startswith("over 1.5 buts "):
        if matches_team(home_name):
            return odds_map.get("home_over_1_5")
        if matches_team(away_name):
            return odds_map.get("away_over_1_5")
    if label.startswith("over 1.5"):
        return odds_map.get("over_1_5")
    if label.startswith("under 1.5"):
        return odds_map.get("under_1_5")
    if label.startswith("over 2.5"):
        return odds_map.get("over_2_5")
    if label.startswith("under 2.5"):
        return odds_map.get("under_2_5")
    if label.startswith("over 3.5"):
        return odds_map.get("over_3_5")
    if label.startswith("under 3.5"):
        return odds_map.get("under_3_5")
    if "handicap -1" in label:
        if matches_team(home_name):
            return odds_map.get("home_win_by_2")
        if matches_team(away_name):
            return odds_map.get("away_win_by_2")
    if "clean sheet" in label:
        if matches_team(home_name):
            return odds_map.get("clean_sheet_home")
        if matches_team(away_name):
            return odds_map.get("clean_sheet_away")
    if "btts + over 2.5" in label or "btts & over 2.5" in label:
        return odds_map.get("btts_yes_over_2_5")
    if "les deux equipes marquent" in label or ("btts" in label and "non" not in label):
        return odds_map.get("btts_yes")
    if label.startswith("btts : non") or "btts : non" in label:
        return odds_map.get("btts_no")
    if label.startswith("mi-temps/fin"):
        suffix = label[len("mi-temps/fin"):].strip()
        if "/" in suffix:
            ht_part, ft_part = [part.strip(" ()") for part in suffix.split("/", 1)]

            def resolve(segment: str) -> Optional[str]:
                if not segment:
                    return None
                if segment.startswith("nul") or segment.startswith("draw") or segment.startswith("n "):
                    return "N"
                if home_name and segment.startswith(home_name):
                    return "1"
                if away_name and segment.startswith(away_name):
                    return "2"
                if home_name and home_name.startswith(segment):
                    return "1"
                if away_name and away_name.startswith(segment):
                    return "2"
                return None

            ht_token = resolve(ht_part.lower())
            ft_token = resolve(ft_part.lower())
            if ht_token and ft_token:
                return odds_map.get(f"htft_{ht_token}/{ft_token}")
    if label.startswith("score exact"):
        match = re.search(r"(\d+)\s*[:\-\u2013\u2014]\s*(\d+)", label)
        if match:
            home_score = match.group(1)
            away_score = match.group(2)
            return odds_map.get(f"score_exact_{home_score}_{away_score}")
        return None
    return None


def _markets_from_matrix(
    matrix: Optional[List[List[float]]],
    current_home: int,
    current_away: int,
) -> Dict[str, float]:
    def _baseline() -> Dict[str, float]:
        total_goals = current_home + current_away
        base = {
            "home": 1.0 if current_home > current_away else 0.0,
            "draw": 1.0 if current_home == current_away else 0.0,
            "away": 1.0 if current_home < current_away else 0.0,
            "over_0_5": 1.0 if total_goals >= 1 else 0.0,
            "over_1_5": 1.0 if total_goals >= 2 else 0.0,
            "over_2_5": 1.0 if total_goals >= 3 else 0.0,
            "over_3_5": 1.0 if total_goals >= 4 else 0.0,
            "btts_yes": 1.0 if current_home > 0 and current_away > 0 else 0.0,
            "home_over_1_5": 1.0 if current_home >= 2 else 0.0,
            "away_over_1_5": 1.0 if current_away >= 2 else 0.0,
            "home_win_by_2": 1.0 if (current_home - current_away) >= 2 else 0.0,
            "away_win_by_2": 1.0 if (current_away - current_home) >= 2 else 0.0,
            "btts_yes_over_2_5": 1.0 if (current_home > 0 and current_away > 0 and total_goals >= 3) else 0.0,
        }
        base["under_0_5"] = 1.0 - base["over_0_5"]
        base["under_1_5"] = 1.0 - base["over_1_5"]
        base["under_2_5"] = 1.0 - base["over_2_5"]
        base["under_3_5"] = 1.0 - base["over_3_5"]
        base["btts_no"] = 1.0 - base["btts_yes"]
        base["ht_home"] = 0.0
        base["ht_draw"] = 0.0
        base["ht_away"] = 0.0
        for combo in ["1/1", "1/N", "1/2", "N/1", "N/N", "N/2", "2/1", "2/N", "2/2"]:
            base[f"htft_{combo}"] = 0.0
        return base

    if matrix is None:
        return _baseline()

    aggregates = {
        "home": 0.0,
        "draw": 0.0,
        "away": 0.0,
        "over_0_5": 0.0,
        "over_1_5": 0.0,
        "over_2_5": 0.0,
        "over_3_5": 0.0,
        "btts_yes": 0.0,
        "home_over_1_5": 0.0,
        "away_over_1_5": 0.0,
        "home_win_by_2": 0.0,
        "away_win_by_2": 0.0,
        "btts_yes_over_2_5": 0.0,
    }
    expected_home = 0.0
    expected_away = 0.0

    for i, row in enumerate(matrix):
        for j, prob in enumerate(row):
            if prob <= 0:
                continue
            final_home = current_home + i
            final_away = current_away + j
            expected_home += final_home * prob
            expected_away += final_away * prob
            total_goals = final_home + final_away
            if final_home > final_away:
                aggregates["home"] += prob
            elif final_home == final_away:
                aggregates["draw"] += prob
            else:
                aggregates["away"] += prob
            if total_goals >= 1:
                aggregates["over_0_5"] += prob
            if total_goals >= 2:
                aggregates["over_1_5"] += prob
            if total_goals >= 3:
                aggregates["over_2_5"] += prob
            if total_goals >= 4:
                aggregates["over_3_5"] += prob
            if final_home > 0 and final_away > 0:
                aggregates["btts_yes"] += prob
                if total_goals >= 3:
                    aggregates["btts_yes_over_2_5"] += prob
            if final_home >= 2:
                aggregates["home_over_1_5"] += prob
            if final_away >= 2:
                aggregates["away_over_1_5"] += prob
            if final_home - final_away >= 2:
                aggregates["home_win_by_2"] += prob
            if final_away - final_home >= 2:
                aggregates["away_win_by_2"] += prob

    aggregates["btts_no"] = 1.0 - aggregates["btts_yes"]
    aggregates["under_0_5"] = 1.0 - aggregates["over_0_5"]
    aggregates["under_1_5"] = 1.0 - aggregates["over_1_5"]
    aggregates["under_2_5"] = 1.0 - aggregates["over_2_5"]
    aggregates["under_3_5"] = 1.0 - aggregates["over_3_5"]

    def _result_token(home: int, away: int) -> str:
        if home > away:
            return "1"
        if home == away:
            return "N"
        return "2"

    def _poisson_row(lmbda: float, limit: int = 4) -> List[float]:
        probs: List[float] = []
        cumulative = 0.0
        for k in range(limit):
            p = poisson_probability(lmbda, k)
            probs.append(p)
            cumulative += p
        tail = max(0.0, 1.0 - cumulative)
        probs.append(tail)
        return probs

    lambda_home = max(0.0, expected_home)
    lambda_away = max(0.0, expected_away)
    half_home = _poisson_row(max(0.0, lambda_home / 2.0))
    half_away = _poisson_row(max(0.0, lambda_away / 2.0))
    second_home = _poisson_row(max(0.0, lambda_home / 2.0))
    second_away = _poisson_row(max(0.0, lambda_away / 2.0))

    halftime_probs = {"ht_home": 0.0, "ht_draw": 0.0, "ht_away": 0.0}
    htft_probs = {f"htft_{combo}": 0.0 for combo in ["1/1", "1/N", "1/2", "N/1", "N/N", "N/2", "2/1", "2/N", "2/2"]}

    for h_ht, p_h_ht in enumerate(half_home):
        for a_ht, p_a_ht in enumerate(half_away):
            p_ht = p_h_ht * p_a_ht
            if p_ht <= 0:
                continue
            ht_token = _result_token(h_ht, a_ht)
            halftime_probs[f"ht_{'home' if ht_token == '1' else 'draw' if ht_token == 'N' else 'away'}"] += p_ht
            for h_2, p_h_2 in enumerate(second_home):
                for a_2, p_a_2 in enumerate(second_away):
                    p_total = p_ht * p_h_2 * p_a_2
                    if p_total <= 0:
                        continue
                    final_home = h_ht + h_2
                    final_away = a_ht + a_2
                    ft_token = _result_token(final_home, final_away)
                    htft_probs[f"htft_{ht_token}/{ft_token}"] += p_total

    aggregates.update(halftime_probs)
    aggregates.update(htft_probs)
    return aggregates


def _probability_edge(probability: float, odds: Optional[float]) -> Optional[float]:
    if odds is None or odds <= 1.0:
        return None
    implied = 1.0 / odds
    return probability - implied


def _betting_tips(
    home_strength: Any,
    away_strength: Any,
    probs: Dict[str, float],
    markets: Dict[str, float],
    *,
    top_scores: Optional[List[Dict[str, Any]]] = None,
    odds_map: Optional[Dict[str, float]] = None,
    over_bias: Optional[float] = None,
) -> List[Dict[str, Any]]:
    odds_snapshot = odds_map or {}
    tips: List[Dict[str, Any]] = []
    seen: set[str] = set()
    MIN_DEFAULT_PROBABILITY = 0.60
    HTFT_MIN_PROBABILITY = max(0.55, MIN_DEFAULT_PROBABILITY - 0.05)
    HTFT_BASELINE = 0.50
    MIN_SCORE_PROBABILITY = 0.05
    EDGE_THRESHOLD = 0.02

    def add_tip(label: str, probability: float, reason: str, *, min_probability: float = MIN_DEFAULT_PROBABILITY) -> None:
        if label in seen or probability <= 0 or probability < min_probability:
            return
        tips.append(
            {
                "label": label,
                "probability": probability,
                "confidence": _confidence_from_probability(probability),
                "reason": reason,
            }
        )
        seen.add(label)

    home_prob = probs.get("home", 0.0)
    draw_prob = probs.get("draw", 0.0)
    away_prob = probs.get("away", 0.0)
    over_prob = markets.get("over_2_5", 0.0)
    under_prob = markets.get("under_2_5", 1.0 - over_prob)
    btts_prob = markets.get("btts_yes", 0.0)
    htft_descriptions = {
        "1": home_strength.name,
        "2": away_strength.name,
        "N": "Nul",
    }

    main_choice = max(
        ("home", home_prob),
        ("draw", draw_prob),
        ("away", away_prob),
        key=lambda item: item[1],
    )

    if main_choice[0] == "home":
        label = f"Victoire {home_strength.name}"
        reason = f"Projection xG {home_strength.lambda_value:.2f} contre {away_strength.lambda_value:.2f}."
    elif main_choice[0] == "away":
        label = f"Victoire {away_strength.name}"
        reason = f"{away_strength.name} affiche {away_strength.lambda_value:.2f} xG attendus."
    else:
        label = "Match nul"
        reason = "Forces proches, scenario equilibre sur le 1X2."

    if main_choice[1] < 0.2:
        reason += " (confiance reduite <20%, verifier contexte)."
    add_tip(label, main_choice[1], reason, min_probability=0.0)

    home_double = home_prob + draw_prob
    away_double = away_prob + draw_prob
    if home_double >= away_double:
        add_tip(
            f"Double chance 1X ({home_strength.name})",
            home_double,
            "Couverture domicile + nul maximise la securite.",
            min_probability=0.5,
        )
    else:
        add_tip(
            f"Double chance X2 ({away_strength.name})",
            away_double,
            "L'equipe exterieure evite souvent la defaite.",
            min_probability=0.5,
        )

    if home_prob >= 0.30:
        add_tip(
            f"Draw no bet {home_strength.name}",
            home_prob,
            "Rembourse si nul, edge leger domicile.",
            min_probability=0.30,
        )
    if away_prob >= 0.30:
        add_tip(
            f"Draw no bet {away_strength.name}",
            away_prob,
            "Rembourse si nul, couverture pour l'exterieur.",
            min_probability=0.30,
        )

    bias = over_bias or 0.0
    adjusted_over = max(0.0, min(1.0, over_prob + bias))
    adjusted_under = max(0.0, min(1.0, under_prob - bias))
    total_norm = adjusted_over + adjusted_under
    if total_norm > 0:
        adjusted_over = adjusted_over / total_norm
        adjusted_under = adjusted_under / total_norm

    over_edge = _probability_edge(adjusted_over, odds_snapshot.get("over_2_5"))
    if over_edge is None:
        over_edge = adjusted_over - 0.52
    under_edge = _probability_edge(adjusted_under, odds_snapshot.get("under_2_5"))
    if under_edge is None:
        under_edge = adjusted_under - 0.52

    total_comment_bits: List[str] = []
    if bias:
        total_comment_bits.append(f"ajustement historique {bias:+.2%}")

    if adjusted_over >= MIN_DEFAULT_PROBABILITY and over_edge >= EDGE_THRESHOLD:
        reason_parts = [
            f"xG projetes {home_strength.lambda_value + away_strength.lambda_value:.2f}"
        ]
        if odds_snapshot.get("over_2_5"):
            reason_parts.append(f"cote {odds_snapshot['over_2_5']:.2f}")
        reason_parts.append(f"value {over_edge*100:.1f}%")
        if total_comment_bits:
            reason_parts.append(" | ".join(total_comment_bits))
        add_tip(
            "Over 2.5 buts",
            adjusted_over,
            ". ".join(reason_parts),
        )
    elif adjusted_under >= MIN_DEFAULT_PROBABILITY and under_edge >= EDGE_THRESHOLD:
        reason_parts = [
            "Projection de buts moderee"
        ]
        if odds_snapshot.get("under_2_5"):
            reason_parts.append(f"cote {odds_snapshot['under_2_5']:.2f}")
        reason_parts.append(f"value {under_edge*100:.1f}%")
        if total_comment_bits:
            reason_parts.append(" | ".join(total_comment_bits))
        add_tip(
            "Under 2.5 buts",
            adjusted_under,
            ". ".join(reason_parts),
        )

    if btts_prob >= 0.5:
        add_tip(
            "Les deux equipes marquent (BTTS)",
            btts_prob,
            "Probabilite notable que chaque equipe marque.",
        )
    else:
        add_tip(
            "BTTS : Non",
            1 - btts_prob,
            "Un camp parait nettement superieur defensivement.",
        )

    combo_prob = markets.get("btts_yes_over_2_5", 0.0)
    if combo_prob and combo_prob >= 0.4:
        add_tip(
            "BTTS + Over 2.5",
            combo_prob,
            "Scenario ouvert : buts des deux camps et total > 2.5.",
        )

    home_team_total = markets.get("home_over_1_5", 0.0)
    if home_team_total and home_team_total >= 0.45:
        add_tip(
            f"Over 1.5 buts {home_strength.name}",
            home_team_total,
            f"{home_strength.name} projette {home_strength.lambda_value:.2f} buts attendus.",
        )
    away_team_total = markets.get("away_over_1_5", 0.0)
    if away_team_total and away_team_total >= 0.45:
        add_tip(
            f"Over 1.5 buts {away_strength.name}",
            away_team_total,
            f"{away_strength.name} projette {away_strength.lambda_value:.2f} buts attendus.",
        )

    if markets.get("home_win_by_2", 0.0) >= 0.35:
        add_tip(
            f"Handicap -1 {home_strength.name}",
            markets["home_win_by_2"],
            "Victoire domicile par au moins deux buts estimee probable.",
        )
    if markets.get("away_win_by_2", 0.0) >= 0.35:
        add_tip(
            f"Handicap -1 {away_strength.name}",
            markets["away_win_by_2"],
            "L'exterieur peut creuser un ecart >=2 buts.",
        )

    htft_codes = ["1/1", "1/N", "1/2", "N/1", "N/N", "N/2", "2/1", "2/N", "2/2"]
    for code in htft_codes:
        prob = float(markets.get(f"htft_{code}", 0.0) or 0.0)
        if prob <= 0:
            continue
        ht_token, ft_token = code.split("/")
        label = f"Mi-temps/Fin {htft_descriptions.get(ht_token, ht_token)} / {htft_descriptions.get(ft_token, ft_token)}"
        odd = odds_snapshot.get(f"htft_{code}")
        edge = _probability_edge(prob, odd)
        if edge is None:
            edge = prob - HTFT_BASELINE
        if prob < HTFT_MIN_PROBABILITY or edge < EDGE_THRESHOLD:
            continue
        reason_parts = [f"Sequence {code} {prob*100:.1f}%"]
        if odd:
            reason_parts.append(f"cote {odd:.2f}")
        reason_parts.append(f"value {edge*100:.1f}%")
        add_tip(
            label,
            prob,
            ". ".join(reason_parts),
            min_probability=HTFT_MIN_PROBABILITY,
        )

    if top_scores:
        for entry in top_scores[:2]:
            label_score = entry.get("label")
            prob_score = float(entry.get("prob", 0.0) or 0.0)
            if label_score and prob_score > 0:
                add_tip(
                    f"Score exact {label_score}",
                    prob_score,
                    "Projection Poisson du score exact le plus probable.",
                    min_probability=MIN_SCORE_PROBABILITY,
                )

    tips.sort(key=lambda item: item["probability"], reverse=True)
    return tips[:6]


def _note_ia_lines(
    home_strength: Any,
    away_strength: Any,
    probs: Dict[str, float],
    top_scores: List[Dict[str, Any]],
    tips: List[Dict[str, Any]],
    status: Dict[str, Any],
    context: Any,
    pressure: Optional[Dict[str, Any]],
    baseline_probs: Optional[Dict[str, float]],
) -> Tuple[List[str], str]:
    bullets: List[str] = []
    bullets.append(
        f"Etat du match : {status['label']} (projection ajustee sur {home_strength.name} vs {away_strength.name})."
    )
    bullets.append(
        "Probabilites finales : "
        f"{home_strength.name} {_format_percentage(probs.get('home', 0.0))} | "
        f"Match nul {_format_percentage(probs.get('draw', 0.0))} | "
        f"{away_strength.name} {_format_percentage(probs.get('away', 0.0))}."
    )
    if top_scores:
        best_score = top_scores[0]
        bullets.append(
            f"Score le plus probable : {best_score['label']} ({_format_percentage(best_score['prob'])})."
        )
    if pressure:
        poss_home = pressure.get("ball_possession_home")
        poss_away = pressure.get("ball_possession_away")
        if poss_home is not None and poss_away is not None:
            bullets.append(
                f"Possession : {home_strength.name} {poss_home*100:.0f}% | {away_strength.name} {poss_away*100:.0f}%."
            )
        passes_home = pressure.get("passes_accurate_home")
        passes_away = pressure.get("passes_accurate_away")
        if passes_home is not None and passes_away is not None:
            bullets.append(
                f"Passes precises : {home_strength.name} {passes_home:.0f} | {away_strength.name} {passes_away:.0f}."
            )
        xg_home = pressure.get("xg_home")
        xg_away = pressure.get("xg_away")
        if xg_home is not None and xg_away is not None:
            bullets.append(f"xG cumules : {home_strength.name} {xg_home:.2f} vs {away_strength.name} {xg_away:.2f}.")
        corners_home = pressure.get("corners_home")
        corners_away = pressure.get("corners_away")
        if corners_home is not None and corners_away is not None:
            bullets.append(
                f"Corners : {home_strength.name} {int(corners_home)} | {away_strength.name} {int(corners_away)}."
            )
        big_home = pressure.get("big_chances_home")
        big_away = pressure.get("big_chances_away")
        if big_home is not None and big_away is not None:
            bullets.append(
                f"Big chances : {home_strength.name} {int(big_home)} | {away_strength.name} {int(big_away)}."
            )
    if tips:
        ordered = ", ".join(tip["label"] for tip in tips[:4])
        bullets.append(f"Priorites paris : {ordered}.")
    context_bits: List[str] = []
    if getattr(context, "red_cards", []):
        context_bits.append("Cartons rouges : " + ", ".join(context.red_cards))
    if getattr(context, "injuries", []):
        context_bits.append("Blessures signalees : " + ", ".join(context.injuries))
    recent_hot = pressure.get("recent_events") if pressure else None
    if recent_hot:
        context_bits.append(f"Actions chaudes (10 dernieres minutes) : {recent_hot}.")
    last_event = pressure.get("last_event_elapsed") if pressure else None
    if last_event is not None:
        context_bits.append(f"Derniere action enregistree {int(last_event)}'.")
    weather_hint = getattr(context, "weather", None)
    if weather_hint:
        context_bits.append(f"Meteo : {weather_hint}")
    elif not weather.is_available():
        context_bits.append("Meteo : non disponible (ajoutez OPENWEATHER_API_KEY).")
    if getattr(context, "halftime", False):
        context_bits.append(context.halftime_message or "Reevaluation mi-temps appliquee.")
    if baseline_probs:
        delta_home = (probs.get("home", 0.0) - baseline_probs.get("home", 0.0)) * 100.0
        delta_draw = (probs.get("draw", 0.0) - baseline_probs.get("draw", 0.0)) * 100.0
        delta_away = (probs.get("away", 0.0) - baseline_probs.get("away", 0.0)) * 100.0
        context_bits.append(
            f"Ecart live vs pre-match : {home_strength.name} {delta_home:+.1f} pts | Nul {delta_draw:+.1f} pts | {away_strength.name} {delta_away:+.1f} pts."
        )
    if context_bits:
        bullets.append("Facteurs contextuels : " + " | ".join(context_bits))
    disclaimer = (
        "Ces estimations reposent sur des modeles statistiques (Poisson, binomiale, forme normalisee). "
        "Elles ne garantissent pas un resultat et ne constituent pas un conseil financier."
    )
    return bullets, disclaimer


def _filter_fixtures(
    fixtures: List[Dict[str, Any]],
    league_id: int,
    status_filter: Optional[set[str]],
) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    for fx in fixtures:
        if not isinstance(fx, dict):
            continue
        if fx.get("league", {}).get("id") not in {None, league_id}:
            continue
        if status_filter:
            status = fx.get("fixture", {}).get("status", {}).get("short")
            if status not in status_filter:
                continue
        filtered.append(fx)
    return filtered


def _build_fixture_options(fixtures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    options: List[Dict[str, Any]] = []
    for item in fixtures:
        if not isinstance(item, dict):
            continue
        fixture_info = item.get("fixture") or {}
        fixture_id = fixture_info.get("id")
        teams_info = item.get("teams") or {}
        home = teams_info.get("home") or {}
        away = teams_info.get("away") or {}
        if fixture_id:
            raw_date = fixture_info.get("date")
            parsed = _parse_datetime(raw_date)
            if parsed:
                date_str = parsed.strftime("%d/%m/%Y %H:%M")
            else:
                date_str = str(raw_date or "")[:16].replace("T", " ")
            label = f"{home.get('name', '?')} vs {away.get('name', '?')} - {date_str}"
            options.append({"id": fixture_id, "label": label, "data": item})
    return options


def _log_prediction_snapshot(
    fixture_id: Any,
    league_id: int,
    season: int,
    home_name: str,
    away_name: str,
    fixture_date: Optional[str],
    probs: Dict[str, float],
    markets: Dict[str, float],
    tips: List[Dict[str, Any]],
    top_scores: List[Dict[str, Any]],
    status: Dict[str, Any],
    *,
    bet_selection: Optional[str] = None,
) -> None:
    main_tip = tips[0] if tips else None
    main_label = main_tip["label"] if main_tip else "N/A"
    main_conf = main_tip["confidence"] if main_tip else 0
    main_reason = main_tip["reason"] if main_tip else ""
    best_score = top_scores[0] if top_scores else None

    parsed_fixture = _parse_datetime(fixture_date)
    fixture_iso = parsed_fixture.isoformat() if parsed_fixture else ""
    over_prob = float(markets.get("over_2_5", 0.0) or 0.0)
    under_prob = float(markets.get("under_2_5", 0.0) or max(0.0, 1.0 - over_prob))
    total_pick = ""
    for tip in tips:
        label = (tip.get("label") or "").lower()
        if label.startswith("over 2.5") or label.startswith("under 2.5"):
            total_pick = tip.get("label", "")
            break
    bet_timestamp = datetime.now(PARIS_TZ).isoformat() if bet_selection else ""

    upsert_prediction(
        {
            "timestamp": datetime.now(PARIS_TZ).isoformat(),
            "fixture_date": fixture_iso,
            "fixture_id": fixture_id,
            "league_id": league_id,
            "season": season,
            "home_team": home_name,
            "away_team": away_name,
            "prob_home": probs.get("home", 0.0),
            "prob_draw": probs.get("draw", 0.0),
            "prob_away": probs.get("away", 0.0),
            "prob_over_2_5": over_prob,
            "prob_under_2_5": under_prob,
            "main_pick": main_label,
            "main_confidence": main_conf,
            "edge_comment": main_reason,
            "top_score": best_score["label"] if best_score else "",
            "total_pick": total_pick,
            "status_snapshot": status["short"],
            "bet_selection": bet_selection or "",
            "bet_timestamp": bet_timestamp,
        }
    )


def _update_history_if_finished(
    fixture_id: Any,
    status: Dict[str, Any],
    teams: Dict[str, Any],
) -> None:
    if status["short"] not in FINISHED_STATUS_CODES:
        return
    home_team = teams.get("home") or {}
    away_team = teams.get("away") or {}
    winner = None
    if home_team.get("winner") is True:
        winner = "home"
    elif away_team.get("winner") is True:
        winner = "away"
    elif status["home_goals"] == status["away_goals"]:
        winner = "draw"
    update_outcome(
        fixture_id,
        status=status["short"],
        goals_home=status["home_goals"],
        goals_away=status["away_goals"],
        winner=winner,
    )


def _round_pct(value: Any, *, multiplier: float = 100.0, ndigits: int = 1) -> Optional[float]:
    try:
        return round(float(value) * multiplier, ndigits)
    except (TypeError, ValueError):
        return None


def _probability_pct_map(values: Mapping[str, Any], keys: Sequence[str]) -> Dict[str, float]:
    snapshot: Dict[str, float] = {}
    for key in keys:
        pct = _round_pct(values.get(key), ndigits=2)
        if pct is not None:
            snapshot[key] = pct
    return snapshot


def _tip_snapshot(tips: List[Dict[str, Any]], limit: int = 4) -> List[Dict[str, Any]]:
    snapshot: List[Dict[str, Any]] = []
    for tip in tips[:limit]:
        snapshot.append(
            {
                "label": tip.get("label"),
                "probability_pct": _round_pct(tip.get("probability"), ndigits=1),
                "confidence": tip.get("confidence"),
                "reason": tip.get("reason"),
            }
        )
    return snapshot


def _top_scores_snapshot(scores: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    snapshot: List[Dict[str, Any]] = []
    for item in scores[:limit]:
        snapshot.append(
            {
                "label": item.get("label"),
                "probability_pct": _round_pct(item.get("prob"), ndigits=1),
            }
        )
    return snapshot


def _team_snapshot(strength: Any, raw_team: Mapping[str, Any]) -> Dict[str, Any]:
    def _safe(value: Any, ndigits: int = 2) -> Optional[float]:
        try:
            num = float(value)
        except (TypeError, ValueError):
            return None
        return round(num, ndigits)

    return {
        "name": raw_team.get("name"),
        "rank": raw_team.get("rank"),
        "lambda": _safe(getattr(strength, "lambda_value", None)),
        "attack_avg": _safe(getattr(strength, "attack", None)),
        "defense_avg": _safe(getattr(strength, "defense", None)),
        "elo": _safe(getattr(strength, "elo_rating", None), ndigits=1),
        "delta_elo": _safe(getattr(strength, "delta_elo", None), ndigits=1),
        "adjustments": list(getattr(strength, "adjustments", []) or []),
    }


def _context_snapshot(context: Any) -> Dict[str, Any]:
    return {
        "weather": getattr(context, "weather", None),
        "referee": getattr(context, "referee", None),
        "red_cards": list(getattr(context, "red_cards", []) or []),
        "injuries": list(getattr(context, "injuries", []) or []),
        "fatigue_flags": list(getattr(context, "fatigue_flags", []) or []),
        "adjustments_home": list(getattr(context, "adjustments_home", []) or []),
        "adjustments_away": list(getattr(context, "adjustments_away", []) or []),
    }


def _pressure_snapshot(pressure: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not pressure:
        return None
    snapshot: Dict[str, Any] = {}
    for field in AI_PRESSURE_FIELDS:
        value = pressure.get(field)
        if value is None:
            continue
        if field == "score":
            pct = _round_pct(value, ndigits=1)
            if pct is not None:
                snapshot["score_pct"] = pct
            continue
        snapshot[field] = value
    return snapshot or None


def _pressure_score_value(pressure: Optional[Dict[str, Any]]) -> Optional[float]:
    if not pressure:
        return None
    score = pressure.get("score")
    try:
        value = float(score)
    except (TypeError, ValueError):
        return None
    if value <= 1.0:
        value *= 100.0
    return value


def _intensity_snapshot(intensity: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not intensity:
        return {}
    return {
        "score": intensity.get("score"),
        "label": intensity.get("label"),
        "comment": intensity.get("comment"),
        "prob_over_pct": _round_pct(intensity.get("prob_over"), ndigits=1),
        "prob_btts_pct": _round_pct(intensity.get("prob_btts"), ndigits=1),
        "total_xg": intensity.get("total_xg"),
    }


def _odds_snapshot(odds: Optional[Mapping[str, Any]]) -> Dict[str, float]:
    snapshot: Dict[str, float] = {}
    for key, value in (odds or {}).items():
        try:
            snapshot[key] = round(float(value), 3)
        except (TypeError, ValueError):
            continue
    return snapshot


def _build_ai_match_payload(
    *,
    fixture: Dict[str, Any],
    fixture_id: int,
    league_id: int,
    season: int,
    home_team: Dict[str, Any],
    away_team: Dict[str, Any],
    home_strength: Any,
    away_strength: Any,
    status: Dict[str, Any],
    projection_probs: Dict[str, float],
    markets: Dict[str, float],
    baseline_probs: Optional[Dict[str, float]],
    tips: List[Dict[str, Any]],
    top_scores: List[Dict[str, Any]],
    intensity_snapshot: Dict[str, Any],
    pressure_metrics: Optional[Dict[str, Any]],
    context: Any,
    odds_map: Dict[str, float],
    bankroll_settings: BankrollSettings,
) -> Dict[str, Any]:
    fixture_block = fixture.get("fixture") or {}
    league_block = fixture.get("league") or {}
    match_meta = {
        "fixture_id": fixture_id,
        "league_id": league_block.get("id") or league_id,
        "league": league_block.get("name"),
        "season": league_block.get("season") or season,
        "kickoff": fixture_block.get("date"),
        "venue": (fixture_block.get("venue") or {}).get("name"),
    }
    status_snapshot = {
        "label": status.get("label"),
        "short": status.get("short"),
        "elapsed": status.get("elapsed"),
        "score": f"{status.get('home_goals', 0)}-{status.get('away_goals', 0)}",
        "home_goals": status.get("home_goals"),
        "away_goals": status.get("away_goals"),
    }
    bankroll_amount = getattr(bankroll_settings, "amount", 0.0)
    default_odds = getattr(bankroll_settings, "default_odds", 1.01)
    try:
        bankroll_amount = round(float(bankroll_amount), 2)
    except (TypeError, ValueError):
        bankroll_amount = 0.0
    try:
        default_odds = round(float(default_odds), 2)
    except (TypeError, ValueError):
        default_odds = 1.01
    return {
        "meta": match_meta,
        "status": status_snapshot,
        "teams": {
            "home": _team_snapshot(home_strength, home_team),
            "away": _team_snapshot(away_strength, away_team),
        },
        "probabilities_pct": _probability_pct_map(projection_probs, ("home", "draw", "away")),
        "market_probs_pct": _probability_pct_map(markets, AI_MARKET_KEYS),
        "baseline_pct": _probability_pct_map(baseline_probs or {}, ("home", "draw", "away")),
        "top_scores": _top_scores_snapshot(top_scores),
        "tips": _tip_snapshot(tips),
        "intensity": _intensity_snapshot(intensity_snapshot),
        "pressure": _pressure_snapshot(pressure_metrics),
        "context": _context_snapshot(context),
        "odds_snapshot": _odds_snapshot(odds_map),
        "bankroll": {
            "strategy": getattr(bankroll_settings, "strategy", ""),
            "amount_eur": bankroll_amount,
            "default_odds": default_odds,
        },
    }


def _render_ai_analysis_section(
    fixture_id: int,
    payload: Dict[str, Any],
    history_meta: Dict[str, Any],
    *,
    extra_instruction: Optional[str] = None,
) -> None:
    ai_ready = is_openai_configured()
    cache: Dict[str, Dict[str, Any]] = st.session_state.setdefault("ai_analysis_cache", {})
    cache_entry = cache.get(str(fixture_id))
    if cache_entry:
        st.caption(f"Dernière réponse IA : {cache_entry['generated_at']}")
        st.markdown(cache_entry["content"])
    button_label = "Demander l'avis de l'IA" if not cache_entry else "Rafraîchir l'avis de l'IA"
    if st.button(button_label, key=f"ai_run_{fixture_id}", disabled=not ai_ready):
        with st.spinner("Consultation OpenAI..."):
            try:
                instruction = (extra_instruction or "").strip()
                analysis = analyse_match_with_ai(
                    payload,
                    instruction=instruction or None,
                )
            except (AIAnalysisError, RuntimeError) as exc:
                st.error(str(exc))
            else:
                generated_at_dt = datetime.now(PARIS_TZ)
                timestamp_display = generated_at_dt.strftime("%d/%m %H:%M")
                cache[str(fixture_id)] = {"content": analysis, "generated_at": timestamp_display}
                st.session_state["ai_analysis_cache"] = cache
                st.success("Analyse IA actualisée.")
                st.markdown(analysis)
                upsert_prediction(
                    {
                        "fixture_id": history_meta.get("fixture_id"),
                        "status_snapshot": history_meta.get("status_short", "NS"),
                        "ai_analysis": analysis,
                        "ai_generated_at": generated_at_dt.isoformat(),
                    }
                )
    if not ai_ready:
        st.info("Ajoutez OPENAI_API_KEY dans votre .env pour activer cette section.")


def _commentator_instruction(
    status: Optional[Mapping[str, Any]],
    pressure: Optional[Dict[str, Any]],
    intensity_snapshot: Mapping[str, Any],
    context: Any,
) -> str:
    hints: list[str] = []
    if status:
        label = status.get("label")
        if label:
            hints.append(f"Etat du match : {label}")
        score = status.get("score")
        if score:
            hints.append(f"Score affiche : {score}")
    pressure_label = (pressure or {}).get("label")
    if pressure_label:
        hints.append(f"Pression offensive : {pressure_label}")
    if intensity_snapshot:
        score_val = intensity_snapshot.get("score")
        label = intensity_snapshot.get("label")
        if score_val is not None and label:
            hints.append(f"Indice intensite {score_val}/100 ({label})")
    def _fmt_pair(home_key: str, away_key: str, label: str) -> Optional[str]:
        if not pressure:
            return None
        home_val = pressure.get(home_key)
        away_val = pressure.get(away_key)
        if home_val in {None, ""} or away_val in {None, ""}:
            return None
        try:
            if isinstance(home_val, float) and home_val.is_integer():
                home_val = int(home_val)
            if isinstance(away_val, float) and away_val.is_integer():
                away_val = int(away_val)
        except AttributeError:
            pass
        return f"{label} {home_val}-{away_val}"
    stats_parts: list[str] = []
    for home_key, away_key, label in [
        ("shots_on_target_home", "shots_on_target_away", "Tirs cadres"),
        ("total_shots_home", "total_shots_away", "Tirs totaux"),
    ]:
        line = _fmt_pair(home_key, away_key, label)
        if line:
            stats_parts.append(line)
    if pressure:
        xg_home = pressure.get("xg_home")
        xg_away = pressure.get("xg_away")
        if xg_home is not None and xg_away is not None:
            try:
                stats_parts.append(f"xG {float(xg_home):.2f}-{float(xg_away):.2f}")
            except (TypeError, ValueError):
                pass
        def _format_possession(raw: Any) -> Optional[str]:
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return None
            if value <= 1.0:
                value *= 100.0
            return f"{int(round(value))}%"
        poss_home = _format_possession(pressure.get("ball_possession_home"))
        poss_away = _format_possession(pressure.get("ball_possession_away"))
        if poss_home and poss_away:
            stats_parts.append(f"Possession {poss_home}-{poss_away}")
    if stats_parts:
        hints.append("Stats clefs : " + ", ".join(stats_parts))
    red_cards = list(getattr(context, "red_cards", []) or [])
    if red_cards:
        hints.append("Cartons rouges : " + " | ".join(red_cards))
    return " | ".join(hints)


def _render_ai_commentator_section(
    fixture_id: int,
    payload: Dict[str, Any],
    *,
    status: Mapping[str, Any],
    pressure_metrics: Optional[Dict[str, Any]],
    intensity_snapshot: Mapping[str, Any],
    context: Any,
    extra_instruction: Optional[str] = None,
) -> None:
    ai_ready = is_openai_configured()
    cache: Dict[str, Dict[str, Any]] = st.session_state.setdefault("ai_commentary_cache", {})
    cache_entry = cache.get(str(fixture_id))
    if cache_entry:
        st.caption(f"Dernier commentaire IA : {cache_entry['generated_at']}")
        st.markdown(cache_entry["content"])
    button_label = "Lancer le commentaire TV" if not cache_entry else "Actualiser le commentaire TV"
    if st.button(button_label, key=f"ai_commentary_{fixture_id}", disabled=not ai_ready):
        with st.spinner("Commentateur IA en cours..."):
            try:
                instruction = _commentator_instruction(status, pressure_metrics, intensity_snapshot, context)
                custom_note = (extra_instruction or "").strip()
                if custom_note:
                    instruction = " | ".join(part for part in [instruction, custom_note] if part)
                commentary = commentate_match_with_ai(
                    payload,
                    instruction=instruction or None,
                )
            except (AIAnalysisError, RuntimeError) as exc:
                st.error(str(exc))
            else:
                generated_at_dt = datetime.now(PARIS_TZ)
                timestamp_display = generated_at_dt.strftime("%d/%m %H:%M")
                cache[str(fixture_id)] = {"content": commentary, "generated_at": timestamp_display}
                st.session_state["ai_commentary_cache"] = cache
                st.success("Commentaire TV actualise.")
                st.markdown(commentary)
    if not ai_ready:
        st.info("Ajoutez OPENAI_API_KEY pour activer le commentateur IA.")


def _render_ai_scenarios_section(
    fixture_id: int,
    payload: Dict[str, Any],
    projection_probs: Dict[str, float],
    intensity_snapshot: Dict[str, Any],
    pressure_metrics: Optional[Dict[str, Any]],
    history_meta: Dict[str, Any],
    *,
    home_label: str,
    away_label: str,
) -> None:
    scenario_catalog = available_scenarios()
    if not scenario_catalog:
        st.info("Aucun scénario n'est encore configuré.")
        return
    default_selection = [key for key in DEFAULT_AI_SCENARIOS if key in scenario_catalog]
    if not default_selection and scenario_catalog:
        default_selection = [next(iter(scenario_catalog.keys()))]
    options = {key: config["label"] for key, config in scenario_catalog.items()}
    selection = st.multiselect(
        "Scénarios à simuler",
        options=list(options.keys()),
        format_func=lambda key: options.get(key, key),
        default=default_selection,
        key=f"scenario_select_{fixture_id}",
    )
    ai_ready = is_openai_configured()
    scenario_store: Dict[str, Dict[str, Any]] = st.session_state.setdefault("ai_scenarios_cache", {})
    fixture_cache: Dict[str, Any] = scenario_store.setdefault(str(fixture_id), {})
    pressure_score = _pressure_score_value(pressure_metrics)
    intensity_score = None
    try:
        intensity_score = float(intensity_snapshot.get("score"))
    except (TypeError, ValueError, AttributeError):
        intensity_score = None
    run_disabled = not (ai_ready and selection)
    if st.button(
        "Simuler ces scénarios",
        key=f"scenario_run_{fixture_id}",
        disabled=run_disabled,
    ):
        with st.spinner("Consultation IA pour chaque scénario..."):
            for key in selection:
                config = scenario_catalog.get(key)
                if not config:
                    continue
                scenario_payload = build_scenario_payload(payload, key)
                instruction = scenario_instruction(payload, key)
                try:
                    analysis = analyse_match_with_ai(scenario_payload, instruction=instruction)
                except (AIAnalysisError, RuntimeError) as exc:
                    st.error(f"{config['label']} : {exc}")
                    continue
                alt_probs = alt_projection_snapshot(
                    projection_probs,
                    intensity_score=intensity_score,
                    pressure_score=pressure_score,
                    scenario_key=key,
                )
                delta = probability_delta(projection_probs, alt_probs)
                fixture_cache[key] = {
                    "label": config["label"],
                    "analysis": analysis,
                    "probabilities": alt_probs,
                    "delta": delta,
                    "generated_at": datetime.now(PARIS_TZ).strftime("%d/%m %H:%M"),
                }
            st.session_state["ai_scenarios_cache"] = scenario_store
            st.success("Scénarios mis à jour.")
            scenarios_snapshot = []
            for scenario_key, data in fixture_cache.items():
                scenarios_snapshot.append(
                    {
                        "key": scenario_key,
                        "label": data.get("label"),
                        "delta": data.get("delta"),
                        "probabilities": data.get("probabilities"),
                        "generated_at": data.get("generated_at"),
                    }
                )
            upsert_prediction(
                {
                    "fixture_id": history_meta.get("fixture_id"),
                    "status_snapshot": history_meta.get("status_short", "NS"),
                    "ai_scenarios": json.dumps(scenarios_snapshot, ensure_ascii=False),
                    "ai_scenarios_generated_at": datetime.now(PARIS_TZ).isoformat(),
                }
            )
    if not fixture_cache:
        if not ai_ready:
            st.info("Ajoutez OPENAI_API_KEY pour lancer les scénarios IA.")
        else:
            st.caption("Sélectionnez des scénarios puis lancez une simulation.")
        return
    display_keys = selection or list(fixture_cache.keys())
    for key in display_keys:
        entry = fixture_cache.get(key)
        if not entry:
            continue
        label = entry.get("label", key)
        timestamp = entry.get("generated_at")
        if timestamp:
            st.caption(f"{label} — généré le {timestamp}")
        else:
            st.caption(label)
        alt_probs = entry.get("probabilities", {})
        deltas = entry.get("delta", {})
        cols = st.columns(3)
        mapping = [
            ("home", f"Victoire {home_label}"),
            ("draw", "Match nul"),
            ("away", f"Victoire {away_label}"),
        ]
        for idx, (prob_key, prob_label) in enumerate(mapping):
            alt_value = float(alt_probs.get(prob_key, 0.0)) * 100.0
            delta_value = float(deltas.get(prob_key, 0.0)) * 100.0
            cols[idx].metric(prob_label, f"{alt_value:.1f}%", f"{delta_value:+.1f} pts")
        analysis_text = entry.get("analysis")
        if analysis_text:
            st.markdown(analysis_text)
        st.markdown("---")


def _render_alt_projection_section(
    fixture_id: int,
    projection_probs: Dict[str, float],
    intensity_snapshot: Dict[str, Any],
    pressure_metrics: Optional[Dict[str, Any]],
    history_meta: Dict[str, Any],
    *,
    home_label: str,
    away_label: str,
) -> None:
    pressure_score = _pressure_score_value(pressure_metrics)
    try:
        intensity_score = float(intensity_snapshot.get("score"))
    except (TypeError, ValueError, AttributeError):
        intensity_score = None
    alt_probs = alt_projection_snapshot(
        projection_probs,
        intensity_score=intensity_score,
        pressure_score=pressure_score,
    )
    delta = probability_delta(projection_probs, alt_probs)
    cols = st.columns(3)
    mapping = [
        ("home", f"Victoire {home_label}"),
        ("draw", "Match nul"),
        ("away", f"Victoire {away_label}"),
    ]
    max_delta = 0.0
    for idx, (prob_key, label) in enumerate(mapping):
        base_val = float(projection_probs.get(prob_key, 0.0)) * 100.0
        alt_val = float(alt_probs.get(prob_key, 0.0)) * 100.0
        delta_val = float(delta.get(prob_key, 0.0)) * 100.0
        max_delta = max(max_delta, abs(delta_val))
        cols[idx].metric(label, f"{alt_val:.1f}% (alt)", f"{delta_val:+.1f} pts", help=f"Modèle principal : {base_val:.1f}%")
    cache_store: Dict[str, Any] = st.session_state.setdefault("alt_projection_cache", {})
    cache_key = str(fixture_id)
    signature = {"alt": alt_probs, "delta": delta}
    if cache_store.get(cache_key) != signature:
        cache_store[cache_key] = signature
        st.session_state["alt_projection_cache"] = cache_store
        upsert_prediction(
            {
                "fixture_id": history_meta.get("fixture_id"),
                "status_snapshot": history_meta.get("status_short", "NS"),
                "alt_home": alt_probs.get("home"),
                "alt_draw": alt_probs.get("draw"),
                "alt_away": alt_probs.get("away"),
                "alt_delta_home": delta.get("home"),
                "alt_delta_draw": delta.get("draw"),
                "alt_delta_away": delta.get("away"),
                "alt_generated_at": datetime.now(PARIS_TZ).isoformat(),
            }
        )
    if max_delta >= 5.0:
        st.warning(
            "Le moteur local diffère notablement du modèle principal (>5 points). Vérifie les facteurs de contexte.",
            icon="⚠️",
        )
    else:
        st.caption("Le moteur local reste aligné (+/-5 pts) avec le modèle principal.")


def _build_share_context(
    fixture_id: int,
    home_team: Dict[str, Any],
    away_team: Dict[str, Any],
    status: Dict[str, Any],
    projection_probs: Dict[str, float],
    markets: Dict[str, float],
    tips: List[Dict[str, Any]],
    tip_meta: Dict[str, Dict[str, Any]],
    intensity_snapshot: Dict[str, Any],
    bankroll_settings: BankrollSettings,
) -> Dict[str, Any]:
    home_name = home_team.get("name", "Equipe A")
    away_name = away_team.get("name", "Equipe B")
    match_label = f"{home_name} - {away_name}"
    status_label = status.get("label", "")
    top_tip = tips[0] if tips else {}
    tip_detail = tip_meta.get(top_tip.get("label", ""), {})
    edge_value = tip_detail.get("edge")
    edge_label = f"{edge_value * 100:.1f}%" if isinstance(edge_value, (int, float)) else "N/A"
    intensity_score = intensity_snapshot.get("score")
    bankroll_label = f"{bankroll_settings.amount:.2f} EUR / strat {bankroll_settings.strategy}"
    probs_pct = {
        "home": f"{projection_probs.get('home', 0.0) * 100:.1f}%",
        "draw": f"{projection_probs.get('draw', 0.0) * 100:.1f}%",
        "away": f"{projection_probs.get('away', 0.0) * 100:.1f}%",
    }
    ai_cache = st.session_state.get("ai_analysis_cache", {})
    ai_entry = ai_cache.get(str(fixture_id)) or {}
    ai_summary = (ai_entry.get("content") or "").strip()
    if ai_summary:
        first_line = ai_summary.splitlines()[0]
        ai_summary = first_line[:240]
    app_url = get_secret("PUBLIC_APP_URL") or "http://localhost:8501"
    return {
        "fixture_id": fixture_id,
        "match_label": match_label,
        "status_label": status_label,
        "scoreline": f"{status.get('home_goals', 0)}-{status.get('away_goals', 0)}",
        "kickoff_label": status_label,
        "prob_home_pct": probs_pct["home"],
        "prob_draw_pct": probs_pct["draw"],
        "prob_away_pct": probs_pct["away"],
        "prob_over": markets.get("over_2_5"),
        "top_tip": {
            "label": top_tip.get("label"),
            "probability": top_tip.get("probability"),
            "confidence": top_tip.get("confidence"),
            "reason": top_tip.get("reason"),
        }
        if top_tip
        else {},
        "edge_label": edge_label,
        "edge_value": edge_label,
        "intensity_score": intensity_score,
        "ai_summary": ai_summary,
        "bankroll_label": bankroll_label,
        "app_url": app_url.rstrip("/"),
        "share_footer": "Powered by ProbaEdge ⚡",
    }


def _render_engagement_panel(fixture_id: int, share_context: Dict[str, Any]) -> None:
    templates = available_templates()
    if not templates:
        st.info("Aucun template disponible pour l’instant.")
        return
    template_options = {entry["key"]: entry["label"] for entry in templates}
    default_key = templates[0]["key"]
    selection = st.selectbox(
        "Template",
        options=list(template_options.keys()),
        format_func=lambda key: f"{template_options.get(key, key)}",
        key=f"share_template_{fixture_id}",
    )
    try:
        rendered = render_template(selection or default_key, share_context)
    except TemplateError as exc:
        st.error(str(exc))
        return
    subject_value = st.text_input(
        "Sujet / Titre",
        value=rendered.get("subject", "ProbaEdge"),
        key=f"share_subject_{fixture_id}",
    )
    body_value = st.text_area(
        "Message à diffuser",
        value=rendered.get("body", ""),
        height=180,
        key=f"share_body_{fixture_id}",
    )
    service = get_engagement_service()
    availability = {
        "email": service.has_email(),
        "webhook": service.has_webhook(),
        "telegram": service.has_telegram(),
        "x": service.has_x(),
    }
    if not any(availability.values()):
        st.info(
            "Configure ENGAGEMENT_SMTP_* / ENGAGEMENT_SOCIAL_WEBHOOK_URL / TELEGRAM_* / X_BEARER_TOKEN pour activer l’envoi direct."
        )
        return
    col_email, col_webhook, col_tg, col_x = st.columns(4)
    if col_email.button("Email", key=f"share_email_{fixture_id}", disabled=not availability["email"]):
        ok, err = service.send_email(subject_value, body_value)
        if ok:
            st.success("Email envoyé.")
        else:
            st.error(f"Echec email : {err}")
    if col_webhook.button("Webhook social", key=f"share_webhook_{fixture_id}", disabled=not availability["webhook"]):
        ok, err = service.post_webhook(body_value)
        if ok:
            st.success("Publication webhook envoyée.")
        else:
            st.error(f"Echec webhook : {err}")
    if col_tg.button("Telegram", key=f"share_tg_{fixture_id}", disabled=not availability["telegram"]):
        ok, err = service.post_telegram(body_value)
        if ok:
            st.success("Message Telegram envoyé.")
        else:
            st.error(f"Echec Telegram : {err}")
    if col_x.button("X (Twitter)", key=f"share_x_{fixture_id}", disabled=not availability["x"]):
        ok, err = service.post_x(body_value)
        if ok:
            st.success("Publication X envoyée.")
        else:
            st.error(f"Echec X : {err}")


def show_predictions(
    default_league_id: Optional[int] = None,
    default_season: Optional[int] = None,
    default_team_id: Optional[int] = None,
) -> None:
    st.header("Predictions & Analyse IA")

    saved_scenes = list_saved_scenes()
    scene_defaults_config = st.session_state.pop("_predictions_scene_to_apply", None)
    if scene_defaults_config:
        _seed_scene_state(scene_defaults_config)
    selected_scene_entry: Optional[Dict[str, Any]] = None
    scene_actions = {"save_new": False, "update": False, "name": "", "target_id": None, "target_label": ""}

    with st.expander("Scenes sauvegardees", expanded=False):
        scene_choices = [{"id": "", "name": "Aucune scene", "config": {}}] + saved_scenes
        selected_scene_entry = st.selectbox(
            "Scenes disponibles",
            options=scene_choices,
            index=0,
            format_func=lambda item: item["name"],
            key="predictions_scene_select",
        )
        effective_scene = (
            selected_scene_entry if selected_scene_entry and selected_scene_entry.get("id") else None
        )
        col_apply, col_delete = st.columns(2)
        if col_apply.button(
            "Appliquer cette scene",
            key="predictions_scene_apply_btn",
            disabled=effective_scene is None,
        ) and effective_scene:
            st.session_state["_predictions_scene_to_apply"] = effective_scene["config"]
            st.success(f"Scene '{effective_scene['name']}' appliquee.")
            st.experimental_rerun()
        if col_delete.button(
            "Supprimer cette scene",
            key="predictions_scene_delete_btn",
            disabled=effective_scene is None,
        ) and effective_scene:
            delete_scene(effective_scene["id"])
            st.success(f"Scene '{effective_scene['name']}' supprimee.")
            st.experimental_rerun()

        scene_name_input = st.text_input(
            "Nom de scene",
            key="predictions_scene_name_input",
            placeholder="Ex : Ligue 1 value bets",
        ).strip()
        save_new_btn = st.button("Sauvegarder comme nouvelle scene", key="predictions_scene_save_btn")
        update_btn = st.button(
            "Mettre a jour la scene selectionnee",
            key="predictions_scene_update_btn",
            disabled=effective_scene is None,
        )
        scene_actions = {
            "save_new": save_new_btn,
            "update": update_btn,
            "name": scene_name_input,
            "target_id": effective_scene["id"] if effective_scene else None,
            "target_label": effective_scene["name"] if effective_scene else "",
        }

    if not st.session_state.get("_prediction_history_normalized"):
        removed = normalize_prediction_history()
        st.session_state["_prediction_history_normalized"] = True
        if removed:
            st.caption(f"Historique prediction nettoye : {removed} doublon(s) supprime(s).")

    render_cache_controls(st.sidebar, key_prefix="predictions_")
    st.sidebar.markdown("---")
    highlight_threshold_pts = st.sidebar.slider(
        "Seuil 'Belles cotes' (pts)",
        min_value=1,
        max_value=15,
        value=int(OPPORTUNITY_EDGE_THRESHOLD * 100),
        help="Ecart minimal (en points d'edge) entre la proba modèle et la cote proposée.",
    )
    highlight_edge_threshold = highlight_threshold_pts / 100.0

    league_id, season, _ = select_league_and_season(
        default_league_id=default_league_id,
        default_season=default_season,
        key_prefix="predictions_",
    )
    team_id = select_team(
        league_id,
        season,
        default_team_id=default_team_id,
        placeholder="Toutes les equipes",
        key=f"predictions_team_{league_id}_{season}",
    )

    col_scope, col_limit = st.columns([1, 1])
    with col_scope:
        scope = st.selectbox("Selection des matchs", ["A venir", "En cours", "Joues"], index=0)
    with col_limit:
        limit = st.slider("Nombre de matchs", min_value=5, max_value=60, value=30, step=1)

    over_under_filters: Dict[str, Any] = {
        "over": {"enabled": False, "thresholds": {}},
        "under": {"enabled": False, "min_prob": None, "limit_intensity": False, "max_intensity": 65},
    }
    with st.expander("Filtres Over/Under (optionnel)", expanded=False):
        over_enabled = st.checkbox("Activer les filtres Over", key="over_filters_enabled")
        over_under_filters["over"]["enabled"] = over_enabled
        if over_enabled:
            over_cols = st.columns(3)
            over_under_filters["over"]["thresholds"] = {
                "over_1_5": over_cols[0].slider("Proba min. Over 1.5 (%)", 0, 100, 55, step=5),
                "over_2_5": over_cols[1].slider("Proba min. Over 2.5 (%)", 0, 100, 60, step=5),
                "over_3_5": over_cols[2].slider("Proba min. Over 3.5 (%)", 0, 100, 45, step=5),
            }
        under_enabled = st.checkbox("Activer les filtres Under", key="under_filters_enabled")
        min_under_prob = None
        limit_intensity = False
        intensity_cap = 65
        if under_enabled:
            min_under_prob = st.slider("Proba min. Under 2.5 (%)", 0, 100, 55, step=5)
            limit_intensity = st.checkbox(
                "Refuser les Under si l'intensite depasse un seuil",
                value=True,
                key="under_intensity_lock",
            )
            if limit_intensity:
                intensity_cap = st.slider(
                    "Intensite max pour jouer un Under",
                    min_value=10,
                    max_value=100,
                    value=60,
                    step=5,
                )
    over_under_filters["under"] = {
        "enabled": under_enabled,
        "min_prob": min_under_prob,
        "limit_intensity": limit_intensity,
        "max_intensity": intensity_cap,
    }

    current_scene_config = _compose_scene_config(
        league_id=league_id,
        season=season,
        team_id=team_id,
        scope=scope,
        limit=limit,
        highlight_points=highlight_threshold_pts,
        over_under_filters=over_under_filters,
    )
    if scene_actions["save_new"]:
        if not scene_actions["name"]:
            st.warning("Choisissez un nom avant d'enregistrer la scene.")
        else:
            upsert_scene(scene_actions["name"], current_scene_config)
            st.success(f"Scene '{scene_actions['name']}' enregistree.")
            st.experimental_rerun()
    if scene_actions["update"]:
        target_id = scene_actions.get("target_id")
        if not target_id:
            st.warning("Selectionnez une scene a mettre a jour.")
        else:
            target_name = scene_actions["name"] or scene_actions.get("target_label") or "Scene"
            upsert_scene(target_name, current_scene_config, scene_id=target_id)
            st.success(f"Scene '{target_name}' mise a jour.")
            st.experimental_rerun()

    streak = _recent_bet_streak()
    if streak:
        mode, count = streak
        if mode == "loss":
            st.warning(
                f"Série en cours : {count} pertes d'affilée. Pense à réduire les mises ou à faire une pause.",
                icon="⚠️",
            )
        else:
            st.info(
                f"Série gagnante de {count} paris. Reste discipliné pour sécuriser le rendement.",
                icon="✅",
            )

    status_filter: Optional[set[str]] = None
    next_n: Optional[int] = None
    last_n: Optional[int] = None
    live_param: Optional[str] = None

    if scope == "A venir":
        status_filter = UPCOMING_STATUS_CODES
        next_n = limit
    elif scope == "Joues":
        status_filter = FINISHED_STATUS_CODES
        last_n = limit
    else:
        status_filter = LIVE_STATUS_CODES
        live_param = "all"
        st.caption("Actualise la page ou clique sur le bouton pour suivre le direct.")

    try:
        with st.spinner("Chargement des matchs..."):
            fixtures = get_fixtures(
                league_id=league_id,
                season=season,
                team_id=team_id,
                next_n=next_n,
                last_n=last_n,
                live=live_param,
            ) or []
    except Exception as exc:
        st.error(f"Impossible d'interroger l'API : {exc}")
        return

    fixtures = _filter_fixtures(fixtures, league_id, status_filter)[:limit]
    if not fixtures:
        st.warning("Aucun match disponible avec ces filtres.")
        return

    snapshot = health_snapshot()
    if snapshot.get("offline"):
        reason = snapshot.get("offline_reason") or "Mode hors ligne actif"
        st.warning(
            f"Mode dÃ©gradÃ© - {reason}. Les donnÃ©es proviennent du cache, les Ã©critures sont dÃ©sactivÃ©es.",
            icon="⚠️",
        )
    elif snapshot.get("low_quota"):
        remaining = snapshot.get("quota_remaining")
        limit_quota = snapshot.get("quota_limit")
        st.info(
            f"Quota API faible ({remaining}/{limit_quota}). Les appels supplÃ©mentaires peuvent basculer en mode hors ligne.",
            icon="⚠️",
        )

    match_rows: List[Dict[str, Any]] = []
    for item in fixtures:
        fixture_block = item.get("fixture") or {}
        teams_block = item.get("teams") or {}
        home_block = teams_block.get("home") or {}
        away_block = teams_block.get("away") or {}
        date_raw = fixture_block.get("date")
        parsed_date = _parse_datetime(date_raw)
        kickoff = parsed_date.strftime("%d/%m %H:%M") if parsed_date else str(date_raw or "")[:16].replace("T", " ")
        status_info = _status_details(item)
        match_rows.append(
            {
                "Fixture ID": fixture_block.get("id"),
                "Heure": kickoff,
                "Match": f"{home_block.get('name', '?')} - {away_block.get('name', '?')}",
                "Statut": status_info.get("label", ""),
            }
        )
    if match_rows:
        st.subheader("Matchs du jour")
        st.dataframe(
            pd.DataFrame(match_rows),
            hide_index=True,
            use_container_width=True,
        )

    options = _build_fixture_options(fixtures)
    if not options:
        st.warning("Aucun match exploitable apres filtrage.")
        return
    preferred_fixture = st.session_state.pop("preferred_fixture_id", None)
    default_index = 0
    if preferred_fixture is not None:
        preferred_str = str(preferred_fixture)
        for idx, item in enumerate(options):
            if preferred_str == str(item.get("id")):
                default_index = idx
                break
    selected = st.selectbox(
        "Choisir un match",
        options=options,
        index=default_index,
        format_func=lambda item: item["label"],
    )
    fixture = selected.get("data", {})
    fixture_id_raw = selected.get("id")
    if not fixture or not fixture_id_raw:
        st.info("Selectionnez un match valable.")
        return
    try:
        fixture_id = int(fixture_id_raw)
    except (TypeError, ValueError):
        st.warning("Identifiant de match invalide.")
        return
    st.caption(f"Fixture ID : {fixture_id}")
    fetch_key = f"predictions_last_fetch_{fixture_id}"
    fetch_meta_key = f"{fetch_key}_meta"
    previous_fetch = st.session_state.get(fetch_key)
    previous_meta = st.session_state.get(fetch_meta_key, {})
    with st.spinner("Synchronisation des statistiques live..."):
        fixture, stats_updated_at, fetch_source = _load_fixture_with_details(fixture_id, fixture)
    now_ts = datetime.now(PARIS_TZ)
    st.session_state[fetch_key] = now_ts
    st.session_state[fetch_meta_key] = {
        "source": fetch_source,
        "updated_at": stats_updated_at,
    }
    if previous_fetch:
        delta_seconds = (now_ts - previous_fetch).total_seconds()
        st.caption(f"Statistiques rafraichies il y a {_format_delta(delta_seconds)}.")
    else:
        st.caption("Statistiques fraichement chargees.")
    if stats_updated_at:
        st.caption(f"Dernieres donnees live enregistrees : {stats_updated_at.strftime('%d/%m %H:%M:%S')} (heure Paris).")
        drift_seconds = max(0.0, (now_ts - stats_updated_at).total_seconds())
        if drift_seconds >= 1.0:
            st.caption(f"Decalage entre API et affichage : {_format_delta(drift_seconds)}.")
    elif fetch_source != "api":
        st.caption("Statistiques live indisponibles : affichage depuis le cache.")
    offline_flag = is_offline_mode()
    if offline_flag:
        st.warning("Mode hors ligne : les donnees proviennent du cache. Rafraichissez une fois la connexion retablie.")
    elif fetch_source in {"cache", "fallback"}:
        st.info("Stats recuperees depuis le cache API. Passer en ligne pour actualiser.")
    elif fetch_source == "error":
        st.warning("Impossible de rafraichir les statistiques live (erreur API).")
    if weather.is_available():
        _attach_weather_to_fixture(fixture)

    teams = fixture.get("teams", {})
    home_team = teams.get("home") or {}
    away_team = teams.get("away") or {}
    home_id = home_team.get("id")
    away_id = away_team.get("id")
    if not home_id or not away_id:
        st.warning("Impossible d'identifier les equipes.")
        return

    def _team_injuries(team_id: int) -> list[dict[str, Any]]:
        if not team_id:
            return []
        try:
            return get_injuries(league_id, season, int(team_id)) or []
        except Exception:
            return []

    injuries_home: list[dict[str, Any]] = _team_injuries(int(home_id))
    injuries_away: list[dict[str, Any]] = _team_injuries(int(away_id))

    status = _status_details(fixture)
    quick_reference = (
        f"{fixture_id} | {home_team.get('name', '?')} vs {away_team.get('name', '?')} | "
        f"{status.get('label', 'statut inconnu')}"
    )
    st.text_input(
        "Repere rapide (copier/coller dans vos notes)",
        value=quick_reference,
        key=f"fixture_reference_{fixture_id}",
    )
    if st.button("Envoyer ce match au Coach IA", key=f"coach_prefill_btn_{fixture_id}"):
        st.session_state["coach_prefill"] = (
            f"Analyse {home_team.get('name', '?')} vs {away_team.get('name', '?')} "
            f"(fixture {fixture_id}) et explique quelles hypotheses ou parametres "
            "justifient ou bloquent ce signal."
        )
        st.success("Ouvre l'onglet Assistant IA pour poursuivre l'analyse.")
    if status.get("short") in EVENT_STATUS_CODES:
        events = load_fixture_events(fixture_id)
        if events:
            st.markdown("**Buteurs & cartons**")
            for ev in events:
                st.markdown(format_event_line(ev), unsafe_allow_html=True)
    standings_raw = get_standings(league_id, season) or []
    standings_block: list[dict[str, Any]] = []
    if isinstance(standings_raw, list) and standings_raw:
        standings_block = standings_raw[0].get("league", {}).get("standings", [[]])[0]

    home_strength, away_strength, baseline = expected_goals_from_standings(
        standings_block,
        int(home_id),
        int(away_id),
        home_team.get("name", "Equipe A"),
        away_team.get("name", "Equipe B"),
    )
    context = apply_context_adjustments(
        home_strength,
        away_strength,
        fixture,
        injuries_home=injuries_home,
        injuries_away=injuries_away,
    )
    pressure_metrics = _live_match_pressure(
        fixture,
        int(home_id),
        int(away_id),
        status.get("elapsed"),
    )
    baseline_probs = _api_probability_snapshot(fixture_id)

    markov_meta = {
        "red_cards_home": sum(1 for note in context.red_cards if str(home_team.get("name", "")).lower() in note.lower()),
        "red_cards_away": sum(1 for note in context.red_cards if str(away_team.get("name", "")).lower() in note.lower()),
    }

    projection = project_match_outcome(
        home_strength,
        away_strength,
        goals_home=status["home_goals"],
        goals_away=status["away_goals"],
        status_short=status["short"],
        elapsed=status.get("elapsed"),
        context_adjustments=context,
        pressure_metrics=pressure_metrics,
        markov_meta=markov_meta,
    )
    if isinstance(projection, tuple):
        if len(projection) == 3:
            projection_probs, top_scores, projection_matrix = projection
        elif len(projection) == 2:
            projection_probs, top_scores = projection
            projection_matrix = None
        else:
            projection_probs, top_scores, projection_matrix = projection, [], None
    else:
        projection_probs, top_scores, projection_matrix = projection, [], None

    markets = _markets_from_matrix(
        projection_matrix,
        status["home_goals"],
        status["away_goals"],
    )
    markets.update(projection_probs)
    intensity_weights = get_intensity_weights()
    intensity_snapshot = _match_intensity_score_with_weights(
        home_strength.lambda_value,
        away_strength.lambda_value,
        markets,
        weights=intensity_weights,
        is_live=status["short"] in LIVE_STATUS_CODES,
    )
    calibration_meta = {
        "lambda_home": home_strength.lambda_value,
        "lambda_away": away_strength.lambda_value,
        "elo_home": getattr(home_strength, "elo_rating", 0.0),
        "elo_away": getattr(away_strength, "elo_rating", 0.0),
        "delta_elo": getattr(home_strength, "delta_elo", 0.0),
        "pressure_score": float(pressure_metrics.get("score", 0.0) if pressure_metrics else 0.0),
        "intensity_score": float(intensity_snapshot.get("score", 0.0)),
    }
    projection_probs = calibrate_match_probabilities(projection_probs, markets, meta=calibration_meta)
    markets.update({key: projection_probs.get(key, 0.0) for key in ("home", "draw", "away")})
    intervals = probability_confidence_interval(
        home_strength,
        away_strength,
        goals_home=status["home_goals"],
        goals_away=status["away_goals"],
        status_short=status["short"],
        elapsed=status.get("elapsed"),
        context_adjustments=context,
        pressure_metrics=pressure_metrics,
        markov_meta=markov_meta,
        calibration_meta=calibration_meta,
    )

    if baseline_probs:
        st.subheader("Comparaison live vs pre-match")
        comparison_cols = st.columns(3)
        delta_map = [
            ("home", f"Victoire {home_team.get('name', '?')}"),
            ("draw", "Match nul"),
            ("away", f"Victoire {away_team.get('name', '?')}"),
        ]
        for idx, (key, label) in enumerate(delta_map):
            live_prob = projection_probs.get(key, 0.0)
            live_val = live_prob * 100.0
            base_val = baseline_probs.get(key, 0.0) * 100.0
            delta_val = live_val - base_val
            interval = intervals.get(key, (max(0.0, live_prob - 0.05), min(1.0, live_prob + 0.05)))
            low_pct = interval[0] * 100.0
            high_pct = interval[1] * 100.0
            display_value = f"{live_val:.1f}% (IC 95% : {low_pct:.0f}-{high_pct:.0f}%)"
            comparison_cols[idx].metric(
                label,
                display_value,
                f"{delta_val:+.1f} pts",
                help=f"Pre-match : {base_val:.1f}%",
            )

    bankroll_settings = BankrollSettings.from_dict(get_bankroll_settings())
    alert_settings = get_alert_settings()
    ai_preferences = get_ai_preferences()
    strategy_label = STRATEGY_LABELS.get(bankroll_settings.strategy, bankroll_settings.strategy)
    profile_label = bankroll_settings.profile_name or bankroll_settings.profile_id or "Profil principal"
    bankroll_caption = (
        f"Bankroll disponible : {bankroll_settings.amount:.2f} EUR - strategie {strategy_label} "
        f"(profil {profile_label})"
    )

    odds_map: Dict[str, float] = {}
    if fixture_id:
        try:
            odds_map = _best_fixture_odds(fixture_id)
        except Exception:
            odds_map = {}

    filter_messages = _evaluate_over_under_filters(
        over_under_filters,
        markets,
        intensity_snapshot,
    )
    if filter_messages:
        st.warning("Ce match ne respecte pas vos filtres Over/Under.")
        for msg in filter_messages:
            st.write(f"- {msg}")
        st.info("Choisissez un autre match ou assouplissez vos seuils dans l'encart de filtres.")
        return

    try:
        bias_summary = over_under_bias(window=250)
    except Exception:
        bias_summary = {'bias': 0.0, 'sample': 0, 'predicted': None, 'actual': None}
    over_bias_value = 0.0
    if isinstance(bias_summary, dict) and (bias_summary.get('sample', 0) or 0) >= 25:
        try:
            over_bias_value = float(bias_summary.get('bias') or 0.0)
        except (TypeError, ValueError):
            over_bias_value = 0.0

    tips = _betting_tips(
        home_strength,
        away_strength,
        projection_probs,
        markets,
        top_scores=top_scores,
        odds_map=odds_map,
        over_bias=over_bias_value,
    )

    tracker = _bet_tracker()
    tip_meta: Dict[str, Dict[str, Any]] = {}

    odds_input_value = bankroll_settings.default_odds

    home_name = home_team.get("name", "")
    away_name = away_team.get("name", "")

    highlight_rows = _top_value_opportunities(
        tips,
        odds_map=odds_map,
        bankroll=bankroll_settings,
        home_name=home_name,
        away_name=away_name,
        edge_threshold=highlight_edge_threshold,
    )
    if highlight_rows:
        st.subheader("Belles cotes à saisir")
        st.caption(f"Edges >= {highlight_threshold_pts} pts selon le modèle vs la cote disponible.")
        table_data: List[Dict[str, Any]] = []
        for row in highlight_rows:
            odd_value = float(row.get("odd") or bankroll_settings.default_odds)
            stake_value = float(row.get("stake") or 0.0)
            confidence = row.get("confidence")
            table_data.append(
                {
                    "Sélection": row["label"],
                    "Cote": f"{odd_value:.2f}",
                    "Edge": f"{row['edge_pct']:.1f} pts",
                    "Mise suggérée": f"{stake_value:.2f} €" if stake_value > 0 else "-",
                    "Confiance": f"{confidence}/100" if confidence else "-",
                }
            )
        st.dataframe(pd.DataFrame(table_data), hide_index=True, use_container_width=True)
        for row in highlight_rows:
            reason = row.get("reason")
            if reason:
                st.caption(f"{row['label']} : {reason}")

    intensity = intensity_snapshot

    st.subheader("Indice d'intensite")
    intensity_cols = st.columns([1, 1, 1])
    intensity_cols[0].metric("Score", f"{intensity['score']}/100", intensity["label"])
    intensity_cols[1].metric("xG total", f"{intensity['total_xg']:.2f}")
    intensity_cols[2].metric("Over 2.5", f"{intensity['prob_over'] * 100:.0f}%")
    st.progress(intensity["score"] / 100.0)
    st.caption(intensity["comment"])
    st.caption(
        f"Drivers : xG {intensity['total_xg']:.2f} | Over 2.5 {intensity['prob_over'] * 100:.0f}% | BTTS {intensity['prob_btts'] * 100:.0f}%"
    )

    if pressure_metrics:
        show_pressure = (
            status["short"] in LIVE_STATUS_CODES
            or pressure_metrics.get("shots_on_target", 0)
            or pressure_metrics.get("total_shots", 0)
        )
        if show_pressure:
            st.subheader("Pression live")
            st.caption(
                f"Niveau : {pressure_metrics['label']} | Score {pressure_metrics['score'] * 100:.0f}/100"
            )
            pressure_cols = st.columns(4)
            pressure_cols[0].metric("Tirs cadres", str(pressure_metrics.get("shots_on_target", 0)))
            pressure_cols[1].metric("Tirs totaux", str(pressure_metrics.get("total_shots", 0)))
            pressure_cols[2].metric("Attaques dangereuses", str(pressure_metrics.get("dangerous_attacks", 0)))
            pressure_cols[3].metric("xG cumules", f"{pressure_metrics.get('xg_total', 0.0):.2f}")
            poss_home = pressure_metrics.get("ball_possession_home")
            poss_away = pressure_metrics.get("ball_possession_away")
            passes_home = pressure_metrics.get("passes_accurate_home")
            passes_away = pressure_metrics.get("passes_accurate_away")
            corners_home = pressure_metrics.get("corners_home")
            corners_away = pressure_metrics.get("corners_away")
            fouls_home = pressure_metrics.get("fouls_home")
            fouls_away = pressure_metrics.get("fouls_away")
            yellow_home = pressure_metrics.get("yellow_cards_home")
            yellow_away = pressure_metrics.get("yellow_cards_away")
            big_home = pressure_metrics.get("big_chances_home")
            big_away = pressure_metrics.get("big_chances_away")
            xg_home = pressure_metrics.get("xg_home")
            xg_away = pressure_metrics.get("xg_away")
            shots_on_target_home = pressure_metrics.get("shots_on_target_home")
            shots_on_target_away = pressure_metrics.get("shots_on_target_away")
            total_shots_home = pressure_metrics.get("total_shots_home")
            total_shots_away = pressure_metrics.get("total_shots_away")
            def _fmt_int(value: Any) -> str:
                if value in (None, "", "-"):
                    return "-"
                try:
                    num = float(value)
                except (TypeError, ValueError):
                    return str(value)
                if abs(num - int(num)) < 1e-6:
                    return str(int(num))
                return f"{num:.1f}"
            def _fmt_pct(value: Optional[float]) -> str:
                if value is None:
                    return "-"
                return f"{value * 100:.0f}%"
            per_team_lines = []
            per_team_lines.append(
                f"{home_name} : tirs cadrÃ©s {_fmt_int(shots_on_target_home)} | tirs {_fmt_int(total_shots_home)} | xG {xg_home:.2f} | "
                f"possession {_fmt_pct(poss_home)} | passes precises {_fmt_int(passes_home)} | corners {_fmt_int(corners_home)} | "
                f"fautes {_fmt_int(fouls_home)} | jaunes {_fmt_int(yellow_home)} | big chances {_fmt_int(big_home)}"
                if poss_home is not None
                else f"{home_name} : tirs cadrÃ©s {_fmt_int(shots_on_target_home)} | tirs {_fmt_int(total_shots_home)} | xG {xg_home:.2f}"
            )
            per_team_lines.append(
                f"{away_name} : tirs cadrÃ©s {_fmt_int(shots_on_target_away)} | tirs {_fmt_int(total_shots_away)} | xG {xg_away:.2f} | "
                f"possession {_fmt_pct(poss_away)} | passes precises {_fmt_int(passes_away)} | corners {_fmt_int(corners_away)} | "
                f"fautes {_fmt_int(fouls_away)} | jaunes {_fmt_int(yellow_away)} | big chances {_fmt_int(big_away)}"
                if poss_away is not None
                else f"{away_name} : tirs cadrÃ©s {_fmt_int(shots_on_target_away)} | tirs {_fmt_int(total_shots_away)} | xG {xg_away:.2f}"
            )
            for line in per_team_lines:
                st.caption(line)
            if pressure_metrics.get("recent_events"):
                st.caption(f"{pressure_metrics['recent_events']} actions chaudes dans les 10 dernieres minutes.")
            last_event_min = pressure_metrics.get("last_event_elapsed")
            if last_event_min is not None:
                st.caption(f"Derniere action enregistree : {int(last_event_min)}'.")

    core_stat_rows = _core_live_stat_rows(
        fixture.get("statistics") or [],
        home_id,
        away_id,
        home_name or "Domicile",
        away_name or "Extérieur",
    )
    if core_stat_rows:
        st.subheader("Stats clés live")
        st.table(pd.DataFrame(core_stat_rows))

    st.subheader("Statistiques du match")
    stats_df = _statistics_dataframe(fixture.get("statistics") or [])
    if not stats_df.empty:
        st.dataframe(stats_df, hide_index=True, use_container_width=True)
    else:
        st.caption("Statistiques live non disponibles pour ce match.")

    history_store: Dict[str, List[Dict[str, Any]]] = st.session_state.setdefault("intensity_history", {})
    fixture_key = str(fixture_id)
    now_ts = datetime.now(PARIS_TZ)
    current_entry = {"timestamp": now_ts.isoformat(), "score": intensity["score"]}
    history = history_store.get(fixture_key, [])
    if not history or history[-1].get("score") != current_entry["score"]:
        history.append(current_entry)
    cutoff = now_ts - timedelta(minutes=30)
    filtered_history: List[Dict[str, Any]] = []
    for item in history:
        timestamp_raw = item.get("timestamp")
        try:
            timestamp = datetime.fromisoformat(str(timestamp_raw))
        except Exception:
            continue
        if timestamp >= cutoff:
            filtered_history.append({"timestamp": timestamp.isoformat(), "score": item.get("score", 0)})
    history_store[fixture_key] = filtered_history[-60:]
    st.session_state["intensity_history"] = history_store
    if status["short"] in LIVE_STATUS_CODES:
        if len(filtered_history) >= 2:
            history_df = pd.DataFrame(filtered_history)
            history_df["timestamp"] = pd.to_datetime(history_df["timestamp"], errors="coerce")
            history_df.dropna(subset=["timestamp"], inplace=True)
            history_df.sort_values("timestamp", inplace=True)
            if not history_df.empty:
                st.caption("Evolution de l'indice (30 dernieres minutes)")
                st.line_chart(history_df.set_index("timestamp")["score"])
        else:
            st.caption("Historique en cours de collecte, recharger la page pour suivre la courbe.")

    cache_info = cache_stats()
    offline_flag = is_offline_mode() or cache_info.get("offline", False)
    cache_expired = cache_info.get("expired", 0)
    cache_hits = cache_info.get("hits", 0)
    if offline_flag or (status["short"] in LIVE_STATUS_CODES and cache_expired > cache_hits):
        st.warning(
            "Mode degrade detecte : les donnees peuvent dater du cache (offline ou quota atteint). "
            "Verifier les horodatages avant d'agir.",
            icon="⚠️",
        )

    st.subheader("Resume match")
    for line in _match_summary_lines(fixture, home_strength, away_strength, status, context=context):
        st.markdown(line)

    st.subheader("Probabilites 1X2")
    st.markdown(
        "\n".join(
            [
                f"- Victoire {home_strength.name} : {_format_percentage(markets.get('home', 0.0))}",
                f"- Match nul : {_format_percentage(markets.get('draw', 0.0))}",
                f"- Victoire {away_strength.name} : {_format_percentage(markets.get('away', 0.0))}",
            ]
        )
    )

    bet_table_rows: List[Dict[str, Any]] = []
    if tips:
        with st.expander("Recommandations de mise", expanded=True):
            default_tip_odd = _odds_for_tip(tips[0], odds_map, home_name, away_name) if tips else None
            fallback_odd = default_tip_odd or bankroll_settings.default_odds
            odds_input_value = st.number_input(
                "Cote disponible",
                min_value=1.01,
                value=float(fallback_odd),
                step=0.05,
            )
            display_tips = tips[:8]
            table_rows = []
            for tip in display_tips:
                tip_odd = _odds_for_tip(tip, odds_map, home_name, away_name) or odds_input_value
                suggestion = suggest_stake(tip["probability"], tip_odd, bankroll_settings)
                entry = _store_tip_meta(tip_meta, tip["label"], tip_odd, suggestion, bankroll_settings)
                comment = entry.get("comment", "")
                table_rows.append(
                    {
                        "Selection": tip["label"],
                        "Probabilite %": round(tip["probability"] * 100, 1),
                        "Cote": round(tip_odd, 2),
                        "Mise EUR": round(suggestion["stake"], 2),
                        "Edge %": round(suggestion["edge"] * 100, 1),
                        "Gain attendu EUR": round(suggestion["expected_profit"], 2),
                        "Commentaire": comment,
                    }
                )
            if table_rows:
                main_tip = tips[0]
                main_tip_odd = table_rows[0]["Cote"]
                main_suggestion = suggest_stake(main_tip["probability"], main_tip_odd, bankroll_settings)
                col_stake, col_edge, col_profit = st.columns(3)
                col_stake.metric("Mise recommandee", f"{main_suggestion['stake']:.2f} EUR", help=main_tip["label"])
                col_edge.metric("Edge estime", f"{main_suggestion['edge'] * 100:.1f}%")
                col_profit.metric("Gain attendu", f"{main_suggestion['expected_profit']:.2f} EUR")
                main_comment = _stake_comment(main_suggestion, bankroll_settings)
                if main_comment:
                    col_stake.caption(main_comment)
                edge_value = float(main_suggestion.get("edge") or 0.0)
                edge_threshold_pct = float(alert_settings.get("edge_threshold_pct", 7.5))
                edge_threshold = edge_threshold_pct / 100.0
                edge_ttl = max(120, int(alert_settings.get("edge_dedup_minutes", 45) * 60))
                if edge_value >= edge_threshold:
                    edge_pct = edge_value * 100.0
                    warn_threshold = edge_threshold_pct + 3.0
                    severity = "warning" if edge_pct >= warn_threshold else "info"
                    notify_event(
                        "Edge detecte",
                        (
                            f"{home_name} vs {away_name} - {main_tip['label']} "
                            f"(edge {edge_pct:.1f} %, cote {main_tip_odd:.2f})."
                        ),
                        severity=severity,
                        tags=["predictions", "edge"],
                        dedup_key=f"edge_{fixture_id}_{main_tip['label']}",
                        ttl_seconds=edge_ttl,
                        extra={
                            "fixture_id": fixture_id,
                            "league_id": league_id,
                            "season": season,
                            "tip": main_tip["label"],
                            "edge_pct": edge_pct,
                            "probability_pct": main_tip["probability"] * 100.0,
                            "threshold_pct": edge_threshold_pct,
                        },
                    )
                table_df = pd.DataFrame(table_rows)
                if "Commentaire" in table_df.columns:
                    if table_df["Commentaire"].fillna("").str.strip().eq("").all():
                        table_df.drop(columns=["Commentaire"], inplace=True)
                    else:
                        table_df["Commentaire"].replace("", pd.NA, inplace=True)
                st.dataframe(table_df, hide_index=True, use_container_width=True)
                st.caption("Les mises sont calculees avec la bankroll, les cotes API (si disponibles) et la valeur saisie en cas d'absence.")
                if (
                    isinstance(bias_summary, dict)
                    and (bias_summary.get("sample", 0) or 0) >= 25
                    and all(bias_summary.get(key) is not None for key in ("actual", "predicted"))
                ):
                    st.caption(
                        "Calibration Over/Under : modele {:.1%} vs resultats {:.1%} ({} matchs recents).".format(
                            float(bias_summary["predicted"]),
                            float(bias_summary["actual"]),
                            int(bias_summary["sample"]),
                        )
                    )
            bet_table_rows = table_rows

    if tips:
        with st.expander("Confirmer un pari jouÃ©", expanded=False):
            available_labels = [row["Selection"] for row in bet_table_rows] or [tip["label"] for tip in tips[:8]]
            if not available_labels:
                st.info("Aucune recommandation Ã  enregistrer pour ce match.")
            else:
                default_label = available_labels[0]
                default_meta = tip_meta.get(default_label, {})
                default_odd_value = float(default_meta.get("odd") or bankroll_settings.default_odds)
                default_stake_value = float(default_meta.get("stake") or 0.0)
                form_key = f"bet_form_{fixture_id}_{status.get('short', '')}"
                with st.form(form_key):
                    selection = st.selectbox("SÃ©lection jouÃ©e", available_labels, index=0)
                    bookmaker_value = st.text_input("Bookmaker", value="")
                    selection_meta = tip_meta.get(selection, default_meta)
                    odd_default = float(selection_meta.get("odd") or default_odd_value)
                    stake_default = float(selection_meta.get("stake") or default_stake_value)
                    odd_value = st.number_input(
                        "Cote prise",
                        min_value=1.01,
                        value=float(odd_default),
                        step=0.05,
                        key=f"bet_odd_{form_key}",
                    )
                    stake_value = st.number_input(
                        "Mise engagÃ©e (â‚¬)",
                        min_value=0.0,
                        value=float(stake_default),
                        step=1.0,
                        key=f"bet_stake_{form_key}",
                    )
                    notes_value = st.text_area("Notes (optionnel)", value="", height=70, key=f"bet_notes_{form_key}")
                    submitted = st.form_submit_button("Enregistrer ce pari")
                if submitted:
                    success = record_bet(
                        fixture_id,
                        status_snapshot=status.get("short"),
                        selection=selection,
                        bookmaker=bookmaker_value.strip(),
                        odd=odd_value,
                        stake=stake_value,
                        notes=notes_value.strip(),
                        profile_id=bankroll_settings.profile_id,
                        profile_name=bankroll_settings.profile_name,
                    )
                    if success:
                        st.success("Pari enregistrÃ© dans l'historique.")
                        st.experimental_rerun()
                    else:
                        st.error("Impossible d'enregistrer le pari (entrÃ©e introuvable).")

    cashout_advice = _cashout_recommendations(
        tips,
        tip_meta,
        status,
        home_name,
        away_name,
        markets,
        projection_matrix,
        pressure_metrics,
    )
    if cashout_advice:
        st.subheader("Option cashout (live)")
        for entry in cashout_advice:
            if entry['action'] == 'cashout':
                st.warning(f"Cashout recommande sur **{entry['label']}** : {entry['reason']}", icon="⚠️")
            else:
                st.info(f"Maintien possible sur **{entry['label']}** : {entry['reason']}")
        if alert_settings.get("cashout_alert_enabled", True):
            cashout_ttl = max(60, int(alert_settings.get("cashout_dedup_minutes", 20) * 60))
            for entry in cashout_advice:
                if entry.get("action") != "cashout":
                    continue
                label = entry.get("label", "Pari")
                label_token = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or "bet"
                notify_event(
                    "Cashout critique",
                    f"{label} sur {home_name} vs {away_name} : {entry.get('reason', '')}",
                    severity="warning",
                    tags=["cashout", "bet"],
                    dedup_key=f"cashout_{fixture_id}_{label_token}",
                    ttl_seconds=cashout_ttl,
                )

    high_intensity_flag = intensity["score"] >= 75
    if high_intensity_flag:
        competitive_edges: List[float] = []
        max_confidence = 0
        for tip in tips[:8]:
            max_confidence = max(max_confidence, tip.get("confidence", 0))
            detail = tip_meta.get(tip["label"])
            if detail is None:
                tip_odd = _odds_for_tip(tip, odds_map, home_name, away_name) or odds_input_value
                suggestion = suggest_stake(tip["probability"], tip_odd, bankroll_settings)
                detail = _store_tip_meta(tip_meta, tip["label"], tip_odd, suggestion, bankroll_settings)
            competitive_edges.append(detail.get("edge", 0.0))
        has_positive_edge = any(edge for edge in competitive_edges if edge and edge > 0)
        if (max_confidence < 60) or not has_positive_edge:
            st.warning(
                "Indice d'intensite eleve mais aucune selection ne franchit vos seuils de confiance/edge. "
                "Requalifier le match avant d'engager des mises.",
                icon="⚠️",
            )

    selected_tip_rows: List[Dict[str, Any]] = []
    score_selected_rows: List[Dict[str, Any]] = []
    scorer_selected_rows: List[Dict[str, Any]] = []

    if tips:
        st.subheader("Paris conseilles (classes)")
        for idx, tip in enumerate(tips, start=1):
            headline = (
                f"{idx}. **{tip['label']}** - proba ~ {_format_percentage(tip['probability'])} - "
                f"confiance {tip['confidence']}/100"
            )
            st.markdown(f"{headline}  \n_{tip['reason']}_")
            bet_key = _bet_state_key(fixture_id, tip["label"])
            default_checked = tracker.get(bet_key, False)
            checked = st.checkbox(
                f"Pari #{idx} joue ?",
                value=default_checked,
                key=bet_key,
                help=f"{tip['label']} - {_format_percentage(tip['probability'])} (confiance {tip['confidence']}/100)",
            )
            tracker[bet_key] = checked

            detail = tip_meta.get(tip["label"])
            if detail is None:
                tip_odd = _odds_for_tip(tip, odds_map, home_name, away_name) or odds_input_value
                suggestion = suggest_stake(tip["probability"], tip_odd, bankroll_settings)
                detail = _store_tip_meta(tip_meta, tip["label"], tip_odd, suggestion, bankroll_settings)

            combo_selection_key = _combo_state_key(fixture_id, tip["label"])
            combo_checked_default = combo_selection_key in _combo_cart()
            combo_checked = st.checkbox(
                f"Inclure dans le combinÃ© #{idx}",
                value=combo_checked_default,
                key=combo_selection_key,
                help="Ajoute ce pari au ticket combinÃ© multi-matchs.",
            )
            if combo_checked:
                try:
                    odd_value = float(detail.get("odd"))
                except (TypeError, ValueError):
                    odd_value = None
                if odd_value is None or odd_value <= 0:
                    try:
                        odd_value = float(odds_input_value)
                    except (TypeError, ValueError):
                        odd_value = 1.0
                probability_value = float(tip.get("probability") or 0.0)
                selection = {
                    "fixture_id": fixture_id,
                    "label": tip["label"],
                    "odd": odd_value,
                    "probability": max(0.0, min(1.0, probability_value)),
                    "match_label": f"{home_name} vs {away_name}",
                    "league_id": league_id,
                    "season": season,
                    "fixture_date": _format_datetime(fixture.get("fixture", {}).get("date")),
                }
                _add_to_combo(combo_selection_key, selection)
            else:
                _remove_from_combo(combo_selection_key)

            if checked:
                selected_tip_rows.append(
                    {
                        "Pari": tip["label"],
                        "Probabilite %": round(tip["probability"] * 100, 1),
                        "Confiance /100": tip["confidence"],
                        "Cote": round(detail["odd"], 2),
                        "Mise EUR": round(detail["stake"], 2),
                        "Gain attendu EUR": round(detail["expected_profit"], 2),
                    }
                )

    st.subheader("Top 5 scores probables")
    if top_scores:
        for idx, item in enumerate(top_scores[:5], start=1):
            score_line = f"{idx}. {item['label']} - {_format_percentage(item['prob'])}"
            st.markdown(score_line)
            score_key = _bet_state_key(f"{fixture_id}_score", item["label"])
            default_score_checked = tracker.get(score_key, False)
            score_checked = st.checkbox(
                f"Score #{idx} joue ?",
                value=default_score_checked,
                key=score_key,
                help=score_line,
            )
            tracker[score_key] = score_checked

            if score_checked:
                score_selected_rows.append(
                    {
                        "Score": item["label"],
                        "Probabilite %": round(item["prob"] * 100, 1),
                    }
                )
    else:
        st.markdown("Donnees insuffisantes.")

    snapshot_args = (
        fixture_id,
        league_id,
        season,
        home_team.get("name", "Equipe A"),
        away_team.get("name", "Equipe B"),
        (fixture.get("fixture") or {}).get("date"),
        projection_probs,
        markets,
        tips,
        top_scores,
        status,
    )

    if selected_tip_rows or score_selected_rows or scorer_selected_rows:
        st.markdown("### Suivi session")
        if selected_tip_rows:
            st.markdown("**Paris recommandes**")
            st.dataframe(pd.DataFrame(selected_tip_rows), hide_index=True, use_container_width=True)
        if score_selected_rows:
            st.markdown("**Scores joues**")
            st.dataframe(pd.DataFrame(score_selected_rows), hide_index=True, use_container_width=True)
        if scorer_selected_rows:
            st.markdown("**Buteurs joues**")
            st.dataframe(pd.DataFrame(scorer_selected_rows), hide_index=True, use_container_width=True)
        action_cols = st.columns([2, 1])
        with action_cols[0]:
            confirm_disabled = not (selected_tip_rows or score_selected_rows or scorer_selected_rows)
            confirm_help = (
                "Sélectionne au moins un pari, score ou buteur avant de confirmer."
                if confirm_disabled
                else "Enregistre ces paris dans l'historique et envoie une notification."
            )
            if st.button(
                "Confirmer ces paris",
                key=f"confirm_{fixture_id}",
                disabled=confirm_disabled,
                help=confirm_help,
            ):
                if confirm_disabled:
                    st.warning("Sélectionne un pari avant confirmation.")
                else:
                    bet_components: List[str] = []
                    bet_components.extend(row["Pari"] for row in selected_tip_rows)
                    bet_components.extend(f"Score {row['Score']}" for row in score_selected_rows)
                    bet_components.extend(f"Buteur {row['Joueur']}" for row in scorer_selected_rows)
                    bet_label = " + ".join(bet_components)
                    _log_prediction_snapshot(*snapshot_args, bet_selection=bet_label)
                    notify_event(
                        "Paris confirmés",
                        f"{bet_label} sur {home_team.get('name', 'Equipe A')} vs {away_team.get('name', 'Equipe B')}",
                        tags=["bet", home_team.get("name", ""), away_team.get("name", "")],
                    )
                    st.success(f"Paris confirmés : {bet_label}")
        with action_cols[1]:
            if st.button("Reinitialiser le suivi", key=f"reset_{fixture_id}"):
                for tip in tips:
                    bet_key = _bet_state_key(fixture_id, tip["label"])
                    tracker.pop(bet_key, None)
                    if bet_key in st.session_state:
                        del st.session_state[bet_key]
                for item in top_scores[:5]:
                    score_key = _bet_state_key(f"{fixture_id}_score", item["label"])
                    tracker.pop(score_key, None)
                    if score_key in st.session_state:
                        del st.session_state[score_key]
                scorer_prefix = f"bet_{fixture_id}_scorer"
                scorer_state_keys = [
                    key for key in list(tracker.keys()) if isinstance(key, str) and key.startswith(scorer_prefix)
                ]
                for scorer_key in scorer_state_keys:
                    tracker.pop(scorer_key, None)
                    if scorer_key in st.session_state:
                        del st.session_state[scorer_key]
                st.session_state["bet_tracker"] = tracker
                st.rerun()
    else:
        st.caption("Coche un pari, un score ou un buteur ci-dessus pour l'ajouter a ton suivi de session.")

    _render_combo_cart(bankroll_settings)

    injured_home_names: set[str] = set()
    injured_away_names: set[str] = set()

    with st.spinner("Analyse buteurs / blessures..."):
        top_scorers, topscorers_fallback_season = _topscorers_best_effort(league_id, season)
        players_home = _players_best_effort(league_id, season, int(home_id))
        players_away = _players_best_effort(league_id, season, int(away_id))
        injured_home_names = _injured_name_set(injuries_home)
        injured_away_names = _injured_name_set(injuries_away)

    scorers = probable_goalscorers(
        league_id,
        season,
        int(home_id),
        int(away_id),
        home_strength.lambda_value,
        away_strength.lambda_value,
        top_scorers,
        players_home,
        players_away,
        injured_home=injured_home_names,
        injured_away=injured_away_names,
    )
    st.subheader("Buteurs probables")
    if scorers:
        scorers_table = [
            {
                "Joueur": s["name"],
                "Probabilite %": round(s["prob"] * 100, 1),
                "Source": "Topscorers" if s.get("source") == "topscorers" else "Effectif",
            }
            for s in scorers
        ]
        st.dataframe(pd.DataFrame(scorers_table), hide_index=True, use_container_width=True)
        st.markdown("Selectionne les buteurs a suivre :")
        for idx, scorer in enumerate(scorers[:8], start=1):
            scorer_key = _bet_state_key(f"{fixture_id}_scorer", scorer["name"])
            default_scorer_checked = tracker.get(scorer_key, False)
            label = f"Buteur #{idx} : {scorer['name']} ({scorer['prob'] * 100:.1f}%)"
            scorer_checked = st.checkbox(
                label,
                value=default_scorer_checked,
                key=scorer_key,
                help=f"Probabilite {_format_percentage(scorer['prob'])} - source {scorer.get('source', 'model')}",
            )
            tracker[scorer_key] = scorer_checked
            if scorer_checked:
                scorer_selected_rows.append(
                    {
                        "Joueur": scorer["name"],
                        "Probabilite %": round(scorer["prob"] * 100, 1),
                        "Source": "Topscorers" if scorer.get("source") == "topscorers" else "Effectif",
                    }
                )
        if topscorers_fallback_season and topscorers_fallback_season != season:
            st.caption(f"Buteurs bases sur la saison {topscorers_fallback_season}.")
    else:
        if topscorers_fallback_season and topscorers_fallback_season != season:
            st.info(
                f"Pas de buteurs publies pour {season} ; aucune donnee reutilisable en {topscorers_fallback_season}."
            )
        else:
            st.info("Pas assez de donnees pour proposer des buteurs probables.")

    st.subheader("Analyse IA - Ton expert")
    note_lines, disclaimer = _note_ia_lines(
        home_strength,
        away_strength,
        projection_probs,
        top_scores,
        tips,
        status,
        context,
        pressure_metrics,
        baseline_probs,
    )
    for line in note_lines:
        st.markdown(f"- {line}")
    st.caption(disclaimer)
    st.caption(bankroll_caption)

    dynamic_prompts: List[str] = []
    weather_desc = str(getattr(context, "weather", "") or "")
    if weather_desc:
        dynamic_prompts.append(
            f"Impact meteo : demande a l'IA comment {weather_desc.lower()} influence les marches Over/Under ou BTTS."
        )
    injuries_list = getattr(context, "injuries", []) or []
    red_cards_list = getattr(context, "red_cards", []) or []
    if alert_settings.get("context_alert_enabled", True):
        alert_lines: List[str] = []
        signature_parts: List[str] = []
        if red_cards_list:
            alert_lines.append("Cartons rouges: " + ", ".join(red_cards_list))
            signature_parts.append("RC:" + "|".join(sorted(red_cards_list)))
        if injuries_list:
            alert_lines.append("Blessures: " + ", ".join(injuries_list))
            signature_parts.append("INJ:" + "|".join(sorted(injuries_list)))
        if alert_lines and signature_parts:
            context_signature = "_".join(signature_parts)
            notify_event(
                "Alerte contexte critique",
                f"{home_name} vs {away_name} • " + " | ".join(alert_lines),
                severity="warning",
                tags=["context", "injury"],
                dedup_key=f"context_{fixture_id}_{context_signature}",
                ttl_seconds=max(900, int(alert_settings.get("edge_dedup_minutes", 45) * 60)),
            )
    if injuries_list or red_cards_list:
        alerts_parts: List[str] = []
        if red_cards_list:
            alerts_parts.append("cartons rouges: " + ", ".join(red_cards_list))
        if injuries_list:
            alerts_parts.append("blessures: " + ", ".join(injuries_list))
        dynamic_prompts.append(
            "Absences detectees (" + " | ".join(alerts_parts) + "). "
            "Prompt suggere : \"Quelle strategie adopter avec ces absences et quels joueurs alternatifs surveiller ?\""
        )
    if pressure_metrics and pressure_metrics.get("score", 0.0) >= 0.6:
        dynamic_prompts.append(
            "Pression offensive tres elevee, la securite prime."
        )
    favorites = get_favorite_competitions()
    if favorites:
        for favorite in favorites:
            try:
                fav_league = int(favorite.get("league_id"))
            except (TypeError, ValueError):
                continue
            fav_season = favorite.get("season")
            if fav_league == int(league_id) and (fav_season in {None, season}):
                label = favorite.get("label") or home_team.get("name") or "ton favori"
                dynamic_prompts.append(
                    f"Favori detecte ({label}). Prompt : \"Compare ce match avec le calendrier de {label} et identifie les risques de fatigue ou rotation.\""
                )
                break
    if dynamic_prompts:
        with st.expander("Prompts dynamiques IA", expanded=False):
            for prompt in dynamic_prompts:
                st.write(f"- {prompt}")

    ai_payload = _build_ai_match_payload(
        fixture=fixture,
        fixture_id=fixture_id,
        league_id=league_id,
        season=season,
        home_team=home_team,
        away_team=away_team,
        home_strength=home_strength,
        away_strength=away_strength,
        status=status,
        projection_probs=projection_probs,
        markets=markets,
        baseline_probs=baseline_probs or {},
        tips=tips,
        top_scores=top_scores,
        intensity_snapshot=intensity_snapshot,
        pressure_metrics=pressure_metrics,
        context=context,
        odds_map=odds_map,
        bankroll_settings=bankroll_settings,
    )
    history_meta = {"fixture_id": fixture_id, "status_short": status.get("short", "NS")}

    with st.expander("Analyse IA (OpenAI)", expanded=False):
        _render_ai_analysis_section(
            fixture_id,
            ai_payload,
            history_meta,
            extra_instruction=ai_preferences.get("analysis_instruction"),
        )
    if ai_preferences.get("commentator_enabled", True):
        with st.expander("Commentateur IA (TV)", expanded=False):
            _render_ai_commentator_section(
                fixture_id,
                ai_payload,
                status=status,
                pressure_metrics=pressure_metrics,
                intensity_snapshot=intensity_snapshot,
                context=context,
                extra_instruction=ai_preferences.get("commentator_instruction"),
            )
    with st.expander("Sc�narios IA (what-if)", expanded=False):
        _render_ai_scenarios_section(
            fixture_id,
            ai_payload,
            projection_probs,
            intensity_snapshot,
            pressure_metrics,
            history_meta,
            home_label=home_team.get("name", "Equipe A"),
            away_label=away_team.get("name", "Equipe B"),
        )
    with st.expander("Moteur local (comparaison rapide)", expanded=False):
        _render_alt_projection_section(
            fixture_id,
            projection_probs,
            intensity_snapshot,
            pressure_metrics,
            history_meta,
            home_label=home_team.get("name", "Equipe A"),
            away_label=away_team.get("name", "Equipe B"),
        )
    share_context = _build_share_context(
        fixture_id,
        home_team,
        away_team,
        status,
        projection_probs,
        markets,
        tips,
        tip_meta,
        intensity_snapshot,
        bankroll_settings,
    )
    with st.expander("Diffusion & partage", expanded=False):
        _render_engagement_panel(fixture_id, share_context)
    with st.expander("Marches couverts par le modele", expanded=False):
        from .prediction_model import MARKETS_CATALOG

        for code, description in MARKETS_CATALOG.items():
            st.markdown(f"- **{code}** : {description}")

    st.markdown("---")
    with st.expander("Donnees API officielles", expanded=False):
        with st.spinner("Chargement des predictions API..."):
            api_predictions = get_predictions(fixture_id)
        if api_predictions:
            entry = api_predictions[0] if isinstance(api_predictions, list) else api_predictions
            prediction = entry.get("prediction") or {}
            winner = prediction.get("winner", {}).get("name", "N/A")
            percent = prediction.get("percent") or {}
            st.write(f"**API :** gagnant estime : {winner}")
            st.write(
                "Probabilites API - Domicile: {home}% | Nul: {draw}% | Exterieur: {away}%".format(
                    home=percent.get("home", "N/A"),
                    draw=percent.get("draw", "N/A"),
                    away=percent.get("away", "N/A"),
                )
            )
            advice = prediction.get("advice")
            if advice:
                st.write(f"Conseil API : {advice}")
            comparison = entry.get("comparison")
            payload = comparison if comparison else prediction
            st.code(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            st.info("Pas de predictions officielles fournies par l'API pour ce match.")

    with st.expander("Widget officiel API-FOOTBALL", expanded=False):
        render_widget("fixture", fixture=fixture_id, season=season, league=league_id)

    if st.button("Rafraichir l'analyse", use_container_width=True):
        st.rerun()

    _log_prediction_snapshot(*snapshot_args)
    _update_history_if_finished(fixture_id, status, teams)
