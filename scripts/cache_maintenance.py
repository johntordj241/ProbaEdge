#!/usr/bin/env python3
""" maintenance du cache API : purge planifiée + statistiques d'usage. """

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.cache import (  # noqa: E402
    cache_stats,
    cache_usage_summary,
    maybe_purge_cache,
    purge_cache,
)


def _format_seconds(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    seconds = max(0, int(value))
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{seconds:02d}s"
    return f"{seconds}s"


def run(force: bool = False) -> Dict[str, Any]:
    purged = purge_cache(force=True) if force else maybe_purge_cache()
    stats = cache_stats()
    usage = cache_usage_summary(limit=10)
    return {
        "purged_files": purged,
        "stats": stats,
        "top_endpoints": usage,
    }


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Maintenance du cache API (purge planifiée).")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Forcer la purge intégrale sans tenir compte de la durée de vie.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Afficher le résultat au format JSON brut.",
    )
    args = parser.parse_args(argv)

    payload = run(force=args.force)
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
        return

    stats = payload["stats"]
    print(f"Fichiers purgés : {payload['purged_files']}")
    print(
        f"Cache : {stats.get('entries', 0)} fichiers, "
        f"{stats.get('size_kb', 0.0)} KB, "
        f"hit% = {stats.get('hit_ratio', 0.0)}"
    )
    last_purge = stats.get("last_purge")
    if last_purge:
        readable = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_purge))
        print(f"Dernière purge : {readable}")
    next_eta = stats.get("next_purge_in")
    print(f"Prochaine purge auto dans ~{_format_seconds(next_eta)}")

    top_usage = payload["top_endpoints"]
    if top_usage:
        print("Endpoints principaux :")
        for row in top_usage:
            print(
                f"  - {row['endpoint']}: {row['hits']} hits / "
                f"{row['misses']} misses (hit% {row['hit_ratio']})"
            )


if __name__ == "__main__":
    main()

