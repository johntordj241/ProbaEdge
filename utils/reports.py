from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

REPORT_INDEX_PATH = Path("data/reports_index.json")
REPORTS_DIR = Path("docs/reports")


def _load_local_index() -> List[Dict[str, Any]]:
    if not REPORT_INDEX_PATH.exists():
        return []
    try:
        payload = json.loads(REPORT_INDEX_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]
    return []


def _discover_reports_dir() -> List[Dict[str, Any]]:
    if not REPORTS_DIR.exists():
        return []
    entries: List[Dict[str, Any]] = []
    for path in sorted(REPORTS_DIR.glob("*"), reverse=True):
        if path.suffix.lower() not in {".md", ".pdf"}:
            continue
        stat = path.stat()
        entries.append(
            {
                "title": path.stem.replace("-", " ").title(),
                "summary": "Rapport local généré automatiquement.",
                "date": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d"),
                "author": "Auto",
                "tags": [],
                "pdf_path": str(path),
            }
        )
    return entries


def _format_date(raw: str | None) -> str:
    if not raw:
        return "-"
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return raw


def _load_supabase_reports(limit: int = 20) -> List[Dict[str, Any]]:
    try:
        from .supabase_client import get_supabase_client
    except Exception:
        return []
    try:
        client = get_supabase_client()
    except Exception:
        return []
    try:
        response = (
            client.table("reports")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception:
        return []
    data = response.data or []
    entries: List[Dict[str, Any]] = []
    for row in data:
        entries.append(
            {
                "title": row.get("title") or "Rapport",
                "summary": row.get("summary") or "",
                "date": (row.get("created_at") or "")[:10],
                "author": row.get("author") or row.get("created_by") or "-",
                "tags": row.get("tags") or [],
                "pdf_path": row.get("pdf_path"),
                "status": row.get("status"),
                "channel": row.get("channel"),
            }
        )
    return entries


def _load_reports() -> List[Dict[str, Any]]:
    supabase_reports = _load_supabase_reports()
    if supabase_reports:
        return supabase_reports
    local_index = _load_local_index()
    if local_index:
        return local_index
    return _discover_reports_dir()


def _render_pdf_controls(entry: Dict[str, Any]) -> None:
    pdf_path = entry.get("pdf_path")
    if not pdf_path:
        st.info("Aucun fichier associé.")
        return
    if isinstance(pdf_path, str) and pdf_path.startswith(("http://", "https://")):
        st.link_button("Ouvrir le PDF", pdf_path, help="Lien externe")
        return
    path = Path(pdf_path)
    if path.exists():
        with path.open("rb") as handle:
            st.download_button(
                label=f"Télécharger {path.name}",
                data=handle.read(),
                file_name=path.name,
                mime="application/pdf" if path.suffix.lower() == ".pdf" else "text/plain",
                key=f"download_{path.name}",
            )
    else:
        st.warning(f"Fichier introuvable : {path}")


def show_reports() -> None:
    st.title("Centre de rapports")
    st.caption("Consultez les audits precedents et telechargez les PDF associes.")

    reports = _load_reports()
    if not reports:
        st.info("Aucun rapport reference pour le moment.")
        return

    for entry in reports:
        title = entry.get("title", "Rapport")
        st.subheader(title)
        meta_cols = st.columns(4)
        meta_cols[0].metric("Date", _format_date(entry.get("date")))
        meta_cols[1].metric("Auteur", entry.get("author", "-"))
        meta_cols[2].metric("Tags", ", ".join(entry.get("tags", [])) or "-")
        meta_cols[3].metric("Statut", entry.get("status", "n/a"))
        summary = entry.get("summary") or "Pas de resume disponible."
        st.write(summary)

        _render_pdf_controls(entry)
        st.markdown("---")


__all__ = ["show_reports"]
