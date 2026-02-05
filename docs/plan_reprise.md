# Plan de reprise opérationnelle

Ce document décrit la marche à suivre lorsque l’application bascule en mode hors ligne (`utils/cache.is_offline_mode()`), que ce soit à cause d’une coupure réseau ou d’un dépassement de quotas API.

---

## 1. Vérifications immédiates

1. Ouvrir la page **Supervision** de l’application.
2. Noter le motif indiqué dans la barre latérale :
   - `user` : mode hors ligne manuel.
   - `network` : erreur réseau.
   - `quota` : limite d’appels atteinte.
3. Lancer `python scripts/export_supervision_metrics.py` pour capturer l’état au format JSON (`docs/supervision_metrics.json`).

---

## 2. Reprise suite à une erreur réseau

1. Désactiver le mode hors ligne depuis la barre latérale.
2. Rafraîchir les pages critiques (Predictions, Bookmakers, Cotes, Dashboard) afin de reconstruire le cache.
3. Vérifier que `docs/supervision_metrics.json` indique un quota restant non nul.
4. Noter l’heure de rétablissement dans le journal d’incident interne.

---

## 3. Reprise après dépassement de quotas

1. Vérifier l’heure de reset indiquée dans la page Supervision (`quota_reset`).
2. Mettre l’application en mode hors ligne **manuel** si ce n’est pas déjà le cas.
3. Attendre le reset :
   - L’application relancera automatiquement le mode en ligne (auto-resume).
   - Sinon, lancer `scripts/check_recovery.py` (voir ci-dessous) ou désactiver manuellement le mode hors ligne après reset.
4. Recharger les pages critiques pour reconstruire le cache.

---

## 4. Script de contrôle rapide

Lancer :

```bash
python scripts/check_recovery.py
```

Ce script affiche :

- état du mode hors ligne,
- temps restant avant reprise automatique,
- métriques cache (taille, hits/misses),
- quotas actuels.

---

## 5. Journalisation

Pour chaque incident, consigner :

- Date / heure d’apparition.
- Motif (`user`, `network`, `quota`).
- Actions menées (purge cache, relance, contact support).
- Heure de reprise en ligne effective.

Ces informations sont stockées dans le fichier partagé `docs/incidents_supervision.md` (à créer si besoin).

---

## 6. Checklist avant de clôturer l’incident

- [ ] Mode hors ligne désactivé.
- [ ] Résumé des métriques exporté (`docs/supervision_metrics.json`).
- [ ] Pages clés ouvertes en ligne (Predictions, Bookmakers, Cotes, Dashboard).
- [ ] Tests fonctionnels rapides (exécution `pytest`).
- [ ] Incidents documentés dans le journal.

