#!/usr/bin/env python3
"""CLI pour mettre a jour data/roadmap.yaml."""
import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

ROOT = Path(__file__).resolve().parents[1]
ROADMAP_PATH = ROOT / "data" / "roadmap.yaml"


def load_sections() -> List[Dict[str, Any]]:
    if not ROADMAP_PATH.exists():
        return []
    try:
        payload = yaml.safe_load(ROADMAP_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"Impossible de charger {ROADMAP_PATH}: {exc}")
    sections = payload.get("sections") if isinstance(payload, dict) else payload
    if not isinstance(sections, list):
        return []
    cleaned: List[Dict[str, Any]] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        tasks = section.get("tasks") if isinstance(section.get("tasks"), list) else []
        cleaned.append(
            {
                "title": section.get("title", "Section"),
                "description": section.get("description", ""),
                "tasks": [
                    {
                        "name": task.get("name", "Tache"),
                        "remaining": float(task.get("remaining", 0.0)),
                        "details": task.get("details", ""),
                    }
                    for task in tasks
                    if isinstance(task, dict)
                ],
            }
        )
    return cleaned


def save_sections(sections: List[Dict[str, Any]]) -> None:
    data = {"sections": sections}
    ROADMAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    ROADMAP_PATH.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def update_task(section_title: str, task_name: str, remaining: float | None, details: str | None) -> None:
    sections = load_sections()
    if not sections:
        raise SystemExit("Aucune section trouvee dans roadmap.yaml")
    matched = False
    for section in sections:
        if section.get("title") != section_title:
            continue
        for task in section.get("tasks", []):
            if task.get("name") == task_name:
                if remaining is not None:
                    task["remaining"] = float(remaining)
                if details is not None:
                    task["details"] = details
                matched = True
                break
        if matched:
            break
    if not matched:
        raise SystemExit(f"Tache '{task_name}' introuvable dans la section '{section_title}'.")
    save_sections(sections)
    print(f"Mise a jour: {section_title} / {task_name}")


def list_tasks() -> None:
    sections = load_sections()
    if not sections:
        print("Aucune section disponible.")
        return
    for section in sections:
        print(f"# {section['title']}")
        for task in section.get("tasks", []):
            remaining = task.get("remaining", 0)
            details = task.get("details", "")
            print(f"- {task['name']} (reste {remaining}%)\n    {details}")


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mise a jour de data/roadmap.yaml")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="Lister les taches disponibles")
    list_parser.set_defaults(func=lambda args: list_tasks())

    update_parser = subparsers.add_parser("update", help="Mettre a jour une tache")
    update_parser.add_argument("section", help="Titre de la section (exact)")
    update_parser.add_argument("task", help="Nom de la tache (exact)")
    update_parser.add_argument("--remaining", type=float, help="Pourcentage restant (0-100)")
    update_parser.add_argument("--details", help="Nouvelle description")
    update_parser.set_defaults(func=lambda args: update_task(args.section, args.task, args.remaining, args.details))

    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> None:
    args = parse_args(argv or sys.argv[1:])
    args.func(args)


if __name__ == "__main__":
    main()

