#!/usr/bin/env python3
"""Génère une vue Markdown de la roadmap à partir de data/roadmap.yaml."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import yaml

ROOT = Path(__file__).resolve().parents[1]
ROADMAP_PATH = ROOT / "data" / "roadmap.yaml"
OUTPUT_PATH = ROOT / "docs" / "roadmap.md"


def load_sections() -> List[Dict[str, Any]]:
    if not ROADMAP_PATH.exists():
        raise SystemExit("data/roadmap.yaml introuvable")
    payload = yaml.safe_load(ROADMAP_PATH.read_text(encoding="utf-8"))
    sections = payload.get("sections") if isinstance(payload, dict) else payload
    if not isinstance(sections, list):
        raise SystemExit("Format inattendu dans la roadmap.")
    cleaned: List[Dict[str, Any]] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        tasks = [
            task
            for task in section.get("tasks", [])
            if isinstance(task, dict)
        ]
        cleaned.append(
            {
                "title": section.get("title", "Section"),
                "description": section.get("description", ""),
                "tasks": tasks,
            }
        )
    return cleaned


def render_markdown(sections: List[Dict[str, Any]]) -> str:
    lines = [
        "# Roadmap - export automatique",
        "",
        f"_Genere le {datetime.now():%d/%m/%Y %H:%M}_",
        "",
    ]
    for section in sections:
        lines.append(f"## {section['title']}")
        if section.get("description"):
            lines.append(section["description"])
            lines.append("")
        for task in section.get("tasks", []):
            remaining = task.get("remaining", 0)
            details = task.get("details", "")
            lines.append(f"- **{task.get('name', 'Tache')}** - reste {remaining}%")
            if details:
                lines.append(f"  - {details}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Markdown de la roadmap.")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH, help="Fichier cible (docs/roadmap.md par défaut)")
    args = parser.parse_args()

    sections = load_sections()
    markdown = render_markdown(sections)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")
    print(f"Roadmap exportée vers {args.output}")


if __name__ == "__main__":
    main()
