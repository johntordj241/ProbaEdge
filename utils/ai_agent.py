from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd

from .ai_.module import analyse_match_with_ai, is_openai_configured
from .profile import get_bankroll_settings, get_alert_settings, get_ai_preferences
from .prediction_history import load_prediction_history


MIN_EDGE = 5.0  # en %


@dataclass
class CoachResponse:
    answer: str
    context: Dict[str, Any]


def _recent_edges(limit: int = 5) -> List[Dict[str, Any]]:
    df = load_prediction_history()
    if df.empty:
        return []
    df = df.copy()
    df["edge_pct"] = pd.to_numeric(df.get("edge_comment"), errors="coerce")
    df = df[df["edge_pct"] >= MIN_EDGE].sort_values("timestamp", ascending=False)
    picks: List[Dict[str, Any]] = []
    for _, row in df.head(limit).iterrows():
        picks.append(
            {
                "match": f"{row.get('home_team')} vs {row.get('away_team')}",
                "edge_pct": float(row["edge_pct"]),
                "selection": row.get("main_pick"),
                "confidence": row.get("main_confidence"),
                "odd": row.get("bet_odd") or row.get("main_odds"),
                "status": row.get("status_snapshot"),
            }
        )
    return picks


def build_coach_context(question: str) -> Dict[str, Any]:
    bankroll = get_bankroll_settings()
    alerts = get_alert_settings()
    ai_prefs = get_ai_preferences()
    edges = _recent_edges()
    if not edges:
        raise ValueError("Aucun match avec edge >= 5% n'est disponible.")
    return {
        "question": question,
        "bankroll": bankroll,
        "edge_threshold_pct": alerts.get("edge_threshold_pct", MIN_EDGE),
        "edges": edges,
        "ai_style": ai_prefs.get("analysis_instruction") or "",
    }


def ask_coach(question: str) -> CoachResponse:
    if not is_openai_configured():
        raise RuntimeError("Configuration OpenAI manquante (OPENAI_API_KEY).")
    try:
        context = build_coach_context(question)
    except ValueError as exc:
        return CoachResponse(answer=str(exc), context={})
    payload = {
        "question": context["question"],
        "bankroll": context["bankroll"],
        "edge_threshold_pct": context["edge_threshold_pct"],
        "edges": context["edges"],
    }
    instruction = (
        "Tu es Coach Edge : pronostiqueur expérimenté et journaliste foot. "
        "Réponds en français avec : 1) synthèse rapide, 2) matches recommandés (max 3) "
        "avec edge, selection, mise conseillée (respecte la stratégie bankroll), "
        "3) rappel des risques. "
        "N'invente rien : si la question sort du cadre paris sportifs, explique-le."
    )
    if context["ai_style"]:
        instruction += f" Style supplementaire : {context['ai_style']}."
    analysis = analyse_match_with_ai(payload, instruction)
    answer = analysis.get("content") if isinstance(analysis, dict) else str(analysis)
    return CoachResponse(answer=answer, context=payload)


__all__ = ["ask_coach", "build_coach_context", "CoachResponse"]
