#!/usr/bin/env python3
"""Comparatif final de tous les modèles testés"""

import json
from pathlib import Path

print("=" * 100)
print("📊 COMPARATIF FINAL - TOUS LES MODÈLES")
print("=" * 100)

models = {
    "1. Baseline (Random)": {
        "accuracy": 0.500,
        "roc_auc": 0.500,
        "features": 0,
        "description": "Lancer une pièce",
    },
    "2. INITIAL (6 features)": {
        "accuracy": 0.612,
        "roc_auc": 0.696,
        "features": 6,
        "description": "feature_*diff, max_prob, confidence_norm, total_pick_over",
    },
    "3. Enhanced (12 features)": {
        "accuracy": 0.621,
        "roc_auc": 0.691,
        "features": 12,
        "description": "Init + prob_home/draw/away + prob_over/under + confidence",
    },
    "4. Optimized (8 features)": {
        "accuracy": 0.621,
        "roc_auc": 0.689,
        "features": 8,
        "description": "Top 8 features par importance",
    },
    "5. Ultimate (11 features)": {
        "accuracy": 0.612,
        "roc_auc": 0.688,
        "features": 11,
        "description": "Init + Elo ratings + Lambda (buts attendus)",
    },
}

print(f"\n{'Modèle':<30} | Accuracy | ROC-AUC | Features | vs Baseline")
print(f"{'-' * 100}")

best_accuracy_model = None
best_roc_model = None
best_acc = 0
best_roc = 0

for name, data in models.items():
    acc_pct = data["accuracy"] * 100
    roc_pct = data["roc_auc"] * 100
    acc_gain = (data["accuracy"] - 0.5) * 100
    roc_gain = (data["roc_auc"] - 0.5) * 100

    print(
        f"{name:<30} | {acc_pct:7.1f}% | {roc_pct:5.1f}% | {data['features']:8d} | +{acc_gain:5.1f}% acc, +{roc_gain:5.1f}% AUC"
    )

    if data["roc_auc"] > best_roc:
        best_roc = data["roc_auc"]
        best_roc_model = name
    if data["accuracy"] > best_acc:
        best_acc = data["accuracy"]
        best_accuracy_model = name

print(f"\n" + "=" * 100)
print("🏆 MEILLEUR MODÈLE")
print("=" * 100)
print(f"\n✅ Meilleur ROC-AUC: {best_roc_model}")
print(f"   {models[best_roc_model]['description']}")
print(f"   Performance: Accuracy {best_acc*100:.1f}% | ROC-AUC {best_roc*100:.1f}%")

print(f"\n💡 CONCLUSION")
print(
    f"""
Tous les modèles performent à peu près pareil (60-62% accuracy, 69% ROC-AUC).
Cela signifie que:

1. ✅ Tes 6 features ORIGINALES étaient déjà excellentes
2. ✅ Ajouter plus de features ne les améliore pas (car redondantes)
3. ✅ Le modèle a atteint un plateau - améliorations margales

RECOMMANDATION pour la PRODUCTION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
→ Utiliser le modèle INITIAL (6 features)
  • Plus simple (moins de risque overfitting)
  • Exactement la même performance
  • Plus rapide à entraîner
  • Chemin: models/prediction_success_model_v2.joblib

Alternative si tu veux tester:
→ Modèle ENHANCED (12 features) - performance identique mais plus complet
  • Plus d'information capturée
  • Pour du deep learning futur
"""
)

print(f"\n" + "=" * 100)
print("📈 POUR VRAIMENT AMÉLIORER DE 5%+, IL FAUDRAIT:")
print("=" * 100)
print(
    """
Option A: Meilleure data
  ✗ Ajouter plus de matchs historiques (500+ au lieu de 411)
  ✗ Intégrer des données de joueurs (blessures, absences)
  ✗ Ajouter contexte (météo, fatigue, suspensions)

Option B: Meilleur modèle
  ✗ Random Forest / XGBoost (au lieu de Logistic Regression)
  ✗ Neural Networks (Deep Learning)
  ✗ Ensemble methods (combiner plusieurs modèles)

Option C: Features créatives
  ✗ Momentum récent (forme derniers 5 matchs)
  ✗ Head-to-head historique
  ✗ Avantage domicile par compétition
  ✗ Tendances saisonnières
  ✗ Arbitres connus pour être agressifs/permissifs
"""
)

print(f"\n✅ TON MODÈLE ACTUEL EST BON POUR COMMENCER!")
print(f"   60%+ de précision en prédiction sportive = très respectable 💪\n")
