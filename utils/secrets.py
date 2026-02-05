from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency declared in requirements
    load_dotenv = None  # type: ignore[assignment]


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE_ENV = "FOOTBALL_APP_ENV_FILE"


def _existing_path(raw_path: str) -> Optional[Path]:
    path = Path(raw_path).expanduser()
    return path if path.exists() else None


def _candidate_env_files() -> list[Path]:
    """Return possible .env locations, in priority order."""
    candidates: list[Path] = []
    override = os.getenv(ENV_FILE_ENV)
    if override:
        explicit = _existing_path(override)
        if explicit:
            candidates.append(explicit)
    repo_env = PROJECT_ROOT / ".env"
    if repo_env.exists():
        candidates.append(repo_env)
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists() and cwd_env not in candidates:
        candidates.append(cwd_env)
    return candidates


@lru_cache(maxsize=1)
def ensure_env_loaded() -> bool:
    """
    Load the .env file exactly once (if python-dotenv is available).

    Returns True when a dotenv file has been processed, False otherwise.
    """
    if load_dotenv is None:
        return False
    candidates = _candidate_env_files()
    loaded = False
    for candidate in candidates:
        if load_dotenv(dotenv_path=candidate, override=False):
            loaded = True
    if not loaded:
        load_dotenv(override=False)
    return True


def get_secret(
    name: str,
    *,
    required: bool = False,
    default: Optional[str] = None,
    hint: Optional[str] = None,
) -> Optional[str]:
    """
    Fetch a secret from the environment after ensuring .env is loaded.
    """
    ensure_env_loaded()
    value = os.getenv(name)
    if value in {None, ""}:
        value = default
    if required and not value:
        message = hint or f"Variable d'environnement {name} manquante."
        raise RuntimeError(message)
    return value


__all__ = ["get_secret", "ensure_env_loaded", "ENV_FILE_ENV", "PROJECT_ROOT"]
