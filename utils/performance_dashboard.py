from __future__ import annotations

from typing import Dict, Iterable, Optional
import re
import math

import altair as alt
import pandas as pd
import streamlit as st
from zoneinfo import ZoneInfo

from .analytics_ui import _prediction_side, _probability_for_side, _auto_sync_prediction_results
from .match_filter import normalize_bookmaker, BOOKMAKER_PRESETS, MARKET_ALIASES, VALUE_ALIASES, resolve_bookmakers, build_alias_lookup
from .prediction_history import (
    load_prediction_history,
    normalize_prediction_history,
    update_outcome,
    FINISHED_STATUS,
)
from .profile import aliases_map
from . import api_calls

PARIS_TZ = ZoneInfo("Europe/Paris")


def _to_paris(series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(series, errors="coerce", utc=True)
    try:
        return dt.dt.tz_convert(PARIS_TZ)
    except Exception:
        return dt


def _prepare_data() -> pd.DataFrame:
    normalize_prediction_history()
    df = load_prediction_history()
    df = _auto_update_completed(df)
    if df.empty:
        return df
    df["timestamp"] = _to_paris(df.get("timestamp"))
    df["fixture_date"] = _to_paris(df.get("fixture_date"))
    df["timeline"] = df["fixture_date"].fillna(df["timestamp"])
    df.sort_values("timeline", inplace=True)
    df.dropna(subset=["timeline"], inplace=True)
    df["success"] = df.apply(_compute_success, axis=1)
    df["bet_category"] = df.apply(_categorize_selection, axis=1)
    return df


def _max_loss_streak(outcomes: Iterable[Optional[bool]]) -> int:
    streak = 0
    max_streak = 0
    for value in outcomes:
        if value is True:
            streak = 0
        elif value is False:
            streak += 1
            if streak > max_streak:
                max_streak = streak
    return max_streak


def _core_performance_metrics(df: pd.DataFrame) -> Dict[str, Optional[float]]:
    resolved = df.dropna(subset=["success"]).sort_values("timeline")
    confirmed = len(resolved)
    if confirmed == 0:
        return {
            "confirmed": 0,
            "max_loss": 0,
            "avg_odds": None,
            "win_rate": None,
        }
    odds_series = pd.to_numeric(resolved.get("bet_odd"), errors="coerce")
    avg_odds = float(odds_series.dropna().mean()) if not odds_series.dropna().empty else None
    win_rate = float(resolved["success"].mean()) if not resolved.empty else None
    max_loss = _max_loss_streak(resolved["success"])
    return {
        "confirmed": confirmed,
        "max_loss": max_loss,
        "avg_odds": avg_odds,
        "win_rate": win_rate,
    }


def _auto_update_completed(df: pd.DataFrame, max_updates: int = 10) -> pd.DataFrame:
    if df.empty:
        return df
    now = pd.Timestamp.now(tz=PARIS_TZ)
    working = df.copy()
    try:
        working["fixture_date"] = pd.to_datetime(working.get("fixture_date"), errors="coerce", utc=True)
    except Exception:
        working["fixture_date"] = pd.NaT
    pending_mask = (
        working["fixture_id"].notna()
        & (
            working["result_status"].isna()
            | (~working["result_status"].astype(str).str.upper().isin(FINISHED_STATUS))
        )
        & working["fixture_date"].notna()
        & (working["fixture_date"] < now)
    )
    pending_ids = (
        working.loc[pending_mask, "fixture_id"]
        .dropna()
        .astype(float)
        .astype(int)
        .drop_duplicates()
        .head(max_updates)
    )
    updated = False
    for fixture_id in pending_ids:
        try:
            details = api_calls.get_fixture_details(fixture_id) or []
            entry = details[0] if isinstance(details, list) and details else None
            if not isinstance(entry, dict):
                continue
            fixture_block = entry.get("fixture") or {}
            status = (fixture_block.get("status") or {}).get("short", "")
            if status.upper() not in FINISHED_STATUS:
                continue
            goals = entry.get("goals") or {}
            teams = entry.get("teams") or {}
            winner = _winner_from_fixture_details(entry)
            update_outcome(
                fixture_id,
                status=status,
                goals_home=goals.get("home"),
                goals_away=goals.get("away"),
                winner=winner,
            )
            updated = True
        except Exception:
            continue
    if updated:
        normalize_prediction_history()
        return load_prediction_history()
    return df


def _parse_score(row: pd.Series) -> tuple[Optional[int], Optional[int]]:
    raw = str(row.get("result_score") or "")
    match = re.search(r"(\d+)\s*[-:\u2013]\s*(\d+)", raw)
    if match:
        try:
            return int(match.group(1)), int(match.group(2))
        except (TypeError, ValueError):
            return None, None
    return None, None


def _normalize_winner(value: str) -> str:
    val = value.lower()
    if val in {"home", "domicile"}:
        return "home"
    if val in {"away", "exterieur"}:
        return "away"
    if val in {"draw", "nul"}:
        return "draw"
    return ""


def _selection_success(selection: str, winner: str, home_goals: Optional[int], away_goals: Optional[int]) -> Optional[bool]:
    if not selection:
        return None
    sel = selection.lower()
    winner_norm = _normalize_winner(winner)
    total_goals = None
    if home_goals is not None and away_goals is not None:
        total_goals = home_goals + away_goals
    over_under = re.search(r"(over|under)\s*([0-9]+(?:\.[0-9])?)", sel)
    if over_under and total_goals is not None:
        threshold = float(over_under.group(2))
        return total_goals > threshold if over_under.group(1) == "over" else total_goals < threshold
    double_chance = re.search(r"(double chance\s*)?([12x]{2})", sel)
    if double_chance and winner_norm:
        token = double_chance.group(2)
        combos = {
            "1x": {"home", "draw"},
            "x1": {"home", "draw"},
            "12": {"home", "away"},
            "21": {"home", "away"},
            "x2": {"draw", "away"},
            "2x": {"draw", "away"},
        }
        allowed = combos.get(token)
        if allowed:
            return winner_norm in allowed
    if "home" in sel or "domicile" in sel:
        return winner_norm == "home" if winner_norm else None
    if "away" in sel or "exterieur" in sel:
        return winner_norm == "away" if winner_norm else None
    if "draw" in sel or "nul" in sel:
        return winner_norm == "draw" if winner_norm else None
    return None


def _compute_success(row: pd.Series) -> Optional[bool]:
    result = str(row.get("result_winner", ""))
    selection = str(row.get("bet_selection") or row.get("total_pick") or "").strip()
    home_goals, away_goals = _parse_score(row)
    selection_result = _selection_success(selection, result, home_goals, away_goals)
    if selection and selection_result is not None:
        return selection_result
    if not result:
        return None
    side = _prediction_side(row)
    if not side:
        return None
    result_norm = _normalize_winner(result)
    if not result_norm:
        return None
    if result_norm == "home":
        return side == "home"
    if result_norm == "away":
        return side == "away"
    if result_norm == "draw":
        return side == "draw"
    return None


def _categorize_selection(row: pd.Series) -> str:
    selection = str(row.get("bet_selection") or row.get("total_pick") or "").strip().lower()
    if not selection:
        return "Non confirmé"
    if re.search(r"(over|under)\s*[0-9]+", selection):
        return "Over/Under"
    if "double chance" in selection or re.search(r"\b(1x|x1|12|21|x2|2x)\b", selection):
        return "Double chance"
    if "buteur" in selection or "scorer" in selection:
        return "Buteur"
    if re.search(r"\b(home|away|domicile|exterieur|nul|draw)\b", selection):
        return "1X2"
    if re.search(r"\d+\s*[-:\u2013]\s*\d+", selection) or "score" in selection:
        return "Score exact"
    return "Autre"


def show_performance_dashboard() -> None:
    st.header("Tableau de bord IA")
    _auto_sync_prediction_results()
    df = _prepare_data()
    if df.empty:
        st.info("Aucune prediction historisee.")
        return

    total_preds = len(df)
    completed = df.dropna(subset=["success"])
    summary = _core_performance_metrics(df)

    avg_display = "ND"
    if summary["avg_odds"] not in {None}:
        try:
            if not math.isnan(summary["avg_odds"]):
                avg_display = f"{summary['avg_odds']:.2f}"
        except TypeError:
            pass

    win_display = "ND"
    if summary["win_rate"] not in {None}:
        try:
            if not math.isnan(summary["win_rate"]):
                win_display = f"{summary['win_rate'] * 100:.1f}%"
        except TypeError:
            pass

    metric_row = st.columns(4)
    metric_row[0].metric("Predictions totales", f"{total_preds}")
    metric_row[1].metric("Paris confirmes", f"{summary['confirmed']}")
    metric_row[2].metric("Cote moyenne", avg_display)
    metric_row[3].metric("Taux de reussite", win_display)

    extra_row = st.columns(2)
    extra_row[0].metric("Serie de pertes max", f"{summary['max_loss']}")
    extra_row[1].metric("Matches termines", f"{len(completed)}")

    if not completed.empty:
        category_stats = completed.copy()
        category_stats["bet_category"] = category_stats["bet_category"].fillna("Autre")
        summary = (
            category_stats.groupby("bet_category")
            .agg(matches=("fixture_id", "count"), winrate=("success", "mean"))
            .reset_index()
        )
        summary["winrate"] = summary["winrate"] * 100
        st.subheader("Performance par type de pari")
        st.dataframe(
            summary.rename(
                columns={
                    "bet_category": "Type",
                    "matches": "Matches",
                    "winrate": "Taux de reussite %",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

    st.markdown("---")
    st.subheader("Evolution du taux de reussite")
    timeline = completed.copy()
    timeline["date"] = timeline["timeline"].dt.date
    daily = timeline.groupby("date")["success"].mean().reset_index()
    daily["success"] = daily["success"] * 100
    if not daily.empty:
        chart = alt.Chart(daily).mark_line(point=True).encode(
            x="date",
            y=alt.Y("success", title="Taux de reussite %"),
        )
        st.altair_chart(chart, use_container_width=True)

    st.markdown("---")
    st.subheader("Comparatif bookmakers (edge attendu)")
    custom_aliases = aliases_map()
    lookup = build_alias_lookup(custom_aliases)
    df_edges = _edge_records(df, resolve_bookmakers(lookup.keys(), custom_aliases))
    if not df_edges.empty:
        df_edges["fixture_date"] = pd.to_datetime(df_edges.get("fixture_date"), errors="coerce", utc=True)
        df_edges["timestamp"] = pd.to_datetime(df_edges.get("timestamp"), errors="coerce", utc=True)
        summary = df_edges.groupby("book_group").agg(
            matches=("fixture_id", "count"),
            expected_edge=("expected_edge", "mean"),
            realized_roi=("realized_roi", "mean"),
        ).reset_index()
        summary["expected_edge"] = summary["expected_edge"] * 100
        summary["realized_roi"] = summary["realized_roi"] * 100
        st.dataframe(
            summary.rename(
                columns={
                    "book_group": "Groupe",
                    "matches": "Matches",
                    "expected_edge": "Edge %",
                    "realized_roi": "ROI %",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )
        bar = alt.Chart(summary).mark_bar().encode(
            x="Groupe",
            y="Edge %",
            color="Groupe"
        )
        st.altair_chart(bar, use_container_width=True)
    else:
        st.info("Pas de cote associee aux predictions.")

    st.markdown("---")
    st.subheader("Top edges recents")
    if not df_edges.empty:
        top_edges = df_edges.sort_values("expected_edge", ascending=False).head(20).copy()
        top_edges = top_edges.rename(columns={"fixture_date": "Date match"})
        if "Date match" in top_edges and hasattr(top_edges["Date match"], "dt"):
            top_edges["Date match"] = top_edges["Date match"].dt.strftime("%d/%m/%Y %H:%M")
        st.dataframe(
            top_edges[["Date match", "home_team", "away_team", "bookmaker", "expected_edge", "odd"]],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("Pas de cote associee aux predictions.")

    st.markdown("---")
    st.subheader("Derniers matchs suivis")
    history = df.sort_values("timeline", ascending=False).copy()
    if history.empty:
        st.info("Aucune prediction historisee.")
    else:
        history["journee"] = history["timeline"].dt.date
        date_options = sorted(history["journee"].dropna().unique(), reverse=True)
        controls = st.columns([2, 1, 1])
        selected_date = None
        if date_options:
            with controls[0]:
                selected_date = st.selectbox(
                    "Journee a afficher",
                    options=date_options,
                    index=0,
                    format_func=lambda d: d.strftime("%d/%m/%Y"),
                )
        else:
            with controls[0]:
                st.write("Aucune date disponible.")
        with controls[1]:
            show_all = st.checkbox(
                "Tout afficher",
                value=True,
                help="Affiche toutes les confirmations pour la journee choisie.",
            )
        with controls[2]:
            max_rows = st.slider(
                "Limite (lignes)",
                min_value=10,
                max_value=120,
                value=30,
                step=5,
                help="Utilisez la limite uniquement si vous ne souhaitez pas tout afficher.",
            )

        filtered = history
        if selected_date is not None:
            filtered = history[history["journee"] == selected_date]
        if filtered.empty:
            st.info("Aucun pari confirme pour cette journee.")
        else:
            if not show_all:
                filtered = filtered.head(max_rows)
            filtered = filtered.copy()
            filtered["Date match"] = filtered["timeline"].dt.strftime("%d/%m/%Y %H:%M")
            filtered["Issue"] = (
                filtered["result_winner"]
                .map({"home": "Domicile", "away": "Exterieur", "draw": "Nul"})
                .fillna("En attente")
            )
            filtered["Succes"] = filtered["success"].map({True: "Oui", False: "Non"}).fillna("-")
            filtered["Selection"] = filtered["bet_selection"].fillna("")
            filtered.loc[filtered["Selection"] == "", "Selection"] = "-"
            filtered["Type"] = filtered["bet_category"].fillna("Autre")
            display_cols = [
                "Date match",
                "home_team",
                "away_team",
                "Selection",
                "Type",
                "Issue",
                "Succes",
            ]
            st.dataframe(
                filtered[display_cols].rename(
                    columns={
                        "home_team": "Domicile",
                        "away_team": "Exterieur",
                        "Selection": "Selection",
                        "Type": "Type",
                        "Succes": "Succes",
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )


def _edge_records(df: pd.DataFrame, filter_tokens: set[str]) -> pd.DataFrame:
    records = []
    for _, row in df.iterrows():
        fixture = row.get("fixture_id")
        if pd.isna(fixture):
            continue
        try:
            fixture_id = int(fixture)
        except (TypeError, ValueError):
            continue
        side = _prediction_side(row)
        probability = _probability_for_side(row, side) if side else None
        if side is None or probability is None:
            continue
        odds_payload = api_calls.get_odds_by_fixture(fixture_id) or []
        bookmakers = odds_payload if isinstance(odds_payload, list) else []
        for entry in bookmakers:
            if not isinstance(entry, dict):
                continue
            for bookmaker in entry.get("bookmakers") or []:
                if not isinstance(bookmaker, dict):
                    continue
                name = str(bookmaker.get("name", "")).strip()
                normalized = normalize_bookmaker(name)
                if filter_tokens and normalized not in filter_tokens:
                    continue
                markets = _extract_markets(bookmaker)
                odd = markets.get(side)
                if not odd:
                    continue
                edge = odd * probability - 1
                records.append(
                    {
                        "timestamp": row.get("timestamp"),
                        "fixture_date": row.get("fixture_date"),
                        "fixture_id": fixture_id,
                        "home_team": row.get("home_team"),
                        "away_team": row.get("away_team"),
                        "bookmaker": name,
                        "book_group": _group_label(normalize_bookmaker(name), custom_map=build_alias_lookup(aliases_map())),
                        "expected_edge": edge,
                        "realized_roi": _realized_roi(row.get("success"), odd),
                        "odd": odd,
                    }
                )
    return pd.DataFrame(records)


def _extract_markets(bookmaker: Dict[str, Any]) -> Dict[str, float]:
    markets: Dict[str, float] = {}
    for bet in bookmaker.get("bets") or []:
        if not isinstance(bet, dict):
            continue
        market = str(bet.get("name", "")).strip().lower()
        if market not in MARKET_ALIASES:
            continue
        for value in bet.get("values") or []:
            outcome = VALUE_ALIASES.get(str(value.get("value", "")).strip().lower())
            if not outcome:
                continue
            try:
                odd = float(value.get("odd"))
            except (TypeError, ValueError):
                continue
            markets[outcome] = odd
    return markets


def _group_label(normalized: str, custom_map: Dict[str, Iterable[str]]) -> str:
    for label, aliases in BOOKMAKER_PRESETS.items():
        if normalized in {normalize_bookmaker(label)} | {normalize_bookmaker(alias) for alias in aliases}:
            return label
    for label, alias_set in custom_map.items():
        tokens = {normalize_bookmaker(label)} | {normalize_bookmaker(alias) for alias in alias_set}
        if normalized in tokens:
            return label
    return "Autres"


def _realized_roi(success: Optional[bool], odd: float) -> Optional[float]:
    if success is None:
        return None
    return (odd - 1.0) if success else -1.0


def _winner_from_fixture_details(details: Dict[str, Any]) -> Optional[str]:
    teams = details.get("teams") or {}
    goals = details.get("goals") or {}
    home = teams.get("home") or {}
    away = teams.get("away") or {}
    if home.get("winner") is True:
        return "home"
    if away.get("winner") is True:
        return "away"
    home_goals = goals.get("home")
    away_goals = goals.get("away")
    if home_goals is not None and away_goals is not None and home_goals == away_goals:
        return "draw"
    return None

__all__ = ["show_performance_dashboard"]
