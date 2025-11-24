from __future__ import annotations

from typing import Dict, Iterable, Optional

import altair as alt
import pandas as pd
import streamlit as st
from zoneinfo import ZoneInfo

from .analytics_ui import _prediction_side, _probability_for_side
from .match_filter import normalize_bookmaker, BOOKMAKER_PRESETS, MARKET_ALIASES, VALUE_ALIASES, resolve_bookmakers, build_alias_lookup
from .prediction_history import load_prediction_history, normalize_prediction_history
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
    if df.empty:
        return df
    df["timestamp"] = _to_paris(df.get("timestamp"))
    df["fixture_date"] = _to_paris(df.get("fixture_date"))
    df["timeline"] = df["fixture_date"].fillna(df["timestamp"])
    df.sort_values("timeline", inplace=True)
    df.dropna(subset=["timeline"], inplace=True)
    df["success"] = df.apply(_compute_success, axis=1)
    return df


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


def show_performance_dashboard() -> None:
    st.header("Tableau de bord IA")
    df = _prepare_data()
    if df.empty:
        st.info("Aucune prediction historisee.")
        return

    total_preds = len(df)
    completed = df.dropna(subset=["success"])
    win_rate = completed["success"].mean() * 100 if not completed.empty else 0
    st.metric("Predictions totales", f"{total_preds}")
    st.metric("Matches termines", f"{len(completed)}")
    st.metric("Taux de reussite", f"{win_rate:.1f}%")

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

__all__ = ["show_performance_dashboard"]

