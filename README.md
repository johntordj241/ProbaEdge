# Proba Edge - Assistant IA pour paris sportifs

Proba Edge est un dashboard Streamlit. Il combine les donnees API-FOOTBALL, plusieurs couches statistiques et une supervision bankroll pour piloter une session de pari. Depuis la version **v2.5**, le moteur repose sur une architecture multi-couches (Elo + Dixon-Coles + ajustements contextuels + Markov live + calibration ML) qui fournit des probabilites recalibrees, des intervalles de confiance et des recommandations plus solides.

## Fonctionnalites principales

- **Moteur multi-couches**
  - Elo persistant (`data/elo_table.parquet`) mis a jour apres chaque match.
  - Scorelines Dixon-Coles (Poisson bivarie disponible).
  - Ajustements contextuels chiffres : meteo, suspensions, fatigue, arbitre, evenements live.
  - Markov "lite" pour adapter les intensites offensives en live (score, pression, cartons).
  - Calibration logistique enrichie (lambda, Elo, pression, intensite) avec metriques Brier/ECE et intervalle 95 % affiche dans l'interface.
- **Suivi bankroll & historique**
  - Enregistrement des paris (pre-match ou live) directement depuis l'interface.
  - Historique normalise (`data/prediction_history.csv`) exploitable pour l'export dataset.
  - Ajustement automatique de la bankroll via `utils/prediction_history.adjust_bankroll`.
- **Scripts pret-a-l'emploi**
  - `scripts/backfill_predictions.py` pour historiser fixtures et predictions.
  - `scripts/train_prediction_model.py` (features elargies + rapport Brier/ECE).
  - `scripts/export_supervision_metrics.py`, `scripts/check_recovery.py` pour la supervision.
  - `scripts/deploy.py` pour preparer un livrable (tests + archive).
- **Dashboard Streamlit**
  - Comparaison live vs pre-match avec intervalles de confiance.
  - Indice d'intensite (lambda total, over 2.5, BTTS).
  - Recommandations de mise (flat, pourcentage, Kelly simplifie), panier combine, suivi paris/score/buteur.
  - Resume IA, prompts dynamiques, modules supervision / H2H / stades.
  - Analyse IA (OpenAI) sur la page Predictions si `OPENAI_API_KEY` est definie.
  - Notifications Slack/Discord configurables pour les edges forts et les alertes supervision.

## Installation rapide

```bash
pip install -r requirements.txt
```

> `requirements.txt` inclut `pyarrow`, `openai`, `altair`, `supabase` et `python-dotenv` pour charger automatiquement vos secrets locaux.

### Variables d'environnement indispensables

Copiez `.env.example` vers `.env` (non versionnÃ©) ou exportez ces variables avant de lancer Streamlit :

```
API_FOOTBALL_KEY=XXXX
API_FOOTBALL_BASE_URL=https://v3.football.api-sports.io
OPENWEATHER_API_KEY=XXXX
OPENAI_API_KEY=XXXX
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
SOCIAL_X_TOKEN=...
SOCIAL_DISCORD_TOKEN=...
DISCORD_WEBHOOK_URL=...
SLACK_WEBHOOK_URL=...
```

Les modules sensibles (`utils/config.py`, `utils/widgets.py`, `utils/ai_.module.py`, `utils/weather.py`, `utils/supabase_client.py`) refusent dÃ©sormais de s'exÃ©cuter si la clÃ© correspondante est absente.  
> Tip : dÃ©finissez `FOOTBALL_APP_ENV_FILE=/chemin/vers/mon.env` pour charger un fichier .env alternatif (Vault / CI).
#### Activer l'offre Beta testeur

Partagez la version **Elite** sans modifier `data/users.json` :

- `BETA_ACCESS_CODES` : liste de codes (CSV) a communiquer aux testeurs. Ils le saisissent dans le champ *Code beta testeur* du formulaire d'inscription, et leur compte bascule directement sur le plan `beta`.
- `BETA_TESTER_EMAILS` : adresses precises a whitelister automatiquement.
- `BETA_TESTER_DOMAINS` : domaines (ex. `club.com,partner.org`) qui debloquent automatiquement le plan `beta` a l'inscription.

Le plan `beta` offre les memes capacites que **Elite** (quotas API, IA, diffusion), mais reste identifie comme tel et n'autorise pas l'onglet **Admin**.


**Activer Telegram (optionnel, diffusion controlee)**
1. Dans Telegram, ouvrez **@BotFather**, lancez `/start` puis `/newbot` pour obtenir `TELEGRAM_BOT_TOKEN`.
2. Envoyez un message a votre bot puis appelez `https://api.telegram.org/bot<TOKEN>/getUpdates` (ou utilisez `@RawDataBot`) pour recuperer `TELEGRAM_CHAT_ID`.
3. Ajoutez ces deux valeurs dans `.env` : le bouton **Telegram** de la section *Diffusion & partage* s'activera automatiquement.


## Lancer le dashboard

```bash
streamlit run app.py
```

### Tests automatises

```bash
pytest
```
> Pour la CI (GitHub Actions, GitLab, cron), lancez `pytest tests/` afin de couvrir le moteur Social Engine, notifications et supervision.
> Le workflow `.github/workflows/tests.yml` exÃ©cute automatiquement ces tests sur chaque push/PR.

### Scripts utiles

| Script | Description |
| --- | --- |
| `python scripts/backfill_predictions.py --league 61 --season 2025 --last 50` | Alimente `data/prediction_history.csv` |
| `python scripts/train_prediction_model.py` | Entraine le modele de calibration (JSON + Brier/ECE) |
| `python scripts/deploy.py` | Execute les tests puis genere `dist/football_app_release.zip` |
| `python scripts/export_supervision_metrics.py` | Exporte les metriques de supervision |
| `python scripts/publish_roadmap.py` | Regenere `docs/roadmap.md` a partir de `data/roadmap.yaml` |
| `python scripts/social_engine.py --publish` | GÃ©nÃ¨re le rÃ©sumÃ© Social Engine et le publie (Slack/Discord + Supabase) |
| `py -3.11 scripts/auto_broadcast.py --mode pre-match --channels telegram,email` | Diffuse automatiquement les templates (pré-match / live / edge) vers les canaux configurés |
| `py -3.11 scripts/auto_broadcast.py --mode pre-match --channels telegram,email --agenda-date today` | Même diffusion mais limitée aux matchs présents dans l'Agenda du jour |
| `py -3.11 scripts/sync_active_squad.py --team 33 --season 2024` | Synchronise l'effectif actif (injuries / transferts / lineups) dans la table `players` |

## Structure des donnees

- `data/prediction_history.csv` : snapshots, paris, resultats.
- `models/` : modeles ML (`match_outcome_model.joblib`, `prediction_success_model.joblib`) et metriques.
- `models/ratings.py` & `data/elo_table.parquet` : Elo persistant.
- `models/goal_models.py`, `models/markov.py` : scorelines et Markov live.

## Reglages & supervision

- Mode hors-ligne : accessible via le panneau "Cache" (utile en cas de quota API).
- Procedure de reprise : voir `docs/plan_reprise.md`.
- Monitoring IA : `utils/performance_dashboard.py` & `docs/supervision.md`.

## Roadmap & contributions

Les evolutions sont suivies dans `docs/roadmap.md` (generation automatique).  
Contributions bienvenues : ouvrez une issue ou proposez une MR en verifiant que `pytest` passe.

### Moteur Social / Content

- Depuis l'onglet **Administration â†’ Jeu de donnees**, gÃ©nÃ©rez un rÃ©sumÃ© en un clic (prÃ©visualisation, export Markdown, publication Slack/Discord).
- En ligne de commande : `python scripts/social_engine.py --publish` pour automatiser la gÃ©nÃ©ration quotidienne (cron ou GitHub Actions).
- Les rapports sont stockÃ©s dans `docs/reports/` et synchronisÃ©s dans Supabase via `store_report_metadata`.
- La page **Rapports** se connecte automatiquement Ã  Supabase (`reports` table) quand la configuration est disponible, sinon elle lit les fichiers locaux.

---

**Tip** : apres une modification de structure (Elo, nouvelles features), rafraichissez l'historique avec :

```bash
python -c "from utils.prediction_history import normalize_prediction_history; normalize_prediction_history()"
```

Bon build et bonnes sessions Proba Edge !


