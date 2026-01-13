#!/usr/bin/env python3
"""
Script pour réparer les identifiants dans data/users.json
et hasher correctement le mot de passe.
"""

import hashlib
import secrets
import json
from pathlib import Path


def hash_password(password: str, salt: str = None) -> tuple:
    """Hash un mot de passe avec PBKDF2"""
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    )
    return salt, hashed.hex()


# Hasher le mot de passe du 2e compte
password_clair = "@Boygomez15111986"
salt, hashed = hash_password(password_clair)

print("=" * 60)
print("🔐 HASHAGE DU MOT DE PASSE")
print("=" * 60)
print(f"\n📝 Mot de passe clair: {password_clair}")
print(f"🔑 Salt généré: {salt}")
print(f"🔒 Hash: {hashed}")

# Corriger le JSON
users_path = Path("data/users.json")

corrected_data = {
    "users": [
        {
            "email": "john.tordjeman@gmail.com",
            "password": "21b79bd1bb94e63a83525f6ee178a45e859dbc2a4c854cbfbe611a5a8bc5a0b2",
            "salt": "b98d9a6071ec3256450407345c1d36c0",
            "name": "john tordjeman",
            "created_at": "2025-12-16T19:53:03.324882+00:00",
            "plan": "elite",
        },
        {
            "email": "g.johntordjeman@icloud.com",
            "password": hashed,
            "salt": salt,
            "name": "g.johntordjeman",
            "created_at": "2026-01-07T12:40:00+00:00",
            "plan": "beta",
        },
    ]
}

# Sauvegarder
users_path.write_text(json.dumps(corrected_data, indent=2), encoding="utf-8")

print(f"\n✅ Fichier data/users.json corrigé et sauvegardé!")
print(f"\n📋 Utilisateurs disponibles:")
print(f"  1. john.tordjeman@gmail.com (plan: elite)")
print(f"  2. g.johntordjeman@icloud.com (plan: beta)")

print("\n" + "=" * 60)
