# Rapport d'audit Proba Edge - 15/11/2025

## Resume executif
- L'application Streamlit couvre 21 pages actives, reliees aux modules utilitaires sous `utils/`.
- Le moteur multi-couches (Poisson + Dixon-Coles + Markov + calibration ML) alimente les pages Predictions, Dashboard et IA.
- La supervision (cache, quotas, mode hors ligne) est operationnelle via `utils/cache.py` et `utils/supervision.py`.
- Aucun Social Engine n'est code pour l'instant : pas de connecteurs reseaux sociaux ni d'automatisations Make/Supabase.

## Modules existants
### Moteur probabiliste
- `utils/prediction_model.py` orchestre Poisson, Markov, calibration scikit-learn et resume editorial.
- `models/ratings.py`, `models/goal_models.py`, `models/markov.py` stockent Elo, matrices Dixon-Coles et Markov live.

### Historique & datasets
- `utils/prediction_history.py` gere le CSV `data/prediction_history.csv` et l'export dataset ML.
- `scripts/backfill_predictions.py` et `scripts/train_prediction_model.py` assurent collecte et entrainement.

### Supervision & cache
- `utils/cache.py`, `utils/supervision.py` et la page Supervision gerent offline, quotas et purge.
- Scripts support : `scripts/cache_maintenance.py`, `scripts/check_recovery.py`, `scripts/export_supervision_metrics.py`.

### Profil & bookmakers
- `utils/profile.py` + `utils/profile_ui.py` stockent bankroll, preferences ligues et alias bookmakers.
- `utils/match_filter.py` et `utils/analytics_ui.py` consolident edges par bookmaker.

## Pages existantes
1. Pilotage : Dashboard, Roadmap, Guides, Admin.
2. Analyse match/joueur : Matchs, Statistiques, Classement, Joueurs, Buteurs, Passeurs, Cartons, Stades, H2H.
3. Paris & IA : Predictions, Bookmakers, Cotes, Performance IA, Tableau IA.
4. Maintenance : Profil, Historique, Supervision, Tester l'API.

## Workflows disponibles
- Collecte batch : `scripts/backfill_predictions.py`, `scripts/update_roadmap.py`, `scripts/publish_roadmap.py`.
- Entrainement ML : `scripts/train_prediction_model.py` produit `models/*.joblib` + metriques JSON.
- Deploiement : `scripts/deploy.py` (pytest + archive) et workflow GitHub `publish-roadmap.yml`.

## Integrations & secrets
- API-Football : cle hard-codee dans `utils/config.py`, utilisee par `utils/api_calls.py` avec cache TTL.
- OpenWeather : cle attendue dans `.env` pour `utils/weather.py`.
- OpenAI : cle projet exposee dans `utils/ai_.module.py` mais module non branche.
- Aucun connecteur Supabase, Make ou reseaux sociaux malgre la roadmap.

> **Mise à jour 23/11/2025** : les clés API (Football, OpenWeather, OpenAI, Supabase) sont désormais chargées via `.env` non versionné grâce à `utils/secrets.py` et `python-dotenv`. Les modules refusent l'exécution si les secrets requis sont absents.

## Elements en attente
1. Social/Content Engine : pas de stockage rapports, pas de diffusion externe.
2. Notifications multi-canal et alerting Slack annonces mais absents du code. *(Résolu 23/11/2025 : module `utils/notifications.py` + alertes supervision/edges vers Slack & Discord.)*
3. Gestion securisee des secrets (Vault/CI) non appliquee : cles dans le repo. *(Résolu 23/11/2025 via `.env` non versionné et loader utils/secrets.py.)*
4. Couverture tests limitee (`tests/` ne couvre que quelques modules).
5. Module AI externe (`utils/ai_.module.py`) inutilisable (dependance manquante, cle invalide). *(Résolu 23/11/2025 via panneau "Analyse IA (OpenAI)" sur la page Prédictions et nouveau loader utils/ai_.module.py.)*

## Recommandations
1. **Securiser les secrets** : externaliser les cles API (Football, OpenAI) dans `.env` ou un vault et nettoyer le code.
2. **Industrialiser les rapports** : stocker metadata JSON, generer PDF et exposer la liste dans l'app (page Rapports).
3. **Lancer le Social Engine** : definir sources (prediction_history, match_filter), templating contenus et connecteurs reseaux sociaux.
4. **Etendre la supervision** : ajouter tests pour scripts critiques, surveiller `utils/test_api_calls.py` (H2H avec IDs).
5. **Mettre a jour la roadmap** : aligner les elements reels (projets Slack/Make non livres) et suivre l'avancement dans `docs/reports/`.
