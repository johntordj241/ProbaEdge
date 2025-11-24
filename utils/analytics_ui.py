from __future__ import annotations

from typing import Optional, Dict, Iterable, List, Any

import pandas as pd
import altair as alt
import streamlit as st
from zoneinfo import ZoneInfo

from .prediction_history import (
    load_prediction_history,
    seed_sample_predictions,
    sync_prediction_results,
    normalize_prediction_history,
)
from .profile import aliases_map, get_ui_defaults
from .match_filter import BOOKMAKER_PRESETS, resolve_bookmakers, normalize_bookmaker
from .api_calls import get_odds_by_fixture

PARIS_TZ = ZoneInfo("Europe/Paris")

MARKET_ALIASES = {"1x2", "match winner", "match result", "fulltime result"}
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
}


def _to_paris(series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(series, errors="coerce", utc=True)
    try:
        return dt.dt.tz_convert(PARIS_TZ)
    except Exception:
        return dt


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
    value = row.get(column_map.get(side, ""))
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_odds(fixture_id: int) -> List[Dict[str, float]]:
    payload = get_odds_by_fixture(fixture_id) or []
    detail: List[Dict[str, float]] = []
    entries = payload if isinstance(payload, list) else []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for bookmaker in entry.get("bookmakers") or []:
            if not isinstance(bookmaker, dict):
                continue
            name = str(bookmaker.get("name", "")).strip()
            if not name:
                continue
            normalized = normalize_bookmaker(name)
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
            if markets:
                detail.append({
                    "name": name,
                    "normalized": normalized,
                    "markets": markets,
                })
    return detail


def _edge_records(df: pd.DataFrame, filter_tokens: set[str]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
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
        odds_detail = _extract_odds(fixture_id)
        for detail in odds_detail:
            if filter_tokens and detail.get("normalized") not in filter_tokens:
                continue
            odd = detail["markets"].get(side)
            if not odd:
                continue
            expected_edge = odd * probability - 1
            success = row.get("success")
            realized = None
            if success in {True, False}:
                realized = (odd - 1.0) if success else -1.0
            records.append(
                {
                    "fixture_id": fixture_id,
                    "bookmaker": detail["name"],
                    "odd": odd,
                    "expected_edge": expected_edge,
                    "realized_roi": realized,
                    "probability": probability,
                    "pick": row.get("main_pick"),
                    "success": success,
                    "fixture_date": row.get("fixture_date"),
                    "captured_at": row.get("timestamp"),
                }
            )
    return records


def show_prediction_performance(path: str = 'data/prediction_history.csv') -> None:
    st.header("Performance IA")
    normalize_prediction_history(path)
    df = load_prediction_history(path)
    df["timestamp"] = _to_paris(df.get("timestamp"))
    df["fixture_date"] = _to_paris(df.get("fixture_date"))
    df["display_date"] = df["fixture_date"].fillna(df["timestamp"])

    col_sync, col_seed = st.columns([1,1])
    if col_sync.button("Synchroniser resultats API"):
        updated = sync_prediction_results()
        if updated:
            st.success(f"{updated} resultats mis a jour.")
        else:
            st.info("Aucun resultat supplementaire a synchroniser.")
        st.experimental_rerun()
    if col_seed.button("Charger des exemples"):
        if seed_sample_predictions():
            st.success("Predictions d'exemple ajoutees.")
        else:
            st.info("Historique deja alimente : utilisez le bouton forcer dans le fichier si besoin.")
        st.experimental_rerun()

    if df.empty:
        st.info("Aucune prediction historisee.")
        return

    df["success"] = df.apply(_compute_success, axis=1)
    valid_df = df.dropna(subset=["success"]) if "success" in df else df
    valid_df = valid_df.copy()
    valid_df["league_id"] = pd.to_numeric(valid_df.get("league_id"), errors="coerce").astype("Int64")
    valid_df["season"] = pd.to_numeric(valid_df.get("season"), errors="coerce").astype("Int64")

    if valid_df.empty:
        st.info("Aucun resultat final pour evaluer les predictions.")
        return

    win_rate = valid_df["success"].mean() * 100
    st.metric("Taux de reussite", f"{win_rate:.1f}%", help="Proportion de predictions correctes sur les matches termines.")

    custom_aliases = aliases_map()
    league_options = sorted(valid_df["league_id"].dropna().astype(int).unique())
    season_options = sorted(valid_df["season"].dropna().astype(int).unique())
    filter_cols = st.columns(2)
    selected_leagues = filter_cols[0].multiselect(
        "Compétitions",
        options=league_options,
        default=league_options,
    )
    selected_seasons = filter_cols[1].multiselect(
        "Saisons",
        options=season_options,
        default=season_options,
    )
    if selected_leagues:
        valid_df = valid_df[valid_df["league_id"].isin(selected_leagues)]
    if selected_seasons:
        valid_df = valid_df[valid_df["season"].isin(selected_seasons)]
    if valid_df.empty:
        st.info("Aucune prédiction ne correspond aux filtres sélectionnés.")
        return

    bookmaker_choices = list(BOOKMAKER_PRESETS.keys()) + sorted(custom_aliases.keys())
    ui_defaults = get_ui_defaults()
    default_selection = [
        name for name in ui_defaults.get("bookmakers", []) if name in bookmaker_choices
    ]
    if not default_selection:
        default_selection = bookmaker_choices if bookmaker_choices else list(BOOKMAKER_PRESETS.keys())

    selected_bookmakers = st.multiselect(
        "Bookmakers a analyser",
        options=bookmaker_choices,
        default=default_selection,
    )
    filter_tokens = resolve_bookmakers(selected_bookmakers, custom_aliases)

    edge_records = _edge_records(valid_df, filter_tokens)
    if edge_records:
        edge_df = pd.DataFrame(edge_records)
        edge_df["fixture_date"] = _to_paris(edge_df.get("fixture_date"))
        edge_df["captured_at"] = _to_paris(edge_df.get("captured_at"))
        summary = edge_df.groupby("bookmaker").agg(
            matches=("fixture_id", "count"),
            expected_edge=("expected_edge", "mean"),
            realized_roi=("realized_roi", "mean"),
        ).reset_index()
        summary["expected_edge"] = summary["expected_edge"] * 100
        if not summary["realized_roi"].isna().all():
            summary["realized_roi"] = summary["realized_roi"] * 100
        st.subheader("ROI / Edge par bookmaker")
        st.dataframe(
            summary.rename(
                columns={
                    "matches": "Matches",
                    "bookmaker": "Bookmaker",
                    "expected_edge": "Edge %",
                    "realized_roi": "ROI %",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )
        st.caption("Edge = odd * proba - 1. ROI reel utilise le resultat final quand il est connu.")

        comparison = summary.melt(
            id_vars=["bookmaker"],
            value_vars=["expected_edge", "realized_roi"],
            var_name="Metric",
            value_name="Value",
        )
        comparison["Metric"] = comparison["Metric"].replace(
            {"expected_edge": "Edge attendu", "realized_roi": "ROI réel"}
        )
        chart = alt.Chart(comparison).mark_bar().encode(
            x=alt.X("bookmaker:N", title="Bookmaker"),
            y=alt.Y("Value:Q", title="Pourcentage"),
            color="Metric:N",
            tooltip=["bookmaker", "Metric", alt.Tooltip("Value:Q", format=".2f")],
        )
        st.altair_chart(chart, use_container_width=True)

        if not edge_df["expected_edge"].empty:
            st.markdown("---")
            st.subheader("Chronologie de precision")
            timeline = valid_df.dropna(subset=["success"]).copy()
            timeline = timeline.assign(
                display_date=timeline["fixture_date"].fillna(timeline["timestamp"])
            )
            timeline.dropna(subset=["display_date"], inplace=True)
            if not timeline.empty:
                timeline["date"] = timeline["display_date"].dt.date
                daily = timeline.groupby("date")["success"].mean().reset_index()
                daily["success"] = daily["success"] * 100
                chart = alt.Chart(daily).mark_line(point=True).encode(
                    x="date",
                    y=alt.Y("success", title="Taux de reussite %"),
                )
                st.altair_chart(chart, use_container_width=True)
                last_rate = daily.iloc[-1]["success"]
                if last_rate < 40:
                    st.error("Alerte : baisse de precision recente (<40%).")
                elif last_rate > 60:
                    st.success("Bon trend : precision > 60% recemment.")
    else:
        st.info("Aucune cote correspondante n'a ete trouvee pour les predictions selectionnees.")

    st.markdown("---")
    st.subheader("Historique recent")
    history_view = valid_df.copy()
    history_view["Date match"] = history_view["fixture_date"].fillna(history_view["timestamp"])
    if hasattr(history_view["Date match"], "dt"):
        history_view["Date match"] = history_view["Date match"].dt.strftime("%d/%m/%Y %H:%M")
    st.dataframe(
        history_view[["Date match", "home_team", "away_team", "main_pick", "result_winner", "success"]].tail(50),
        hide_index=True,
        use_container_width=True,
    )


def _compute_success(row: pd.Series) -> Optional[bool]:
    result = str(row.get("result_winner", ""))
    if not result:
        return None
    side = _prediction_side(row)
    if not side:
        return None
    if result.lower() in {"home", "domicile"}:
        return side == "home"
    if result.lower() in {"away", "exterieur"}:
        return side == "away"
    if result.lower() in {"draw", "nul"}:
        return side == "draw"
    return None

__all__ = ["show_prediction_performance"]
