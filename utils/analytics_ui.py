from __future__ import annotations

from typing import Optional, Dict, Iterable, List, Any
from datetime import datetime
import math
import re
import json

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
from .cache import is_offline_mode

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

_SYNC_STATE_KEY = "prediction_performance_last_sync"
_AUTO_SYNC_COOLDOWN_SECONDS = 90


def _auto_sync_prediction_results(
    *,
    limit: int = 40,
    force: bool = False,
    status_placeholder: Optional[Any] = None,
    notify_on_no_change: bool = False,
) -> int:
    """
    Rafraichit automatiquement les resultats des matches termines afin
    que la page Performance IA reste a jour sans action manuelle.
    """
    if is_offline_mode():
        if status_placeholder:
            status_placeholder.info("Mode hors ligne actif : synchronisation differée.")
        return 0

    now = datetime.now(PARIS_TZ)
    last_run_raw = st.session_state.get(_SYNC_STATE_KEY)
    last_run = None
    if isinstance(last_run_raw, str):
        try:
            last_run = datetime.fromisoformat(last_run_raw)
        except ValueError:
            last_run = None
    elif isinstance(last_run_raw, datetime):
        last_run = last_run_raw

    if not force and last_run is not None:
        delta = (now - last_run).total_seconds()
        if delta < _AUTO_SYNC_COOLDOWN_SECONDS:
            return 0

    with st.spinner("Mise à jour des résultats en attente..."):
        updated = sync_prediction_results(limit=limit)
    st.session_state[_SYNC_STATE_KEY] = now.isoformat()

    if status_placeholder:
        if updated:
            status_placeholder.success(f"{updated} résultat(s) synchronisé(s).")
        elif notify_on_no_change:
            status_placeholder.caption("Résultats déjà à jour.")

    if updated:
        st.experimental_rerun()
    return updated


def _to_paris(series: pd.Series) -> pd.Series:
    dt = pd.to_datetime(series, errors="coerce", utc=True)
    try:
        return dt.dt.tz_convert(PARIS_TZ)
    except Exception:
        return dt


def _as_nullable_int(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if not isinstance(numeric, pd.Series):
        numeric = pd.Series(numeric)
    try:
        return numeric.astype("Int64")
    except (TypeError, ValueError):
        return numeric.round().astype("Int64")


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
    sync_placeholder = st.empty()
    _auto_sync_prediction_results(status_placeholder=sync_placeholder)
    normalize_prediction_history(path)
    df = load_prediction_history(path)
    df["timestamp"] = _to_paris(df.get("timestamp"))
    df["fixture_date"] = _to_paris(df.get("fixture_date"))
    df["display_date"] = df["fixture_date"].fillna(df["timestamp"])

    col_sync, col_seed = st.columns([1,1])
    if col_sync.button("Synchroniser resultats API"):
        manual_placeholder = st.empty()
        _auto_sync_prediction_results(
            limit=80,
            force=True,
            status_placeholder=manual_placeholder,
            notify_on_no_change=True,
        )
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
    filtered_df = df.copy()
    filtered_df["league_id"] = _as_nullable_int(filtered_df.get("league_id"))
    filtered_df["season"] = _as_nullable_int(filtered_df.get("season"))

    if filtered_df.empty:
        st.info("Aucune prediction historisee.")
        return

    custom_aliases = aliases_map()
    league_options = sorted(filtered_df["league_id"].dropna().astype(int).unique())
    season_options = sorted(filtered_df["season"].dropna().astype(int).unique())
    filter_cols = st.columns(2)
    selected_leagues = filter_cols[0].multiselect(
        "Comp?titions",
        options=league_options,
        default=league_options,
    )
    selected_seasons = filter_cols[1].multiselect(
        "Saisons",
        options=season_options,
        default=season_options,
    )
    if selected_leagues:
        filtered_df = filtered_df[filtered_df["league_id"].isin(selected_leagues)]
    if selected_seasons:
        filtered_df = filtered_df[filtered_df["season"].isin(selected_seasons)]
    if filtered_df.empty:
        st.info("Aucune pr?diction ne correspond aux filtres s?lectionn?s.")
        return

    scope_df = filtered_df.copy()
    confirmed_mask = scope_df["bet_selection"].fillna("").str.strip() != ""
    confirmed_df = scope_df[confirmed_mask]
    if confirmed_df.empty:
        st.info("Aucun pari confirm? n'a ?t? enregistr? pour ces filtres.")
        _render_ai_trace_section(scope_df)
        return

    completed_df = confirmed_df.dropna(subset=["success"])
    pending_df = confirmed_df[confirmed_df["success"].isna()]

    metric_cols = st.columns(3)
    total_confirmed = int(confirmed_df["bet_selection"].fillna("").str.strip().replace("", pd.NA).dropna().shape[0])
    metric_cols[0].metric("Paris confirm?s", f"{total_confirmed}")
    pending_count = int(pending_df["bet_selection"].fillna("").str.strip().replace("", pd.NA).dropna().shape[0])
    metric_cols[1].metric("Paris en attente", f"{pending_count}")
    if not completed_df.empty:
        win_rate = completed_df["success"].mean() * 100
        metric_cols[2].metric(
            "Taux de r?ussite",
            f"{win_rate:.1f}%",
            help="Proportion des paris confirm?s termin?s qui sont gagnants.",
        )
    else:
        metric_cols[2].metric("Taux de r?ussite", "0.0%", help="Aucun match termin? pour cette s?lection.")

    if not pending_df.empty:
        st.info("Certains paris sont encore en attente : ils seront valid?s automatiquement lorsque le score final sera connu.")
        st.markdown("---")
        st.subheader("Paris confirm?s en attente")
        pending_view = pending_df.copy()
        pending_view["Date match"] = pending_view["fixture_date"].fillna(pending_view["timestamp"])
        pending_view["Selection"] = pending_view.apply(
            lambda row: _first_valid_selection(row.get("bet_selection"), row.get("total_pick"), row.get("main_pick")),
            axis=1,
        )
        if hasattr(pending_view["Date match"], "dt"):
            pending_view["Date match"] = pending_view["Date match"].dt.strftime("%d/%m/%Y %H:%M")
        st.dataframe(
            pending_view[["Date match", "home_team", "away_team", "Selection", "status_snapshot"]].rename(
                columns={
                    "home_team": "Domicile",
                    "away_team": "Exterieur",
                    "Selection": "Selection",
                    "status_snapshot": "Statut API",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

    if completed_df.empty:
        st.info("Aucun resultat final pour evaluer les predictions.")
        _render_ai_trace_section(scope_df)
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

    edge_records = _edge_records(completed_df, filter_tokens)
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
            timeline = completed_df.copy()
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

    _render_ai_trace_section(scope_df)

    st.markdown("---")
    st.subheader("Historique recent")
    history_view = confirmed_df.copy()
    history_view["Date match"] = history_view["fixture_date"].fillna(history_view["timestamp"])
    history_view["Selection"] = history_view.apply(
        lambda row: _first_valid_selection(row.get("bet_selection"), row.get("total_pick"), row.get("main_pick")),
        axis=1,
    )
    if hasattr(history_view["Date match"], "dt"):
        history_view["Date match"] = history_view["Date match"].dt.strftime("%d/%m/%Y %H:%M")
    st.dataframe(
        history_view[["Date match", "home_team", "away_team", "Selection", "result_winner", "success"]].tail(50),
        hide_index=True,
        use_container_width=True,
    )


def _render_ai_trace_section(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        return
    ai_df = df.dropna(subset=["ai_analysis"]).copy()
    scenario_rows: List[Dict[str, Any]] = []
    if "ai_scenarios" in df.columns:
        scenario_source = df.dropna(subset=["ai_scenarios"])
        for _, row in scenario_source.iterrows():
            raw_payload = row.get("ai_scenarios")
            try:
                entries = json.loads(str(raw_payload))
            except (TypeError, ValueError):
                continue
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                scenario_rows.append(
                    {
                        "generated": row.get("ai_scenarios_generated_at") or entry.get("generated_at"),
                        "match": f"{row.get('home_team', '?')} - {row.get('away_team', '?')}",
                        "scenario": entry.get("label") or entry.get("key"),
                        "delta_home": float(entry.get("delta", {}).get("home", 0.0)) * 100.0,
                        "delta_draw": float(entry.get("delta", {}).get("draw", 0.0)) * 100.0,
                        "delta_away": float(entry.get("delta", {}).get("away", 0.0)) * 100.0,
                    }
                )
    alt_df = df.copy()
    for column in ("alt_home", "alt_draw", "alt_away", "alt_delta_home", "alt_delta_draw", "alt_delta_away"):
        alt_df[column] = pd.to_numeric(alt_df.get(column), errors="coerce")
    alt_df = alt_df.dropna(subset=["alt_home", "alt_draw", "alt_away"])
    if ai_df.empty and not scenario_rows and alt_df.empty:
        return
    st.markdown("---")
    st.subheader("Trace IA & sc\u00e9narios")
    if not ai_df.empty:
        ai_df["ai_generated_at"] = _to_paris(ai_df.get("ai_generated_at"))
        ai_df["ai_generated_at"].fillna(ai_df.get("timestamp"), inplace=True)
        ai_df.sort_values("ai_generated_at", inplace=True)
        recent_ai = ai_df.tail(5).copy()
        recent_ai["Analyse"] = recent_ai["ai_analysis"].fillna("").astype(str).str.slice(0, 240)
        if hasattr(recent_ai["ai_generated_at"], "dt"):
            recent_ai["Date"] = recent_ai["ai_generated_at"].dt.strftime("%d/%m %H:%M")
        else:
            recent_ai["Date"] = recent_ai["ai_generated_at"]
        st.caption("Analyses IA r\u00e9centes")
        st.dataframe(
            recent_ai[["Date", "home_team", "away_team", "Analyse"]],
            hide_index=True,
            use_container_width=True,
        )
    if scenario_rows:
        scenario_df = pd.DataFrame(scenario_rows)
        scenario_df["generated"] = _to_paris(scenario_df.get("generated"))
        scenario_df.sort_values("generated", inplace=True)
        if hasattr(scenario_df["generated"], "dt"):
            scenario_df["generated"] = scenario_df["generated"].dt.strftime("%d/%m %H:%M")
        st.caption("Sc\u00e9narios simul\u00e9s (variations en points)")
        st.dataframe(
            scenario_df.tail(6).rename(
                columns={
                    "generated": "Date",
                    "match": "Match",
                    "scenario": "Sc\u00e9nario",
                    "delta_home": "Δ Home",
                    "delta_draw": "Δ Nul",
                    "delta_away": "Δ Away",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )
    if not alt_df.empty:
        alt_df["alt_generated_at"] = _to_paris(alt_df.get("alt_generated_at"))
        alt_df["gap_home"] = (alt_df["alt_home"] - alt_df["prob_home"]) * 100.0
        alt_df["gap_draw"] = (alt_df["alt_draw"] - alt_df["prob_draw"]) * 100.0
        alt_df["gap_away"] = (alt_df["alt_away"] - alt_df["prob_away"]) * 100.0
        avg_gap = (
            alt_df[["gap_home", "gap_draw", "gap_away"]].abs().mean().mean()
            if not alt_df[["gap_home", "gap_draw", "gap_away"]].empty
            else 0.0
        )
        st.caption("Comparaison moteur local vs mod\u00e8le principal")
        st.metric("Écart moyen", f"{avg_gap:.1f} pts")
        alt_view = alt_df.sort_values("alt_generated_at").tail(5).copy()
        if hasattr(alt_view["alt_generated_at"], "dt"):
            alt_view["Date"] = alt_view["alt_generated_at"].dt.strftime("%d/%m %H:%M")
        else:
            alt_view["Date"] = alt_view["alt_generated_at"]
        st.dataframe(
            alt_view[
                [
                    "Date",
                    "home_team",
                    "away_team",
                    "gap_home",
                    "gap_draw",
                    "gap_away",
                ]
            ].rename(
                columns={
                    "home_team": "Domicile",
                    "away_team": "Ext\u00e9rieur",
                    "gap_home": "Δ Home",
                    "gap_draw": "Δ Nul",
                    "gap_away": "Δ Away",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )


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
    val = (value or "").strip().lower()
    if val in {"home", "domicile"}:
        return "home"
    if val in {"away", "exterieur"}:
        return "away"
    if val in {"draw", "nul"}:
        return "draw"
    return ""


def _selection_success(
    selection: str,
    winner: str,
    home_goals: Optional[int],
    away_goals: Optional[int],
    home_name: Optional[str],
    away_name: Optional[str],
) -> Optional[bool]:
    if not selection:
        return None
    sel = selection.lower()
    winner_norm = _normalize_winner(winner)
    total_goals = None
    if home_goals is not None and away_goals is not None:
        total_goals = home_goals + away_goals

    over_under = re.search(r"(over|under)\s*([0-9]+(?:[.,][0-9])?)", sel)
    if over_under and total_goals is not None:
        threshold = float(over_under.group(2).replace(",", "."))
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

    if "btts" in sel or "deux equipes marquent" in sel:
        if home_goals is None or away_goals is None:
            return None
        both_score = home_goals > 0 and away_goals > 0
        if "non" in sel or "pas" in sel:
            return not both_score
        return both_score

    home_token = (home_name or "").lower()
    away_token = (away_name or "").lower()
    if any(keyword in sel for keyword in ("draw no bet", "rembourse si nul")) and winner_norm:
        if home_token and home_token in sel:
            if winner_norm == "draw":
                return True
            return winner_norm == "home"
        if away_token and away_token in sel:
            if winner_norm == "draw":
                return True
            return winner_norm == "away"

    if "match nul" in sel or sel.strip() in {"nul", "draw"}:
        return winner_norm == "draw" if winner_norm else None

    if home_token and home_token in sel:
        return winner_norm == "home" if winner_norm else None
    if away_token and away_token in sel:
        return winner_norm == "away" if winner_norm else None

    if "home" in sel or "domicile" in sel:
        return winner_norm == "home" if winner_norm else None
    if "away" in sel or "exterieur" in sel:
        return winner_norm == "away" if winner_norm else None

    if "draw" in sel or "nul" in sel:
        return winner_norm == "draw" if winner_norm else None

    return None


def _first_valid_selection(*candidates: Any) -> str:
    for value in candidates:
        if value is None:
            continue
        if isinstance(value, float):
            if math.isnan(value):
                continue
            text = str(value).strip()
        else:
            text = str(value).strip()
        lowered = text.lower()
        if not text or lowered == "nan":
            continue
        return text
    return ""


def _compute_success(row: pd.Series) -> Optional[bool]:
    result = str(row.get("result_winner", ""))
    selection = _first_valid_selection(
        row.get("bet_selection"),
        row.get("total_pick"),
        row.get("main_pick"),
    )
    home_goals, away_goals = _parse_score(row)
    selection_result = _selection_success(
        selection,
        result,
        home_goals,
        away_goals,
        row.get("home_team"),
        row.get("away_team"),
    )
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

__all__ = ["show_prediction_performance"]
