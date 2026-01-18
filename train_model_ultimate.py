#!/usr/bin/env python3
"""Modèle ULTIMATE enrichi avec Elo et Lambda"""

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

# FEATURES ULTIMATE (toutes les bonnes ones)
ULTIMATE_FEATURES = [
    # Originales (6)
    "feature_max_prob",
    "feature_total_pick_over",
    "feature_over_under_diff",
    "feature_home_draw_diff",
    # NOUVELLES - Probabilités
    "prob_draw",
    "prob_over_2_5",
    "prob_under_2_5",
    "prob_away",
    # NOUVELLES - Elo et Lambda (les vraies nouveautés)
    "delta_elo",  # 🎯 Elo ratings
    "feature_lambda_home",  # 🎯 Buts attendus domicile
    "feature_lambda_away",  # 🎯 Buts attendus extérieur
]

df = pd.read_csv("data/prediction_dataset_enriched_v2.csv")
df_valid = df[df["success"].notna()].copy()

print("=" * 80)
print("🚀 MODÈLE ULTIMATE - AVEC ELO + LAMBDA")
print("=" * 80)
print(f"📊 Dataset: {len(df_valid)} prédictions")
print(f"📈 Features: {len(ULTIMATE_FEATURES)}")

print(f"\n✅ Features utilisées:")
for i, feat in enumerate(ULTIMATE_FEATURES, 1):
    filled = df_valid[feat].notna().sum()
    print(f"   {i:2d}. {feat:30s} ({filled}/{len(df_valid)})")

X = df_valid[ULTIMATE_FEATURES].copy()
y = df_valid["success"].astype(int)

print(f"\n📊 Distribution:")
print(f"   Succès: {(y == 1).sum()} (60.6%)")
print(f"   Échecs: {(y == 0).sum()} (39.4%)")

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

print(f"\n⏳ Entraînement...")
pipeline.fit(X_train, y_train)

# Évaluer
y_pred = pipeline.predict(X_test)
y_proba = pipeline.predict_proba(X_test)[:, 1]
accuracy = accuracy_score(y_test, y_pred)
roc_auc = roc_auc_score(y_test, y_proba)

print(f"\n" + "=" * 80)
print("🎯 RÉSULTATS FINALS")
print("=" * 80)
print(f"📊 Accuracy: {accuracy:.1%}")
print(f"📊 ROC-AUC:  {roc_auc:.1%}")

print(f"\n📈 PROGRESSION")
print(f"{'':25s} | Baseline | Initiale | Ultimate | Gain")
print(f"{'-' * 70}")
print(
    f"{'Accuracy':25s} | 50.0%    | 61.2%    | {accuracy:.1%}  | +{(accuracy - 0.612) * 100:+.1f}%"
)
print(
    f"{'ROC-AUC':25s} | 50.0%    | 69.6%    | {roc_auc:.1%}  | +{(roc_auc - 0.696) * 100:+.1f}%"
)
print(f"{'Features':25s} |    -     |    6     |   11    | +5")

# Sauvegarder
model_path = Path("models/prediction_success_model_ultimate.joblib")
model_path.parent.mkdir(exist_ok=True)
joblib.dump(pipeline, model_path)
print(f"\n💾 Modèle ULTIMATE: {model_path}")

# Métriques
metrics = {
    "version": "ultimate_with_elo_lambda",
    "accuracy": float(accuracy),
    "roc_auc": float(roc_auc),
    "samples": int(len(df_valid)),
    "features_count": len(ULTIMATE_FEATURES),
    "features": ULTIMATE_FEATURES,
    "improvements": {
        "accuracy_vs_baseline": float((accuracy - 0.5) * 100),
        "roc_auc_vs_baseline": float((roc_auc - 0.5) * 100),
        "accuracy_vs_initial": float((accuracy - 0.612) * 100),
        "roc_auc_vs_initial": float((roc_auc - 0.696) * 100),
    },
}

metrics_path = Path("models/prediction_success_metrics_ultimate.json")
metrics_path.write_text(json.dumps(metrics, indent=2))
print(f"💾 Métriques: {metrics_path}")

print(f"\n" + "=" * 80)
print("✅ MODÈLE ULTIMATE ENTRAÎNÉ & PRÊT POUR PRODUCTION!")
print("=" * 80)

# Show feature importance
print(f"\n📊 Importance des features:")
model = pipeline.named_steps["model"]
scaler = pipeline.named_steps["scaler"]
importance = np.abs(model.coef_[0])
for feat, imp in sorted(
    zip(ULTIMATE_FEATURES, importance), key=lambda x: x[1], reverse=True
):
    bar = "█" * int(imp * 50)
    print(f"   {feat:30s} {bar} ({imp:.3f})")
