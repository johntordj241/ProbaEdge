from __future__ import annotations

from functools import lru_cache

from .secrets import get_secret

API_FOOTBALL_KEY_ENV = "API_FOOTBALL_KEY"
API_FOOTBALL_BASE_URL_ENV = "API_FOOTBALL_BASE_URL"
DEFAULT_BASE_URL = "https://v3.football.api-sports.io"


def _missing_key_message() -> str:
    return (
        "Clé API Football manquante. "
        "Définissez API_FOOTBALL_KEY dans votre environnement (.env local ou secret Vault)."
    )


@lru_cache(maxsize=1)
def get_api_key() -> str:
    api_key = get_secret(API_FOOTBALL_KEY_ENV, required=True, hint=_missing_key_message())
    if not api_key:
        raise RuntimeError(_missing_key_message())
    return api_key


@lru_cache(maxsize=1)
def get_headers() -> dict[str, str]:
    return {"x-apisports-key": get_api_key()}


BASE_URL = get_secret(API_FOOTBALL_BASE_URL_ENV, default=DEFAULT_BASE_URL) or DEFAULT_BASE_URL


__all__ = ["BASE_URL", "get_api_key", "get_headers"]
