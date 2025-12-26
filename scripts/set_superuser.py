"""
Utility script to guarantee that an administrator account exists with the
right password hash and subscription plan.

Usage:
    py -3.11 scripts/set_superuser.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.auth import _hash_password  # noqa: E402

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
EMAIL = "john.tordjeman@gmail.com"
PASSWORD = "@Boygomez15111986"
PLAN = "elite"
USERS_PATH = Path("data/users.json")


def main() -> None:
    if not USERS_PATH.exists():
        raise FileNotFoundError(f"Impossible de trouver {USERS_PATH}")

    data = json.loads(USERS_PATH.read_text(encoding="utf-8"))
    salt, hashed = _hash_password(PASSWORD)
    updated = False

    for user in data.get("users", []):
        if user.get("email") == EMAIL:
            user["salt"] = salt
            user["password"] = hashed
            user["plan"] = PLAN
            updated = True
            break

    if not updated:
        data.setdefault("users", []).append(
            {
                "email": EMAIL,
                "password": hashed,
                "salt": salt,
                "name": EMAIL.split("@")[0],
                "created_at": "2025-12-16T19:53:03.324882+00:00",
                "plan": PLAN,
            }
        )

    USERS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"{EMAIL} -> plan {PLAN} (hash régénéré)")


if __name__ == "__main__":
    main()
