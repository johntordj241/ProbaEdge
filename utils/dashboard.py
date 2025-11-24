from __future__ import annotations



from datetime import datetime

from typing import Any, Dict, List, Optional, Tuple

from zoneinfo import ZoneInfo



import pandas as pd

import streamlit as st





from .api_calls import (
    get_fixtures,
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

from .widgets import render_widget



LOCAL_TZ = ZoneInfo("Europe/Paris")







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



    leagues = load_leagues()

    if not leagues:

        st.error("Impossible de charger les competitions (cle API / reseau ?)")

        return



    league_labels = [item["label"] for item in leagues]

    default_idx = 0

    if default_league_id:

        for idx, item in enumerate(leagues):

            if item["id"] == default_league_id:

                default_idx = idx

                break



    col_season, col_league = st.columns([1, 2])

    with col_league:

        league_label = st.selectbox("Championnat", league_labels, index=min(default_idx, len(league_labels) - 1))

    selected_league = next(item for item in leagues if item["label"] == league_label)



    seasons = selected_league.get("seasons") or [default_season or 2025]

    seasons = sorted(seasons, reverse=True)

    default_season_value = default_season or selected_league.get("current_season") or seasons[0]

    with col_season:

        season = st.selectbox("Saison", seasons, index=seasons.index(default_season_value) if default_season_value in seasons else 0)



    league_id = selected_league["id"]



    team_id = select_team(

        league_id,

        season,

        default_team_id=default_team_id,

        placeholder="Toutes les equipes",

        key=f"dashboard_team_{league_id}_{season}",

    )



    with st.spinner("Chargement des donnees live..."):

        live_fixtures = get_fixtures(league_id, season, team_id=team_id, live="all") or []

        upcoming_fixtures = get_fixtures(league_id, season, team_id=team_id, next_n=6) or []

        standings_raw = get_standings(league_id, season) or []

        standings = []

        if isinstance(standings_raw, list) and standings_raw:

            standings = standings_raw[0].get("league", {}).get("standings", [[]])[0]



    highlight = _highlight_fixture(live_fixtures + upcoming_fixtures)



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

        if fixture_id:
            st.markdown("---")
            st.subheader("Widget officiel - Match")
            render_widget("game", height=620, game_id=fixture_id, config={"refresh": 60})
    else:

        st.info("Selectionnez un championnat comportant des matchs pour la periode choisie.")



    if league_id and season:
        st.markdown("---")
        st.subheader("Widget officiel - Classement complet")
        render_widget("standings", height=720, league=league_id, season=season)






