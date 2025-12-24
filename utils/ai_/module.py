from __future__ import annotations

import json
from datetime import date, datetime
from functools import lru_cache
from typing import Any, Mapping

import openai

from ..secrets import get_secret

try:
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover - compat pour anciennes versions
    OpenAI = None  # type: ignore[assignment]

OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
SYSTEM_PROMPT = (
    "Tu es l'assistant IA de Proba Edge. Tu produis une analyse claire et actionnable "
    "en trois points maximum : 1) dynamique et score probable, 2) opportunité ou absence d'edge, "
    "3) risques à surveiller (blessures, météo, discipline). Tu ne donnes pas de conseils financiers "
    "et tu rappelles de comparer les cotes."
)
COMMENTATOR_PROMPT = (
    "Tu es le commentateur TV officiel de Proba Edge, en direct sur un match de football. "
    "Tu gardes un ton dynamique, professionnel et en francais moderne. "
    "Tu restitues l'ambiance, le score, les faits marquants (cartons, blessures, penalties) "
    "et relies ces elements aux statistiques fournies (tirs cadres, xG, possession, intensite). "
    "Tu ne donnes jamais de conseils financiers."
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


def _friendly_openai_error(exc: Exception) -> AIAnalysisError:
    message = str(exc)
    lowered = message.lower()
    auth_tokens = [
        "incorrect api key",
        "invalid api key",
        "api key provided",
        "authentication",
        "401",
    ]
    if any(token in lowered for token in auth_tokens):
        return AIAnalysisError(
            "Clé OpenAI refusée (401). Vérifie OPENAI_API_KEY dans ton fichier .env ou régénère une clé valide "
            "depuis https://platform.openai.com/account/api-keys, puis relance l'application."
        )
    return AIAnalysisError(f"Impossible d'interroger OpenAI : {exc}")


def analyse_match_with_ai(
    match_data: Mapping[str, Any],
    *,
    model: str = "gpt-4o-mini",
    instruction: str | None = None,
) -> str:
    """
    Analyse un match via OpenAI à partir d'un dictionnaire de contexte/faits (probabilités en %).
    """
    summary = _compact_payload(match_data)
    user_content = (
        "Analyse ces données JSON (probabilités en %) et fournis trois puces : "
        "1) dynamique / score probable, 2) opportunité ou edge potentiel, "
        "3) risques ou facteurs de prudence. "
        "Rappelle de vérifier les cotes avant d'agir.\n"
        f"{summary}"
    )
    if instruction:
        user_content += f"\nContexte supplémentaire : {instruction}"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": user_content,
        },
    ]
    try:
        return _call_chat_completion(messages, model=model)
    except AIAnalysisError:
        raise
    except Exception as exc:  # pragma: no cover - dépendance externe
        raise _friendly_openai_error(exc) from exc



def commentate_match_with_ai(
    match_data: Mapping[str, Any],
    *,
    model: str = "gpt-4o-mini",
    instruction: str | None = None,
) -> str:
    """
    Produit un commentaire live facon TV a partir du meme socle de donnees JSON.
    """
    summary = _compact_payload(match_data)
    user_content = (
        "Decris le match comme un commentateur TV en deux courts paragraphes : "
        "1) l'ambiance en direct (minute, score, intensite, incidents) ; "
        "2) l'analyse tactique/statistique (tirs cadres, xG, possession, cartons, pression). "
        "Cite explicitement les chiffres importants et termine par une phrase qui projette la suite du match.\n"
        f"{summary}"
    )
    if instruction:
        user_content += f"\nConsigne supplementaire : {instruction}"
    messages = [
        {"role": "system", "content": COMMENTATOR_PROMPT},
        {
            "role": "user",
            "content": user_content,
        },
    ]
    try:
        return _call_chat_completion(messages, model=model)
    except AIAnalysisError:
        raise
    except Exception as exc:  # pragma: no cover
        raise _friendly_openai_error(exc) from exc


__all__ = ["analyse_match_with_ai", "commentate_match_with_ai", "is_openai_configured", "AIAnalysisError"]
