#!/usr/bin/env python3
"""
Script de test LOCAL: crée un environnement de développement.
"""

import sys
from pathlib import Path

# Ajouter le répertoire du projet
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

print("=" * 70)
print("🚀 INITIALISATION DE L'ENVIRONNEMENT LOCAL")
print("=" * 70)

# 1. Corriger les utilisateurs
print("\n[1/4] 🔐 Correction des utilisateurs...")
import subprocess

result = subprocess.run(
    [sys.executable, "fix_users_json.py"], cwd=ROOT, capture_output=True, text=True
)
print(result.stdout)
if result.returncode != 0:
    print(f"❌ Erreur: {result.stderr}")
    sys.exit(1)

# 2. Vérifier les variables d'environnement
print("[2/4] 📋 Vérification des variables d'environnement...")
from utils.secrets import get_secret

required_vars = [
    "API_FOOTBALL_KEY",
    "OPENWEATHER_API_KEY",
]

missing = []
for var in required_vars:
    val = get_secret(var)
    if val:
        print(f"  ✅ {var}: défini")
    else:
        print(f"  ⚠️  {var}: NON défini")
        missing.append(var)

if missing:
    print(f"\n⚠️  Variables manquantes: {', '.join(missing)}")
    print("   → L'app fonctionnera partiellement")
else:
    print("  ✅ Toutes les variables requises sont définies")

# 3. Tester l'historique des prédictions
print("\n[3/4] 📊 Vérification de l'historique des prédictions...")
from utils.prediction_history import load_prediction_history, sync_prediction_results

df = load_prediction_history()
print(f"  📈 Historique chargé: {len(df)} lignes")

pending_count = ((df["result_status"].isna()) | (df["result_status"] == "")).sum()
print(f"  ⏳ Matchs en attente: {pending_count}")

# 4. Tester la connexion
print("\n[4/4] 🔑 Vérification des utilisateurs...")
from utils.auth import list_users

users = list_users()
print(f"  👥 Utilisateurs enregistrés: {len(users)}")
for user in users:
    print(f"    • {user.get('email')} ({user.get('plan')})")

print("\n" + "=" * 70)
print("✅ ENVIRONNEMENT PRÊT!")
print("=" * 70)

print("\n📝 Prochaines étapes:")
print("  1. Lancer l'app: streamlit run app.py")
print("  2. 👑 Se connecter avec (COMPTE PRINCIPAL): john.tordjeman@gmail.com")
print("     (ou g.johntordjeman@icloud.com pour le compte beta)")
print("\n🔗 L'app sera disponible sur: http://localhost:8501")
print("=" * 70 + "\n")
