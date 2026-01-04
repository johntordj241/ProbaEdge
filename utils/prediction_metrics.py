from __future__ import annotations

from typing import Any, Optional

import pandas as pd


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip().lower()
    return str(value).strip().lower()


def _has_excluded_keyword(text: str) -> bool:
    keywords = {
        "double chance",
        "over",
        "under",
        "buts",
        "handicap",
        "btts",
        "buteur",
        "score exact",
        "carton",
        "corners",
        "total",
    }
    return any(keyword in text for keyword in keywords)


def _prediction_side(row: pd.Series) -> Optional[str]:
    home = _normalize_text(row.get("home_team"))
    away = _normalize_text(row.get("away_team"))
    candidates = [
        _normalize_text(row.get("main_pick")),
        _normalize_text(row.get("bet_selection")),
    ]
    for text in candidates:
        if not text:
            continue
        if _has_excluded_keyword(text):
            continue
        if home and home in text:
            return "home"
        if away and away in text:
            return "away"
        if "match nul" in text or "nul" in text or "draw" in text or text.strip() == "x":
            return "draw"
        if "victoire domicile" in text or "gagne domicile" in text:
            return "home"
        if "victoire exterieur" in text or "gagne exterieur" in text:
            return "away"
    return None


def compute_success_flag(row: pd.Series) -> Optional[bool]:
    result = _normalize_text(row.get("result_winner"))
    if not result:
        return None
    side = _prediction_side(row)
    if not side:
        return None
    if any(token in result for token in {"home", "domicile", "1"}):
        return side == "home"
    if any(token in result for token in {"away", "exterieur", "2"}):
        return side == "away"
    if any(token in result for token in {"draw", "nul", "x"}):
        return side == "draw"
    return None


def ensure_success_flag(df: pd.DataFrame) -> pd.DataFrame:
    if "success_flag" in df.columns:
        return df
    df = df.copy()
    df["success_flag"] = df.apply(compute_success_flag, axis=1)
    return df


__all__ = ["compute_success_flag", "ensure_success_flag"]
