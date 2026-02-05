#!/usr/bin/env python3
"""
Génère un résumé Social/Content Engine et le publie (optionnel) vers Slack/Discord/Supabase.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from utils.content_engine import (
    broadcast_content,
    generate_content_payload,
    log_report_metadata,
    save_report_markdown,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Générer et publier un rapport Social Engine.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Chemin Markdown cible (par défaut docs/reports/rapport-<timestamp>.md).",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Diffuse le résumé via Slack/Discord et alimente la queue Supabase.",
    )
    args = parser.parse_args()

    payload = generate_content_payload()
    path = save_report_markdown(payload, filename=args.output.name if args.output else None)
    log_report_metadata(payload, path)
    print(f"Rapport sauvegardé : {path}")
    if args.publish:
        broadcast_content(payload)
        print("Publication envoyée (Slack/Discord + queue Supabase).")


if __name__ == "__main__":
    main()
