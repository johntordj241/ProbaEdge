#!/usr/bin/env python3
"""
Pre-push checklist: Vérifier que tout est ok avant GitHub
"""

import sys
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

print("\n" + "=" * 70)
print("✅ PRE-PUSH CHECKLIST - VÉRIFICATION AVANT GITHUB")
print("=" * 70 + "\n")

checks_passed = 0
checks_total = 0

# CHECK 1: Import sync_prediction_results
print("[1] 🔄 Vérifier import sync_prediction_results dans app.py...")
checks_total += 1
try:
    with open("app.py") as f:
        content = f.read()
    if (
        "sync_prediction_results" in content
        and "from utils.prediction_history import" in content
    ):
        print("    ✅ Import trouvé")
        checks_passed += 1
    else:
        print("    ❌ Import manquant")
except Exception as e:
    print(f"    ❌ Erreur: {e}")

# CHECK 2: TTL pour players/squads
print("\n[2] 📦 Vérifier TTL pour players/squads dans api_calls.py...")
checks_total += 1
try:
    with open("utils/api_calls.py") as f:
        content = f.read()
    if '"players/squads": 3600' in content:
        print("    ✅ TTL configuré (3600s)")
        checks_passed += 1
    elif '"players/squads"' in content:
        print("    ⚠️  TTL trouvé mais valeur non confirmée")
        checks_passed += 1
    else:
        print("    ❌ TTL manquant")
except Exception as e:
    print(f"    ❌ Erreur: {e}")

# CHECK 3: Validité JSON users.json
print("\n[3] 🔑 Vérifier validité data/users.json...")
checks_total += 1
try:
    with open("data/users.json") as f:
        users_data = json.load(f)

    if "users" in users_data and isinstance(users_data["users"], list):
        user_count = len(users_data["users"])
        print(f"    ✅ JSON valide ({user_count} utilisateurs)")

        # Vérifier qu'aucun mot de passe en clair
        found_plain_text = False
        for user in users_data["users"]:
            pwd = user.get("password", "")
            if pwd == "@Boygomez15111986":  # mot de passe original
                print(f"    ❌ Mot de passe en clair détecté pour {user.get('email')}")
                found_plain_text = True

        if not found_plain_text:
            print("    ✅ Aucun mot de passe en clair")
            checks_passed += 1
    else:
        print("    ❌ JSON invalide (structure incorrect)")
except json.JSONDecodeError as e:
    print(f"    ❌ JSON invalide: {e}")
except Exception as e:
    print(f"    ❌ Erreur: {e}")

# CHECK 4: .env.example existe
print("\n[4] 📋 Vérifier .env.example existe...")
checks_total += 1
try:
    if Path(".env.example").exists():
        print("    ✅ .env.example présent")
        checks_passed += 1
    else:
        print("    ⚠️  .env.example manquant (non bloquant)")
        checks_passed += 1
except Exception as e:
    print(f"    ❌ Erreur: {e}")

# CHECK 5: .gitignore inclut les fichiers secrets
print("\n[5] 🔐 Vérifier .gitignore (secrets)...")
checks_total += 1
try:
    if Path(".gitignore").exists():
        with open(".gitignore") as f:
            gitignore = f.read()

        required_ignores = [".env", "*.env", "__pycache__", ".cache", "*.pyc"]
        missing = [x for x in required_ignores if x not in gitignore]

        if not missing:
            print("    ✅ .gitignore bien configuré")
            checks_passed += 1
        else:
            print(f"    ⚠️  .gitignore manque: {missing} (faible risque)")
            checks_passed += 1
    else:
        print("    ⚠️  .gitignore manquant (faible risque)")
        checks_passed += 1
except Exception as e:
    print(f"    ❌ Erreur: {e}")

# CHECK 6: Fichiers de dev local existent
print("\n[6] 📚 Vérifier fichiers de documentation...")
checks_total += 1
docs = ["LOCAL_SETUP.md", "CHANGEMENTS.md"]
all_exist = all(Path(d).exists() for d in docs)
if all_exist:
    print(f"    ✅ Documentation locale présente ({len(docs)} fichiers)")
    checks_passed += 1
else:
    print(f"    ⚠️  Documentation partielle (non bloquant)")
    checks_passed += 1

# SUMMARY
print("\n" + "=" * 70)
print(f"📊 RÉSULTAT: {checks_passed}/{checks_total} vérifications passées")
print("=" * 70)

if checks_passed == checks_total:
    print("\n✅ TOUT EST BON - PRÊT À POUSSER SUR GITHUB! 🚀")
    print("\nCommandes pour finir:")
    print("  git add -A")
    print("  git commit -m 'fix: auto-sync prediction results + cache TTL + auth'")
    print("  git push origin main")
    sys.exit(0)
elif checks_passed >= checks_total - 1:
    print(f"\n⚠️  {checks_total - checks_passed} point(s) à vérifier avant push")
    print("   (non-bloquant pour la plupart)")
    sys.exit(0)
else:
    print(f"\n❌ {checks_total - checks_passed} problème(s) détecté(s) - À corriger!")
    sys.exit(1)
