#!/usr/bin/env python3
"""Affiche un état synthétique du mode hors ligne et des quotas."""

from __future__ import annotations

from utils.cache import cache_stats, is_offline_mode, offline_reason, auto_resume_remaining
from utils.supervision import quota_status


def human_time(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    seconds = max(0, int(seconds))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{sec:02d}s"
    return f"{sec}s"


def main() -> None:
    offline = is_offline_mode()
    reason = offline_reason()
    resume = auto_resume_remaining()
    cache = cache_stats()
    quota = quota_status()

    print("=== Etat général ===")
    print(f"Mode hors ligne : {'OUI' if offline else 'NON'}")
    print(f"Raison        : {reason or '-'}")
    print(f"Reprise auto  : {human_time(resume)}")

    print("\n=== Cache ===")
    print(f"Entries       : {cache.get('entries')}")
    print(f"Hits / Misses : {cache.get('hits')} / {cache.get('misses')}")
    print(f"Taille (KB)   : {cache.get('size_kb')}")
    next_purge = cache.get("next_purge_in")
    if isinstance(next_purge, (int, float)):
        print(f"Purge auto    : {human_time(next_purge)}")

    print("\n=== Quota API ===")
    print(f"Limite        : {quota.get('limit')}")
    print(f"Restant       : {quota.get('remaining')}")
    print(f"Reset         : {quota.get('reset')}")


if __name__ == "__main__":
    main()

