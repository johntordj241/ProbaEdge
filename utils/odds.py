from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import streamlit as st

from .api_calls import (
    get_odds,
    get_odds_bookmakers,
    get_odds_by_fixture,
)
from .supervision import health_snapshot
from .ui_helpers import select_league_and_season
from .widgets import render_widget


_MATCH_WINNER_KEYS = {"match winner", "1x2", "fulltime result", "match result"}
_HOME_TOKENS = {"home", "1", "1 (home)", "1 (domicile)", "domicile"}
_DRAW_TOKENS = {"draw", "x", "match nul", "nul"}
_AWAY_TOKENS = {"away", "2", "2 (away)", "2 (exterieur)", "exterieur"}


def _parse_datetime(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    token = str(raw).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(token)
    except ValueError:
        return None


def _fixture_options(payload: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    options: List[Dict[str, Any]] = []
    for entry in payload or []:
        if not isinstance(entry, dict):
            continue
        fixture = entry.get("fixture") or {}
        teams = entry.get("teams") or {}
        home = (teams.get("home") or {}).get("name")
        away = (teams.get("away") or {}).get("name")
        fixture_id = fixture.get("id")
        kickoff = _parse_datetime(fixture.get("date"))
        if kickoff:
            ts_label = kickoff.strftime("%d/%m %H:%M")
        else:
            ts_label = "Date inconnue"
        if home and away:
            label = f"{home} vs {away} - {ts_label}"
        else:
            label = f"Match #{fixture_id or '?'} - {ts_label}"
        options.append(
            {
                "label": label,
                "fixture_id": fixture_id,
                "data": entry,
            }
        )
    return options


def _normalize_outcome(value: str) -> Optional[str]:
    token = (value or "").strip().lower()
    if token in _HOME_TOKENS or token.startswith("home"):
        return "1"
    if token in _DRAW_TOKENS or token.startswith("draw") or token.startswith("nul"):
        return "N"
    if token in _AWAY_TOKENS or token.startswith("away"):
        return "2"
    return None


def _match_winner_row(bookmaker: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    name = str(bookmaker.get("name", "")).strip()
    bets = bookmaker.get("bets") or []
    for bet in bets:
        if not isinstance(bet, dict):
            continue
        market = str(bet.get("name", "")).lower()
        if market not in _MATCH_WINNER_KEYS:
            continue
        row = {"Bookmaker": name, "1": None, "N": None, "2": None}
        for entry in bet.get("values") or []:
            outcome = _normalize_outcome(str(entry.get("value", "")))
            if not outcome:
                continue
            try:
                odd = float(entry.get("odd"))
            except (TypeError, ValueError):
                continue
            row[outcome] = odd
        return row
    return None


def _format_1x2_table(bookmakers: Iterable[Dict[str, Any]]) -> Optional[pd.DataFrame]:
    rows: List[Dict[str, Any]] = []
    for bookmaker in bookmakers or []:
        if not isinstance(bookmaker, dict):
            continue
        row = _match_winner_row(bookmaker)
        if row:
            rows.append(row)
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df.sort_values("Bookmaker", inplace=True)
    return df.reset_index(drop=True)


def _best_price(df: pd.DataFrame, column: str) -> Optional[Dict[str, Any]]:
    if column not in df.columns:
        return None
    series = df[column]
    if series.isna().all():
        return None
    idx = series.astype(float).idxmax()
    return {
        "book": df.at[idx, "Bookmaker"],
        "odd": float(series.at[idx]),
    }


def _latest_update(entry: Dict[str, Any]) -> Optional[str]:
    latest: Optional[datetime] = None
    for bookmaker in entry.get("bookmakers") or []:
        for bet in bookmaker.get("bets") or []:
            for value in bet.get("values") or []:
                ts = _parse_datetime(value.get("last_update"))
                if ts and (latest is None or ts > latest):
                    latest = ts
    if latest:
        return latest.strftime("%d/%m/%Y %H:%M")
    return None


def _raw_odds_table(entry: Dict[str, Any]) -> pd.DataFrame:
    rows: List[Tuple[str, str, str, float]] = []
    for bookmaker in entry.get("bookmakers") or []:
        book_name = str(bookmaker.get("name", "")).strip()
        for bet in bookmaker.get("bets") or []:
            market = str(bet.get("name", "")).strip()
            for value in bet.get("values") or []:
                label = str(value.get("value", "")).strip()
                try:
                    odd = float(value.get("odd"))
                except (TypeError, ValueError):
                    continue
                rows.append((book_name, market, label, odd))
    df = pd.DataFrame(rows, columns=["Bookmaker", "Marché", "Sélection", "Cote"])
    if not df.empty:
        df.sort_values(["Bookmaker", "Marché"], inplace=True)
    return df


def _render_bookmaker_list() -> None:
    with st.expander("Liste des bookmakers supportés"):
        refresh = st.button("Actualiser la liste des bookmakers", key="refresh_odds_bookmakers")
        payload = get_odds_bookmakers(force_refresh=refresh) or []
        rows: List[Dict[str, Any]] = []
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            rows.append(
                {
                    "ID": entry.get("id"),
                    "Bookmaker": entry.get("name"),
                    "Pays": entry.get("country"),
                }
            )
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, hide_index=True, use_container_width=True)
        else:
            st.info("Aucun bookmaker renvoyé par l'API pour le moment.")


def _normalize_date_input(raw: str) -> Optional[str]:
    token = raw.strip()
    if not token:
        return None
    try:
        return datetime.strptime(token, "%Y-%m-%d").date().isoformat()
    except ValueError:
        pass
    try:
        return datetime.strptime(token, "%d/%m/%Y").date().isoformat()
    except ValueError:
        pass
    try:
        return datetime.strptime(token, "%d-%m-%Y").date().isoformat()
    except ValueError:
        pass
    return None


def show_odds(
    default_league_id: Optional[int] = None,
    default_season: Optional[int] = None,
) -> None:
    st.header("Cotes")

    snapshot = health_snapshot()
    if snapshot.get("offline"):
        reason = snapshot.get("offline_reason") or "Mode hors ligne actif"
        st.warning(
            f"Mode dégradé : {reason}. Les cotes peuvent provenir du cache.",
            icon="⚠️",
        )
    elif snapshot.get("low_quota"):
        st.info(
            "Quota API faible : les rafraîchissements peuvent être limités.",
            icon="ℹ️",
        )

    league_id, season, league_label = select_league_and_season(
        default_league_id=default_league_id,
        default_season=default_season,
    )
    st.caption(f"{league_label} — Saison {season}")

    date_value = st.text_input("Date (YYYY-MM-DD ou JJ/MM/AAAA)", "").strip()
    date_param = _normalize_date_input(date_value) if date_value else None
    if date_value and date_param is None:
        st.warning("Format de date invalide. Utilisez 2025-11-08 ou 08/11/2025.", icon="⚠️")

    force_refresh = st.button(
        "Forcer une mise à jour des cotes",
        help="Relance immédiatement l'endpoint `odds` pour contourner le cache.",
    )

    with st.spinner("Chargement des cotes..."):
        odds_payload = get_odds(
            league_id,
            season,
            date_param,
            force_refresh=force_refresh,
        ) or []

    options = _fixture_options(odds_payload)
    if not options:
        st.info("Aucune cote disponible pour cette sélection.")
        _render_bookmaker_list()
        return

    selected = st.selectbox(
        "Match",
        options,
        format_func=lambda item: item["label"],
    )
    entry = selected.get("data", {})
    bookmakers = entry.get("bookmakers") or []
    df = _format_1x2_table(bookmakers)

    col_meta, col_update = st.columns([3, 1])
    with col_meta:
        fixture = entry.get("fixture") or {}
        venue = (fixture.get("venue") or {}).get("name")
        if venue:
            st.caption(f"Stade : {venue}")
    with col_update:
        update_label = _latest_update(entry)
        if update_label:
            st.caption(f"Dernière mise à jour : {update_label}")

    if df is None:
        st.warning("Aucun marché 1X2 détecté pour ce match.")
    else:
        st.dataframe(df, hide_index=True, use_container_width=True)
        home_best = _best_price(df, "1")
        draw_best = _best_price(df, "N")
        away_best = _best_price(df, "2")
        col_h, col_d, col_a = st.columns(3)
        if home_best:
            col_h.metric(
                "Meilleure cote domicile",
                home_best["odd"],
                help=f"Bookmaker : {home_best['book']}",
            )
        if draw_best:
            col_d.metric(
                "Meilleure cote nul",
                draw_best["odd"],
                help=f"Bookmaker : {draw_best['book']}",
            )
        if away_best:
            col_a.metric(
                "Meilleure cote extérieur",
                away_best["odd"],
                help=f"Bookmaker : {away_best['book']}",
            )

    fixture_id = selected.get("fixture_id")
    if fixture_id:
        st.markdown("---")
        st.subheader("Widget officiel du match")
        render_widget("game", height=660, game_id=int(fixture_id))

        with st.expander("Cotes complètes (tous marchés)"):
            match_odds = get_odds_by_fixture(int(fixture_id)) or entry
            df_raw = _raw_odds_table(match_odds[0] if isinstance(match_odds, list) else entry)
            if df_raw.empty:
                st.info("Aucune cote détaillée à afficher.")
            else:
                st.dataframe(df_raw, hide_index=True, use_container_width=True)

    _render_bookmaker_list()
