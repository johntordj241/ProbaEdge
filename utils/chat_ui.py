from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

from .ai_.module import is_openai_configured
from .chat_assistant import handle_chat_query

SUGGESTED_QUESTIONS = [
    "Quels matchs depassent 70% de proba ce week-end ?",
    "Calcule la mise recommandee sur mon edge favori",
    "Quelles sont mes perfs sur les 50 derniers paris ?",
    "Dois-je passer mon tour si l'edge est <5% ?",
]

WELCOME_MESSAGE = (
    "Assistant ProbaEdge connecte au moteur Poisson/Dixon-Coles + Elo + calibration ML. "
    "Je t'aide a analyser les matchs, comprendre les edges et gerer la bankroll sans jamais pousser a miser."
)

ASSISTANT_EXTRA_CONTEXT = (
    "Combine trois voix : (1) moteur probabiliste interne, (2) pronostiqueur senior discipline, (3) journaliste foot. "
    "Expose les facteurs clefs (formules, absents, edge, Kelly) et rappelle que l'abstention est une option rationnelle."
)


def _history() -> List[Dict[str, Any]]:
    history = st.session_state.setdefault("assistant_messages", [])
    if not history:
        history.append({"role": "assistant", "content": WELCOME_MESSAGE})
    return history


def _user_identifier() -> str:
    user = st.session_state.get("auth_user") or {}
    return (user.get("email") or user.get("name") or "anonymous")


def _format_pct(value: Optional[float], precision: int = 1) -> str:
    if value is None:
        return "ND"
    return f"{value * 100:.{precision}f}%"


def _format_currency(value: Optional[float]) -> str:
    if value is None:
        return "ND"
    return f"{value:,.0f}".replace(",", " ")


def _render_metadata(metadata: Dict[str, Any]) -> None:
    stats = metadata.get("history_stats") or {}
    matches = metadata.get("top_matches") or []
    bankroll = metadata.get("bankroll") or {}
    kelly = metadata.get("kelly") or {}

    with st.expander("Contexte chiffre de l'analyse", expanded=False):
        if stats:
            cols = st.columns(3)
            cols[0].metric("Matchs suivis", stats.get("tracked_matches", 0))
            cols[1].metric("ROI total", _format_pct(stats.get("roi_total")))
            cols[2].metric("Win rate 50 derniers", _format_pct(stats.get("win_rate_recent")))
        if bankroll:
            st.caption(
                "Bankroll: "
                f"strategie {bankroll.get('strategy', 'n/a')} | montant {_format_currency(bankroll.get('amount'))} | "
                f"kelly {bankroll.get('kelly_fraction', 0):.2f}"
            )
        if matches:
            st.markdown("**Matchs a forte proba detectes**")
            for match in matches:
                prob = _format_pct(match.get("probability"))
                edge = _format_pct(match.get("edge")) if match.get("edge") is not None else "N/A"
                direction = str(match.get("direction", "?"))
                st.markdown(
                    f"- {match.get('match', 'Match inconnu')} - {direction.upper()} - {prob} - edge {edge}"
                )
        if kelly:
            st.markdown("**Mise suggeree (filtre bankroll)**")
            st.write(
                f"Stake: {kelly.get('stake', 0)} | edge modele: {_format_pct(kelly.get('edge'))} | "
                f"gain attendu: {kelly.get('expected_profit', 0)} | statut: {kelly.get('status', 'n/a')}"
            )


def _render_history(history: List[Dict[str, Any]]) -> None:
    for message in history:
        role = message.get("role", "assistant")
        content = message.get("content", "")
        metadata = message.get("metadata")
        with st.chat_message(role):
            st.markdown(content)
            if role == "assistant" and metadata:
                _render_metadata(metadata)


def _process_prompt(prompt: str, history: List[Dict[str, Any]]) -> None:
    history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyse des edges, du ROI et des filtres bankroll..."):
            try:
                result = handle_chat_query(
                    prompt,
                    context={
                        "user_id": _user_identifier(),
                        "extra": ASSISTANT_EXTRA_CONTEXT,
                    },
                )
            except Exception as exc:  # pragma: no cover - dependances externes
                answer = f"Assistant indisponible : {exc}"
                history.append({"role": "assistant", "content": answer})
                st.error(answer)
            else:
                answer = result.get("answer", "")
                metadata = result.get("metadata")
                history.append({"role": "assistant", "content": answer, "metadata": metadata})
                st.markdown(answer)
                if metadata:
                    _render_metadata(metadata)


def _render_suggestions(history: List[Dict[str, Any]]) -> None:
    st.markdown("**Questions rapides**")
    cols = st.columns(2)
    for idx, question in enumerate(SUGGESTED_QUESTIONS):
        col = cols[idx % 2]
        if col.button(question, key=f"assistant_suggestion_{idx}"):
            _process_prompt(question, history)
            st.experimental_rerun()


def show_chat_assistant() -> None:
    st.title("Assistant IA ProbaEdge")
    st.caption(
        "GPT-4-turbo + moteur interne. Ton neutre, pas d'incitation a miser, rappel systematique des garde-fous."
    )

    history = _history()
    _render_suggestions(history)
    _render_history(history)

    if not is_openai_configured():
        st.warning("OPENAI_API_KEY manquante. Ajoute la cle dans ton fichier .env pour activer l'assistant.")
        return

    prompt = st.chat_input(
        "Pose une question sur les predictions, la bankroll ou ton historique",
    )

    if not prompt:
        return

    _process_prompt(prompt, history)


__all__ = ["show_chat_assistant"]
