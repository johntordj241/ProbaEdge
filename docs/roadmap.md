# Roadmap - export automatique

_Genere le 23/10/2025 22:37_

## Collecte et donnees
Renforcer la collecte et les fondations data pour fiabiliser les calculs.

- **Cache API et relecture hors ligne** - reste 0%
  - Purge planifiee + stats usage exposes dans la sidebar + limite taille cache.
- **Schemas unifies equipes / joueurs** - reste 0%
  - Normalisation teams/players en place; mapping statistics et referentiel IDs unifies entre toutes les sources.
- **Historique matches enrichi** - reste 0%
  - History_sync a importe les 3 dernieres saisons et fiabilise les correspondances fixtures/teams.
- **Flux evenements temps reel** - reste 0%
  - Endpoints events/lineups integres, xG/shots minute harmonises et prediction_history alimente avec les evenements temps reel.
- **Qualite data & validation** - reste 0%
  - Checks Great Expectations en production et tests de coherence sur historique.csv / cache API prevenant duplicats et anomalies.

## Experience produit
Pages utilisateur, personnalisation et assistance a la prise de decision.

- **Vue Bookmakers - comparatif cotes** - reste 0%
  - Vue multi-journee completee avec marches secondaires et sauvegarde des filtres relies au profil.
- **Page Profil et preferences** - reste 0%
  - UI par defaut liee aux favoris et parametres horizon/bookmakers appliques a toutes les vues statistiques/matches.
- **Guides prompts et parcours IA** - reste 0%
  - Prompts/alertes deployes sur toutes les pages et valides par feedback utilisateurs avec traductions disponibles.
- **Match Center interactif** - reste 0%
  - Fiches matchs, timeline et analytics_ui fusionnes dans une vue unique avec scenarios What-if et alertes personnalisees.
- **Notifications & alertes multi-canal** - reste 0%
  - Service d'alerting email/Discord branche sur match_filter diffusant edges et changements de cotes en quasi temps reel.

## Fiabilite et exploitation
Mettre en place supervision, resilience et automation pour l'application.

- **Surveillance erreurs API** - reste 0%
  - Retries + export JSON + workflow CI en place; supervision exploitable et script check_recovery disponible.
- **Plan de reprise** - reste 0%
  - Plan de reprise documente (docs/plan_reprise.md) + scripts export/check.
- **Automatisation publication roadmap** - reste 0%
  - Script publish_roadmap + workflow GitHub Actions (publish-roadmap.yml) operables.
- **Gestion des secrets & rotation cles** - reste 0%
  - Cles OpenAI/API externalisees, config chiffree et rotation automatisee via vault/variables CI.
- **Alerting supervision temps reel** - reste 0%
  - Supervision branchee sur Slack/Webhook avec seuils quota/cache et generation automatique de post-mortem apres incident.

## Apprentissage et analytics
Mesurer la performance IA et capitaliser sur l'historique.

- **Historique predictions -> apprentissage** - reste 0%
  - Dataset export + script train_prediction_model.py alimentent la boucle d'apprentissage.
- **Tableau de bord precision** - reste 0%
  - Dashboard precision enrichi (filtres ligue/saison, ROI attendu vs reel).
- **Backtests strategies & ROI cumulatif** - reste 0%
  - Backtests bankroll/strategies integres aux scripts/train_prediction_model.py avec reporting CSV et Streamlit.
- **Explainabilite des pronostics** - reste 0%
  - SHAP/feature importance disponibles dans les fiches matches et logs prediction_history pour expliquer les pronostics.
