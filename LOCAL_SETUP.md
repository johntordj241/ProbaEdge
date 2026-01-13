# 🚀 Guide de démarrage LOCAL

## ⚙️ Setup initial

### 1️⃣ Initialiser l'environnement

```bash
python init_local.py
```

Cela va:
- ✅ Corriger les identifiants dans `data/users.json`
- ✅ Vérifier les variables d'environnement
- ✅ Charger l'historique des prédictions
- ✅ Afficher les utilisateurs disponibles

### 2️⃣ Configurer les variables d'environnement

Créez un fichier `.env.local` à la racine du projet:

```env
API_FOOTBALL_KEY=votre_clé_api_football
OPENWEATHER_API_KEY=votre_clé_openweather
OPENAI_API_KEY=votre_clé_openai (optionnel)
SUPABASE_URL=votre_url_supabase (optionnel)
SUPABASE_SERVICE_KEY=votre_service_key (optionnel)
```

> **Note**: Le fichier `.env` est utilisé par défaut. Créez `.env.local` pour un environnement séparé.

### 3️⃣ Lancer l'application

```bash
streamlit run app.py
```

L'app s'ouvrira automatiquement sur `http://localhost:8501`

**👉 Se connecter avec:** `john.tordjeman@gmail.com` (ton compte principal)

---

## 🔑 Identifiants de test

### 👑 Compte Principal (Admin) - TON COMPTE
- **Email**: `john.tordjeman@gmail.com` ← **C'EST TON COMPTE PRINCIPAL**
- **Plan**: Elite
- **Mot de passe**: [Hash stocké - utilise le hash dans users.json]
- **Utilisation**: Dashboard complet, toutes les fonctionnalités

### 📱 Compte Secondaire (Beta)
- **Email**: `g.johntordjeman@icloud.com`
- **Plan**: Beta
- **Mot de passe**: `@Boygomez15111986`
- **Utilisation**: Test du plan beta

---

## ✅ Vérification avant de pusher sur GitHub

### Checklist

- [ ] Se connecter avec succès
- [ ] Voir l'historique des prédictions
- [ ] Cliquer sur "Performance IA" → voir la synchro des résultats
- [ ] Vérifier les changements récents:
  - ✅ Import `sync_prediction_results` dans `app.py`
  - ✅ TTL pour `players/squads` dans `api_calls.py`
- [ ] Pas d'erreurs dans la console

### Avant le push

```bash
# 1. Vérifier le statut
git status

# 2. Voir les changements
git diff

# 3. Ajouter les modifs
git add -A

# 4. Commit
git commit -m "fix: auto-sync prediction results + cache TTL for squads"

# 5. Push
git push origin main
```

---

## 🐛 Troubleshooting

### "Identifiants incorrects"
→ Lancer `python fix_users_json.py` pour corriger les utilisateurs

### "Pas d'API_FOOTBALL_KEY"
→ Créer `.env` avec votre clé API

### "Module not found"
→ S'assurer que le répertoire racine est dans le `sys.path`

### "Aucune prédiction"
→ Lancer `python scripts/backfill_predictions.py --league 61 --season 2025 --last 20`

---

## 📊 Tester la synchronisation

```bash
python test_sync_results.py
```

Montre:
- Nombre de matchs en attente
- Matchs mis à jour
- État avant/après synchronisation

---

## 🔄 Workflow local

```
1. Modifier le code
   ↓
2. Tester en local avec: streamlit run app.py
   ↓
3. Vérifier les changements: python test_sync_results.py
   ↓
4. Commit et push
```

---

**Questions?** Consulte le `README.md` principal ou lance `python init_local.py` 🚀
