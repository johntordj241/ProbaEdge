#!/usr/bin/env python3
"""
Rapport diagnostic Over/Under (2.5) pour la série de prédictions stockées.

Ce script examine `data/prediction_history.csv`, compare les probabilités Over/Under
calculées par le modèle avec le résultat réel (total de buts), et affiche les écarts
les plus importants pour aider à calibrer les lambda ou à identifier des matchs
où la formule diverge.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd


PREDICTION_HISTORY_PATH = Path("data/prediction_history.csv")


def _parse_score(score: Optional[str]) -> Optional[int]:
    if not isinstance(score, str) or "-" not in score:
        return None
    try:
        home, away = score.split("-", 1)
        return int(home.strip()) + int(away.strip())
    except ValueError:
        return None


def _to_datetime(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce", utc=True)
    return parsed


def _load_history(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{path} introuvable.")
    df = pd.read_csv(path)
    return df


def _build_report(
    df: pd.DataFrame, *, include_live: bool, min_rows: int
) -> pd.DataFrame:
    df = df.copy()
    df["fixture_date"] = _to_datetime(df.get("fixture_date"))
    df["total_goals"] = df.get("result_score").apply(_parse_score)
    df["over_real"] = df["total_goals"].apply(lambda value: 1 if value is not None and value >= 3 else 0)
    df["prob_over_2_5"] = pd.to_numeric(df.get("prob_over_2_5"), errors="coerce")
    df["prob_under_2_5"] = pd.to_numeric(df.get("prob_under_2_5"), errors="coerce")

    mask = df["prob_over_2_5"].notna() & df["total_goals"].notna()
    if not include_live:
        mask &= df["result_status"].fillna("").str.upper().isin({"FT", "AET", "PEN"})

    filtered = df.loc[mask]
    if filtered.empty:
        raise SystemExit("Aucun match terminé disponible.")

    filtered = filtered.assign(
        gap=(filtered["prob_over_2_5"] - filtered["over_real"]),
        lambda_home=pd.to_numeric(filtered.get("feature_lambda_home"), errors="coerce"),
        lambda_away=pd.to_numeric(filtered.get("feature_lambda_away"), errors="coerce"),
        fixture_label=filtered.get("home_team", "").fillna("Domicile")
        + " vs "
        + filtered.get("away_team", "").fillna("Extérieur"),
    )

    filtered["gap_percent"] = filtered["gap"].abs() * 100
    filtered.sort_values("gap_percent", ascending=False, inplace=True)
    return filtered.head(min_rows)


def _print_summary(report: pd.DataFrame) -> None:
    summary = report[["fixture_label", "fixture_date", "prob_over_2_5", "over_real", "gap_percent", "lambda_home", "lambda_away"]]
    summary["fixture_date"] = summary["fixture_date"].dt.strftime("%d/%m/%Y %H:%M")  # type: ignore[arg-type]
    print()
    print("Matchs avec les plus grands écarts Over 2.5 :")
    print("-" * 66)
    print(summary.to_string(index=False, float_format="%.1f", justify="left"))
    print()
    avg_gap = report["gap_percent"].mean() if not report.empty else 0
    print(f"Gap moyen (abs) : {avg_gap:.1f}%")


def _write_csv(report: pd.DataFrame, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(target, index=False)
    print(f"Diagnostic sauvegardé dans {target}")


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnostic Over/Under : affiche les matchs où la probabilité diverge le plus."
    )
    parser.add_argument("--limit", type=int, default=20, help="Nombre de matchs à afficher")
    parser.add_argument(
        "--include-live", action="store_true", help="Inclure aussi les matchs encore en cours"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Chemin CSV de sortie pour enregistrer le diagnostic",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    df = _load_history(PREDICTION_HISTORY_PATH)
    report = _build_report(
        df, include_live=args.include_live, min_rows=args.limit
    )
    _print_summary(report)
    if args.output:
        _write_csv(report, args.output)


if __name__ == "__main__":
    main()
