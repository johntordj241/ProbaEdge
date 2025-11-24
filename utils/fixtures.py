from __future__ import annotations



from datetime import datetime

from typing import Any, Dict, List, Optional

from zoneinfo import ZoneInfo



import streamlit as st



from .api_calls import get_fixtures

from .ui_helpers import select_league_and_season, select_team

from .widgets import render_widget



Fixture = Dict[str, Any]

LIVE_STATUS = {"LIVE", "1H", "2H", "ET", "P", "BT", "HT", "INT", "INP"}

UPCOMING_STATUS = {"NS", "TBD", "PST"}

FINISHED_STATUS = {"FT", "AET", "PEN", "CANC", "ABD", "AWD"}

LOCAL_TZ = ZoneInfo("Europe/Paris")

FORM_LABELS = {"W": "V", "V": "V", "L": "D", "D": "N", "N": "N"}
FORM_CLASSES = {"W": "win", "V": "win", "L": "loss", "D": "draw", "N": "draw"}


def _form_badges_html(form: Optional[str]) -> str:
    if not form:
        return ""
    badges: List[str] = []
    cleaned = form.replace(" ", "").replace(",", "")
    for char in cleaned.strip():
        label = FORM_LABELS.get(char.upper(), char.upper())
        css_class = FORM_CLASSES.get(char.upper(), "neutral")
        bg = {"win": "#2ecc71", "draw": "#f1c40f", "loss": "#e74c3c", "neutral": "#7f8c8d"}.get(
            css_class, "#7f8c8d"
        )
        fg = "#111" if css_class == "draw" else "#fff"
        badges.append(
            f"<span class='form-badge {css_class}' "
            f"style='display:inline-block;width:22px;height:22px;line-height:22px;"
            f"text-align:center;border-radius:4px;margin-right:4px;font-size:0.8rem;"
            f"background:{bg};color:{fg};'>{label}</span>"
        )
    return "".join(badges)


def _to_local(value: Optional[str], tz_hint: Optional[str]) -> Optional[datetime]:

    if not value:

        return None

    try:

        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))

        if dt.tzinfo is None:

            dt = dt.replace(tzinfo=ZoneInfo(tz_hint or "UTC"))

        return dt.astimezone(LOCAL_TZ)

    except Exception:

        return None





def _status_badge(status: Dict[str, Any]) -> str:

    short = status.get("short", "")

    long = status.get("long", "")

    elapsed = status.get("elapsed")

    if short in LIVE_STATUS:

        minute = f"{elapsed}'" if elapsed is not None else "Live"

        return f"?? {minute} - {long or short}"

    if short in FINISHED_STATUS:

        return f"?? {long or 'Match terminé'}"

    if short in UPCOMING_STATUS:

        return f"?? {long or 'Match à venir'}"

    return long or short or "Statut inconnu"




def _render_fixture(match: Fixture) -> None:

    fixture_info = match.get("fixture", {})

    league_info = match.get("league", {})

    teams_info = match.get("teams", {})

    goals_info = match.get("goals", {})

    score_info = match.get("score", {}) or {}



    home = teams_info.get("home") or {}

    away = teams_info.get("away") or {}



    home_name = home.get("name") or "Équipe A"

    away_name = away.get("name") or "Équipe B"



    st.subheader(f"{home_name} vs {away_name}")

    st.caption(_status_badge(fixture_info.get("status", {})))



    caption_parts: List[str] = []

    league_name = league_info.get("name")

    if league_name:

        caption_parts.append(league_name)

    round_name = league_info.get("round")

    if round_name:

        caption_parts.append(round_name)

    local_time = _to_local(fixture_info.get("date"), fixture_info.get("timezone"))

    if local_time:

        caption_parts.append(local_time.strftime("%d/%m/%Y %H:%M"))

    venue = fixture_info.get("venue", {}).get("name")

    if venue:

        caption_parts.append(venue)

    if caption_parts:

        st.caption(" | ".join(caption_parts))



    is_live = fixture_info.get("status", {}).get("short") in LIVE_STATUS

    is_finished = fixture_info.get("status", {}).get("short") in FINISHED_STATUS



    col_home, col_score, col_away = st.columns([3, 1, 3])

    if home.get("logo"):
        col_home.image(home["logo"], width=72)

    col_home.markdown(f"**{home_name}**")
    col_home.caption("🏠 Domicile")
    home_form_badges = _form_badges_html(home.get("form"))
    if home_form_badges:
        col_home.markdown(home_form_badges, unsafe_allow_html=True)



    if goals_info.get("home") is not None and goals_info.get("away") is not None:

        score_text = f"{goals_info['home']} - {goals_info['away']}"

    else:

        score_text = "-"

    col_score.markdown(f"<h2 style='text-align:center;'>{score_text}</h2>", unsafe_allow_html=True)

    if is_live and fixture_info.get("status", {}).get("elapsed"):

        col_score.caption(f"{fixture_info['status']['elapsed']}'")



    if away.get("logo"):
        col_away.image(away["logo"], width=72)

    col_away.markdown(f"**{away_name}**")
    col_away.caption("✈️ Extérieur")
    away_form_badges = _form_badges_html(away.get("form"))
    if away_form_badges:
        col_away.markdown(away_form_badges, unsafe_allow_html=True)



    if is_finished:

        extra = score_info.get("extratime") or score_info.get("penalty")

        if extra:

            st.caption(

                f"Prolongation / Pénalty : {extra.get('home', '-')}-{extra.get('away', '-')}"

            )





def show_matches(

    default_league_id: Optional[int] = None,

    default_season: Optional[int] = None,

    default_team_id: Optional[int] = None,

) -> None:

    st.header("Matchs")



    league_id, season, league_label = select_league_and_season(

        default_league_id=default_league_id,

        default_season=default_season,

    )

    st.caption(f"Ligue : {league_label} - Saison {season}")



    is_default_context = (

        default_team_id is not None

        and default_league_id is not None

        and default_season is not None

        and league_id == default_league_id

        and season == default_season

    )



    filter_team = st.checkbox(

        "Filtrer par équipe",

        value=is_default_context,

        key=f"fixtures_filter_{league_id}_{season}",

    )



    team_id: Optional[int] = None

    venue_param: Optional[str] = None



    if filter_team:

        team_default = default_team_id if is_default_context else None

        team_id = select_team(

            league_id,

            season,

            default_team_id=team_default,

            placeholder="Toutes les équipes",

            key=f"fixtures_team_{league_id}_{season}",

        )



        if team_id:

            venue_choice = st.radio(

                "Lieu",

                ["Tous", "Domicile", "Extérieur"],

                horizontal=True,

                index=0,

                key=f"fixtures_venue_{league_id}_{season}_{team_id}",

            )

            if venue_choice == "Domicile":

                venue_param = "home"

            elif venue_choice == "Extérieur":

                venue_param = "away"

        else:

            st.caption("Choisissez une équipe pour filtrer par domicile/extérieur.")



    col_scope, col_limit = st.columns([1, 1])

    with col_scope:

        scope = st.selectbox("Sélection", ["À venir", "En cours", "Joués"], index=0)

    with col_limit:

        limit = st.slider("Nombre de matchs", min_value=3, max_value=30, value=10, step=1)



    live_param: Optional[str] = None

    status_filter: Optional[set[str]] = None

    next_n: Optional[int] = None

    last_n: Optional[int] = None



    if scope == "À venir":

        status_filter = UPCOMING_STATUS

        next_n = limit

    elif scope == "Joués":

        status_filter = FINISHED_STATUS

        last_n = limit

    else:

        status_filter = LIVE_STATUS

        live_param = "all"

        st.caption("Actualise la page ou utilise le bouton rafraîchir pour suivre le direct.")



    try:

        with st.spinner("Chargement des matchs..."):

            fixtures = get_fixtures(

                league_id=league_id,

                season=season,

                team_id=team_id,

                venue=venue_param,

                next_n=next_n,

                last_n=last_n,

                live=live_param,

            ) or []

    except Exception as exc:

        st.error(f"Impossible de récupérer les matchs : {exc}")

        return



    if status_filter:

        fixtures = [

            fx

            for fx in fixtures

            if fx.get("fixture", {}).get("status", {}).get("short") in status_filter

        ]



    def _fixture_datetime(item: Dict[str, Any]) -> datetime:

        fixture = item.get("fixture", {})

        dt = _to_local(fixture.get("date"), fixture.get("timezone"))

        return dt or datetime.max



    fixtures.sort(key=_fixture_datetime)

    fixtures = fixtures[:limit]



    if not fixtures:

        st.warning("Pas de données disponibles pour cette sélection.")

        return



    for match in fixtures:

        if not isinstance(match, dict):

            continue

        _render_fixture(match)

        st.divider()




    st.markdown("---")
    st.subheader("Widget officiel - Calendrier")
    widget_tab = "scheduled"
    if scope == "En cours":
        widget_tab = "live"
    elif scope == "Jou�s":
        widget_tab = "finished"
    render_widget("games", height=720, league=league_id, tab=widget_tab)

    if scope == "En cours":

        if st.button("?? Rafraîchir", use_container_width=True):

            st.rerun()

