from __future__ import annotations

from datetime import datetime
from statistics import mean
from typing import List, Dict, Any

import streamlit as st
import pandas as pd
import yaml
from pathlib import Path


RoadmapTask = Dict[str, Any]
RoadmapSection = Dict[str, Any]


ROADMAP_PATH = Path("data/roadmap.yaml")


def _load_sections() -> List[RoadmapSection]:
    if ROADMAP_PATH.exists():
        try:
            with ROADMAP_PATH.open("r", encoding="utf-8") as handle:
                payload = yaml.safe_load(handle)
            sections = payload.get("sections") if isinstance(payload, dict) else payload
            if isinstance(sections, list):
                cleaned: List[RoadmapSection] = []
                for section in sections:
                    if not isinstance(section, dict):
                        continue
                    raw_tasks = section.get("tasks", [])
                    tasks: List[RoadmapTask] = []
                    for task in raw_tasks if isinstance(raw_tasks, list) else []:
                        if not isinstance(task, dict):
                            continue
                        tasks.append(
                            {
                                "name": task.get("name", "Tache"),
                                "remaining": float(task.get("remaining", 0.0)),
                                "details": task.get("details", ""),
                            }
                        )
                    cleaned.append(
                        {
                            "title": section.get("title", "Section"),
                            "description": section.get("description", ""),
                            "tasks": tasks,
                        }
                    )
                if cleaned:
                    return cleaned
        except Exception:
            pass
    return [
        {
            "title": "Roadmap indisponible",
            "description": "Impossible de charger data/roadmap.yaml ; utiliser le fallback code.",
            "tasks": [
                {
                    "name": "Verifier le fichier roadmap",
                    "remaining": 100.0,
                    "details": "Assurez-vous que data/roadmap.yaml existe et est valide.",
                }
            ],
        }
    ]


ROADMAP_SECTIONS: List[RoadmapSection] = _load_sections()




def _flatten_tasks(sections: List[RoadmapSection]) -> List[RoadmapTask]:
    flattened: List[RoadmapTask] = []
    for section in sections:
        for task in section.get("tasks", []):
            flattened.append(
                {
                    "section": section.get("title"),
                    "name": task.get("name"),
                    "remaining": float(task.get("remaining", 0.0)),
                    "details": task.get("details"),
                }
            )
    return flattened


def _priority_label(remaining: float) -> str:
    if remaining >= 70.0:
        return "Critique"
    if remaining >= 40.0:
        return "A surveiller"
    return "En bonne voie"

def _average_remaining(tasks: List[RoadmapTask]) -> float:
    if not tasks:
        return 0.0
    return float(mean(task.get("remaining", 0.0) for task in tasks))


def _progress_from_remaining(remaining: float) -> float:
    remaining = max(0.0, min(100.0, float(remaining)))
    return 1.0 - remaining / 100.0


def show_roadmap() -> None:
    st.title("Roadmap du projet")
    st.write("Vue d'ensemble des chantiers et du travail restant.")

    section_remaining = [_average_remaining(section["tasks"]) for section in ROADMAP_SECTIONS]
    overall_remaining = float(mean(section_remaining)) if section_remaining else 0.0
    overall_progress = _progress_from_remaining(overall_remaining)

    st.progress(overall_progress)
    st.metric("Travail restant estime", f"{overall_remaining:.0f}%")
    st.caption(f"Mise a jour: {datetime.now().strftime('%d/%m/%Y')}")
    tasks_summary = _flatten_tasks(ROADMAP_SECTIONS)

    if tasks_summary:
        st.subheader("Priorites du jour")
        alert_threshold = st.slider("Seuil d'alerte (%)", 30, 90, 60, step=5)
        critical_tasks = [
            task for task in tasks_summary if task["remaining"] >= alert_threshold
        ]
        if critical_tasks:
            lines = "\n".join(
                f"- {task['section']} / {task['name']} ({task['remaining']:.0f}% restant)"
                for task in critical_tasks
            )
            st.error(f"Chantiers critiques (>= {alert_threshold}% restant):\n{lines}")
        else:
            st.success("Aucun chantier au-dessus du seuil d'alerte.")

        df = pd.DataFrame(tasks_summary)
        df["etat"] = df["remaining"].apply(_priority_label)
        df["% accompli"] = 100.0 - df["remaining"]
        display_df = (
            df[["section", "name", "etat", "remaining", "% accompli", "details"]]
            .rename(
                columns={
                    "section": "Section",
                    "name": "Tache",
                    "etat": "Etat",
                    "remaining": "% restant",
                    "details": "Details",
                }
            )
            .sort_values("% restant", ascending=False)
        )
        st.dataframe(display_df, hide_index=True, use_container_width=True)

        section_progress = display_df.groupby("Section")["% accompli"].mean().sort_values(ascending=False)
        st.caption("Progression moyenne par section")
        st.bar_chart(section_progress)


    for section in ROADMAP_SECTIONS:
        st.subheader(section["title"])
        st.caption(section["description"])

        section_remaining_value = _average_remaining(section["tasks"])
        section_cols = st.columns([4, 1])
        with section_cols[0]:
            st.progress(_progress_from_remaining(section_remaining_value))
        with section_cols[1]:
            st.metric("Reste", f"{section_remaining_value:.0f}%")

        for task in section["tasks"]:
            task_cols = st.columns([4, 1])
            with task_cols[0]:
                st.markdown(f"**{task['name']}**")
                st.caption(task["details"])
                st.progress(_progress_from_remaining(task.get("remaining", 0.0)))
            with task_cols[1]:
                st.metric("Reste", f"{task.get('remaining', 0.0):.0f}%")

        st.markdown("---")








