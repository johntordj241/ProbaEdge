from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

import hashlib

from .secrets import get_secret
from .subscription import DEFAULT_PLAN, normalize_plan, BETA_PLAN_CODE

USERS_PATH = Path("data/users.json")
BETA_CODES_ENV = "BETA_ACCESS_CODES"
BETA_EMAILS_ENV = "BETA_TESTER_EMAILS"
BETA_DOMAINS_ENV = "BETA_TESTER_DOMAINS"


def _ensure_store() -> None:
    USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not USERS_PATH.exists():
        USERS_PATH.write_text(json.dumps({"users": []}, indent=2), encoding="utf-8")


def _load_store() -> Dict[str, list]:
    _ensure_store()
    try:
        data = json.loads(USERS_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Invalid users.json shape")
        data.setdefault("users", [])
        return data
    except Exception:
        return {"users": []}


def _save_store(store: Dict[str, list]) -> None:
    USERS_PATH.write_text(json.dumps(store, indent=2), encoding="utf-8")


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    )
    return salt, hashed.hex()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_user_entry(entry: Dict[str, str]) -> Dict[str, str]:
    normalized = dict(entry)
    normalized["plan"] = normalize_plan(normalized.get("plan"))
    return normalized


def _env_list(name: str) -> set[str]:
    raw = get_secret(name) or ""
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _is_beta_email(email: str) -> bool:
    email_norm = _normalize_email(email)
    if not email_norm or "@" not in email_norm:
        return False
    if email_norm in _env_list(BETA_EMAILS_ENV):
        return True
    domain = email_norm.split("@", 1)[1]
    return domain in _env_list(BETA_DOMAINS_ENV)


def _has_beta_code(access_code: Optional[str]) -> bool:
    if not access_code:
        return False
    candidate = access_code.strip().lower()
    if not candidate:
        return False
    return candidate in _env_list(BETA_CODES_ENV)


def _initial_plan(email: str, access_code: Optional[str]) -> str:
    if _has_beta_code(access_code) or _is_beta_email(email):
        return BETA_PLAN_CODE
    return DEFAULT_PLAN


def list_users() -> list[Dict[str, str]]:
    store = _load_store()
    users = []
    for entry in store.get("users", []):
        users.append(_normalize_user_entry(entry))
    return users


def find_user(email: str) -> Optional[Dict[str, str]]:
    needle = _normalize_email(email)
    for user in list_users():
        if user.get("email") == needle:
            return user
    return None


def create_user(
    email: str,
    password: str,
    full_name: str,
    access_code: Optional[str] = None,
) -> Dict[str, str]:
    email_norm = _normalize_email(email)
    if not email_norm or "@" not in email_norm:
        raise ValueError("Adresse email invalide.")
    if len(password) < 6:
        raise ValueError("Le mot de passe doit contenir au moins 6 caracteres.")
    if find_user(email_norm):
        raise ValueError("Un compte existe deja avec cette adresse.")
    salt, hashed = _hash_password(password)
    store = _load_store()
    entry = {
        "email": email_norm,
        "password": hashed,
        "salt": salt,
        "name": full_name.strip() or email_norm.split("@")[0],
        "created_at": _now_iso(),
        "plan": _initial_plan(email_norm, access_code),
    }
    store.setdefault("users", []).append(entry)
    _save_store(store)
    return _normalize_user_entry(entry)


def authenticate_user(email: str, password: str) -> Optional[Dict[str, str]]:
    user = find_user(email)
    if not user:
        return None
    salt = user.get("salt") or ""
    _, hashed = _hash_password(password, salt=salt)
    if hashed != user.get("password"):
        return None
    return _normalize_user_entry(user)


def change_password(email: str, old_password: str, new_password: str) -> bool:
    if len(new_password) < 6:
        raise ValueError("Le nouveau mot de passe doit contenir au moins 6 caracteres.")
    store = _load_store()
    email_norm = _normalize_email(email)
    for user in store.get("users", []):
        if user.get("email") != email_norm:
            continue
        salt = user.get("salt") or ""
        _, hashed = _hash_password(old_password, salt=salt)
        if hashed != user.get("password"):
            return False
        new_salt, new_hash = _hash_password(new_password)
        user["salt"] = new_salt
        user["password"] = new_hash
        user["updated_at"] = _now_iso()
        _save_store(store)
        return True
    return False


def set_user_plan(email: str, new_plan: str) -> bool:
    plan_code = normalize_plan(new_plan)
    store = _load_store()
    email_norm = _normalize_email(email)
    updated = False
    for user in store.get("users", []):
        if user.get("email") != email_norm:
            continue
        user["plan"] = plan_code
        user["plan_updated_at"] = _now_iso()
        updated = True
        break
    if updated:
        _save_store(store)
    return updated


__all__ = [
    "create_user",
    "authenticate_user",
    "find_user",
    "list_users",
    "change_password",
    "set_user_plan",
]
