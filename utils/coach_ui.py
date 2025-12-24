from __future__ import annotations

import unicodedata
from typing import Any, Dict, List, Optional

import streamlit as st

from .ai_.module import is_openai_configured
from .chat_assistant import handle_chat_query

SUGGESTIONS = [
    "Quels parametres degradent cette estimation ?",
    "Quels filtres bloquent ce match ?",
    "Quelles hypotheses restent fragiles ici ?",
    "Pourquoi aucune recommandation n'est proposee ?",
]

PROHIBITED_PATTERNS = [
    "combien miser",
    "combien dois-je miser",
    "combien devrais-je miser",
    "quel pari",
    "quel match a le plus d'edge",
    "edge le plus eleve",
    "faut-il parier",
    "dois-je parier",
    "parier ici",
    "parier sur",
    "mise optimale",
    "mise max",
]

PROHIBITED_KEYWORDS = ["mise", "miser", "pari", "parier", "edge le plus"]

REFUSAL_MESSAGE = (
    "Je n'autorise ni pari ni indication de mise. Formule plutôt une question sur les "
    "parametres, filtres ou incertitudes a analyser."
)

_WIDGET_STYLE = """
<style>
#coach-edge-wrapper {
    position: fixed;
    bottom: 18px;
    right: 18px;
    z-index: 960;
    width: min(360px, 92vw);
    font-size: 0.85rem;
}
#coach-edge-wrapper .coach-toggle .stButton>button {
    width: 100%;
    border-radius: 999px;
    border: 1px solid #2b3042;
    background: #121522;
    color: #f2f2f2;
    font-size: 0.8rem;
    font-weight: 500;
}
#coach-edge-wrapper.open .coach-toggle .stButton>button {
    background: #1b1f30;
}
#coach-edge-wrapper.closed .coach-panel {
    display: none;
}
#coach-edge-wrapper .coach-panel {
    margin-top: 0.4rem;
    background: #0d101b;
    border-radius: 16px;
    border: 1px solid #2b3042;
    padding: 0.85rem;
    box-shadow: 0 12px 32px rgba(0,0,0,0.45);
}
#coach-edge-wrapper .suggestions .stButton>button {
    width: 100%;
    font-size: 0.74rem;
    border-radius: 999px;
    background: #151828;
    border: 1px solid #2b3042;
    color: #e7e7ec;
}
#coach-edge-wrapper .message {
    border-radius: 10px;
    padding: 0.5rem 0.65rem;
    margin-bottom: 0.4rem;
    font-size: 0.82rem;
}
#coach-edge-wrapper .message.user {
    background: #1d202f;
    border: 1px solid #2c3040;
}
#coach-edge-wrapper .message.assistant {
    background: #121522;
    border: 1px solid #272b3d;
}
</style>
"""

COACH_EXTRA_CONTEXT = (
    "Coach IA institutionnel : reponds en moins de 120 mots, explique les parametres, "
    "les filtres et les raisons d'incertitude. Tu peux refuser les demandes orientées "
    "mise, pari ou avantage. Rappelle que s'abstenir reste une issue valide."
)


def _history() -> List[Dict[str, Any]]:
    return st.session_state.setdefault("coach_chat_history", [])


def _normalize_question(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    normalized = normalized.replace("’", "'").replace("‘", "'").replace("`", "'")
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return stripped.lower()


def _state() -> Dict[str, bool]:
    return st.session_state.setdefault("coach_widget_state", {"open": False})


def _ensure_question_buffer() -> None:
    st.session_state.setdefault("coach_question_input", "")


def _user_identifier() -> str:
    user = st.session_state.get("auth_user") or {}
    ident = user.get("email") or user.get("name")
    if ident:
        return f"coach#{ident}"
    return "coach#anonymous"


def _set_last_error(message: str) -> None:
    st.session_state["coach_last_error"] = message


def _clear_last_error() -> None:
    st.session_state.pop("coach_last_error", None)


def _requires_refusal(question: str) -> bool:
    normalized = _normalize_question(question)
    if any(pattern in normalized for pattern in PROHIBITED_PATTERNS):
        return True
    return any(keyword in normalized for keyword in PROHIBITED_KEYWORDS)


def _refusal_reply() -> str:
    return REFUSAL_MESSAGE + " Les donnees actuelles ne justifient aucune action."


def _format_pct(value: Optional[float]) -> str:
    if value is None:
        return "ND"
    return f"{value * 100:.1f}%"


def _metadata_summary(metadata: Dict[str, Any]) -> Optional[str]:
    stats = metadata.get("history_stats") or {}
    matches = metadata.get("top_matches") or []
    kelly = metadata.get("kelly") or {}
    parts: List[str] = []
    roi = stats.get("roi_total")
    if roi not in (None, ""):
        parts.append(f"ROI {_format_pct(roi)}")
    if matches:
        best = matches[0]
        prob = _format_pct(best.get("probability"))
        edge_value = best.get("edge")
        edge = _format_pct(edge_value) if edge_value is not None else "ND"
        direction = str(best.get("direction", "?")).upper()
        parts.append(f"{best.get('match', 'Match')} {direction} {prob} edge {edge}")
    if kelly and kelly.get("stake"):
        parts.append(f"Mise {kelly.get('stake')} ({kelly.get('status', 'ok')})")
    if not parts:
        return None
    return " | ".join(parts)


def _render_status() -> None:
    if not is_openai_configured():
        st.warning("Cle OpenAI manquante. Renseigne OPENAI_API_KEY dans ton .env.")
        return
    last_error = st.session_state.get("coach_last_error")
    if last_error:
        st.warning(f"Dernier souci OpenAI : {last_error}")
    else:
        st.caption("Canal IA disponible pour analyses explicatives uniquement.")

def render_coach_widget() -> None:
    state = _state()
    open_state = state.get("open", False)
    wrapper_class = "open" if open_state else "closed"
    container = st.container()
    container.markdown(_WIDGET_STYLE, unsafe_allow_html=True)
    container.markdown(f"<div id='coach-edge-wrapper' class='{wrapper_class}'>", unsafe_allow_html=True)
    with container:
        container.markdown("<div class='coach-toggle'>", unsafe_allow_html=True)
        toggle_clicked = st.button(
            "Refermer le Coach IA" if open_state else "Ouvrir le Coach IA",
            key="coach_widget_toggle",
        )
        container.markdown("</div>", unsafe_allow_html=True)
        if toggle_clicked:
            state["open"] = not open_state
            st.experimental_rerun()
        if state.get("open", False):
            _render_coach_panel()
    container.markdown("</div>", unsafe_allow_html=True)


def _render_coach_panel() -> None:
    st.markdown("<div class='coach-panel'>", unsafe_allow_html=True)
    st.markdown("#### Coach IA - mode observation")
    st.caption(
        "Outil explicatif : il detaille les parametres, les filtres et signale quand l'inaction reste preferable."
    )
    _render_status()

    if not is_openai_configured():
        st.markdown("</div>", unsafe_allow_html=True)
        return

    _ensure_question_buffer()
    st.markdown("Angles d'analyse possibles")
    suggestion_cols = st.columns(2)
    for idx, label in enumerate(SUGGESTIONS):
        col = suggestion_cols[idx % 2]
        if col.button(label, key=f"coach_suggestion_{idx}"):
            st.session_state["coach_prefill"] = label
            st.experimental_rerun()

    prefill = st.session_state.pop("coach_prefill", None)
    if prefill:
        st.session_state["coach_question_input"] = prefill

    with st.form("coach_widget_form", clear_on_submit=True):
        question = st.text_area(
            "Pose ta question",
            key="coach_question_input",
            placeholder="Ex: Quels filtres bloquent ce match ?",
        )
        submitted = st.form_submit_button("Soumettre au Coach")

    history = _history()
    if submitted:
        cleaned = question.strip()
        if not cleaned:
            st.warning("Merci de saisir une question.")
        else:
            history.append({"role": "user", "content": cleaned})
            if _requires_refusal(cleaned):
                history.append({"role": "assistant", "content": _refusal_reply()})
            else:
                with st.spinner("Analyse contextuelle en cours..."):
                    try:
                        result = handle_chat_query(
                            cleaned,
                            context={
                                "user_id": _user_identifier(),
                                "extra": COACH_EXTRA_CONTEXT,
                            },
                        )
                    except Exception as exc:  # pragma: no cover
                        history.pop()
                        _set_last_error(str(exc))
                        st.error(f"Coach indisponible : {exc}")
                    else:
                        _clear_last_error()
                        history.append(
                            {
                                "role": "assistant",
                                "content": result.get("answer", ""),
                                "metadata": result.get("metadata"),
                            }
                        )

    if history:
        st.markdown("###### Derniers echanges")
        for message in history[-5:]:
            role_class = "user" if message["role"] == "user" else "assistant"
            st.markdown(
                f"<div class='message {role_class}'>{message['content']}</div>",
                unsafe_allow_html=True,
            )
            metadata = message.get("metadata")
            if role_class == "assistant" and metadata:
                summary = _metadata_summary(metadata)
                if summary:
                    st.caption(summary)
    else:
        st.info(
            "Exemples acceptes : 'Quels parametres rendent cette estimation instable ?' "
            "ou 'Pourquoi aucune recommandation n'apparait ?'."
        )

    st.markdown("</div>", unsafe_allow_html=True)
