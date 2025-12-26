from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import unicodedata

import numpy as np
import pandas as pd
import streamlit as st
from zoneinfo import ZoneInfo

from .auth import list_users, set_user_plan
from .cache import (
    auto_resume_remaining,
    cache_stats,
    is_offline_mode,
    purge_cache,
    render_cache_controls,
    set_offline_mode,
)
from .prediction_history import (
    PREDICTION_DATASET_PATH,
    PREDICTION_HISTORY_PATH,
    load_prediction_history,
    normalize_prediction_history,
    training_progress,
)
from .content_engine import (
    broadcast_content,
    generate_content_payload,
    log_report_metadata,
    save_report_markdown,
)
from .subscription import DEFAULT_PLAN, PLAN_CODES, plan_label, normalize_plan
from .supervision import endpoint_summary, health_snapshot, recent_calls, quota_status


def _format_timestamp(ts: Optional[float]) -> str:
    if ts in {None, ""}:
        return "-"
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError, OSError):
        return "-"


def _format_timespan(seconds: Optional[float]) -> str:
    if not seconds or seconds <= 0:
        return "-"
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    if minutes:
        return f"{minutes} min {remaining_seconds:02d}s"
    return f"{remaining_seconds}s"


def _csv_overview(path: Path) -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "name": path.name,
        "exists": path.exists(),
        "rows": 0,
        "columns": 0,
        "updated_at": None,
        "sample": None,
        "error": None,
    }
    if not info["exists"]:
        return info

    try:
        stat = path.stat()
        info["updated_at"] = stat.st_mtime
    except OSError:
        info["updated_at"] = None

    try:
        with path.open("r", encoding="utf-8") as handle:
            # subtract the header line if present
            total_lines = sum(1 for _ in handle)
        info["rows"] = max(total_lines - 1, 0)
    except OSError:
        info["rows"] = 0

    try:
        sample_df = pd.read_csv(path, nrows=5)
        info["columns"] = len(sample_df.columns)
        info["sample"] = sample_df
    except Exception as exc:  # pragma: no cover - display purpose only
        info["error"] = str(exc)
    return info


def _render_dataset_section(title: str, path: Path) -> None:
    st.markdown(f"**{title}**")
    overview = _csv_overview(path)
    if not overview["exists"]:
        st.info(f"Fichier `{overview['name']}` introuvable.")
        return

    cols = st.columns(3)
    cols[0].metric("Lignes", f"{overview['rows']:,}")
    cols[1].metric("Colonnes", overview["columns"])
    cols[2].metric("Derniere mise a jour", _format_timestamp(overview["updated_at"]))

    if overview["sample"] is not None and not overview["sample"].empty:
        with st.expander("Apercu (5 premieres lignes)"):
            st.dataframe(overview["sample"], use_container_width=True)
    if overview["error"]:
        st.warning(f"Lecture partielle : {overview['error']}")


def _render_offline_form() -> None:
    offline_now = is_offline_mode()
    snapshot = health_snapshot()
    current_reason = snapshot.get("offline_reason") or ""
    auto_resume = auto_resume_remaining()

    with st.form("admin_offline_form"):
        enable = st.checkbox("Activer le mode hors ligne", value=offline_now)
        reason = st.text_input("Raison (facultatif)", value=current_reason)
        resume_minutes = st.number_input(
            "Reprise automatique (minutes)",
            min_value=0,
            max_value=1440,
            value=0 if not auto_resume else max(1, int(auto_resume // 60)),
            help="Permet de planifier la reprise automatique des appels API.",
        )
        submitted = st.form_submit_button("Mettre a jour")

    if submitted:
        if enable:
            resume_in = resume_minutes * 60 if resume_minutes > 0 else None
            set_offline_mode(True, reason=reason.strip() or "admin", resume_in=resume_in)
        else:
            set_offline_mode(False)
        st.success("Parametres hors ligne mis a jour.")
        st.experimental_rerun()


def _normalize_text(value: Any) -> str:
    base = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = "".join(ch for ch in base if ord(ch) < 128)
    return " ".join(ascii_text.lower().split())


def _has_excluded_keyword(text: str) -> bool:
    if not text:
        return False
    keywords = {
        "double chance",
        "over",
        "under",
        "buts",
        "handicap",
        "btts",
        "buteur",
        "score exact",
        "carton",
        "corners",
        "total",
    }
    return any(keyword in text for keyword in keywords)


def _prediction_side(row: pd.Series) -> Optional[str]:
    home = _normalize_text(row.get("home_team"))
    away = _normalize_text(row.get("away_team"))
    candidates = [
        _normalize_text(row.get("main_pick")),
        _normalize_text(row.get("bet_selection")),
    ]
    for text in candidates:
        if not text:
            continue
        if _has_excluded_keyword(text):
            continue
        if home and home in text:
            return "home"
        if away and away in text:
            return "away"
        if "match nul" in text or "nul" in text or "draw" in text or text.strip() == "x":
            return "draw"
        if "victoire domicile" in text or "gagne domicile" in text:
            return "home"
        if "victoire exterieur" in text or "gagne exterieur" in text:
            return "away"
    return None


def _compute_success_flag(row: pd.Series) -> Optional[bool]:
    result = _normalize_text(row.get("result_winner"))
    if not result:
        return None
    side = _prediction_side(row)
    if not side:
        return None
    if any(token in result for token in {"home", "domicile", "1"}):
        return side == "home"
    if any(token in result for token in {"away", "exterieur", "2"}):
        return side == "away"
    if any(token in result for token in {"draw", "nul", "x"}):
        return side == "draw"
    return None


def _load_prediction_dataframe() -> pd.DataFrame:
    try:
        df = load_prediction_history()
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df.get("timestamp"), errors="coerce", utc=True)
    df["fixture_date"] = pd.to_datetime(df.get("fixture_date"), errors="coerce", utc=True)
    df["timeline"] = pd.to_datetime(
        df.get("fixture_date").fillna(df.get("timestamp")), errors="coerce", utc=True
    )

    for column in ("bet_stake", "bet_odd", "bet_return", "main_confidence", "league_id", "season"):
        df[column] = pd.to_numeric(df.get(column), errors="coerce")

    df["success_flag"] = df.apply(_compute_success_flag, axis=1)
    df["bet_return_computed"] = np.where(
        df["success_flag"] == True,
        df["bet_stake"] * df["bet_odd"],
        np.where(df["success_flag"] == False, 0.0, np.nan),
    )
    df["bet_return_final"] = df["bet_return"].where(df["bet_return"].notna(), df["bet_return_computed"])
    return df


def _format_datetime(value: Optional[pd.Timestamp]) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "-"
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return "-"
        dt = value.to_pydatetime()
        paris = ZoneInfo("Europe/Paris")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(paris)
        else:
            dt = dt.astimezone(paris)
        return dt.strftime("%d/%m/%Y %H:%M")
    return "-"


def _prediction_summary(df: pd.DataFrame) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "data": df,
        "total": int(len(df)),
        "completed": 0,
        "pending": int(len(df)),
        "win_rate": None,
        "win_rate_delta": None,
        "roi": None,
        "stake_volume": 0.0,
        "avg_stake": None,
        "avg_confidence": None,
        "added_last_7d": 0,
        "last_update": None,
        "daily_success": pd.DataFrame(),
        "pending_table": pd.DataFrame(),
        "recent_table": pd.DataFrame(),
        "status_counts": pd.DataFrame(),
        "league_counts": pd.DataFrame(),
    }
    if df.empty:
        return summary

    success_mask = df["success_flag"].isin({True, False})
    completed = df.loc[success_mask]
    summary["completed"] = int(len(completed))
    summary["pending"] = int(summary["total"] - summary["completed"])

    if not completed.empty:
        win_rate = float(completed["success_flag"].mean() * 100)
        summary["win_rate"] = round(win_rate, 1)
        recent_window = pd.Timestamp.utcnow() - pd.Timedelta(days=30)
        recent_completed = completed.loc[
            completed["timeline"].notna() & (completed["timeline"] >= recent_window)
        ]
        if not recent_completed.empty:
            recent_rate = float(recent_completed["success_flag"].mean() * 100)
            summary["win_rate_delta"] = round(recent_rate - win_rate, 1)

    bet_mask = (
        df["bet_return_final"].notna()
        & df["bet_stake"].notna()
        & (df["bet_stake"] > 0)
    )
    if bet_mask.any():
        total_staked = float(df.loc[bet_mask, "bet_stake"].sum())
        profit = float((df.loc[bet_mask, "bet_return_final"] - df.loc[bet_mask, "bet_stake"]).sum())
        summary["stake_volume"] = total_staked
        summary["avg_stake"] = round(float(df.loc[bet_mask, "bet_stake"].mean()), 2)
        if total_staked > 0:
            summary["roi"] = round((profit / total_staked) * 100, 1)

    if df["main_confidence"].notna().any():
        summary["avg_confidence"] = round(float(df["main_confidence"].dropna().mean()), 1)

    now = pd.Timestamp.utcnow()
    timeline = df["timeline"]
    recent_mask = timeline.notna() & (timeline >= now - pd.Timedelta(days=7))
    summary["added_last_7d"] = int(recent_mask.sum())

    if timeline.notna().any():
        summary["last_update"] = timeline.max()

    daily = completed.dropna(subset=["timeline"]).copy()
    if not daily.empty:
        timeline_series = daily["timeline"]
        if timeline_series.dt.tz is None:
            timeline_series = timeline_series.dt.tz_localize("UTC")
        else:
            timeline_series = timeline_series.dt.tz_convert("Europe/Paris")
        daily["Date"] = timeline_series.dt.date
        success_by_day = daily.groupby("Date")["success_flag"].mean().reset_index()
        success_by_day["Taux de reussite %"] = success_by_day["success_flag"] * 100
        success_by_day.drop(columns=["success_flag"], inplace=True)
        summary["daily_success"] = success_by_day.tail(60)

    pending = df.loc[~success_mask].copy()
    if not pending.empty:
        pending = pending.sort_values("timeline", ascending=True)
        pending_table = pending[
            ["timeline", "home_team", "away_team", "main_pick", "main_confidence", "status_snapshot"]
        ].head(20)
        pending_table["Date"] = pending_table["timeline"].apply(_format_datetime)
        pending_table.drop(columns=["timeline"], inplace=True)
        pending_table.rename(
            columns={
                "home_team": "Equipe domicile",
                "away_team": "Equipe exterieur",
                "main_pick": "Selection",
                "main_confidence": "Confiance",
                "status_snapshot": "Statut",
            },
            inplace=True,
        )
        summary["pending_table"] = pending_table

    recent = df.sort_values("timeline", ascending=False).head(30)
    if not recent.empty:
        recent_table = recent[
            [
                "timeline",
                "home_team",
                "away_team",
                "main_pick",
                "result_winner",
                "success_flag",
                "bet_stake",
                "bet_odd",
                "bet_return_final",
            ]
        ].copy()
        recent_table["Date"] = recent_table["timeline"].apply(_format_datetime)
        recent_table.drop(columns=["timeline"], inplace=True)
        recent_table.rename(
            columns={
                "home_team": "Equipe domicile",
                "away_team": "Equipe exterieur",
                "main_pick": "Selection",
                "result_winner": "Issue officielle",
                "success_flag": "Succes?",
                "bet_stake": "Mise",
                "bet_odd": "Cote",
                "bet_return_final": "Retour",
            },
            inplace=True,
        )
        summary["recent_table"] = recent_table

    status_counts = (
        df.get("status_snapshot")
        .fillna("INCONNU")
        .astype(str)
        .str.upper()
        .value_counts()
        .reset_index()
        .rename(columns={"index": "Statut", "status_snapshot": "Predictions"})
    )
    summary["status_counts"] = status_counts

    league_counts = (
        df.get("league_id")
        .dropna()
        .astype(int)
        .astype(str)
        .value_counts()
        .reset_index()
        .rename(columns={"index": "Competition", "league_id": "Predictions"})
    )
    summary["league_counts"] = league_counts.head(10)

    return summary


def _render_prediction_kpis() -> None:
    df = _load_prediction_dataframe()
    if df.empty:
        st.info("Aucune prediction historisee pour le moment.")
        return

    summary = _prediction_summary(df)
    col_total, col_completed, col_pending, col_recent = st.columns(4)
    col_total.metric("Predictions totales", f"{summary['total']}")
    col_completed.metric("Matches finalises", f"{summary['completed']}")
    col_pending.metric("En attente", f"{summary['pending']}")
    col_recent.metric("Nouvelles (7 jours)", f"{summary['added_last_7d']}")

    col_win, col_roi, col_stake, col_conf = st.columns(4)
    delta = summary["win_rate_delta"]
    delta_label = None if delta is None else f"{delta:+.1f} pts (vs 30j)"
    win_value = "-" if summary["win_rate"] is None else f"{summary['win_rate']:.1f}%"
    col_win.metric("Taux de reussite", win_value, delta=delta_label)
    roi_value = "-" if summary["roi"] is None else f"{summary['roi']:.1f}%"
    col_roi.metric("ROI realise", roi_value)
    stake_value = "-" if not summary["stake_volume"] else f"{summary['stake_volume']:.2f} EUR"
    col_stake.metric("Volume mise", stake_value)
    confidence_value = "-" if summary["avg_confidence"] is None else f"{summary['avg_confidence']:.1f}"
    col_conf.metric("Confiance moyenne", confidence_value)

    if summary["last_update"]:
        st.caption(f"Derniere prediction importee : {_format_datetime(summary['last_update'])}")

    daily = summary["daily_success"]
    if not daily.empty:
        chart_df = daily.set_index("Date")["Taux de reussite %"]
        st.subheader("Evolution du taux de reussite (dernieres semaines)")
        st.line_chart(chart_df)

    st.markdown("---")
    st.subheader("Matches en attente de resultat")
    if not summary["pending_table"].empty:
        st.dataframe(summary["pending_table"], hide_index=True, use_container_width=True)
    else:
        st.info("Aucun match en attente dans l'historique.")

    st.subheader("Dernieres predictions enregistrees")
    if not summary["recent_table"].empty:
        st.dataframe(summary["recent_table"], hide_index=True, use_container_width=True)
    else:
        st.info("Historique recent vide.")

    st.markdown("---")
    col_status, col_league = st.columns(2)
    if not summary["status_counts"].empty:
        col_status.subheader("Repartition par statut API")
        col_status.dataframe(summary["status_counts"], hide_index=True, use_container_width=True)
    else:
        col_status.info("Pas de statut disponible.")

    if not summary["league_counts"].empty:
        col_league.subheader("Top competitions suivies")
        col_league.dataframe(summary["league_counts"], hide_index=True, use_container_width=True)
    else:
        col_league.info("Aucune competition renseignee.")


def show_admin() -> None:
    st.title("Administration")
    st.caption(
        "Vue d'ensemble pour la supervision, la maintenance et la preparation des donnees."
    )

    snapshot = health_snapshot()
    quota = quota_status()
    cache_info = cache_stats()
    training = training_progress()

    col_status, col_quota, col_cache, col_training = st.columns(4)
    col_status.metric("Mode hors ligne", "Oui" if snapshot.get("offline") else "Non")
    remaining = quota.get("remaining")
    limit = quota.get("limit")
    quota_label = "-"
    if remaining is not None and limit:
        quota_label = f"{remaining}/{limit}"
    elif remaining is not None:
        quota_label = str(remaining)
    col_quota.metric("Quota API", quota_label)
    col_cache.metric("Cache (fichiers)", cache_info.get("entries", 0))
    col_training.metric(
        "Fixtures prêtes",
        f"{training.get('ready', 0)} / {training.get('target', 0)}",
    )

    alert_placeholder = st.container()
    if snapshot.get("offline"):
        reason = snapshot.get("offline_reason") or "raison non specifiee"
        alert_placeholder.warning(
            f"Mode hors ligne actif ({reason}). Les donnees proviennent du cache.",
            icon="⚠️",
        )
    elif snapshot.get("recent_failures"):
        failures = snapshot["recent_failures"]
        alert_placeholder.warning(
            f"{failures} erreurs reseau detectees sur les derniers appels API.",
            icon="⚠️",
        )
    elif snapshot.get("low_quota"):
        alert_placeholder.info(
            "Quota API faible : limiter les rafraichissements manuels.",
            icon="ℹ️",
        )

    kpi_tab, maintenance_tab, data_tab, logs_tab, users_tab = st.tabs(
        ["KPI Predictions", "Maintenance", "Jeu de donnees", "Logs API", "Utilisateurs"]
    )

    with kpi_tab:
        _render_prediction_kpis()

    with maintenance_tab:
        st.subheader("Cache & connectivite")
        render_cache_controls(st, key_prefix="admin_")
        _render_offline_form()

        st.markdown("---")
        st.subheader("Actions rapides")
        action_cols = st.columns(3)

        if action_cols[0].button("Purger le cache API (force)", key="admin_purge_force"):
            purged = purge_cache(force=True)
            st.success(f"{purged} fichiers supprimes du cache.")
            st.experimental_rerun()

        if action_cols[1].button("Normaliser l'historique des predictions", key="admin_normalize"):
            normalized = normalize_prediction_history()
            st.success(f"{normalized} lignes normalisees.")

        auto_resume = auto_resume_remaining()
        action_cols[2].metric(
            "Reprise auto planifiee",
            _format_timespan(auto_resume),
        )

    with data_tab:
        st.subheader("Fichiers principaux")
        _render_dataset_section("Historique des predictions", PREDICTION_HISTORY_PATH)
        _render_dataset_section("Dataset d'apprentissage", PREDICTION_DATASET_PATH)

        st.markdown("---")
        st.subheader("Social / Content Engine")
        content_placeholder = st.empty()
        content_payload = None
        if st.button("Générer un résumé automatique", key="content_generate"):
            with st.spinner("Agrégation des insights..."):
                content_payload = generate_content_payload()
            content_placeholder.success("Résumé généré. Vous pouvez le prévisualiser ou le publier.")
        if content_payload is None:
            content_payload = generate_content_payload()
        with st.expander("Prévisualisation du rapport", expanded=False):
            st.markdown(content_payload.render_markdown())
        col_save_md, col_publish = st.columns(2)
        if col_save_md.button("Enregistrer en Markdown", key="content_save_md"):
            path = save_report_markdown(content_payload)
            log_report_metadata(content_payload, path)
            st.success(f"Rapport sauvegardé sous {path}.")
        if col_publish.button("Publier (Slack/Discord + queue Social)", key="content_publish"):
            broadcast_content(content_payload)
            st.success("Résumé diffusé (Slack/Discord) et ajouté à la queue Supabase.")

    with logs_tab:
        st.subheader("Synthese par endpoint")
        endpoints = endpoint_summary()
        if endpoints:
            st.dataframe(pd.DataFrame(endpoints), use_container_width=True, hide_index=True)
        else:
            st.info("Aucun appel enregistre pour le moment.")

        st.subheader("Derniers appels (50)")
        calls = recent_calls(limit=50)
        if calls:
            st.dataframe(pd.DataFrame(calls), use_container_width=True, hide_index=True)
        else:
            st.info("Pas de logs disponibles.")

    with users_tab:
        st.subheader("Gestion des abonnements")
        users = list_users()
        if not users:
            st.info("Aucun utilisateur enregistre.")
        else:
            overview_rows = [
                {
                    "Nom": user.get("name", "-"),
                    "Email": user.get("email", "-"),
                    "Plan": plan_label(user.get("plan")),
                    "Cree le": user.get("created_at", "-").split("T")[0] if user.get("created_at") else "-",
                }
                for user in users
            ]
            st.dataframe(
                pd.DataFrame(overview_rows),
                use_container_width=True,
                hide_index=True,
            )
            st.caption("Les changements de plan s'appliquent immediatement (Stripe Ã\xa0 venir).")

            with st.form("plan_update_form"):
                emails = [user.get("email") for user in users]
                selections = {user.get("email"): f"{user.get('name','?')} ({plan_label(user.get('plan'))})" for user in users}
                selected_email = st.selectbox(
                    "Utilisateur",
                    options=emails,
                    format_func=lambda value: selections.get(value, value),
                )
                current_plan_code = normalize_plan(
                    next((u.get("plan") for u in users if u.get("email") == selected_email), DEFAULT_PLAN)
                )
                selected_plan = st.selectbox(
                    "Plan",
                    PLAN_CODES,
                    index=PLAN_CODES.index(current_plan_code),
                    format_func=plan_label,
                )
                if st.form_submit_button("Mettre Ã\xa0 jour le plan"):
                    if set_user_plan(selected_email, selected_plan):
                        current = st.session_state.get("auth_user")
                        if current and current.get("email") == selected_email:
                            current["plan"] = normalize_plan(selected_plan)
                        st.success("Plan mis Ã\xa0 jour.")
                        st.experimental_rerun()
                    else:
                        st.error("Impossible de mettre Ã\xa0 jour ce compte.")
