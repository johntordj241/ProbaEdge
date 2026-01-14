# 📋 AUDIT COMPLET DU PROJET - Proba Edge

**Date**: 14 janvier 2026  
**Scope**: Architecture, Code Quality, Sécurité, Performance, Dépendances  
**Version Analysée**: Current state

---

## 1️⃣ ARCHITECTURE GÉNÉRALE

### ✅ Points forts

- **Séparation claire** : Frontend Streamlit (`app.py`) + Modules utilitaires dans `utils/`
- **Modularité** : Chaque feature a son propre module (players.py, standings.py, predictions.py, etc.)
- **Caching intelligent** : Système de cache multi-niveaux (fichier + mémoire + fallback offline)
- **Retry et fallback** : Gestion des erreurs API avec retry exponential + fallback sur cache
- **Supervision** : Logging de toutes les appels API (supervision.py)

### ⚠️ Problèmes identifiés

| Problème | Sévérité | Impact | Recommandation |
|----------|----------|--------|-----------------|
| **Dépendances dans `requirements.txt` mal versionnées** | 🔴 HAUTE | Risques de compatibilité | Ajouter des versions spécifiques (`streamlit==1.27.2` au lieu de `streamlit`) |
| **Pas de `setup.py` ou `pyproject.toml`** | 🟠 MOYENNE | Difficile à déployer/packager | Créer `pyproject.toml` avec structure modern Python |
| **Trop de fichiers temporaires à la racine** | 🟡 BASSE | Clutter, confusion | Créer dossier `/tmp` ou `/debug` pour fichiers de test |
| **No `__init__.py` clair au niveau root** | 🟡 BASSE | Imports potentiellement fragiles | Vérifier que `sys.path.insert()` en haut du `app.py` est nécessaire |
| **Modules Word documents dans `utils/`** | 🟡 BASSE | Pollution du code | Déplacer vers `/docs` |

---

## 2️⃣ SÉCURITÉ

### ✅ Points forts

- **Authentification par hash PBKDF2** : Hash sécurisé avec salt (120k iterations)
- **Gestion de secrets** : Utilisation de `secrets.py` + variables d'environnement
- **Pas de secrets en dur** : `.env` dans `.gitignore`
- **Contrôle d'accès par plan** : Vérification des droits via `plan_allows()`

### 🔴 PROBLÈMES DE SÉCURITÉ CRITIQUES

#### 1. **Stockage des credentials en local (data/users.json)**
```
❌ RISQUE: Si le repo est publié, les hashs de mots de passe sont accessibles
```
**Recommandation** : 
- [ ] Utiliser Supabase Auth ou Firebase Authentication au lieu du fichier JSON local
- [ ] Si vraiment local, ajouter chiffrement AES sur `users.json`
- [ ] Audit du `.gitignore` : vérifier que `data/users.json` n'est PAS committé

#### 2. **Hardcoded emails de test visibles (LOCAL_SETUP.md)**
```
❌ RISQUE: Emails et détails des comptes tests sont documentés publiquement
```
**Recommandation** :
- [ ] Ne pas inclure de credentials de test dans la documentation publique
- [ ] Utiliser `REDACTED` ou des placeholders

#### 3. **Bearer Token X/Twitter en clair** (engagement.py)
```python
# ❌ Bearer token passé directement
headers={"Authorization": f"Bearer {self.bearer_token}"}
```
**Recommandation** :
- [ ] Chiffrer en transit (HTTPS ✅)
- [ ] Rotation régulière des tokens
- [ ] Audit de rotation de secrets

#### 4. **Pas de HTTPS validé dans les appels API**
```python
# ⚠️  requests.get() sans verify=True explicite
response = requests.get(url, headers=headers, params=params, timeout=20)
```
**Recommandation** :
- [ ] Ajouter `verify=True` explicite (c'est le défaut mais clarifier)
- [ ] SSL pinning pour API crítica (api-sports.io)

#### 5. **Injection SQL potentielle** (sync_active_squad.py)
```python
# ❌ Query builder rudimentaire - risque d'injection
psycopg2.connect(DB_DSN)  # Si DB_DSN est mal formée
```
**Recommandation** :
- [ ] Utiliser ORM (SQLAlchemy) ou queries paramétrées
- [ ] Valider le DSN

---

## 3️⃣ GESTION DES ERREURS

### ⚠️ Problèmes identifiés

| Issue | Fichier | Exemple | Fix |
|-------|---------|---------|-----|
| **Generic `except Exception`** | `api_calls.py:191` | `except Exception as exc:` | Catcher exceptions spécifiques |
| **Bare `except`** | Plusieurs | `except: pass` | Toujours spécifier l'exception type |
| **Pas de logging centralisé** | Partout | `print()` au lieu de logging | Utiliser `logging` module + Sentry |
| **st.stop() sans contexte** | `app.py:73,229` | `st.stop()` | Ajouter message d'erreur + redirect |
| **Errors swallowed silently** | `api_calls.py:330,514` | `except Exception: return []` | Logger l'erreur avant de retourner |

### 🔧 Recommandations

```python
# ✅ BON PATTERN
import logging
logger = logging.getLogger(__name__)

try:
    result = fetch_data()
except TimeoutError as e:
    logger.warning(f"API timeout: {e}")
    return cached_fallback()
except ConnectionError as e:
    logger.error(f"Network error: {e}", exc_info=True)
    return None
except Exception as e:
    logger.critical(f"Unexpected error: {e}", exc_info=True)
    raise
```

---

## 4️⃣ PERFORMANCE & CACHING

### ✅ Points forts

- **TTL bien configuré** : Standings (600s), Players (600s), Fixtures (120s)
- **Cache à plusieurs niveaux** : Fichier JSON + mémoire
- **Offline mode** : Fallback sur cache en cas d'erreur réseau
- **Supervision** : Tracking de tous les appels API

### ⚠️ Optimisations possibles

| Problème | Impact | Fix |
|----------|--------|-----|
| **N+1 queries** sur `get_players_enriched()` | 🔴 HAUTE | Fusionner API calls, paginer |
| **Pas de streaming** pour gros DataFrames | 🟠 MOYENNE | Utiliser `st.dataframe(use_container_width=True)` |
| **Cache naïf** (pas de LRU/expiration) | 🟡 BASSE | Ajouter `@lru_cache(maxsize=128)` |
| **st.cache_resource trop large** | 🟡 BASSE | Limiter scope de `_init_sync()` |

### Métriques actuelles
```
- Appels API : ~20-30 par session selon navigation
- TTL moyens : 5-10 minutes
- Taille cache : ?  (à mesurer)
- Temps chargement page : ? (à mesurer avec st.write(st.session_state))
```

---

## 5️⃣ QUALITÉ DU CODE

### 🔍 Type hints & Linting

| Aspect | Status | Action |
|--------|--------|--------|
| **Type hints** | ⚠️ PARTIEL | Beaucoup de files manquent (models.py, handlers...) |
| **Docstrings** | ⚠️ PEU | Peu de docstrings, beaucoup de code self-documenting |
| **Imports** | ✅ PROPRE | Bien organisés, pas de imports circulaires détectés |
| **Code duplication** | 🟠 MOYENNE | Plusieurs `_dataframe()` répétées (players_ui, topscorers, topassists) |
| **Magic strings** | 🟠 MOYENNE | Beaucoup de strings hardcoded (ex: "all", "domicile", "exterieur") |

### 🔧 Corrections à apporter

```python
# ❌ AVANT: Pas de type hints, pas de docstring
def show_players(league_id, season, team_id):
    players = get_players_enriched(league_id, season, team_id)
    df = _players_dataframe(players)
    st.dataframe(df)

# ✅ APRÈS: Avec types et docstring
def show_players(
    league_id: int,
    season: int,
    team_id: int,
) -> None:
    """
    Affiche la liste complète des joueurs filtrée par équipe.
    
    Args:
        league_id: ID de la ligue
        season: Année de la saison
        team_id: ID de l'équipe
    """
    players = get_players_enriched(league_id, season, team_id)
    df = _players_dataframe(players)
    st.dataframe(df, use_container_width=True)
```

---

## 6️⃣ DÉPENDANCES

### 📦 Versions actuelles (requirements.txt)

```
streamlit==1.27.2           ✅ Épinglée (bonne)
requests                    ❌ PAS épinglée
pandas                      ❌ PAS épinglée
scikit-learn                ❌ PAS épinglée
matplotlib                  ❌ PAS épinglée
numpy                       ❌ PAS épinglée
pytest                      ❌ PAS épinglée (test seulement)
pyyaml                      ❌ PAS épinglée
pyarrow                     ❌ PAS épinglée
openai                      ❌ PAS épinglée
altair                      ❌ PAS épinglée
supabase                    ❌ PAS épinglée
python-dotenv               ❌ PAS épinglée
```

### 🔴 RISQUES IDENTIFIÉS

- **Breaking changes** : Une maj de `scikit-learn` ou `pandas` pourrait casser le code
- **Security vulns** : Pas de pinning = pas de contrôle des CVE
- **Compatibility** : Versions différentes sur dev/prod

### 🔧 Correction - Générer un `requirements.lock`

```bash
pip freeze > requirements.lock
# Renommer et ajouter:
# -r requirements-dev.txt (pour pytest, sphinx, etc)
```

---

## 7️⃣ TESTS

### 📊 État actuel

| Category | Files | Status |
|----------|-------|--------|
| **Unit tests** | 9 files | ⚠️ Peu d'assertions |
| **Coverage** | ? | ❌ Aucun rapport généré |
| **E2E tests** | ❌ Aucun | Streamlit difficile à tester |
| **Integration** | ⚠️ Partiel | Tests de cache + auth OK |

### Tests importants manquants

```python
# ❌ PAS DE TEST POUR:
- get_players_enriched() avec déduplication
- show_standings() avec filtrage domicile/extérieur
- render_widget() avec fallback si API key manquante
- Cache expiration TTL
- Offline mode avec données périmées
```

### 🔧 Ajouter coverage

```bash
pip install pytest-cov
pytest --cov=utils --cov-report=html
```

---

## 8️⃣ DOCUMENTATION

### ✅ Points forts

- README.md, QUICK_START.md, LOCAL_SETUP.md
- CHANGEMENTS.md bien détaillé
- Docstrings inline dans les modules critiques

### ⚠️ Lacunes

| Doc | Status | Action |
|-----|--------|--------|
| **API endpoints** | ⚠️ | Créer `docs/API.md` |
| **Architecture diagrams** | ❌ | Ajouter diagramme de flux |
| **Database schema** | ✅ | `schema.sql` existe |
| **Deployment guide** | ⚠️ | Peu de détails pour prod |
| **Runbook** | ❌ | Créer pour incidents |

---

## 9️⃣ MONITORING & OBSERVABILITÉ

### Système existant

- ✅ `supervision.py` : Logging des appels API
- ✅ `reports` table : Tracking des rapports
- ⚠️ `st.session_state` : Pas d'export de metrics

### Manques

```
❌ Aucun alerting (ex: si API quota atteint)
❌ Aucun dashboard de monitoring
❌ Aucun traçage distribué (traces)
❌ Aucun health check
```

### 🔧 Recommandé

- [ ] Ajouter Sentry pour error tracking
- [ ] Prometheus pour metrics
- [ ] Datadog ou équivalent pour APM
- [ ] Health check endpoint (`/health`)

---

## 🔟 PROBLÈMES DÉTECTÉS - RÉSUMÉ EXÉCUTIF

### 🔴 CRITIQUES (Fix immédiatement)

1. **Déduplication joueurs** ✅ FIXÉ (correction appliquée)
2. **Widget classement figé** ✅ FIXÉ (correction appliquée)
3. **Stockage credentials en JSON** ⚠️ À migrer vers Supabase Auth
4. **Versions dépendances non épinglées** ⚠️ Générer `requirements.lock`
5. **Pas de test de déploiement** ⚠️ Ajouter CI/CD pipeline

### 🟠 IMPORTANTS (Fix bientôt)

6. Generic `except Exception` → spécifier exception types
7. N+1 queries dans certains endpoints
8. Pas de centralized logging
9. Dépendances de dev mélangées aux dépendances de prod
10. Pas de rate limiting sur les endpoints Streamlit

### 🟡 MINEURS (Nice to have)

11. Magic strings → créer `constants.py` dédié
12. Code duplication (`_dataframe()`) → extraire en fonction commune
13. Peu de docstrings → ajouter progressivement
14. Pas de type hints complets → améliorer progressivement

---

## ✅ RECOMMANDATIONS PRIORITAIRES

### Sprint 1 (URGENT)

- [ ] Générer `requirements.lock` avec `pip freeze`
- [ ] Migrer `data/users.json` vers Supabase Auth
- [ ] Ajouter setup CI/CD GitHub Actions
- [ ] Remplacer `except Exception` par exceptions spécifiques

### Sprint 2 (IMPORTANT)

- [ ] Ajouter Sentry pour error tracking
- [ ] Créer test coverage report
- [ ] Documenter API endpoints
- [ ] Ajouter health check endpoint

### Sprint 3 (POLISH)

- [ ] Centraliser logging avec `logging` module
- [ ] Extraire constantes magic strings
- [ ] Améliorer docstrings
- [ ] Ajouter type hints complets

---

## 📊 SCORECARD FINAL

| Domaine | Score | Trend |
|---------|-------|-------|
| **Architecture** | 7/10 | ↗️ |
| **Sécurité** | 5/10 | ⚠️  |
| **Performance** | 8/10 | ↗️ |
| **Code Quality** | 6/10 | ➡️  |
| **Testing** | 4/10 | ⬇️  |
| **Documentation** | 7/10 | ↗️ |
| **DevOps/Deployment** | 3/10 | ⬇️  |
| **Monitoring** | 3/10 | ⬇️  |
| **GLOBAL** | **5.4/10** | **⚠️  À AMÉLIORER** |

---

## 📝 NOTES

- Audit effectué sur codebase au 14 jan 2026
- Basé sur analyse statique du code + configuration
- Pas de pentest ou audit de sécurité approfondi
- Recommandations basées sur best practices Python/Streamlit

**Prochain audit recommandé**: 3 mois après implémentation des correctifs prioritaires

---

**FIN DE L'AUDIT**
