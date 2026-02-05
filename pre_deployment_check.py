"""
Script de déploiement pour Proba Edge sur production.
À exécuter depuis CI/CD ou manuellement avant push en production.
"""

import subprocess
import sys
from pathlib import Path


def run_checks() -> bool:
    """Exécute tous les checks avant deployment."""
    root = Path(__file__).parent
    sys.path.insert(0, str(root))

    print("\n" + "=" * 70)
    print("🚀 PRE-DEPLOYMENT CHECKS")
    print("=" * 70)

    checks_passed = 0
    checks_total = 0

    # CHECK 1: Tests
    print("\n[1] 🧪 Exécuter tests...")
    checks_total += 1
    try:
        result = subprocess.run(
            ["pytest", "tests/", "-v", "--tb=short"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            print("    ✅ Tests passés")
            checks_passed += 1
        else:
            print("    ❌ Tests échoués")
            print(result.stdout)
    except Exception as e:
        print(f"    ⚠️  Erreur: {e}")

    # CHECK 2: Type hints
    print("\n[2] 🏷️  Vérifier type hints avec mypy...")
    checks_total += 1
    try:
        result = subprocess.run(
            ["mypy", "utils/", "app.py", "--ignore-missing-imports"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            print("    ✅ Type hints OK")
            checks_passed += 1
        else:
            print("    ⚠️  Type hints issues (non-bloquant)")
    except Exception as e:
        print(f"    ⚠️  mypy non installé: {e}")

    # CHECK 3: Code quality (pylint)
    print("\n[3] 📊 Vérifier qualité code...")
    checks_total += 1
    try:
        result = subprocess.run(
            [
                "pylint",
                "utils/api_calls.py",
                "utils/auth.py",
                "--disable=all",
                "--enable=E",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if "error" not in result.stdout.lower():
            print("    ✅ Code quality OK")
            checks_passed += 1
        else:
            print("    ⚠️  Code quality issues (non-bloquant)")
    except Exception as e:
        print(f"    ⚠️  pylint non installé: {e}")

    # CHECK 4: Secrets en dur
    print("\n[4] 🔐 Chercher secrets en dur...")
    checks_total += 1
    try:
        result = subprocess.run(
            [
                "grep",
                "-r",
                "--include=*.py",
                r"(password|key|token|secret)\s*=\s*['\"]",
                "utils/",
                "app.py",
            ],
            cwd=root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:  # 1 = pas d'occurrences trouvées
            print("    ✅ Pas de secrets en dur détectés")
            checks_passed += 1
        else:
            print("    ⚠️  Secrets potentiels détectés:")
            print(result.stdout)
    except Exception as e:
        print(f"    ⚠️  Erreur: {e}")

    # CHECK 5: Requirements.lock exists
    print("\n[5] 📦 Vérifier requirements.lock...")
    checks_total += 1
    req_lock = root / "requirements.lock"
    if req_lock.exists():
        print("    ✅ requirements.lock existe")
        checks_passed += 1
    else:
        print("    ❌ requirements.lock manquant!")

    # RÉSUMÉ
    print("\n" + "=" * 70)
    print(f"RÉSUMÉ: {checks_passed}/{checks_total} checks passés")
    print("=" * 70 + "\n")

    return checks_passed == checks_total


if __name__ == "__main__":
    success = run_checks()
    sys.exit(0 if success else 1)
