# Next Version – Enhancements Overview

This document synthesizes the improvements discussed for a future major release of the football app. It groups the work by theme, highlights expected outcomes, and sketches a delivery timeline (≈3–4 weeks full‑time).

## 1. IA & Modélisation
- Étendre `analyse_match_with_ai` avec des scénarios “what‑if” (carton rouge, météo extrême, but rapide) pour quantifier l’impact sur les probabilités et les conseils.
- Ajouter un second moteur de prédiction (ex. modèle gradient boosting ou réseau léger local) pour comparer ses sorties avec l’IA OpenAI et déclencher des alertes en cas de divergence.
- Historiser les réponses IA et exposer un tableau de calibrage (prédictions vs résultats) dans `Performance IA`.

## 2. Personnalisation bankroll & alertes
- Autoriser plusieurs profils de bankroll/stratégies par utilisateur, chacun avec ses paramètres (montant, méthode Kelly/flat, limites).
- Offrir des alertes push (email/Telegram/Webhook) quand un edge dépasse un seuil configurable ou lorsqu’un pari suivi atteint un état critique (cashout, blessure, etc.).
- Enrichir le suivi session avec des “scènes” sauvegardées (filtres + sélection de paris) pour revenir rapidement à une configuration.

## 3. Données enrichies
- Intégrer des flux complémentaires : cotes bookmakers temps réel, ratings joueurs, forme des équipes, météo avancée pour améliorer blessures/contexte.
- Compléter la section blessure avec des temps de retour estimés et les positions affectées.
- Construire un historique visuel des performances IA vs résultats réels par compétition afin de mesurer la valeur ajoutée.

## 4. Expérience utilisateur
- Optimiser les pages clés (Predictions, Buteurs) pour mobile/tablette et préparer un mode PWA pour un suivi depuis le terrain.
- Ajouter un mode sombre/clair configurable et des préférences utilisateur persistées (nombre de matchs, filtres par compétition).
- Simplifier la navigation avec des “quick actions” (Demander l’avis de l’IA, Rafraîchir les cotes, Ajouter au combiné) accessibles depuis la carte match.

## 5. Engagement & Diffusion (réseaux sociaux / mails)
- Brancher le module `notify_event` sur des connecteurs (Twitter/X, Facebook, Telegram, Discord, Email/SMS) pour pousser automatiquement les meilleurs edges, alertes live ou bilans journaliers directement depuis l’app.
- Offrir un éditeur de templates (pré‑match, live update, bilan, cashout, “résultats du jour”) avec fusion des stats IA, des cotes et des recommandations pour publier/l’envoyer en un clic.
- Historiser les posts envoyés et mesurer leur performance (ouverture email, clic, reach social) afin d’ajuster le ton et rendre l’expérience addictive.
- Proposer un “mode broadcast” : sélectionne un match, clique “Partager” et publie instantanément la carte IA + tips sur les canaux activés.

## 6. Qualité logicielle & opérations
- Couvrir `utils/prediction_model.py`, `utils/predictions.py` et les modules IA/banque de paris avec des tests unitaires + tests de régression sur données enregistrées.
- Mettre en place une CI (GitHub Actions) qui exécute tests, linting et vérifie la présence des clés d’environnement nécessaires avant déploiement Streamlit.
- Ajouter des scripts de validation (sanity check des cotes, comparaison API/cache) exécutables avant release.

## 6. Planning indicatif
| Semaine | Focus principal | Détails |
|--------|-----------------|---------|
| 1 | Cadrage & architecture | Définition des scénarios IA, choix du modèle secondaire, design des flux d’alertes, cartographie des nouvelles sources de données. |
| 2 | Implémentation IA & backend | Intégration scénario “what‑if”, moteur secondaire, stockage des analyses, premiers endpoints d’alertes. |
| 3 | UX, personnalisation & engagement | Multi-bankroll, scènes sauvegardées, PWA/mobile, quick actions, intégration des flux de données enrichies, connecteurs sociaux/email + templates de diffusion. |
| 4 | Tests, CI/CD, stabilisation | Couverture de tests, GitHub Actions, scripts de validation, polishing UI et documentation release. |

**Durée totale estimée** : 3 à 4 semaines selon la profondeur de chaque lot. Chaque bloc peut être livré de manière incrémentale si une priorité se dégage (ex. IA + alertes avant UX).
