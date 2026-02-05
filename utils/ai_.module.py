from __future__ import annotations

import json
from datetime import date, datetime
from functools import lru_cache
from typing import Any, Mapping

import openai

from .secrets import get_secret

try:
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover - compat pour anciennes versions
    OpenAI = None  # type: ignore[assignment]

OPENAI_API_KEY_ENV = "=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"
SYSTEM_PROMPT = (
    "Tu es l'assistant IA de Proba Edge. Tu produis une analyse claire et actionnable "
    "en trois points maximum : 1) dynamique et score probable, 2) opportunité ou absence d'edge, "
    "3) risques à surveiller (blessures, météo, discipline). Tu ne donnes pas de conseils financiers "
    "et tu rappelles de comparer les cotes."
)
MAX_INPUT_CHARS = 6000


class AIAnalysisError(RuntimeError):
    """Erreur lors de l'analyse IA externe."""


def _ensure_openai_key() -> str:
    api_key = get_secret(
        OPENAI_API_KEY_ENV,
        required=True,
        hint="OPENAI_API_KEY manquante. Ajoutez-la à votre .env (non versionné) ou à votre gestionnaire de secrets.",
    )
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY manquante. Ajoutez-la à votre .env (non versionné) ou à votre gestionnaire de secrets."
        )
    return api_key


def is_openai_configured() -> bool:
    """Indique si une clé OpenAI est disponible (sans lever d'exception)."""
    return bool(get_secret(OPENAI_API_KEY_ENV))


@lru_cache(maxsize=1)
def _get_openai_client() -> Any:
    api_key = _ensure_openai_key()
    if OpenAI is not None:
        return OpenAI(api_key=api_key)
    openai.api_key = api_key
    return openai


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _compact_payload(match_data: Mapping[str, Any]) -> str:
    try:
        payload = json.dumps(match_data, ensure_ascii=False, default=_json_default)
    except TypeError:
        payload = str(match_data)
    if len(payload) > MAX_INPUT_CHARS:
        payload = payload[:MAX_INPUT_CHARS] + "... (tronqué)"
    return payload


def _call_chat_completion(messages: list[dict[str, str]], *, model: str) -> str:
    client = _get_openai_client()
    if hasattr(client, "responses"):
        response = client.responses.create(
            model=model,
            temperature=0.2,
            input=messages,
        )
        text = getattr(response, "output_text", None)
        if text:
            return text.strip()
        output = getattr(response, "output", None) or []
        chunks: list[str] = []
        for block in output:
            content = getattr(block, "content", [])
            for item in content:
                snippet = item.get("text")
                if snippet:
                    chunks.append(snippet)
        if chunks:
            return "\n".join(chunks).strip()
        raise AIAnalysisError("Réponse OpenAI vide.")
    completion = client.ChatCompletion.create(
        model=model,
        temperature=0.2,
        messages=messages,
    )
    try:
        return completion["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:  # pragma: no cover
        raise AIAnalysisError(f"Réponse OpenAI inattendue : {completion}") from exc


def analyse_match_with_ai(
    match_data: Mapping[str, Any], *, model: str = "gpt-4o-mini"
) -> str:
    """
    Analyse un match via OpenAI à partir d'un dictionnaire de contexte/faits (probabilités en %).
    """
    summary = _compact_payload(match_data)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Analyse ces données JSON (probabilités en %) et fournis trois puces : "
                "1) dynamique / score probable, 2) opportunité ou edge potentiel, "
                "3) risques ou facteurs de prudence. "
                "Rappelle de vérifier les cotes avant d'agir.\n"
                f"{summary}"
            ),
        },
    ]
    try:
        return _call_chat_completion(messages, model=model)
    except AIAnalysisError:
        raise
    except Exception as exc:  # pragma: no cover - dépendance externe
        raise AIAnalysisError(f"Impossible d'interroger OpenAI : {exc}") from exc


__all__ = ["analyse_match_with_ai", "is_openai_configured", "AIAnalysisError"]
