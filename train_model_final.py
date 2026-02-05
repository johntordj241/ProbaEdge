#!/usr/bin/env python3
"""Modèle FINAL optimisé avec les meilleures features"""

import json
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

# Les 8 MEILLEURES features (basé sur l'analyse d'importance)
OPTIMIZED_FEATURES = [
    "feature_max_prob",  # LA plus importante (0.541)
    "feature_total_pick_over",  # 2e (0.311)
    "prob_draw",  # 3e (0.265)
    "feature_over_under_diff",  # 4e (0.249)
    "prob_over_2_5",  # 5e (0.249)
    "prob_under_2_5",  # 6e (0.249)
    "prob_away",  # 7e (0.159)
    "feature_home_draw_diff",  # 8e (0.142)
]

df = pd.read_csv("data/prediction_dataset_enriched.csv")
df_valid = df[df["success"].notna()].copy()

print("=" * 80)
print("MODÈLE FINAL OPTIMISÉ")
print("=" * 80)
print(f"📊 Dataset: {len(df_valid)} prédictions")
print(f"📈 Features: {len(OPTIMIZED_FEATURES)}")

X = df_valid[OPTIMIZED_FEATURES].copy()
y = df_valid["success"].astype(int)

print(f"\n📊 Distribution des classes:")
print(f"   Succès: {(y == 1).sum()} (60.6%)")
print(f"   Échecs: {(y == 0).sum()} (39.4%)")

# Split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, random_state=42, stratify=y
)

# Pipeline
pipeline = Pipeline(
    [
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(max_iter=1000)),
    ]
)

print(f"\n⏳ Entraînement...")
pipeline.fit(X_train, y_train)

# Évaluer
y_pred = pipeline.predict(X_test)
y_proba = pipeline.predict_proba(X_test)[:, 1]
accuracy = accuracy_score(y_test, y_pred)
roc_auc = roc_auc_score(y_test, y_proba)

print(f"\n" + "=" * 80)
print("RÉSULTATS FINAUX")
print("=" * 80)
print(f"📊 Accuracy: {accuracy:.1%}")
print(f"📊 ROC-AUC:  {roc_auc:.1%}")

print(f"\n📈 COMPARAISON")
print(f"                      Avant  →  Après   (Amélioration)")
print(
    f"   Accuracy:         61.2% →  {accuracy:.1%}    ({(accuracy - 0.612) * 100:+.1f}%)"
)
print(
    f"   ROC-AUC:          69.6% →  {roc_auc:.1%}    ({(roc_auc - 0.696) * 100:+.1f}%)"
)
print(f"   Nombre features:     6  →      8         (+2)")

# Sauvegarder
model_path = Path("models/prediction_success_model_final.joblib")
model_path.parent.mkdir(exist_ok=True)
joblib.dump(pipeline, model_path)
print(f"\n💾 Modèle FINAL: {model_path}")

# Métriques
metrics = {
    "version": "final_optimized",
    "accuracy": float(accuracy),
    "roc_auc": float(roc_auc),
    "samples": int(len(df_valid)),
    "features_count": len(OPTIMIZED_FEATURES),
    "features": OPTIMIZED_FEATURES,
    "improvements_from_baseline": {
        "accuracy_delta_percent": float((accuracy - 0.612) * 100),
        "roc_auc_delta_percent": float((roc_auc - 0.696) * 100),
    },
}

metrics_path = Path("models/prediction_success_metrics_final.json")
metrics_path.write_text(json.dumps(metrics, indent=2))
print(f"💾 Métriques: {metrics_path}")

print(f"\n" + "=" * 80)
print("✅ Modèle prêt pour production!")
print("=" * 80)
