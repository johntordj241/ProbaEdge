from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import streamlit as st

from .api_calls import get_leagues, get_teams
from .models import normalize_team_list
from .profile import get_favorite_competitions, get_ui_defaults

COUNTRY_TRANSLATIONS: Dict[str, str] = {
    "Argentina": "Argentine",
    "Belgium": "Belgique",
    "Brazil": "Bresil",
    "Chile": "Chili",
    "China": "Chine",
    "Colombia": "Colombie",
    "Croatia": "Croatie",
    "Denmark": "Danemark",
    "Dominican Republic": "Republique dominicaine",
    "Ecuador": "Equateur",
    "Egypt": "Egypte",
    "England": "Angleterre",
    "France": "France",
    "Germany": "Allemagne",
    "Greece": "Grece",
    "Ireland": "Irlande",
    "Italy": "Italie",
    "Japan": "Japon",
    "Korea Republic": "Coree du Sud",
    "Mexico": "Mexique",
    "Morocco": "Maroc",
    "Netherlands": "Pays-Bas",
    "Norway": "Norvege",
    "Paraguay": "Paraguay",
    "Peru": "Perou",
    "Portugal": "Portugal",
    "Qatar": "Qatar",
    "Russia": "Russie",
    "Saudi Arabia": "Arabie saoudite",
    "Scotland": "Ecosse",
    "South Korea": "Coree du Sud",
    "Spain": "Espagne",
    "Sweden": "Suede",
    "Switzerland": "Suisse",
    "Tunisia": "Tunisie",
    "Turkey": "Turquie",
    "United States": "Etats-Unis",
    "Uruguay": "Uruguay",
    "Wales": "Pays de Galles",
}

CATEGORY_KEYWORDS = {
    "Feminin": ("women", "feminine", "femenino", "feminil", "ladies", "femmes"),
    "Jeunes": (
        "youth",
        "junior",
        "academy",
        "development",
        "u17",
        "u-17",
        "u18",
        "u-18",
        "u19",
        "u-19",
        "u20",
        "u-20",
        "u21",
        "u-21",
        "u22",
        "u-22",
        "u23",
        "u-23",
        "u15",
        "u-15",
        "u16",
        "u-16",
    ),
    "Reserve": ("reserve", "reserves", "b team", "b-team", "ii"),
    "Futsal": ("futsal",),
    "Beach Soccer": ("beach",),
}


def _detect_categories(name: str) -> Set[str]:
    lowered = name.lower()
    detected: Set[str] = set()
    for label, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            detected.add(label)
    if not detected:
        detected.add("Senior")
    return detected


def _translate_country(raw_name: Optional[str]) -> str:
    if not raw_name:
        return ""
    return COUNTRY_TRANSLATIONS.get(raw_name.strip(), raw_name.strip())


@st.cache_data(show_spinner=False, ttl=600)
def load_leagues() -> List[Dict[str, Any]]:
    try:
        raw = get_leagues() or []
    except Exception as exc:  # pragma: no cover
        print(f"[UI] get_leagues exception: {exc}")
        return []

    leagues: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        league = item.get("league") or {}
        country = item.get("country") or {}
        seasons = item.get("seasons") or []

        league_id = league.get("id")
        name = league.get("name")
        if not league_id or not name:
            continue

        competition_type = (league.get("type") or "").title() or "Indefini"
        categories = _detect_categories(name)

        years: Set[int] = set()
        current_year: Optional[int] = None
        for season in seasons:
            if not isinstance(season, dict):
                continue
            year = season.get("year")
            if year is None:
                continue
            try:
                year_int = int(year)
            except (TypeError, ValueError):
                continue
            years.add(year_int)
            if season.get("current"):
                current_year = year_int

        raw_country = (country.get("name") or "").strip()
        display_country = _translate_country(raw_country)

        label_parts = [name]
        if display_country:
            label_parts.append(f"({display_country})")

        leagues.append(
            {
                "id": int(league_id),
                "name": name,
                "country": display_country,
                "country_raw": raw_country,
                "label": " ".join(label_parts).strip(),
                "type": competition_type,
                "categories": tuple(sorted(categories)),
                "seasons": sorted(years, reverse=True),
                "current_season": current_year,
            }
        )

    leagues.sort(key=lambda entry: (entry["country"], entry["name"]))
    return leagues


def _filter_leagues(
    leagues: Iterable[Dict[str, Any]],
    *,
    country: Optional[str],
    query: str,
    comp_type: Optional[str],
    categories: Iterable[str],
) -> List[Dict[str, Any]]:
    query_lower = query.lower()
    category_set = {cat for cat in categories if cat}

    filtered: List[Dict[str, Any]] = []
    for item in leagues:
        if country and country != "Tous" and item.get("country") != country:
            continue
        if comp_type and comp_type != "Toutes" and item.get("type") != comp_type:
            continue
        if query_lower and query_lower not in item.get("label", "").lower() and query_lower not in item.get("name", "").lower():
            continue
        if category_set and not category_set.issubset(set(item.get("categories", ()))):
            continue
        filtered.append(item)
    return filtered


def _default_league_index(leagues: List[Dict[str, Any]], default_id: Optional[int]) -> int:
    if default_id is None:
        return 0
    for idx, item in enumerate(leagues):
        if item.get("id") == default_id:
            return idx
    return 0


def _format_league_label(item: Any) -> str:
    if isinstance(item, dict):
        label = item.get("label")
        if label:
            return label
        name = item.get("name")
        if name:
            return name
        identifier = item.get("id")
        if identifier is not None:
            return f"Ligue {identifier}"
    return str(item)


def select_league_and_season(
    *,
    league_label: str = "Championnat",
    season_label: str = "Saison",
    default_league_id: Optional[int] = None,
    default_season: Optional[int] = None,
    enable_favorites: bool = True,
    favorites: Optional[List[Dict[str, Any]]] = None,
    key_prefix: str = "",
    respect_user_defaults: bool = True,
) -> Tuple[int, int, str]:
    leagues = load_leagues()
    if not leagues:
        st.error("Impossible de charger la liste des ligues (cle API ou reseau).")
        st.stop()

    favorites = favorites if favorites is not None else (
        get_favorite_competitions() if enable_favorites else []
    )
    selected_favorite: Optional[Dict[str, Any]] = None
    pref_league_id = default_league_id
    pref_season = default_season
    pref_country: Optional[str] = None
    pref_type: Optional[str] = None
    pref_categories: List[str] = []
    pref_query = ""

    if respect_user_defaults:
        ui_defaults = get_ui_defaults()
        user_league = ui_defaults.get("league_id")
        if user_league is not None:
            pref_league_id = user_league
        user_season = ui_defaults.get("season")
        if user_season is not None:
            pref_season = user_season
    if favorites:
        favorite_labels = ["Aucun favori"] + [
            fav.get("label", f"Ligue {fav.get('league_id')}") for fav in favorites
        ]
        default_fav_index = 0
        for idx, fav in enumerate(favorites, start=1):
            fav_league = fav.get("league_id")
            fav_season = fav.get("season")
            if fav_league == default_league_id and (fav_season in {None, default_season}):
                default_fav_index = idx
                break
        selected_label = st.selectbox(
            "Favoris",
            favorite_labels,
            index=min(default_fav_index, len(favorite_labels) - 1),
            key=f"{key_prefix}favorite_select",
        )
        if selected_label != "Aucun favori":
            idx = favorite_labels.index(selected_label) - 1
            selected_favorite = favorites[idx]
            pref_league_id = selected_favorite.get("league_id")
            pref_season = selected_favorite.get("season", pref_season)
            pref_country = selected_favorite.get("country")
            pref_type = selected_favorite.get("type")
            pref_categories = [str(cat) for cat in selected_favorite.get("categories", []) if cat]
            pref_query = selected_favorite.get("query", "")

    countries = sorted({entry.get("country") for entry in leagues if entry.get("country")})
    country_options = ["Tous"] + countries
    if pref_country and pref_country in country_options:
        country_index = country_options.index(pref_country)
    else:
        country_index = 0
    country = st.selectbox("Pays", country_options, index=country_index, key=f"{key_prefix}country")

    types = sorted({entry.get("type") for entry in leagues if entry.get("type")})
    type_options = ["Toutes"] + types
    if pref_type and pref_type in type_options:
        type_index = type_options.index(pref_type)
    else:
        type_index = 0
    comp_type = st.selectbox("Type de competition", type_options, index=type_index, key=f"{key_prefix}type")

    all_categories = sorted({cat for entry in leagues for cat in entry.get("categories", ())})
    default_categories = [cat for cat in pref_categories if cat in all_categories] if pref_categories else []
    selected_categories = st.multiselect(
        "Categories",
        options=all_categories,
        default=default_categories,
        key=f"{key_prefix}categories",
    )

    query_default = pref_query if pref_query else ""
    query = st.text_input("Recherche ligue", query_default, key=f"{key_prefix}query").strip()

    filtered = _filter_leagues(
        leagues,
        country=country,
        query=query,
        comp_type=comp_type,
        categories=selected_categories,
    )
    if not filtered:
        st.warning("Aucune ligue ne correspond aux filtres. Affichage complet.")
        filtered = leagues

    index = _default_league_index(filtered, pref_league_id)
    league_key = f"{key_prefix}league_select" if key_prefix else "league_select"
    selected_league = st.selectbox(
        league_label,
        options=filtered,
        index=min(index, len(filtered) - 1),
        key=league_key,
        format_func=_format_league_label,
    )

    if not isinstance(selected_league, dict):
        fallback = None
        if isinstance(selected_league, str):
            fallback = next(
                (
                    item
                    for item in filtered
                    if item.get("label") == selected_league or item.get("name") == selected_league
                ),
                None,
            )
        if fallback is None and filtered:
            fallback = filtered[0]
        selected_league = fallback or {}
        if not selected_league:
            st.error("Impossible d'initialiser la ligue selectionnee.")
            st.stop()

    season_options = selected_league.get("seasons") or []
    if not season_options and selected_league.get("current_season"):
        season_options = [selected_league["current_season"]]
    if not season_options:
        season_options = [pref_season or 2025]

    default_year = pref_season or selected_league.get("current_season")
    if default_year in season_options:
        season_index = season_options.index(default_year)
    else:
        season_index = 0

    season_value = st.selectbox(season_label, season_options, index=season_index, key=f"{key_prefix}season")
    return selected_league["id"], int(season_value), selected_league["label"]


@st.cache_data(show_spinner=False, ttl=300)
def load_teams(league_id: int, season: int) -> List[Dict[str, Any]]:
    teams = get_teams(league_id, season) or []
    normalized = normalize_team_list(teams if isinstance(teams, list) else [])
    result: List[Dict[str, Any]] = []
    for team in normalized:
        result.append(
            {
                "id": team.id,
                "name": team.name,
                "country": team.country,
                "logo": team.logo,
                "venue": team.venue_name,
                "model": team,
            }
        )
    return result


def select_team(
    league_id: int,
    season: int,
    *,
    default_team_id: Optional[int] = None,
    placeholder: str = "Toutes les equipes",
    key: Optional[str] = None,
) -> Optional[int]:
    teams = load_teams(league_id, season)
    options: List[Dict[str, Any]] = [{"id": None, "name": placeholder}] + teams

    index = 0
    if default_team_id is not None:
        for idx, option in enumerate(options):
            if option.get("id") == default_team_id:
                index = idx
                break

    selection = st.selectbox(
        "Equipe",
        options=options,
        index=min(index, len(options) - 1),
        key=key,
        format_func=lambda item: item.get("name", "?"),
    )
    return selection.get("id")




