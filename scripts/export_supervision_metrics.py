#!/usr/bin/env python3
"""Export des métriques de supervision API dans un fichier JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from utils.supervision import endpoint_summary, quota_status
from utils.cache import cache_stats


def export_metrics(output: Path) -> None:
    summary = {
        "quota": quota_status(),
        "cache": cache_stats(),
        "endpoints": endpoint_summary(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Métriques supervision exportées vers {output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export JSON des métriques de supervision API.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs") / "supervision_metrics.json",
        help="Fichier de sortie (par défaut docs/supervision_metrics.json)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    export_metrics(args.output)


if __name__ == "__main__":
    main()

