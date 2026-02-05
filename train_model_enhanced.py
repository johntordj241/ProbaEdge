#!/usr/bin/env python3
"""Entraîne un modèle amélioré avec plus de features"""

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

# FEATURES AMÉLIORÉES (13 au lieu de 6)
ENHANCED_FEATURES = [
    # Originales (6)
    "feature_home_draw_diff",
    "feature_home_away_diff",
    "feature_over_under_diff",
    "feature_max_prob",
    "feature_main_confidence_norm",
    "feature_total_pick_over",
    # NOUVELLES (7)
    "prob_home",  # Probabilité Poisson domicile
    "prob_draw",  # Probabilité Poisson nul
    "prob_away",  # Probabilité Poisson extérieur
    "prob_over_2_5",  # Proba Over 2.5 buts
    "prob_under_2_5",  # Proba Under 2.5 buts
    "main_confidence",  # Confiance du pick (0-100)
]

# Charger
df = pd.read_csv("data/prediction_dataset_enriched.csv")
print(f"📊 Dataset: {len(df)} lignes")

# Filtrer les succès
df_valid = df[df["success"].notna()].copy()
print(f"✅ Succès calculés: {len(df_valid)}")

# Préparer features
X = df_valid[ENHANCED_FEATURES].copy()
y = df_valid["success"].astype(int)

# Normaliser main_confidence (0-100 -> 0-1)
if "main_confidence" in X.columns:
    X["main_confidence"] = X["main_confidence"] / 100.0

print(f"\n📈 MODÈLE AMÉLIORÉ")
print(f"   Features: {len(ENHANCED_FEATURES)}")
for feat in ENHANCED_FEATURES:
    filled = X[feat].notna().sum()
    print(f"   ✅ {feat:30s} : {filled:3d}/{len(X)}")

print(f"\n📊 Distribution:")
print(f"   Succès: {(y == 1).sum()}")
print(f"   Échecs: {(y == 0).sum()}")

# Split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, random_state=42, stratify=y
)

print(f"\n🔄 Train/Test: {len(X_train)}/{len(X_test)}")

# Pipeline
pipeline = Pipeline(
    [
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(max_iter=1000)),
    ]
)

# Entraîner
print("\n⏳ Entraînement...")
pipeline.fit(X_train, y_train)

# Évaluer
y_pred = pipeline.predict(X_test)
y_proba = pipeline.predict_proba(X_test)[:, 1]
accuracy = accuracy_score(y_test, y_pred)
roc_auc = roc_auc_score(y_test, y_proba)

print(f"\n✅ RÉSULTATS")
print(f"📊 Accuracy: {accuracy:.1%}")
print(f"📊 ROC-AUC:  {roc_auc:.1%}")

# Comparaison
print(f"\n📈 AMÉLIORATION")
print(f"Accuracy: 61.2% → {accuracy:.1%} ({(accuracy - 0.612) * 100:+.1f}%)")
print(f"ROC-AUC:  69.6% → {roc_auc:.1%} ({(roc_auc - 0.696) * 100:+.1f}%)")

# Sauvegarder
model_path = Path("models/prediction_success_model_enhanced.joblib")
model_path.parent.mkdir(exist_ok=True)
joblib.dump(pipeline, model_path)
print(f"\n💾 Modèle: {model_path}")

# Métriques
metrics = {
    "version": "enhanced",
    "accuracy": float(accuracy),
    "roc_auc": float(roc_auc),
    "samples": int(len(df_valid)),
    "features": ENHANCED_FEATURES,
    "improvements": {
        "accuracy_delta": float((accuracy - 0.612) * 100),
        "roc_auc_delta": float((roc_auc - 0.696) * 100),
    },
}

metrics_path = Path("models/prediction_success_metrics_enhanced.json")
metrics_path.write_text(json.dumps(metrics, indent=2))
print(f"💾 Métriques: {metrics_path}")
