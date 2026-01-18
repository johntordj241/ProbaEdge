#!/usr/bin/env python3
"""Entraîne les modèles avec le dataset enrichi (prediction_dataset.csv)"""

import json
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

# Colonnes de features
FEATURE_COLUMNS = [
    "feature_home_draw_diff",
    "feature_home_away_diff",
    "feature_over_under_diff",
    "feature_max_prob",
    "feature_main_confidence_norm",
    "feature_total_pick_over",
]

# Charger le dataset
df = pd.read_csv("data/prediction_dataset_enriched.csv")
print(f"📊 Dataset chargé: {len(df)} lignes")

# Filtrer les lignes avec success
df_valid = df[df["success"].notna()].copy()
print(f"✅ Prédictions avec succès: {len(df_valid)}")

if len(df_valid) < 30:
    print("❌ Pas assez de données!")
    exit(1)

# Préparer les données
X = df_valid[FEATURE_COLUMNS].copy()
y = df_valid["success"].astype(int)

print(f"\n📈 Features utilisées: {len(FEATURE_COLUMNS)}")
print(f"📊 Distribution classes:")
print(f"   Succès (1): {(y == 1).sum()}")
print(f"   Échec (0): {(y == 0).sum()}")

# Split train/test
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, random_state=42, stratify=y
)

print(f"\n🔄 Train: {len(X_train)}, Test: {len(X_test)}")

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

print(f"\n✅ Modèle entraîné!")
print(f"📊 Accuracy: {accuracy:.1%}")
print(f"📊 ROC-AUC: {roc_auc:.1%}")

# Sauvegarder
model_path = Path("models/prediction_success_model_v2.joblib")
model_path.parent.mkdir(exist_ok=True)
joblib.dump(pipeline, model_path)
print(f"💾 Modèle sauvegardé: {model_path}")

# Sauvegarder les métriques
metrics = {
    "accuracy": float(accuracy),
    "roc_auc": float(roc_auc),
    "samples": int(len(df_valid)),
    "train_samples": int(len(X_train)),
    "test_samples": int(len(X_test)),
    "features": FEATURE_COLUMNS,
    "class_distribution": {
        "success": int((y == 1).sum()),
        "fail": int((y == 0).sum()),
    },
}

metrics_path = Path("models/prediction_success_metrics_v2.json")
metrics_path.write_text(json.dumps(metrics, indent=2))
print(f"💾 Métriques sauvegardées: {metrics_path}")
print(f"\n{json.dumps(metrics, indent=2)}")
