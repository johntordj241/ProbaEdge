# Supervision, mode dégradé et purge du cache

Ce document décrit le fonctionnement de la supervision API, la gestion du cache hors ligne et les procédures de purge/remise en ligne. Il sert de référence rapide lorsque le quota API est bas ou que la connexion est coupée.

---

## 1. Architecture et flux de supervision

- **Instrumentation des appels**  
  Tous les appels sortants passent par `utils/api_calls._request`. Le wrapper mesure la durée, récupère les en-têtes de quota (`x-ratelimit-requests-*`) et consigne le résultat (succès, erreur, fallback cache) via `utils/supervision.record_api_call`.

- **Stockage des métriques**  
  Les entrées sont conservées dans une deque mémoire (max 400). Les agrégats par endpoint (taux de succès, durée moyenne, ratio cache) sont recalculés à la volée. Les quotas restants/limites sont mis à jour à chaque réponse réseau.

- **Retries & auto-resume**  
  Le wrapper applique désormais jusqu’à trois retries (backoff exponentiel) pour les erreurs 5xx/429. En cas de bascule automatique hors ligne (`quota` ou `network`), une reprise automatique est programmée (5 min pour quota, 3 min pour réseau) et affichée dans la sidebar.

- **Indicateurs globaux**  
  `utils/supervision.health_snapshot()` synthétise : quota restant, mode hors ligne actif, quota faible, nombre d’erreurs récentes. Cette fonction alimente :
  - la sidebar (`render_supervision_status`) ;
  - le tableau de bord Supervision (`utils/supervision_dashboard.py`).

- **Mode dégradé**  
  `utils/cache.set_offline_mode()` active la lecture cache uniquement. Les écritures critiques (historicisation des prédictions, seed) se stoppent automatiquement. Le motif (`user`, `quota`, `network`) est affiché dans la sidebar et sur les pages sensibles (Predictions, Bookmakers, Cotes).

---

## 2. Tableau de bord Supervision

Accessible via le menu **Supervision** :

1. **Métriques globales** : quota restant, taux de succès moyen, durée moyenne (ms).  
2. **Alertes** :
   - Rappel du mode hors ligne + motif.
   - Avertissement quotas faibles ou erreurs récentes.
3. **Cache API** :
   - Nombre de fichiers / taille totale.
   - Dernière purge.
   - Bouton *Purger le cache* (force la suppression de tous les fichiers).
4. **Statistiques par endpoint** : nombre d’appels, succès %, durée moyenne, ratio cache, dernière erreur.
5. **Journal des appels** : filtrable par endpoint, présente la dernière centaine de requêtes (timestamp, durée, params, statut, source).

---

## 3. Mode hors ligne & lecture cache

- **Activation manuelle** : bouton *Activer le mode hors ligne* (sidebar). À utiliser uniquement si les données nécessaires ont déjà été chargées en ligne.
- **Activation automatique** :
  - Codes HTTP 402/403/429 (quota épuisé).
  - Exceptions réseau lors des requêtes.
- **Effets immédiats** :
  - Toutes les pages utilisent exclusivement le cache local.
  - Plus aucune écriture dans `prediction_history.csv`.
  - Avertissements affichés en haut des pages Predictions/Bookmakers/Cotes.
- **Retour en ligne** :
  - Cliquer sur *Désactiver le mode hors ligne*.
  - Recharger les pages critiques pour reconstituer le cache.

---

## 4. Procédure de purge & reprise

1. **Avant la purge**  
   - Désactiver le mode hors ligne.  
   - Vérifier dans la page Supervision que le quota est suffisant pour recharger les données.

2. **Purge**  
   - Bouton *Purger le cache* dans la sidebar ou l’onglet Supervision.  
   - La métrique “Cache : 0 fichiers” confirme la suppression.

3. **Reconstitution du cache**  
   - Toujours en ligne, ouvrir les pages clés (Predictions, Bookmakers, Cotes, Dashboard) avec les filtres habituels.  
   - S’assurer que les tableaux se remplissent (aucun message “Aucun match disponible…”).

4. **Bascule hors ligne (facultative)**  
   - Cliquer sur *Activer le mode hors ligne*.  
   - Les bandeaux “Mode dégradé” apparaissent, mais les données restent disponibles tant que le cache n’est pas purgé.

---

## 5. Bonnes pratiques

- **Ne pas purger le cache en mode hors ligne.** Sinon, il n'y a plus de données à afficher.
- **Toujours recharger les compétitions nécessaires avant de basculer hors ligne.** Le cache est spécifique à chaque combinaison ligue/saison/équipe.
- **Surveillance quotas** : en dessous de 10 % du quota ou <5 appels restants, la sidebar affiche une alerte orange. Prévoir la mise en hors ligne ou limiter les requêtes.
- **Logs détaillés** : si un endpoint échoue (HTTP ≠ 200), consulter l'onglet Supervision pour récupérer le message d'erreur exact (colonne “Erreur récente”).
- **Scripts utiles** :
  - `python scripts/export_supervision_metrics.py` pour enregistrer l'état courant (quota, cache, endpoints).
  - `python scripts/check_recovery.py` pour vérifier instantanément le statut hors ligne / reprise automatique.

---

### Checklist rapide

- [ ] Mode hors ligne désactivé ?
- [ ] Cache purgé (uniquement si nécessaire) ?
- [ ] Pages clés rechargées en ligne ?
- [ ] Mode hors ligne réactivé (si besoin) ?
- [ ] Aucune alerte quota rouge dans la sidebar ?

---

## Hook CI/CD (exemple)

```yaml
name: Update roadmap

on:
  workflow_dispatch:
    inputs:
      section:
        description: Section a mettre a jour
        required: true
      task:
        description: Tache cible
        required: true
      remaining:
        description: Pourcentage restant
        required: true

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install pyyaml
      - run: |
          python scripts/update_roadmap.py update "${{ github.event.inputs.section }}" "${{ github.event.inputs.task }}" --remaining "${{ github.event.inputs.remaining }}"
      - run: |
          git config user.name "CI"
          git config user.email "ci@example.com"
          git commit -am "ci: update roadmap" || echo "Rien a commiter"
          git push
```

Utilise `scripts/update_roadmap.py list` pour retrouver les noms exacts des sections/taches.

---

### Auto-resume

- Les bascules hors ligne declenchees par un quota ou une erreur reseau programment automatiquement un retour en ligne (5 min pour quota, 3 min pour reseau).
- La sidebar affiche "Reprise automatique prevue" avec le compteur ; attendre la fin du delai avant de repasser en ligne manuellement.
- Les desactivations manuelles (raison "user") ne declenchent pas de reprise automatique.
