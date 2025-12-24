from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime, timezone
import csv

from .cache import is_offline_mode

FEEDBACK_PATH = Path("data/feedback.csv")
FEEDBACK_HEADER = ["timestamp", "name", "email", "message"]


def _ensure_feedback_file() -> None:
    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if FEEDBACK_PATH.exists():
        return
    with FEEDBACK_PATH.open("w", encoding="utf-8", newline="") as handle:
        csv.DictWriter(handle, fieldnames=FEEDBACK_HEADER).writeheader()


def append_feedback(name: str, email: str, message: str) -> None:
    if not message.strip():
        return
    if is_offline_mode():
        return
    _ensure_feedback_file()
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "name": name.strip(),
        "email": email.strip(),
        "message": message.strip(),
    }
    with FEEDBACK_PATH.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FEEDBACK_HEADER)
        writer.writerow(payload)


def load_feedback(limit: int = 10) -> List[Dict[str, Any]]:
    if not FEEDBACK_PATH.exists():
        return []
    try:
        rows: List[Dict[str, Any]] = []
        with FEEDBACK_PATH.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                rows.append(row)
        return rows[-limit:]
    except Exception:
        return []


__all__ = ["append_feedback", "load_feedback", "FEEDBACK_PATH"]
