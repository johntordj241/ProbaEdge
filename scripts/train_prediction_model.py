#!/usr/bin/env python3
"""Entraîne les modèles ML utilisés par l'IA de pronostics.

Deux tâches sont gérées :
- Prédiction du vainqueur (multi-classe home/draw/away).
- Estimation de la réussite du pronostic principal (succès binaire).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    log_loss,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.prediction_history import export_prediction_dataset

FALLBACK_DATASET_PATH = Path("data") / "prediction_dataset.csv"
MIN_OUTCOME_SAMPLES = 30

FEATURE_COLUMNS = [
    "feature_home_draw_diff",
    "feature_home_away_diff",
    "feature_over_under_diff",
    "feature_max_prob",
    "feature_main_confidence_norm",
    "feature_total_pick_over",
]

ADDITIONAL_FEATURE_COLUMNS = [
    "feature_lambda_home",
    "feature_lambda_away",
    "elo_home",
    "elo_away",
    "delta_elo",
    "pressure_score",
    "intensity_score",
]

OUTCOME_FEATURE_COLUMNS = [
    "prob_home",
    "prob_draw",
    "prob_away",
    *FEATURE_COLUMNS,
    "prob_over_2_5",
    "prob_under_2_5",
    *ADDITIONAL_FEATURE_COLUMNS,
]


def _normalize_result(value: Any) -> str | None:
    token = str(value or "").strip().lower()
    if token in {"home", "domicile", "1"}:
        return "home"
    if token in {"away", "exterieur", "extérieur", "2"}:
        return "away"
    if token in {"draw", "nul", "x"}:
        return "draw"
    return None


def _prediction_side(row: pd.Series) -> str | None:
    pick = str(row.get("main_pick", "") or "").lower()
    home = str(row.get("home_team", "") or "").lower()
    away = str(row.get("away_team", "") or "").lower()
    if home and home in pick or "home" in pick or "1" in pick:
        return "home"
    if away and away in pick or "away" in pick or "2" in pick:
        return "away"
    if "nul" in pick or "draw" in pick or "x" in pick:
        return "draw"
    return None


def _compute_success(df: pd.DataFrame) -> pd.Series:
    sides = df.apply(_prediction_side, axis=1)
    result = df["result_winner"].astype(str).str.lower()
    success = []
    for side, res in zip(sides, result):
        if not side or not res or res in {"nan", ""}:
            success.append(np.nan)
        elif res in {"home", "domicile"}:
            success.append(1 if side == "home" else 0)
        elif res in {"away", "exterieur", "extérieur"}:
            success.append(1 if side == "away" else 0)
        elif res in {"draw", "nul"}:
            success.append(1 if side == "draw" else 0)
        else:
            success.append(np.nan)
    return pd.Series(success, index=df.index, dtype="float64")


def _brier_score_multiclass(y_true: np.ndarray, proba: np.ndarray, classes: np.ndarray) -> float:
    class_to_index = {str(label): idx for idx, label in enumerate(classes)}
    y_one_hot = np.zeros_like(proba)
    for i, label in enumerate(y_true):
        idx = class_to_index.get(str(label), None)
        if idx is not None:
            y_one_hot[i, idx] = 1.0
    return float(np.mean(np.sum((proba - y_one_hot) ** 2, axis=1)))


def _expected_calibration_error(
    y_true: np.ndarray,
    proba: np.ndarray,
    classes: np.ndarray,
    bins: int = 10,
) -> tuple[float, list[dict[str, float]]]:
    if proba.size == 0:
        return 0.0, []
    confidences = proba.max(axis=1)
    predictions = classes[proba.argmax(axis=1)]
    accuracies = (predictions.astype(str) == y_true.astype(str)).astype(float)
    bin_edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    curve: list[dict[str, float]] = []
    for idx in range(bins):
        mask = (confidences >= bin_edges[idx]) & (confidences < bin_edges[idx + 1])
        if not np.any(mask):
            continue
        bin_conf = confidences[mask].mean()
        bin_acc = accuracies[mask].mean()
        weight = mask.mean()
        ece += abs(bin_conf - bin_acc) * weight
        curve.append(
            {
                "bin_start": float(bin_edges[idx]),
                "bin_end": float(bin_edges[idx + 1]),
                "confidence": float(bin_conf),
                "accuracy": float(bin_acc),
                "weight": float(weight),
            }
        )
    return float(ece), curve


def load_dataset(output: Path | None = None) -> pd.DataFrame:
    dataset_path = export_prediction_dataset(str(output) if output else None)
    df = pd.read_csv(dataset_path)
    needs_fallback = False
    if len(df) < MIN_OUTCOME_SAMPLES:
        needs_fallback = True
    else:
        normalized = df.get("result_winner")
        if normalized is not None:
            normalized = normalized.map(_normalize_result)
            if normalized.dropna().nunique() < 2:
                needs_fallback = True
    if needs_fallback and FALLBACK_DATASET_PATH.exists():
        df = pd.read_csv(FALLBACK_DATASET_PATH)
    return df


def train_success_model(
    df: pd.DataFrame,
    *,
    model_path: Path,
    metrics_path: Path,
) -> Dict[str, Any]:
    dataset = df.copy()
    dataset["success"] = _compute_success(dataset)
    dataset.dropna(subset=["success"], inplace=True)
    dataset = dataset[dataset["success"].isin({0, 1})]

    if dataset.empty:
        raise SystemExit("Dataset vide : impossible d'entraîner le modèle de réussite.")

    X = dataset[FEATURE_COLUMNS]
    y = dataset["success"].astype(int)
    if pd.Series(y).nunique() < 2:
        metrics = {
            "status": "skipped",
            "reason": "Insufficient positive/negative samples",
            "samples": int(len(dataset)),
            "class_distribution": {str(k): int(v) for k, v in pd.Series(y).value_counts().to_dict().items()},
            "generated_at": pd.Timestamp.utcnow().isoformat(),
            "features": FEATURE_COLUMNS,
        }
        if model_path.exists():
            try:
                model_path.unlink()
            except Exception:
                pass
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        return metrics
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42,
        stratify=y,
    )

    model = LogisticRegression(max_iter=1000)
    model.fit(X_train, y_train)

    proba = model.predict_proba(X_test)[:, 1]
    preds = model.predict(X_test)
    accuracy = accuracy_score(y_test, preds)
    roc_auc = roc_auc_score(y_test, proba) if len(np.unique(y_test)) > 1 else float("nan")

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)

    metrics = {
        "accuracy": accuracy,
        "roc_auc": roc_auc,
        "samples": int(len(dataset)),
        "train_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "features": FEATURE_COLUMNS,
    }
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def train_outcome_model(
    df: pd.DataFrame,
    *,
    model_path: Path,
    metrics_path: Path,
) -> Dict[str, Any]:
    dataset = df.copy()
    dataset["result_norm"] = dataset["result_winner"].map(_normalize_result)
    dataset.dropna(subset=["result_norm"], inplace=True)

    if dataset.empty:
        raise SystemExit("Dataset vide : impossible d'entraîner le modèle outcome.")

    X = dataset[OUTCOME_FEATURE_COLUMNS].copy()
    y = dataset["result_norm"].astype(str)

    if pd.Series(y).nunique() < 2:
        metrics = {
            "status": "skipped",
            "reason": "Insufficient class diversity",
            "samples": int(len(dataset)),
            "class_distribution": {str(k): int(v) for k, v in pd.Series(y).value_counts().to_dict().items()},
            "generated_at": pd.Timestamp.utcnow().isoformat(),
        }
        if model_path.exists():
            try:
                model_path.unlink()
            except Exception:
                pass
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        return metrics

    pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    max_iter=2000,
                    multi_class="multinomial",
                    class_weight="balanced",
                ),
            ),
        ]
    )

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42,
        stratify=y,
    )

    pipeline.fit(X_train, y_train)

    proba = pipeline.predict_proba(X_test)
    preds = pipeline.predict(X_test)

    y_test_array = np.array(y_test)
    accuracy = accuracy_score(y_test, preds)
    logloss = log_loss(y_test, proba, labels=pipeline.classes_)
    report = classification_report(y_test, preds, output_dict=True)
    brier = _brier_score_multiclass(y_test_array, proba, pipeline.classes_)
    ece, reliability = _expected_calibration_error(y_test_array, proba, pipeline.classes_)

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_path)

    metrics = {
        "accuracy": accuracy,
        "log_loss": logloss,
        "samples": int(len(dataset)),
        "train_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
        "class_distribution": {str(k): int(v) for k, v in y.value_counts().to_dict().items()},
        "classification_report": report,
        "brier_score": brier,
        "ece": ece,
        "reliability_curve": reliability,
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "features": OUTCOME_FEATURE_COLUMNS,
        "classes": list(map(str, pipeline.classes_)),
    }
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Entraînement des modèles prédictifs IA")
    parser.add_argument("--output-dataset", type=Path, help="Chemin CSV temporaire pour le dataset exporté")
    parser.add_argument("--model-path", type=Path, default=Path("models") / "prediction_success_model.joblib")
    parser.add_argument("--metrics-path", type=Path, default=Path("models") / "prediction_success_metrics.json")
    parser.add_argument(
        "--outcome-model-path",
        type=Path,
        default=Path("models") / "match_outcome_model.joblib",
    )
    parser.add_argument(
        "--outcome-metrics-path",
        type=Path,
        default=Path("models") / "match_outcome_metrics.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = load_dataset(args.output_dataset)
    if df.empty:
        raise SystemExit("Dataset vide : aucune donnée disponible.")

    outcome_metrics = train_outcome_model(
        df,
        model_path=args.outcome_model_path,
        metrics_path=args.outcome_metrics_path,
    )
    outcome_status = outcome_metrics.get("status")
    if outcome_status == "skipped":
        print("Modèle outcome ignoré (échantillon insuffisant) :", args.outcome_model_path)
    else:
        print("Modèle outcome entraîné :", args.outcome_model_path)
    print(json.dumps(outcome_metrics, indent=2))

    success_metrics = train_success_model(
        df,
        model_path=args.model_path,
        metrics_path=args.metrics_path,
    )
    success_status = success_metrics.get("status")
    if success_status == "skipped":
        print("Modèle de succès ignoré (échantillon insuffisant) :", args.model_path)
    else:
        print("Modèle de succès entraîné :", args.model_path)
    print(json.dumps(success_metrics, indent=2))


if __name__ == "__main__":
    main()
