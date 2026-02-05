from __future__ import annotations



from datetime import date, datetime

from typing import Any, Dict, List, Optional, Tuple

from zoneinfo import ZoneInfo
from textwrap import dedent



import pandas as pd

import streamlit as st





from .api_calls import (
    get_fixtures,
    get_fixtures_by_date,
    get_fixture_statistics,
    get_injuries,
    get_odds,
    get_odds_by_fixture,
    get_players_for_team,
    get_standings,
    get_statistics,
    get_topscorers,
)

from .prediction_model import (

    aggregate_poisson_markets,

    apply_context_adjustments,

    editorial_summary,

    expected_goals_from_standings,

    poisson_matrix,

    probable_goalscorers,

    top_scorelines,

)

from .ui_helpers import load_leagues, select_team
from .profile import list_saved_scenes

from .widgets import render_widget
from .form_utils import form_badges_html, FORM_STYLE
from .events import load_fixture_events, format_event_line



LOCAL_TZ = ZoneInfo("Europe/Paris")

TEAM_FORM_STYLE = dedent(
    """\
    <style>
    .team-form {
        margin-top: 8px;
    }
    .team-form small {
        display: block;
        color: rgba(255,255,255,0.7);
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
    </style>
    """
)

LIVE_EVENT_STATUS = {"LIVE", "1H", "2H", "ET", "P", "BT", "HT", "INT", "INP", "FT", "AET", "PEN", "CANC", "ABD", "AWD"}


def _format_local_time(raw_iso: Any) -> str:
    if not raw_iso:
        return "-"
    try:
        dt_obj = datetime.fromisoformat(str(raw_iso).replace("Z", "+00:00"))
        return dt_obj.astimezone(LOCAL_TZ).strftime("%H:%M")
    except Exception:
        return "-"


def _format_local_datetime(raw_iso: Any) -> str:
    if not raw_iso:
        return "-"
    try:
        dt_obj = datetime.fromisoformat(str(raw_iso).replace("Z", "+00:00"))
        return dt_obj.astimezone(LOCAL_TZ).strftime("%d/%m %H:%M")
    except Exception:
        return "-"


def _worldwide_rows(fixtures: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for entry in fixtures or []:
        teams_block = entry.get("teams") or {}
        fixture_block = entry.get("fixture") or {}
        league_block = entry.get("league") or {}
        rows.append(
            {
                "Date": _format_local_datetime(fixture_block.get("date")),
                "Match": f"{teams_block.get('home', {}).get('name', 'Equipe A')} vs "
                f"{teams_block.get('away', {}).get('name', 'Equipe B')}",
                "Competition": league_block.get("name", ""),
                "Pays": league_block.get("country", ""),
            }
        )
    return rows


def _matches_of_the_day_rows(fixtures: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for entry in fixtures or []:
        teams_block = entry.get("teams") or {}
        home_team = teams_block.get("home") or {}
        away_team = teams_block.get("away") or {}
        fixture_block = entry.get("fixture") or {}
        status_block = fixture_block.get("status") or {}
        league_block = entry.get("league") or {}
        rows.append(
            {
                "Heure": _format_local_time(fixture_block.get("date")),
                "Match": f"{home_team.get('name', 'Equipe A')} vs {away_team.get('name', 'Equipe B')}",
                "Competition": league_block.get("name", ""),
                "Statut": status_block.get("long") or status_block.get("short") or "Programme",
            }
        )
    return rows


def _upcoming_rows(fixtures: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for entry in fixtures or []:
        teams_block = entry.get("teams") or {}
        fixture_block = entry.get("fixture") or {}
        league_block = entry.get("league") or {}
        rows.append(
            {
                "Date": _format_local_datetime(fixture_block.get("date")),
                "Match": f"{teams_block.get('home', {}).get('name', 'Equipe A')} vs "
                f"{teams_block.get('away', {}).get('name', 'Equipe B')}",
                "Competition": league_block.get("name", ""),
            }
        )
    return rows


def _normalize_stat_label(raw: Any) -> str:
    import unicodedata

    text = unicodedata.normalize("NFKD", str(raw or "").strip())
    ascii_text = "".join(ch for ch in text if ord(ch) < 128)
    return "".join(ch for ch in ascii_text.lower() if ch.isalnum())


STAT_LABEL_ALIASES: Dict[str, set[str]] = {
    "shotsongoal": {"shotsongoal", "shotsontarget", "tirscadres", "tirscadre", "shotsatgoal"},
    "totalshots": {"totalshots", "tirstotaux", "shotstotal"},
    "ballpossession": {"ballpossession", "possession", "possessiondeballe"},
    "expectedgoals": {"expectedgoals", "xg", "butsattendus"},
    "cornerkicks": {"cornerkicks", "corners"},
}


def _stat_label_variants(label: str) -> set[str]:
    normalized = _normalize_stat_label(label)
    variants = {normalized}
    for key, entries in STAT_LABEL_ALIASES.items():
        if normalized == key or normalized in entries:
            variants.update({key, *entries})
            break
    return variants


def _stat_value(statistics: List[Dict[str, Any]], team_id: Optional[int], label: str) -> Optional[float]:
    if team_id is None:
        return None
    targets = _stat_label_variants(label)
    for block in statistics or []:
        team_block = block.get("team") or {}
        if team_block.get("id") != team_id:
            continue
        for entry in block.get("statistics") or []:
            stat_label = _normalize_stat_label(entry.get("type"))
            if stat_label not in targets:
                continue
            value = entry.get("value")
            if value in {None, "", "-"}:
                return None
            try:
                raw = str(value).strip().replace(",", ".")
                if raw.endswith("%"):
                    return float(raw[:-1]) / 100.0
                return float(raw)
            except (TypeError, ValueError):
                return None
    return None


def _highlight_stat_lines(
    statistics: List[Dict[str, Any]],
    home_id: Optional[int],
    away_id: Optional[int],
) -> List[Dict[str, Any]]:
    metrics = [
        ("Tirs cadrés", "Shots on Goal"),
        ("Tirs totaux", "Total Shots"),
        ("xG cumulés", "Expected Goals"),
        ("Possession", "Ball Possession"),
        ("Corners", "Corner Kicks"),
    ]
    rows: List[Dict[str, Any]] = []
    for label, key in metrics:
        home_value = _stat_value(statistics, home_id, key)
        away_value = _stat_value(statistics, away_id, key)
        if home_value is None and away_value is None:
            continue
        if label == "Possession":
            to_pct = lambda val: f"{val * 100:.0f}%" if val is not None else "-"
            home_display = to_pct(home_value)
            away_display = to_pct(away_value)
        else:
            fmt = lambda val: f"{val:.2f}" if isinstance(val, float) and not val.is_integer() else f"{int(val)}"
            home_display = fmt(home_value) if home_value is not None else "-"
            away_display = fmt(away_value) if away_value is not None else "-"
        rows.append({"Stat": label, "Domicile": home_display, "Extérieur": away_display})
    return rows


def _injured_name_set(payload: Optional[List[Dict[str, Any]]]) -> set[str]:
    names: set[str] = set()
    for item in payload or []:
        player = (item.get("player") or {}).get("name")
        if player:
            names.add(player)
    return names







def _to_local(date_value: Optional[str], tz_hint: Optional[str]) -> Optional[datetime]:

    if not date_value:

        return None

    try:

        dt = datetime.fromisoformat(date_value.replace("Z", "+00:00"))

        if dt.tzinfo is None:

            dt = dt.replace(tzinfo=ZoneInfo(tz_hint or "UTC"))

        return dt.astimezone(LOCAL_TZ)

    except Exception:

        return None





def _highlight_fixture(fixtures: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:

    if not fixtures:

        return None

    live = [fx for fx in fixtures if fx.get("fixture", {}).get("status", {}).get("short") in {"LIVE", "1H", "2H", "ET"}]

    if live:

        return live[0]

    upcoming = [fx for fx in fixtures if fx.get("fixture", {}).get("status", {}).get("short") not in {"FT", "AET", "PEN"}]

    return upcoming[0] if upcoming else fixtures[0]


def _form_rows_for_teams(
    standings: List[Dict[str, Any]],
    teams: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    if not standings or not teams:
        return rows
    for team in teams:
        if not team:
            continue
        team_id = team.get("id")
        name = team.get("name") or f"Equipe {team_id or '?'}"
        entry = None
        if team_id is not None:
            entry = next(
                (row for row in standings if row.get("team", {}).get("id") == team_id),
                None,
            )
        if not entry and name:
            entry = next(
                (
                    row
                    for row in standings
                    if row.get("team", {}).get("name") == name
                ),
                None,
            )
        form_value = (entry.get("form") if entry else "") or ""
        rows.append({"team": name, "form": form_value})
    return rows





def _standings_table(standings: List[Dict[str, Any]], scope: str = "all") -> pd.DataFrame:

    """
    Build a top-10 standings table for the requested scope ("all", "home", "away").
    """

    rows: List[Dict[str, Any]] = []

    for row in standings[:10]:

        team = row.get("team", {})

        stats = row.get(scope, {}) if scope != "all" else row.get("all", {})

        if not stats:

            stats = row.get("all", {})

        goals = stats.get("goals") or {}

        goals_for = goals.get("for", 0) or 0

        goals_against = goals.get("against", 0) or 0

        goal_diff = goals_for - goals_against

        if scope == "all":

            points = row.get("points")

        else:

            wins = stats.get("win") or 0

            draws = stats.get("draw") or 0

            points = wins * 3 + draws

        rows.append(

            {

                "#": row.get("rank"),

                "Equipe": team.get("name"),

                "Pts": points,

                "J": stats.get("played"),

                "V": stats.get("win"),

                "N": stats.get("draw"),

                "D": stats.get("lose"),

                "B": f"{goals_for}:{goals_against}",

                "+/-": goal_diff,

            }

        )

    return pd.DataFrame(rows)





def _top_stats_from_standings(standings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

    rows = []

    if not standings:

        return rows

    best = standings[:3]

    max_points = max((row.get("points", 0) for row in best), default=1)

    for row in best:

        team = row.get("team", {})

        rows.append(

            {

                "name": team.get("name", "?"),

                "rank": row.get("rank"),

                "points": row.get("points", 0),

                "ratio": row.get("points", 0) / max_points if max_points else 0,

            }

        )

    return rows





def _odds_table(odds_payload: Any) -> Optional[pd.DataFrame]:
    if not isinstance(odds_payload, list) or not odds_payload:
        return None

    bookmakers = odds_payload[0].get("bookmakers") or []
    rows = []
    label_map = {
        "1": "1",
        "home": "1",
        "home team": "1",
        "2": "2",
        "away": "2",
        "away team": "2",
        "x": "N",
        "draw": "N",
    }

    for bookmaker in bookmakers[:4]:
        name = bookmaker.get("name")
        bets = bookmaker.get("bets") or []
        values = bets[0].get("values") if bets else []
        row = {"Book": name, "1": None, "N": None, "2": None}
        for value in values:
            raw_label = str(value.get("value", "")).strip().lower()
            key = label_map.get(raw_label)
            if key:
                row[key] = value.get("odd")
        if any(row[col] not in {None, "", "-"} for col in ("1", "N", "2")):
            rows.append(row)

    if not rows:
        return None

    return pd.DataFrame(rows)


def _has_usable_odds(payload: Any) -> bool:
    for entry in payload or []:
        for bookmaker in entry.get("bookmakers") or []:
            for bet in bookmaker.get("bets") or []:
                for value in bet.get("values") or []:
                    odd = value.get("odd")
                    if odd not in {None, "", "-"}:
                        return True
    return False


def _fixture_odds_best_effort(
    league_id: int,
    season: int,
    fixture_id: Optional[int],
    fixture_date: Optional[str],
) -> Tuple[Any, bool]:
    if not fixture_id:
        return [], False
    payload = get_odds_by_fixture(fixture_id) or []
    if _has_usable_odds(payload):
        return payload, False
    if not fixture_date:
        return payload, False
    date_key = str(fixture_date)[:10]
    if not date_key:
        return payload, False
    fallback = get_odds(league_id, season, date_key) or []
    for item in fallback:
        fixture_block = item.get("fixture") or {}
        if fixture_block.get("id") == fixture_id:
            return [item], True
    return payload, False


def _topscorers_best_effort(league_id: int, season: int) -> Tuple[List[Dict[str, Any]], Optional[int]]:
    current = get_topscorers(league_id, season) or []
    if current:
        return current, None
    previous_season = season - 1 if season and season > 2000 else None
    if previous_season is None:
        return [], None
    fallback = get_topscorers(league_id, previous_season) or []
    if fallback:
        return fallback, previous_season
    return [], None






def _injury_lines(injuries: Any, limit: int = 6) -> List[str]:

    lines: List[str] = []

    if not isinstance(injuries, list):

        return lines

    for item in injuries[:limit]:

        player = item.get("player", {})

        team = item.get("team", {})

        reason = player.get("type") or player.get("reason") or "Indisponible"

        lines.append(f"{player.get('name', 'Joueur')} - {team.get('name', '?')} ({reason})")

    return lines













def show_dashboard(

    default_league_id: Optional[int] = None,

    default_season: Optional[int] = None,

    default_team_id: Optional[int] = None,

) -> None:

    st.title("Dashboard Paris Sportifs")

    saved_scenes = list_saved_scenes()
    scene_defaults_config = st.session_state.pop("_dashboard_scene_to_apply", None)
    sidebar_scene_options = [{"id": "", "name": "Aucune scène", "config": {}}] + saved_scenes
    sidebar_scene_labels = [entry["name"] or "Scène" for entry in sidebar_scene_options]
    current_sidebar_scene_id = st.session_state.get("_dashboard_scene_current", "")
    try:
        sidebar_default_index = next(
            idx for idx, entry in enumerate(sidebar_scene_options) if entry["id"] == current_sidebar_scene_id
        )
    except StopIteration:
        sidebar_default_index = 0
    sidebar_choice = st.sidebar.selectbox(
        "Scène rapide (dashboard)",
        options=list(range(len(sidebar_scene_options))),
        index=sidebar_default_index,
        format_func=lambda idx: sidebar_scene_labels[idx],
        key="dashboard_scene_select",
    )
    selected_sidebar_scene = sidebar_scene_options[sidebar_choice]
    if selected_sidebar_scene.get("id"):
        if selected_sidebar_scene["id"] != current_sidebar_scene_id:
            st.session_state["_dashboard_scene_to_apply"] = selected_sidebar_scene.get("config", {})
            st.session_state["_dashboard_scene_current"] = selected_sidebar_scene["id"]
            st.experimental_rerun()
    else:
        if current_sidebar_scene_id:
            st.session_state["_dashboard_scene_current"] = ""



    leagues = load_leagues()

    if not leagues:

        st.error("Impossible de charger les competitions (cle API / reseau ?)")

        if st.button("Reessayer la recuperation", key="dashboard_retry_leagues"):

            try:

                load_leagues.clear()  # type: ignore[attr-defined]

            except Exception:

                pass

            st.experimental_rerun()

        st.caption(

            "Verifie API_FOOTBALL_KEY, la connectivite et purge le cache si besoin (bouton dans le panneau lateral)."

        )

        return



    league_labels = [item["label"] for item in leagues]
    pref_league_id = scene_defaults_config.get("league_id") if scene_defaults_config else default_league_id
    default_idx = 0
    if pref_league_id:
        for idx, item in enumerate(leagues):
            if item["id"] == pref_league_id:
                default_idx = idx
                break



    col_season, col_league = st.columns([1, 2])

    with col_league:

        league_label = st.selectbox("Championnat", league_labels, index=min(default_idx, len(league_labels) - 1))

    selected_league = next(item for item in leagues if item["label"] == league_label)



    seasons = selected_league.get("seasons") or [default_season or 2025]
    seasons = sorted(seasons, reverse=True)
    preferred_season = scene_defaults_config.get("season") if scene_defaults_config else default_season
    default_season_value = preferred_season or selected_league.get("current_season") or seasons[0]

    with col_season:

        season = st.selectbox("Saison", seasons, index=seasons.index(default_season_value) if default_season_value in seasons else 0)



    league_id = selected_league["id"]



    preferred_team = scene_defaults_config.get("team_id") if scene_defaults_config else default_team_id
    team_id = select_team(
        league_id,
        season,
        default_team_id=preferred_team,
        placeholder="Toutes les equipes",
        key=f"dashboard_team_{league_id}_{season}",
    )



    today_rows: List[Dict[str, str]] = []
    world_rows: List[Dict[str, str]] = []

    with st.spinner("Chargement des donnees live..."):

        live_fixtures = get_fixtures(league_id, season, team_id=team_id, live="all") or []

        upcoming_fixtures = get_fixtures(league_id, season, team_id=team_id, next_n=6) or []

        league_upcoming = get_fixtures(league_id, season, next_n=6) or []

        standings_raw = get_standings(league_id, season) or []

        standings = []

        if isinstance(standings_raw, list) and standings_raw:

            standings = standings_raw[0].get("league", {}).get("standings", [[]])[0]

        today_payload = get_fixtures_by_date(
            date.today().isoformat(),
            timezone="Europe/Paris",
            league_id=league_id,
        ) or []
        today_rows = _matches_of_the_day_rows(today_payload)
        world_payload = get_fixtures_by_date(
            date.today().isoformat(),
            timezone="Europe/Paris",
        ) or []
        world_rows = _worldwide_rows(world_payload)



    candidate_fixtures = live_fixtures + upcoming_fixtures
    highlight = _highlight_fixture(candidate_fixtures)

    st.markdown("### Matches du monde (toutes competitions)")
    world_filter = st.text_input("Filtrer (club, competition, pays)", key="dashboard_world_filter")
    filtered_world = world_rows
    if world_filter:
        needle = world_filter.lower()
        filtered_world = [
            row
            for row in world_rows
            if needle in (row.get("Match", "").lower())
            or needle in (row.get("Competition", "").lower())
            or needle in (row.get("Pays", "").lower())
        ]
    if filtered_world:
        st.dataframe(pd.DataFrame(filtered_world), hide_index=True, use_container_width=True)
    else:
        st.info("Aucun match ne correspond au filtre ou la date ne comporte pas de rencontre connue.")

    st.markdown("### Matchs du jour")
    if today_rows:
        st.dataframe(pd.DataFrame(today_rows), hide_index=True, use_container_width=True)
    else:
        fallback_source = upcoming_fixtures or league_upcoming or []
        fallback_rows = _upcoming_rows(fallback_source[:5])
        if fallback_rows:
            st.warning("Aucun match programme aujourd'hui. Voici les prochaines rencontres a surveiller.")
            st.dataframe(pd.DataFrame(fallback_rows), hide_index=True, use_container_width=True)
        else:
            st.info(
                "Pas de calendrier disponible pour cette combinaison. Consulte l'agenda ou change de championnat."
            )

    widget_source = league_upcoming or candidate_fixtures
    widget_fixture_ids: list[int] = []
    for fx in widget_source:
        fid = fx.get("fixture", {}).get("id")
        if fid and fid not in widget_fixture_ids:
            widget_fixture_ids.append(fid)
        if len(widget_fixture_ids) == 3:
            break



    top_stats = _top_stats_from_standings(standings)

    standings_df = _standings_table(standings)



    st.markdown("---")

    col_match, col_stats = st.columns([1.4, 1])

    with col_match:

        st.subheader("Match mis en avant")

        if highlight:

            fixture = highlight.get("fixture", {})

            teams = highlight.get("teams", {})

            goals = highlight.get("goals", {})

            status = fixture.get("status", {})

            home = teams.get("home", {})

            away = teams.get("away", {})



            left, center, right = st.columns([3, 1.5, 3])

            with left:

                if home.get("logo"):

                    st.image(home["logo"], width=72)

                st.markdown(f"**{home.get('name', 'Equipe A')}**")

            with center:

                score = "-"

                if goals.get("home") is not None and goals.get("away") is not None:

                    score = f"{goals['home']} - {goals['away']}"

                st.markdown(f"<h2 style='text-align:center;'>{score}</h2>", unsafe_allow_html=True)

                if status.get("elapsed"):

                    st.caption(f"{status['elapsed']}'")

            with right:

                if away.get("logo"):

                    st.image(away["logo"], width=72)

                st.markdown(f"**{away.get('name', 'Equipe B')}**")



            local_time = _to_local(fixture.get("date"), fixture.get("timezone"))

            venue = fixture.get("venue", {}).get("name")

            info_parts = [status.get("long") or status.get("short") or "Statut inconnu"]

            if local_time:

                info_parts.append(local_time.strftime("%d/%m/%Y %H:%M"))

            if venue:

                info_parts.append(venue)

            st.caption(" - ".join(info_parts))

            form_rows = _form_rows_for_teams(standings, [home, away])
            if form_rows:
                st.markdown(FORM_STYLE + TEAM_FORM_STYLE, unsafe_allow_html=True)
                form_lookup = {row["team"]: row["form"] for row in form_rows}
                home_form = form_lookup.get(home.get("name"))
                away_form = form_lookup.get(away.get("name"))
            if home_form:
                badges = form_badges_html(home_form)
                left.markdown(
                    f"<div class='team-form'><small>Forme (5 derniers)</small>{badges}</div>",
                    unsafe_allow_html=True,
                )
            if away_form:
                badges = form_badges_html(away_form)
                right.markdown(
                    f"<div class='team-form'><small>Forme (5 derniers)</small>{badges}</div>",
                    unsafe_allow_html=True,
                )

            fixture_id = fixture.get("id")
            status_code = (status.get("short") or "").upper()
            if fixture_id and status_code in LIVE_EVENT_STATUS:
                events = load_fixture_events(int(fixture_id))
                if events:
                    st.markdown("**Buteurs & cartons**")
                    for ev in events:
                        st.markdown(format_event_line(ev), unsafe_allow_html=True)
                try:
                    statistics_payload = get_fixture_statistics(int(fixture_id)) or []
                except Exception:
                    statistics_payload = []
                stat_rows = _highlight_stat_lines(
                    statistics_payload,
                    teams.get("home", {}).get("id"),
                    teams.get("away", {}).get("id"),
                )
                if stat_rows:
                    st.subheader("Statistiques live clés")
                    st.table(pd.DataFrame(stat_rows), use_container_width=True)
                else:
                    st.caption("Statistiques live indisponibles pour ce match.")

        else:

            st.info("Aucun match a mettre en avant.")



    with col_stats:

        st.subheader("Statistiques (Top 3)")

        if top_stats:

            for entry in top_stats:

                st.progress(entry["ratio"], text=f"#{entry['rank']} {entry['name']} - {entry['points']} pts")

        else:

            st.info("Statistiques indisponibles.")



    col_table, col_pred = st.columns([1.2, 1])

    with col_table:

        st.subheader("Classement Top 10")

        if standings_df.empty:

            st.info("Classement indisponible.")

        else:

            st.dataframe(standings_df, hide_index=True, use_container_width=True)



    if highlight:

        fixture_id = highlight.get("fixture", {}).get("id")

        teams = highlight.get("teams", {})

        strength_home, strength_away, baseline = expected_goals_from_standings(

            standings,

            teams.get("home", {}).get("id"),

            teams.get("away", {}).get("id"),

            teams.get("home", {}).get("name", "Equipe A"),

            teams.get("away", {}).get("name", "Equipe B"),

        )

        context = apply_context_adjustments(strength_home, strength_away, highlight)

        matrix = poisson_matrix(strength_home.lambda_value, strength_away.lambda_value)

        probs = aggregate_poisson_markets(matrix)

        top_scores = top_scorelines(matrix, strength_home.name, strength_away.name)



        with col_pred:

            st.subheader("Predictions & Paris")

            st.metric(strength_home.name, f"{probs['home']*100:.1f}%", help="Proba victoire domicile")

            st.metric("Nul", f"{probs['draw']*100:.1f}%")

            st.metric(strength_away.name, f"{probs['away']*100:.1f}%")

            st.markdown("**Scorelines favoris**")

            for item in top_scores[:4]:

                st.write(f"{item['label']} - {item['prob']*100:.1f}%")

            st.caption(editorial_summary(strength_home, strength_away, probs, context, baseline))

        with st.spinner("Cotes & blessures"):
            fixture_block = highlight.get("fixture", {}) if highlight else {}
            odds_payload, used_fallback_odds = _fixture_odds_best_effort(
                league_id,
                season,
                fixture_id,
                fixture_block.get("date"),
            )
            injuries_home = get_injuries(league_id, season, teams.get("home", {}).get("id")) or []
            injuries_away = get_injuries(league_id, season, teams.get("away", {}).get("id")) or []
            injured_home_names = _injured_name_set(injuries_home)
            injured_away_names = _injured_name_set(injuries_away)

        col_odds, col_inj = st.columns([1, 1])
        with col_odds:
            st.subheader("Cotes 1X2")
            odds_df = _odds_table(odds_payload)
            if odds_df is not None:
                st.table(odds_df)
                if used_fallback_odds:
                    st.caption("Cotes cherchées via la date faute de données live pour ce match.")
            else:
                st.info("Cotes indisponibles pour ce match.")
        with col_inj:
            st.subheader("Blessés / Absents")
            lines = _injury_lines(injuries_home + injuries_away)
            if lines:
                for line in lines:
                    st.write(f"- {line}")
            else:
                st.info("Aucun joueur signalé absent.")

        with st.spinner("Buteurs probables"):
            top_scorers, topscorers_fallback_season = _topscorers_best_effort(league_id, season)
            players_home = get_players_for_team(
                league_id,
                season,
                teams.get("home", {}).get("id"),
            )
            players_away = get_players_for_team(
                league_id,
                season,
                teams.get("away", {}).get("id"),
            )

        scorers = probable_goalscorers(
            league_id,
            season,
            teams.get("home", {}).get("id"),
            teams.get("away", {}).get("id"),
            strength_home.lambda_value,
            strength_away.lambda_value,
            top_scorers,
            players_home,
            players_away,
            injured_home=injured_home_names,
            injured_away=injured_away_names,
        )

        st.subheader("Buteurs probables")
        if scorers:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Joueur": s["name"],
                            "Probabilite %": round(s["prob"] * 100, 1),
                            "Source": "Topscorers" if s.get("source") == "topscorers" else "Effectif",
                        }
                        for s in scorers
                    ]
                ),
                hide_index=True,
                use_container_width=True,
            )
            if topscorers_fallback_season and topscorers_fallback_season != season:
                st.caption(
                    f"Données buteurs basées sur la saison {topscorers_fallback_season}."
                )
        else:
            if topscorers_fallback_season and topscorers_fallback_season != season:
                st.info(
                    f"Pas de buteurs publiés pour {season} ; aucune donnée exploitable en {topscorers_fallback_season}."
                )
            else:
                st.info("Pas assez de donnees pour les buteurs probables.")

    else:

        st.info("Selectionnez un championnat comportant des matchs pour la periode choisie.")

    if widget_fixture_ids:
        st.markdown("---")
        title = "Widget officiel - Matchs" if len(widget_fixture_ids) > 1 else "Widget officiel - Match"
        st.subheader(title)
        columns = st.columns(len(widget_fixture_ids))
        widget_height = 240
        for col, fixture_id in zip(columns, widget_fixture_ids):
            with col:
                render_widget(
                    "game",
                    height=widget_height,
                    game_id=fixture_id,
                    config={"refresh": 60, "height": widget_height},
                )

    if league_id and season:
        st.markdown("---")
        st.subheader("Widget officiel - Classement complet")
        render_widget("standings", height=720, league=league_id, season=season)
