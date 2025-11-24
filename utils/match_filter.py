from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_cls, datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional

from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st

from . import api_calls
from .api_calls import get_fixtures, get_odds
from .prediction_history import load_prediction_history
from .profile import aliases_map, get_ui_defaults, save_ui_defaults
from .ui_helpers import select_league_and_season
from .supervision import health_snapshot

BOOKMAKER_PRESETS: Dict[str, set[str]] = {
    "Betclic": {"betclic", "betclicfr"},
    "ParionsSport": {"parionssport", "parionssportfdj", "fdjparionssport", "parionssportfr"},
}

UPCOMING_STATUS = {"NS", "TBD", "PST"}
LIVE_STATUS = {"LIVE", "1H", "2H", "ET", "BT", "HT", "INT", "INP"}
FINISHED_STATUS = {"FT", "AET", "PEN", "CANC", "ABD", "AWD"}

PARIS_TZ = ZoneInfo("Europe/Paris")
MARKET_ALIASES = {"1x2", "match winner", "match result", "fulltime result"}
OVER_UNDER_MARKET_ALIASES = {
    "over/under",
    "goals over/under",
    "goals over/under - full time",
    "goals over/under (full time)",
    "total goals",
    "total goals (incl. ot)",
    "match goals over/under",
}
VALUE_ALIASES = {
    "1": "home",
    "home": "home",
    "home team": "home",
    "home win": "home",
    "w1": "home",
    "2": "away",
    "away": "away",
    "away team": "away",
    "away win": "away",
    "w2": "away",
    "x": "draw",
    "draw": "draw",
    "over 2.5": "over_2_5",
    "over2.5": "over_2_5",
    "over2,5": "over_2_5",
    "o 2.5": "over_2_5",
    "o2.5": "over_2_5",
    "o 25": "over_2_5",
    "o25": "over_2_5",
    "over (2.5)": "over_2_5",
    "plus de 2.5": "over_2_5",
    "over 25": "over_2_5",
    "over 2.5 goals": "over_2_5",
    "over 25 goals": "over_2_5",
    "under 2.5": "under_2_5",
    "under2.5": "under_2_5",
    "under2,5": "under_2_5",
    "u 2.5": "under_2_5",
    "u2.5": "under_2_5",
    "u 25": "under_2_5",
    "u25": "under_2_5",
    "under (2.5)": "under_2_5",
    "moins de 2.5": "under_2_5",
    "under 25": "under_2_5",
    "under 2.5 goals": "under_2_5",
    "under 25 goals": "under_2_5",
}


def normalize_bookmaker(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def build_alias_lookup(custom_aliases: Optional[Dict[str, Iterable[str]]] = None) -> Dict[str, set[str]]:
    lookup: Dict[str, set[str]] = {}
    for label, aliases in BOOKMAKER_PRESETS.items():
        tokens = {normalize_bookmaker(label)}
        tokens.update(normalize_bookmaker(alias) for alias in aliases)
        lookup[label] = tokens
    if custom_aliases:
        for label, aliases in custom_aliases.items():
            tokens = {normalize_bookmaker(label)}
            for alias in aliases:
                tokens.add(normalize_bookmaker(alias))
            lookup[label] = tokens
    return lookup


def resolve_bookmakers(labels: Iterable[str], custom_aliases: Optional[Dict[str, Iterable[str]]] = None) -> set[str]:
    lookup = build_alias_lookup(custom_aliases)
    resolved: set[str] = set()
    for label in labels:
        tokens = lookup.get(label)
        if tokens:
            resolved.update(tokens)
        else:
            resolved.add(normalize_bookmaker(label))
    return resolved


def _custom_label_map(custom_aliases: Dict[str, Iterable[str]]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for label, aliases in custom_aliases.items():
        mapping[normalize_bookmaker(label)] = label
        for alias in aliases:
            mapping[normalize_bookmaker(alias)] = label
    for preset in BOOKMAKER_PRESETS:
        mapping[normalize_bookmaker(preset)] = preset
    return mapping


def _prediction_side(row: pd.Series) -> Optional[str]:
    pick = str(row.get("main_pick", ""))
    home = str(row.get("home_team", ""))
    away = str(row.get("away_team", ""))
    pick_lower = pick.lower()
    if home and home.lower() in pick_lower or "home" in pick_lower or "1" in pick_lower:
        return "home"
    if away and away.lower() in pick_lower or "away" in pick_lower or "2" in pick_lower:
        return "away"
    if "nul" in pick_lower or "draw" in pick_lower or "x" in pick_lower:
        return "draw"
    return None


def _probability_for_side(row: pd.Series, side: str) -> Optional[float]:
    column_map = {
        "home": "prob_home",
        "draw": "prob_draw",
        "away": "prob_away",
    }
    try:
        return float(row.get(column_map.get(side, "")))
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> Optional[float]:
    if value in {None, "", "nan"}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=1)
def _prediction_map() -> Dict[int, Dict[str, Any]]:
    df = load_prediction_history()
    if df.empty:
        return {}
    mapping: Dict[int, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        fixture = row.get("fixture_id")
        if pd.isna(fixture):
            continue
        try:
            fixture_id = int(fixture)
        except (TypeError, ValueError):
            continue
        side = _prediction_side(row)
        if not side:
            continue
        probability = _probability_for_side(row, side)
        if probability is None:
            continue
        mapping[fixture_id] = {
            "side": side,
            "probability": probability,
            "pick": row.get("main_pick"),
            "home": row.get("home_team"),
            "away": row.get("away_team"),
            "prob_over_2_5": _safe_float(row.get("prob_over_2_5")),
            "prob_under_2_5": _safe_float(row.get("prob_under_2_5")),
        }
        if mapping[fixture_id]["prob_under_2_5"] is None and mapping[fixture_id]["prob_over_2_5"] is not None:
            over_val = mapping[fixture_id]["prob_over_2_5"]
            mapping[fixture_id]["prob_under_2_5"] = max(0.0, min(1.0, 1.0 - over_val))
    return mapping


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _format_local(dt: Optional[datetime]) -> str:
    if dt is None:
        return "Date inconnue"
    try:
        localized = dt.astimezone(PARIS_TZ)
        return localized.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return dt.isoformat(timespec="minutes")


def _extract_markets(bookmaker: Dict[str, Any]) -> Dict[str, float]:
    markets: Dict[str, float] = {}
    for bet in bookmaker.get("bets") or []:
        if not isinstance(bet, dict):
            continue
        raw_market = str(bet.get("name", "")).strip()
        market = raw_market.lower()
        is_main_market = market in MARKET_ALIASES
        is_over_under_market = (
            market in OVER_UNDER_MARKET_ALIASES
            or ("over" in market and "under" in market and ("2.5" in market or "2,5" in market or "25" in market))
        )
        if is_over_under_market and any(flag in market for flag in {"first half", "second half", "1st half", "2nd half"}):
            # Ignore partial-time markets to stay on full-time context
            continue
        if not is_main_market and not is_over_under_market:
            continue
        for value in bet.get("values") or []:
            label_raw = str(value.get("value", "")).strip()
            label = label_raw.lower()
            compact = label.replace(" ", "")
            sanitized = compact.replace(".", "").replace(",", "")
            outcome = VALUE_ALIASES.get(label)
            if not outcome:
                outcome = VALUE_ALIASES.get(compact)
            if not outcome:
                outcome = VALUE_ALIASES.get(sanitized)
            if not outcome and "/" in label:
                outcome = VALUE_ALIASES.get(label.replace("/", ""))
            if not outcome:
                continue
            if outcome in {"over_2_5", "under_2_5"}:
                if not is_over_under_market:
                    continue
                if "2.5" not in label and "2,5" not in label and "25" not in label:
                    continue
            elif not is_main_market:
                # Avoid mapping unrelated markets (handicaps etc.) to 1X2 outcomes
                continue
            try:
                odd = float(value.get("odd"))
            except (TypeError, ValueError):
                continue
            markets[outcome] = odd
    return markets


def _index_odds(odds_payload: Any) -> Dict[int, Dict[str, Any]]:
    index: Dict[int, Dict[str, Any]] = {}
    entries = odds_payload if isinstance(odds_payload, list) else []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        fixture = entry.get("fixture") or {}
        fixture_id = fixture.get("id")
        if fixture_id is None:
            continue
        bookmakers = entry.get("bookmakers") or []
        detail: List[Dict[str, Any]] = []
        names: List[str] = []
        for bookmaker in bookmakers:
            if not isinstance(bookmaker, dict):
                continue
            name = str(bookmaker.get("name", "")).strip()
            if not name:
                continue
            markets = _extract_markets(bookmaker)
            if not markets:
                continue
            detail.append(
                {
                    "name": name,
                    "normalized": normalize_bookmaker(name),
                    "markets": markets,
                }
            )
            names.append(name)
        index[int(fixture_id)] = {"detail": detail, "bookmakers": names}
    return index


@dataclass
class MatchAvailability:
    fixture_id: int
    league_id: Optional[int]
    season: Optional[int]
    home: str
    away: str
    kickoff_utc: Optional[datetime]
    status_short: str
    bookmakers: List[str]
    bookmaker_detail: List[Dict[str, Any]]

    @property
    def label(self) -> str:
        return f"{self.home} vs {self.away}"

    @property
    def kickoff_local_text(self) -> str:
        return _format_local(self.kickoff_utc)


def _build_match_entry(
    fixture: Dict[str, Any],
    odds_index: Dict[int, Dict[str, Any]],
) -> Optional[MatchAvailability]:
    fixture_block = fixture.get("fixture") or {}
    teams = fixture.get("teams") or {}
    fixture_id = fixture_block.get("id")
    if fixture_id is None:
        return None
    league = fixture.get("league") or {}
    status = fixture_block.get("status") or {}
    odds_info = odds_index.get(int(fixture_id), {"detail": [], "bookmakers": []})
    return MatchAvailability(
        fixture_id=int(fixture_id),
        league_id=league.get("id"),
        season=league.get("season"),
        home=teams.get("home", {}).get("name", "Equipe A"),
        away=teams.get("away", {}).get("name", "Equipe B"),
        kickoff_utc=_parse_datetime(fixture_block.get("date")),
        status_short=str(status.get("short", "NS")).upper(),
        bookmakers=odds_info.get("bookmakers", []),
        bookmaker_detail=odds_info.get("detail", []),
    )


def get_league_matches_with_availability(
    league_id: int,
    season: int,
    *,
    bookmakers: Optional[Iterable[str]] = None,
    custom_aliases: Optional[Dict[str, Iterable[str]]] = None,
    date_filter: Optional[date_cls] = None,
    status_filter: Optional[set[str]] = None,
    next_n: Optional[int] = None,
    last_n: Optional[int] = None,
) -> List[MatchAvailability]:
    odds_payload = get_odds(league_id, season, date_filter.isoformat() if date_filter else None) or []
    odds_index = _index_odds(odds_payload)

    fixtures = get_fixtures(
        league_id=league_id,
        season=season,
        next_n=next_n,
        last_n=last_n,
    ) or []

    matches: List[MatchAvailability] = []
    for fx in fixtures:
        entry = _build_match_entry(fx, odds_index)
        if not entry:
            continue
        if status_filter and entry.status_short not in status_filter:
            continue
        if date_filter and (not entry.kickoff_utc or entry.kickoff_utc.date() != date_filter):
            continue
        matches.append(entry)
    matches.sort(key=lambda item: (item.kickoff_utc or datetime.max, item.label))
    return matches


def _fetch_generic(path: str, params: Dict[str, Any]) -> Any:
    return api_calls._request(path, params)  # type: ignore[attr-defined]


def get_matches_by_date(
    target_date: date_cls,
    *,
    bookmakers: Optional[Iterable[str]] = None,
    custom_aliases: Optional[Dict[str, Iterable[str]]] = None,
) -> List[MatchAvailability]:
    odds_index = _index_odds(_fetch_generic("odds", {"date": target_date.isoformat()}) or [])
    fixtures_payload = _fetch_generic("fixtures", {"date": target_date.isoformat()}) or []

    matches: List[MatchAvailability] = []
    for fx in fixtures_payload:
        entry = _build_match_entry(fx, odds_index)
        if entry:
            matches.append(entry)
    matches.sort(key=lambda item: (item.kickoff_utc or datetime.max, item.label))
    return matches


def get_matches_over_horizon(
    start_date: date_cls,
    *,
    days: int,
    bookmakers: Optional[Iterable[str]] = None,
    custom_aliases: Optional[Dict[str, Iterable[str]]] = None,
) -> List[MatchAvailability]:
    days = max(1, days)
    combined: List[MatchAvailability] = []
    for offset in range(days):
        current = start_date + timedelta(days=offset)
        day_matches = get_matches_by_date(
            current,
            bookmakers=bookmakers,
            custom_aliases=custom_aliases,
        )
        combined.extend(day_matches)
    combined.sort(key=lambda item: (item.kickoff_utc or datetime.max, item.label))
    return combined


def _edge_map(
    match: MatchAvailability,
    filter_tokens: set[str],
    *,
    prediction: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, float]]:
    if prediction is None:
        prediction = _prediction_map().get(match.fixture_id)
    if not prediction:
        return {}
    side = prediction["side"]
    probability = prediction["probability"]
    edges: Dict[str, Dict[str, float]] = {}
    for detail in match.bookmaker_detail:
        normalized = detail.get("normalized")
        if filter_tokens and normalized not in filter_tokens:
            continue
        odd = detail.get("markets", {}).get(side)
        if not odd:
            continue
        edges[normalized] = {
            "edge": odd * probability - 1,
            "odd": odd,
            "bookmaker": detail.get("name"),
        }
    return edges


def _edge_display(edge: Optional[Dict[str, float]]) -> str:
    if not edge:
        return "-"
    return f"{edge['edge']*100:+.1f}% ({edge['bookmaker']} {edge['odd']:.2f})"


def _secondary_edge_map(
    match: MatchAvailability,
    filter_tokens: set[str],
    *,
    prediction: Optional[Dict[str, Any]] = None,
) -> Dict[str, tuple[Optional[str], Optional[Dict[str, float]]]]:
    if prediction is None:
        prediction = _prediction_map().get(match.fixture_id)
    results: Dict[str, tuple[Optional[str], Optional[Dict[str, float]]]] = {
        "over_2_5": (None, None),
        "under_2_5": (None, None),
    }
    if not prediction:
        return results
    candidates = [
        ("over_2_5", prediction.get("prob_over_2_5")),
        ("under_2_5", prediction.get("prob_under_2_5")),
    ]
    for outcome_key, probability in candidates:
        if probability is None:
            continue
        best_norm: Optional[str] = None
        best_info: Optional[Dict[str, Any]] = None
        for detail in match.bookmaker_detail:
            normalized = detail.get("normalized")
            if filter_tokens and normalized not in filter_tokens:
                continue
            markets = detail.get("markets", {})
            odd = markets.get(outcome_key)
            if not odd:
                continue
            edge_value = odd * probability - 1
            info = {
                "edge": edge_value,
                "odd": odd,
                "bookmaker": detail.get("name"),
            }
            if best_info is None or edge_value > best_info["edge"]:
                best_info = info
                best_norm = normalized
        results[outcome_key] = (best_norm, best_info)
    return results


def _bookmaker_label(
    normalized: Optional[str],
    info: Optional[Dict[str, float]],
    alias_label_map: Dict[str, str],
) -> str:
    if not info:
        return "-"
    if normalized:
        label = alias_label_map.get(normalized)
        if label:
            return label
    name = info.get("bookmaker")
    if isinstance(name, str) and name:
        return name
    return "-"


def _availability_badge(match: MatchAvailability) -> tuple[str, str]:
    if match.bookmakers:
        return f"OK - {len(match.bookmakers)} book.", "green"
    return "ALERTE - non propose", "red"


def _build_table(
    matches: List[MatchAvailability],
    *,
    show_all: bool,
    filter_tokens: set[str],
    alias_label_map: Dict[str, str],
) -> pd.DataFrame:
    rows = []
    betclic_norm = normalize_bookmaker("Betclic")
    parions_norm = normalize_bookmaker("ParionsSport")
    predictions = _prediction_map()
    for match in matches:
        availability_text, _ = _availability_badge(match)
        if not show_all and not match.bookmakers:
            continue
        prediction = predictions.get(match.fixture_id)
        edge_map = _edge_map(match, filter_tokens, prediction=prediction)
        secondary_edges = _secondary_edge_map(match, filter_tokens, prediction=prediction)
        best_norm: Optional[str] = None
        best: Optional[Dict[str, float]] = None
        if edge_map:
            best_norm, best = max(edge_map.items(), key=lambda item: item[1]["edge"])
        betclic_edge = edge_map.get(betclic_norm)
        parions_edge = edge_map.get(parions_norm)
        custom_edges = [info for norm, info in edge_map.items() if norm not in {betclic_norm, parions_norm}]
        custom_best = max(custom_edges, key=lambda info: info["edge"], default=None)
        best_label = _bookmaker_label(best_norm, best, alias_label_map)
        best_odd = f"{best['odd']:.2f}" if best and isinstance(best.get("odd"), (int, float)) else "-"
        best_edge_pct = round(best["edge"] * 100, 1) if best else None
        over_norm, over_edge = secondary_edges.get("over_2_5", (None, None))
        under_norm, under_edge = secondary_edges.get("under_2_5", (None, None))
        rows.append(
            {
                "Date": match.kickoff_local_text,
                "Match": match.label,
                "Statut": match.status_short,
                "Disponibilite": availability_text,
                "Bookmakers detectes": ", ".join(match.bookmakers) or "-",
                "Edge %": best_edge_pct,
                "Edge global": _edge_display(best),
                "Edge Betclic": _edge_display(betclic_edge),
                "Edge ParionsSport": _edge_display(parions_edge),
                "Edge Custom": _edge_display(custom_best),
                "Edge Over 2.5": _edge_display(over_edge),
                "Book Over 2.5": _bookmaker_label(over_norm, over_edge, alias_label_map),
                "Edge Under 2.5": _edge_display(under_edge),
                "Book Under 2.5": _bookmaker_label(under_norm, under_edge, alias_label_map),
                "Meilleur bookmaker": best_label,
                "Meilleure cote": best_odd,
            }
        )
    return pd.DataFrame(rows)


def _top_edges(
    matches: List[MatchAvailability],
    *,
    filter_tokens: set[str],
    alias_label_map: Dict[str, str],
    limit: int = 5,
) -> List[Dict[str, Any]]:
    highlights: List[Dict[str, Any]] = []
    predictions = _prediction_map()
    for match in matches:
        prediction = predictions.get(match.fixture_id)
        edge_map = _edge_map(match, filter_tokens, prediction=prediction)
        if not edge_map:
            continue
        best_norm, best_info = max(edge_map.items(), key=lambda item: item[1]["edge"])
        highlights.append(
            {
                "Date": match.kickoff_local_text,
                "Match": match.label,
                "Edge %": round(best_info["edge"] * 100, 1),
                "Cote": f"{best_info['odd']:.2f}",
                "Bookmaker": _bookmaker_label(best_norm, best_info, alias_label_map),
            }
        )
    highlights.sort(key=lambda item: item["Edge %"], reverse=True)
    return highlights[:limit]


def show_bookmaker_availability(
    default_league_id: Optional[int] = None,
    default_season: Optional[int] = None,
) -> None:
    st.header("Matchs disponibles chez les bookmakers")
    st.caption("Comparer disponibilites + estimation IA (edge) par operateur.")

    snapshot = health_snapshot()
    if snapshot.get("offline"):
        reason = snapshot.get("offline_reason") or "Mode hors ligne actif"
        st.warning(
            f"Mode dégradé - {reason}. Les données proviennent du cache et peuvent être obsolètes.",
            icon="⚠️",
        )
    elif snapshot.get("low_quota"):
        remaining = snapshot.get("quota_remaining")
        limit = snapshot.get("quota_limit")
        st.info(
            f"Quota API faible ({remaining}/{limit}). Les nouvelles requêtes seront limitées.",
            icon="⚠️",
        )

    custom_aliases = aliases_map()
    ui_defaults = get_ui_defaults()
    alias_label_map = _custom_label_map(custom_aliases)
    bookmaker_choices = list(BOOKMAKER_PRESETS.keys()) + sorted(custom_aliases.keys())
    default_selection = [
        name for name in ui_defaults.get("bookmakers", []) if name in bookmaker_choices
    ]
    if not default_selection:
        default_selection = bookmaker_choices if bookmaker_choices else list(BOOKMAKER_PRESETS.keys())

    selected_bookmakers = st.multiselect(
        "Bookmakers suivis",
        options=bookmaker_choices,
        default=default_selection,
        help="Ajoutez vos operateurs dans Profil pour les retrouver ici."
    )
    filter_tokens = resolve_bookmakers(selected_bookmakers, custom_aliases)

    tab_league, tab_day = st.tabs(["Par ligue", "Par date"])

    pref_league = ui_defaults.get("league_id") or default_league_id
    pref_season = ui_defaults.get("season") or default_season
    selected_league_id = pref_league
    selected_season = pref_season

    with tab_league:
        league_id, season, league_label = select_league_and_season(
            default_league_id=pref_league,
            default_season=pref_season,
            key_prefix="book_",
        )
        st.caption(f"{league_label} - Saison {season}")
        selected_league_id = league_id
        selected_season = season

        col_filter, col_scope, col_show_all = st.columns([1, 1, 1])
        enable_date_filter = col_filter.checkbox("Filtrer par date", value=False, key="book_league_toggle")
        selected_date = None
        if enable_date_filter:
            selected_date = col_filter.date_input(
                "Date",
                value=datetime.now().date(),
                key="book_league_date",
            )
        scope = col_scope.selectbox(
            "Statut",
            ["A venir", "En direct", "Termines", "Tous"],
            key="book_league_scope",
        )
        show_all = col_show_all.checkbox(
            "Inclure matches sans cotes",
            value=False,
            key="book_league_show_all",
        )

        status_mapping = {
            "A venir": UPCOMING_STATUS,
            "En direct": LIVE_STATUS,
            "Termines": FINISHED_STATUS,
        }
        status_filter = status_mapping.get(scope)

        with st.spinner("Analyse des matches..."):
            matches = get_league_matches_with_availability(
                league_id,
                season,
                bookmakers=selected_bookmakers,
                custom_aliases=custom_aliases,
                date_filter=selected_date,
                status_filter=status_filter,
                next_n=60 if not selected_date else None,
            )

        df = _build_table(matches, show_all=show_all, filter_tokens=filter_tokens, alias_label_map=alias_label_map)
        if df.empty:
            st.info("Aucun match selon les filtres choisis.")
        else:
            st.dataframe(df, hide_index=True, use_container_width=True)
            st.caption("Colonnes Betclic/Parions/Custom = edge calcule par rapport a l'estimation IA.")

    preferred_horizon = int(ui_defaults.get("horizon_days", 1))
    horizon_days = preferred_horizon

    with tab_day:
        date_col, horizon_col = st.columns([2, 1])
        target_date = date_col.date_input(
            "Date de départ",
            value=datetime.now().date(),
            key="book_day_date",
        )
        horizon_days = int(
            horizon_col.slider(
                "Horizon (jours)",
                min_value=1,
                max_value=7,
                value=min(max(preferred_horizon, 1), 7),
                help="Affiche les matches et edges sur plusieurs journees consecutives.",
                key="book_day_horizon",
            )
        )
        show_all_day = st.checkbox(
            "Inclure matches sans cotes (toutes ligues)",
            value=False,
            key="book_day_show_all",
        )
        with st.spinner("Recuperation globale..."):
            if horizon_days > 1:
                matches_day = get_matches_over_horizon(
                    target_date,
                    days=horizon_days,
                    bookmakers=selected_bookmakers,
                    custom_aliases=custom_aliases,
                )
            else:
                matches_day = get_matches_by_date(
                    target_date,
                    bookmakers=selected_bookmakers,
                    custom_aliases=custom_aliases,
                )

        df_day = _build_table(matches_day, show_all=show_all_day, filter_tokens=filter_tokens, alias_label_map=alias_label_map)
        if df_day.empty:
            st.info("Aucun match trouve a cette date.")
        else:
            st.caption(f"{len(matches_day)} matches analyses sur {horizon_days} jour(s).")
            st.dataframe(df_day, hide_index=True, use_container_width=True)
            st.caption("Matches provenant de toutes les ligues couvertes par l'API pour cette date.")
            highlights = _top_edges(
                matches_day,
                filter_tokens=filter_tokens,
                alias_label_map=alias_label_map,
                limit=5,
            )
            if highlights:
                st.markdown("**Top edges 1X2 sur l'horizon selectionne**")
                st.table(pd.DataFrame(highlights))
                alert_edges = [entry for entry in highlights if entry["Edge %"] >= 5]
                if alert_edges:
                    st.success(f"{len(alert_edges)} edges >= 5% identifi�s.")

    if st.button("Sauvegarder ces filtres comme defaut", key="book_save_defaults"):
        save_ui_defaults(
            {
                "league_id": int(selected_league_id) if selected_league_id else None,
                "season": int(selected_season) if selected_season else None,
                "bookmakers": selected_bookmakers,
                "horizon_days": int(horizon_days),
            }
        )
        st.success("Filtres Bookmakers sauvegardes comme defaut.")
        st.experimental_rerun()


__all__ = [
    "MatchAvailability",
    "get_league_matches_with_availability",
    "get_matches_by_date",
    "get_matches_over_horizon",
    "show_bookmaker_availability",
    "BOOKMAKER_PRESETS",
    "UPCOMING_STATUS",
    "LIVE_STATUS",
    "FINISHED_STATUS",
    "normalize_bookmaker",
    "build_alias_lookup",
    "resolve_bookmakers",
]
