from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from .cache import cache_stats
from .supervision import (
    endpoint_summary,
    health_snapshot,
    purge_cache_via_supervision,
    recent_calls,
    quota_status,
)


def _overall_metrics() -> tuple[float, float]:
    rows = endpoint_summary()
    if not rows:
        return 0.0, 0.0
    total_calls = sum(row["Appels"] for row in rows)
    total_success = sum(row["Appels"] * (row["Succes %"] / 100.0) for row in rows)
    avg_success = (total_success / total_calls * 100.0) if total_calls else 0.0
    avg_duration = sum(row["Duree moy (ms)"] for row in rows) / len(rows)
    return round(avg_success, 1), round(avg_duration, 1)


def show_supervision_dashboard() -> None:
    st.title("Supervision API & Cache")

    quota = quota_status()
    cache_info = cache_stats()
    success_rate, avg_duration = _overall_metrics()

    col_quota, col_success, col_duration = st.columns(3)
    remaining = quota.get("remaining")
    limit = quota.get("limit")
    quota_label = f"{remaining}/{limit}" if remaining is not None and limit else "-"
    col_quota.metric("Quota restant", quota_label)
    col_success.metric("Succes moyenne", f"{success_rate:.1f}%")
    col_duration.metric("Duree moyenne (ms)", f"{avg_duration:.1f}")

    snapshot = health_snapshot()
    alert_cols = st.columns(2)
    if snapshot.get("offline"):
        reason = snapshot.get("offline_reason") or "inconnu"
        alert_cols[0].error(f"Mode hors ligne ({reason}) : lecture cache uniquement.", icon="⚠️")
    elif snapshot.get("low_quota"):
        alert_cols[0].warning("Quota API faible, surveillez les appels.", icon="⚠️")
    failures = snapshot.get("recent_failures", 0)
    if failures:
        alert_cols[1].warning(f"{failures} erreurs récentes détectées.", icon="❗")

    st.subheader("Cache API")
    cache_cols = st.columns(3)
    cache_cols[0].metric("Entrées", cache_info.get("entries", 0))
    cache_cols[1].metric("Taille (KB)", cache_info.get("size_kb", 0.0))
    cache_cols[2].metric("Hits / Misses", f"{cache_info.get('hits', 0)} / {cache_info.get('misses', 0)}")
    purge_col1, purge_col2 = st.columns([1, 3])
    if purge_col1.button("Purger le cache maintenant", use_container_width=True):
        purged = purge_cache_via_supervision()
        st.success(f"{purged} fichiers supprimés.")
        st.experimental_rerun()
    else:
        last_purge = cache_info.get("last_purge")
        if last_purge:
            readable = pd.to_datetime(last_purge, unit="s").strftime("%d/%m %H:%M")
            purge_col2.caption(f"Dernière purge : {readable}")

    st.subheader("Statistiques par endpoint")
    endpoint_rows = endpoint_summary()
    if endpoint_rows:
        st.dataframe(pd.DataFrame(endpoint_rows), use_container_width=True, hide_index=True)
    else:
        st.info("Aucun appel enregistré pour le moment.")

    st.subheader("Journal des appels")
    endpoints = ["Tous"] + sorted({row["Endpoint"] for row in endpoint_rows})
    selected_endpoint = st.selectbox("Filtrer par endpoint", endpoints, index=0)
    endpoint_filter: Optional[str] = None if selected_endpoint == "Tous" else selected_endpoint
    calls = recent_calls(limit=120, endpoint=endpoint_filter)
    if calls:
        st.dataframe(pd.DataFrame(calls), use_container_width=True, hide_index=True)
    else:
        st.info("Pas d'appels correspondants aux filtres.")
