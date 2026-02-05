from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

try:
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore

from .bankroll import BankrollSettings, suggest_stake
from .chat_prompts import build_system_prompt
from .prediction_history import load_prediction_history
from .profile import get_bankroll_settings
from .secrets import get_secret
from .supabase_client import get_supabase_client

CHAT_MODEL = "gpt-4-turbo"
EMBED_MODEL = "text-embedding-3-large"
GLOBAL_EDGE_THRESHOLD = 0.05
HISTORY_ROLLING_WINDOW = 50


def _ensure_openai_key() -> str:
    return get_secret(
        "OPENAI_API_KEY",
        required=True,
        hint="OPENAI_API_KEY manquante. Ajoutez-la a votre fichier .env.",
    )


@lru_cache(maxsize=1)
def _history_dataframe() -> pd.DataFrame:
    try:
        return load_prediction_history()
    except Exception:
        return pd.DataFrame()


def _safe_float(value: Any) -> Optional[float]:
    if value in {None, "", "nan"}:
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _extract_percentage(text: Any) -> Optional[float]:
    if not text:
        return None
    matches = re.findall(r"(-?\d+(?:\.\d+)?)\s*%", str(text))
    if not matches:
        return None
    try:
        return float(matches[-1]) / 100.0
    except ValueError:
        return None


def _compute_history_stats(df: pd.DataFrame) -> Dict[str, Any]:
    stats = {
        "total_rows": int(len(df)),
        "tracked_matches": 0,
        "roi_total": 0.0,
        "roi_recent": 0.0,
        "win_rate_recent": 0.0,
    }
    if df.empty:
        return stats

    finished = df[df["result_status"].fillna("").str.len() > 0]
    stats["tracked_matches"] = int(len(finished))

    stake_series = finished.get("bet_stake")
    return_series = finished.get("bet_return")
    total_stake = 0.0
    if stake_series is not None and return_series is not None:
        total_stake = float(pd.to_numeric(stake_series, errors="coerce").fillna(0).sum())
        total_return = float(pd.to_numeric(return_series, errors="coerce").fillna(0).sum())
        if total_stake > 0:
            stats["roi_total"] = (total_return - total_stake) / total_stake

    recent = finished.tail(HISTORY_ROLLING_WINDOW)
    if not recent.empty and total_stake > 0:
        stake_recent = float(pd.to_numeric(recent.get("bet_stake"), errors="coerce").fillna(0).sum())
        return_recent = float(pd.to_numeric(recent.get("bet_return"), errors="coerce").fillna(0).sum())
        if stake_recent > 0:
            stats["roi_recent"] = (return_recent - stake_recent) / stake_recent

    if "bet_result" in recent.columns:
        wins = recent["bet_result"].str.lower().eq("win").sum()
        losses = recent["bet_result"].str.lower().eq("lose").sum()
        total = wins + losses
        if total > 0:
            stats["win_rate_recent"] = wins / total

    return stats


def _probability_from_row(row: pd.Series) -> Tuple[Optional[float], str]:
    probs = {
        "home": _safe_float(row.get("prob_home")),
        "draw": _safe_float(row.get("prob_draw")),
        "away": _safe_float(row.get("prob_away")),
    }
    target = max(probs, key=lambda key: probs[key] or 0)
    return probs[target], target


def _find_high_probability_matches(
    df: pd.DataFrame,
    threshold: float = 0.7,
    limit: int = 5,
    horizon_days: int = 7,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    if df.empty:
        return results
    candidates = df.tail(200).copy()

    if "fixture_date" in candidates.columns:
        fixture_dates = pd.to_datetime(candidates.get("fixture_date"), errors="coerce", utc=True)
        now = pd.Timestamp.now(tz=timezone.utc)
        horizon = now + pd.Timedelta(days=horizon_days)
        future_mask = fixture_dates.notna() & (fixture_dates >= now)
        window_mask = future_mask & (fixture_dates <= horizon)
        if window_mask.any():
            candidates = candidates.loc[window_mask]
        elif future_mask.any():
            candidates = candidates.loc[future_mask]

    for _, row in candidates.iterrows():
        prob, direction = _probability_from_row(row)
        if prob is None or prob < threshold:
            continue
        edge = _extract_percentage(row.get("edge_comment"))
        match_label = f"{row.get('home_team', 'Equipe A')} vs {row.get('away_team', 'Equipe B')}"
        odds = _safe_float(row.get("bet_odd")) or _safe_float(row.get("main_odds"))
        results.append(
            {
                "match": match_label,
                "direction": direction,
                "probability": prob,
                "edge": edge,
                "league": row.get("league_id"),
                "fixture_id": row.get("fixture_id"),
                "odds": odds,
            }
        )
    results.sort(key=lambda item: (item["probability"] or 0), reverse=True)
    return results[:limit]


def _bankroll_settings() -> BankrollSettings:
    data = get_bankroll_settings()
    return BankrollSettings.from_dict(data)


def _kelly_recommendation(match: Dict[str, Any], settings: BankrollSettings) -> Dict[str, Any]:
    prob = match.get("probability") or 0.0
    odds = match.get("odds")
    stake_info = suggest_stake(probability=prob, odds=odds, settings=settings)
    return {
        "stake": stake_info["stake"],
        "edge": stake_info["edge"],
        "expected_profit": stake_info["expected_profit"],
        "odds": stake_info["odds"],
        "status": stake_info["status"],
    }


def _call_openai_chat(messages: List[Dict[str, str]]) -> str:
    api_key = _ensure_openai_key()
    if OpenAI is None:
        raise RuntimeError("Le package openai est requis pour l'assistant.")
    client = OpenAI(api_key=api_key)
    try:
        response = client.responses.create(
            model=CHAT_MODEL,
            temperature=0.15,
            max_output_tokens=600,
            input=messages,
        )
    except Exception as exc:  # pragma: no cover - dépendance externe
        lowered = str(exc).lower()
        if "invalid api key" in lowered or "incorrect api key" in lowered or "401" in lowered:
            raise RuntimeError(
                "Clé OpenAI refusée (401). Vérifie OPENAI_API_KEY ou régénère une clé valide."
            ) from exc
        raise RuntimeError(f"Impossible d'interroger OpenAI : {exc}") from exc

    text = getattr(response, "output_text", None)
    if text:
        return text.strip()
    output = getattr(response, "output", None) or []
    chunks: List[str] = []
    for block in output:
        content = getattr(block, "content", [])
        for item in content:
            snippet = item.get("text")
            if snippet:
                chunks.append(snippet)
    if chunks:
        return "\n".join(chunks).strip()
    raise RuntimeError("Réponse OpenAI vide.")


def _store_memory_entry(user_id: str, question: str, answer: str) -> None:
    try:
        client = get_supabase_client()
    except Exception:
        return
    embedding = None
    if OpenAI is not None:
        try:
            openai_client = OpenAI(api_key=_ensure_openai_key())
            response = openai_client.embeddings.create(
                model=EMBED_MODEL,
                input=question + "\n" + answer,
            )
            embedding = response.data[0].embedding
        except Exception:
            embedding = None
    payload = {
        "user_id": user_id,
        "question": question,
        "answer": answer,
        "embedding": embedding,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        client.table("chat_memory").insert(payload).execute()
    except Exception:
        return


def _load_memory_entries(user_id: str, limit: int = 3) -> List[Dict[str, str]]:
    try:
        client = get_supabase_client()
    except Exception:
        return []
    try:
        response = (
            client.table("chat_memory")
            .select("question,answer")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception:
        return []
    entries = response.data or []
    messages: List[Dict[str, str]] = []
    for entry in reversed(entries):
        if entry.get("question"):
            messages.append({"role": "user", "content": entry["question"]})
        if entry.get("answer"):
            messages.append({"role": "assistant", "content": entry["answer"]})
    return messages


def _build_context_summary(
    stats: Dict[str, Any],
    matches: List[Dict[str, Any]],
    bankroll: BankrollSettings,
) -> str:
    summary = {
        "history_stats": stats,
        "top_matches": matches,
        "bankroll": {
            "amount": bankroll.amount,
            "strategy": bankroll.strategy,
            "percent": bankroll.percent,
            "kelly_fraction": bankroll.kelly_fraction,
            "min_stake": bankroll.min_stake,
            "max_stake": bankroll.max_stake,
        },
        "guardrails": {
            "edge_min": GLOBAL_EDGE_THRESHOLD,
            "philosophy": "discipline, pas d'urgence, abstention acceptable",
        },
    }
    return json.dumps(summary, ensure_ascii=False)


def handle_chat_query(user_message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    context = context or {}
    user_id = context.get("user_id") or "anonymous"

    df = _history_dataframe()
    stats = _compute_history_stats(df)
    matches = _find_high_probability_matches(df)
    bankroll = _bankroll_settings()

    kelly_block = {}
    if matches:
        kelly_block = _kelly_recommendation(matches[0], bankroll)

    summary = _build_context_summary(stats, matches, bankroll)
    system_prompt = build_system_prompt(context.get("extra") or "")
    memory_messages = _load_memory_entries(user_id)

    assistant_context = (
        f"Question utilisateur : {user_message}\n"
        f"Resume des donnees : {summary}\n"
        "Reponds en restant neutre, factuel et en rappelant les garde-fous."
    )

    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages.extend(memory_messages)
    messages.append({"role": "user", "content": assistant_context})

    answer = _call_openai_chat(messages)
    _store_memory_entry(user_id, user_message, answer)

    return {
        "answer": answer,
        "metadata": {
            "history_stats": stats,
            "top_matches": matches,
            "bankroll": {
                "amount": bankroll.amount,
                "strategy": bankroll.strategy,
                "percent": bankroll.percent,
                "kelly_fraction": bankroll.kelly_fraction,
            },
            "kelly": kelly_block,
        },
    }


__all__ = ["handle_chat_query"]
