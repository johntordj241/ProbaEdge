# IA Scenarios & Dual-Engine Plan

## 1. État actuel
- `utils/ai_/module.py` expose `analyse_match_with_ai` (OpenAI GPT-4o-mini) et gère la clé via `secrets.get_secret`.
- Payload construit dans `utils/predictions.py::_build_ai_match_payload` : snapshot complet (match, status, probabilités, tips, intensité, pression, contexte, bankroll).
- `show_predictions` appelle `_render_ai_analysis_section` → bouton Streamlit qui stocke la réponse dans `st.session_state["ai_analysis_cache"]` par `fixture_id`.
- Aucune variation/scénario : un seul prompt système, pas de sauvegarde historique ni de comparaison avec un autre moteur.

## 2. Objectifs vNext (ordre d’exécution)
1. **Scénarios “what-if”** : générer rapidement des analyses IA pour 3 situations types (carton rouge, météo extrême, but rapide) afin de mesurer la variation des probabilités et des tips.
2. **Moteur secondaire** : implémenter un modèle local léger (ex. gradient boosting ou règles Poisson ajustées) pour comparer ses sorties avec l’IA OpenAI et détecter les divergences.
3. **Historique & calibrage** : stocker les réponses IA + moteur secondaire dans `prediction_history` pour alimenter la vue “Performance IA”.

## 3. Découpage technique
### 3.1 Module de scénarios
- Nouveau fichier `utils/ai_scenarios.py`.
- Fonction `build_scenario_payload(base_payload, scenario_type)` qui applique les tweaks (ex. `red_cards+=1`, `weather='Pluie forte'`).
- Fonction `run_ai_scenarios(fixture_id, payload, scenarios)` qui :
  - Itère sur les scénarios demandés.
  - Ajuste le prompt utilisateur (“Imagine qu’un carton rouge frappe l’équipe domicile…”).
  - Met en cache les réponses dans `st.session_state["ai_scenarios_cache"]`.

### 3.2 UI scénarios
- Dans `show_predictions`, sous la carte IA existante :
  - Section “Scénarios IA” avec une multiselect (par défaut 3 scénarios) + bouton “Simuler”.
  - Affichage en accordéon des réponses (titre = scénario, sous-texte = variation de probabilités si dispo).
- Ajout d’un résumé comparant `projection_probs` vs les variations suggérées (même si heuristique au début).

### 3.3 Moteur secondaire
- Nouveau module `utils/alt_predictor.py` :
  - Calcul basé sur Poisson (déjà dispo) + ajustements spécifiques (cartons, météo, forme).
  - Expose `alt_projection(snapshot) -> dict(home/draw/away/propositions)` pour comparaison.
- UI : badge “Divergence” si écart > seuil, loggable via `notify_event`.

### 3.4 Historisation
- Étendre `prediction_history.upsert_prediction` (ou une nouvelle table) pour stocker :
  - `analysis_ai`, `analysis_alt`, `scenarios`.
  - Timestamp + identifiant fixture.
- Rendre accessible depuis la future vue “Performance IA”.

## 4. Points à trancher / dépendances
- Modèle local exact (GBM entraîné offline vs heuristique). Pour version nocturne : implémentation heuristique basée sur Poisson + facteurs de contexte (dispo).
- Format de stockage des scénarios (JSON compressé) et politique de rétention.
- Seuils d’alerte divergence (ex. >8 pts sur proba 1X2).
- Gouvernance des clés API supplémentaires (aucune pour scénarios, possible pour diffusion).

## 5. Prochaines étapes
1. [En cours] Finaliser ce design et créer les modules vides (`ai_scenarios.py`, `alt_predictor.py`) avec signatures/documentation.
2. Implémenter scénarios “carton rouge”, “but rapide”, “météo extrême” + UI.
3. Construire le moteur local léger et l’intégration de comparaison.
4. Ajouter la persistance/historique.
5. Étendre ensuite aux fonctionnalités d’engagement (diffusion, emailing) – hors scope de cette étape mais à garder en backlog.

Chaque étape livrera un message de progression avec la liste des modules restants à traiter.

